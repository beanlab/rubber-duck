from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Callable, TypedDict

from requests import Session
from openai.types.responses import EasyInputMessage
from quest import step


from src.duck_protocols import DuckContext, DuckConversation, MessageHandler, MetricsHandler
from src.gen_ai.ai_responses import ResponsesAPI, Agent
from src.gen_ai.jev_responses import JevAPI
from src.utils.config_types import HistoryType
from src.utils.message_utils import wait_for_message
from src.utils.python_exec_container import FileResult, PythonExecContainer
from src.armory.tools import ToolBox


INTRODUCTION = ("I can perform many statistical operations on a list of provided datasets."
                "If you want more specifics, please ask. How can I help you with stats?")


def build_stats_tools(
    container: PythonExecContainer,
    result_holder: list[dict[str, Any]],
) -> ToolBox:
    toolbox = ToolBox()

    async def execute_python(code: str) -> dict[str, Any]:
        """Write and execute Python code in the statistics sandbox."""
        result = await container.run_code(code)
        result_holder.append(result)
        return {
            "exit_code": result["exit_code"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "files": {
                filename: file["description"]
                for filename, file in result["files"].items()
            },
        }

    toolbox.add_tool(
        execute_python,
        name="execute_python",
        description=(
            "Executes Python code in the statistics sandbox. "
            "The code may read available datasets and create output files."
        ),
    )
    return toolbox


class CacheEntry(TypedDict):
    request: str
    stdout: str
    files: dict[str, FileResult]


class StatsDuckWorkflow:
    commands = []

    def __init__(
        self,
        name: str,
        agent: Agent,
        responses_api: ResponsesAPI,
        typing: Callable,
        record_message: Callable,
        record_usage: Callable,
        send_message: Callable,
        sandbox: PythonExecContainer,
        wait_message: Callable = wait_for_message,
        jev_api: JevAPI | None = None,
    ):
        self.name = name
        self._sandbox = sandbox
        self._jev = jev_api or JevAPI(None)
        self.tool_caches = []
        self._agent = agent
        self._responses_api = responses_api
        self._wait_message = step(wait_message)
        self._typing = typing
        self._record_message = step(record_message)
        self._record_usage = step(record_usage)
        self._send_message = step(send_message)

    async def _record_response(self, context: DuckContext, response: dict[str, Any]):
        for output in response["outputs"]:
            output_type = output.get("type")
            if output_type == "message":
                await self._record_message(
                    context.guild_id,
                    context.thread_id,
                    context.author_id,
                    "assistant",
                    json.dumps(output.get("content")),
                )
            elif output_type == "function_call_output":
                await self._record_message(
                    context.guild_id,
                    context.thread_id,
                    context.author_id,
                    "function_call_output",
                    str(output),
                )

    async def _record_response_usage(self, context: DuckContext, response: dict[str, Any]):
        usage = response["usage"]
        if not usage:
            return
        await self._record_usage(
            context.guild_id,
            context.parent_channel_id,
            context.thread_id,
            context.author_id,
            usage["model"],
            usage["input_tokens"],
            usage["output_tokens"],
            usage["cached_tokens"],
            usage["reasoning_tokens"],
        )

    def _retry_notifier(self, context: DuckContext):
        async def notify(delay_seconds: int):
            await self._send_message(
                context.thread_id,
                "I hit a temporary connection issue with an upstream server. "
                f"Retrying in {delay_seconds} seconds...",
            )

        return notify

    async def _find_cached_entry(
        self,
        user_message: str,
        cache: list[CacheEntry],
    ) -> CacheEntry | None:
        state = {
            "user_request": user_message,
            "cache_entries": [
                {
                    "id": str(index),
                    "request": entry["request"],
                    "stdout": entry["stdout"],
                    "files": list(entry["files"]),
                }
                for index, entry in enumerate(cache)
            ],
        }
        criteria = {
            str(index): (
                f"Use the cached result for this earlier request: {entry['request']}"
            )
            for index, entry in enumerate(cache)
        }
        criteria["no_match"] = "No cached result can fulfill the current request."
        assessment = await self._jev.assess(
            state=state,
            questions={
                "cache_match": self._jev.choice(
                    instructions=(
                        "Determine whether the latest user request can be fulfilled "
                        "by one of the cached results. Select the best matching cache "
                        "entry, or no_match."
                    ),
                    criteria=criteria,
                )
            },
        )
        answer = assessment["answers"].get("cache_match")
        selected = getattr(answer, "choice", answer)
        if isinstance(selected, dict):
            selected = selected.get("choice")
        if selected == "no_match":
            return None
        try:
            return cache[int(selected)]
        except (TypeError, ValueError, IndexError):
            return None

    async def _deliver_result(
        self,
        channel_id: int,
        result: dict[str, Any],
    ):
        for filename, file_data in result.get("files", {}).items():
            await self._send_message(
                channel_id,
                file={
                    "filename": filename,
                    "bytes": file_data["bytes"],
                },
            )
        stdout = result.get("stdout", "")
        if stdout:
            await self._send_message(channel_id, stdout)

    async def _deliver_cached_entry(
        self,
        channel_id: int,
        entry: CacheEntry,
    ):
        await self._deliver_result(
            channel_id,
            {"stdout": entry["stdout"], "files": entry["files"]},
        )

    async def __call__(self, context: DuckContext):
        history: list[HistoryType] = []
        semantic_cache: list[CacheEntry] = []
        await self._send_message(context.thread_id, INTRODUCTION)
        notify_retry = self._retry_notifier(context)

        while True:
            message = await self._wait_message(context.timeout)
            if message is None:
                return history

            user_message = message["content"]
            await self._record_message(
                context.guild_id,
                context.thread_id,
                context.author_id,
                "message",
                json.dumps(user_message),
            )
            history.append(
                EasyInputMessage(
                    role="user",
                    content=user_message,
                    type="message",
                ).model_dump()
            )

            cached_entry = await self._find_cached_entry(
                user_message,
                semantic_cache,
            )
            if cached_entry is not None:
                await self._deliver_cached_entry(context.thread_id, cached_entry)
                continue

            execution_results: list[dict[str, Any]] = []
            agent = replace(
                self._agent,
                tools=build_stats_tools(self._sandbox, execution_results),
            )
            async with self._typing(context.thread_id):
                response = await self._responses_api.run_agent_turn(
                    agent,
                    history,
                    notify_retry,
                )

            await self._record_response(context, response)
            history.extend(response["outputs"])
            await self._record_response_usage(context, response)

            result = response["result"]
            if result:
                await self._send_message(context.thread_id, str(result))

            for executed in execution_results:
                await self._deliver_result(context.thread_id, executed)
                if executed["exit_code"] == 0:
                    semantic_cache.append({
                        "request": user_message,
                        "stdout": executed.get("stdout", ""),
                        "files": executed.get("files", {}),
                    })


def build_stats_agent(settings: dict[str, Any]) -> Agent:
    prompt = "\n".join(
        Path(prompt_file).read_text(encoding="utf-8")
        for prompt_file in settings["prompt_files"]
    )
    return Agent(
        name=settings["name"],
        model=settings["engine"],
        prompt=prompt,
        reasoning=settings.get("reasoning"),
    )


def build(
        name: str,
        settings: dict,
        *,
        message_handler: MessageHandler,
        metrics_handler: MetricsHandler,
        responses_api: ResponsesAPI,
        containers: dict[str, PythonExecContainer],
        sql_session: "Session",
        tool_configs: dict,
) -> DuckConversation:
    try:
        sandbox = containers["stats-python-sandbox"]
    except KeyError as error:
        if len(containers) != 1:
            raise ValueError(
                "The new stats duck requires a 'stats-python-sandbox' container"
            ) from error
        sandbox = next(iter(containers.values()))
    return StatsDuckWorkflow(
        name=name,
        agent=build_stats_agent(settings["agent"]),
        responses_api=responses_api,
        typing=message_handler.typing,
        record_message=metrics_handler.record_message,
        record_usage=metrics_handler.record_usage,
        send_message=message_handler.send_message,
        sandbox=sandbox,
    )
