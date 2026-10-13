import io
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import pandas as pd
from openai import OpenAI
from openai.types.responses import EasyInputMessage
from quest import step

from ...armory.tool_cache import InMemoryToolCache, SemanticCacheKeyBuilder, SqlToolCache
from ...armory.tools import DatasetTools, PythonTools, ToolBox, send_table
from ...duck_protocols import DuckContext, DuckConversation, MessageHandler, MetricsHandler
from ...gen_ai.ai_responses import Agent, ResponsesAPI
from ...utils.config_types import HistoryType
from ...utils.message_utils import wait_for_message
from ...utils.protocols import ToolCache
from ...utils.python_exec_container import (
    DeferredExecutionResult,
    PythonExecContainer,
    is_image,
    is_table,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class TextOutput:
    text: str


@dataclass
class FileOutput:
    filename: str
    data: bytes


@dataclass
class ExecutionOutput:
    container: PythonExecContainer
    result: DeferredExecutionResult
    stdout: str
    tool_cache: ToolCache | None
    cache_key: str | None


class StatsOutputCollector:
    def __init__(self):
        self.items: list[TextOutput | FileOutput | ExecutionOutput] = []

    async def capture(self, _channel_id: int, message: str = None, file=None, view=None):
        if message is not None:
            self.capture_text(message)
        if file is not None:
            self.items.append(FileOutput(file["filename"], file["bytes"]))

    def capture_text(self, message: str):
        self.items.append(TextOutput(message))

    def capture_execution(
            self,
            container: PythonExecContainer,
            result: DeferredExecutionResult,
            stdout: str,
            tool_cache: ToolCache | None,
            cache_key: str | None,
    ):
        self.items.append(
            ExecutionOutput(container, result, stdout, tool_cache, cache_key)
        )

    async def deliver(self, channel_id: int, send_message: Callable):
        for item in self.items:
            if isinstance(item, TextOutput):
                await send_message(channel_id, item.text)
            elif isinstance(item, FileOutput):
                await send_message(
                    channel_id,
                    file={"filename": item.filename, "bytes": item.data},
                )
            else:
                await self._deliver_execution(item, channel_id, send_message)

    async def _deliver_execution(
            self,
            item: ExecutionOutput,
            channel_id: int,
            send_message: Callable,
    ):
        execution_dir = item.result.get("execution_dir")
        try:
            if execution_dir:
                await self._deliver_artifacts(
                    item,
                    execution_dir,
                    channel_id,
                    send_message,
                )
            if item.stdout:
                await self._deliver_stdout(item, channel_id, send_message)
        finally:
            if execution_dir:
                await item.container.cleanup_execution(execution_dir)
                item.result["execution_dir"] = None

    async def _deliver_artifacts(
            self,
            item: ExecutionOutput,
            execution_dir: str,
            channel_id: int,
            send_message: Callable,
    ):
        for filename in item.result.get("files", {}):
            data = await item.container.read_artifact(execution_dir, filename)
            await self._deliver_artifact(
                item,
                filename,
                data,
                channel_id,
                send_message,
            )

    async def _deliver_artifact(
            self,
            item: ExecutionOutput,
            filename: str,
            data: bytes,
            channel_id: int,
            send_message: Callable,
    ):
        if is_table(filename):
            await self._deliver_table(item, filename, data, channel_id, send_message)
        else:
            await self._deliver_file_artifact(
                item,
                filename,
                data,
                channel_id,
                send_message,
            )

    async def _deliver_table(
            self,
            item: ExecutionOutput,
            filename: str,
            data: bytes,
            channel_id: int,
            send_message: Callable,
    ):
        table = pd.read_csv(io.BytesIO(data))
        chunks = await send_table(send_message, channel_id, table)
        if item.tool_cache and item.cache_key is not None:
            item.tool_cache.cache_table(
                item.cache_key,
                filename,
                chunks,
                item.result["files"][filename]["description"],
            )

    async def _deliver_file_artifact(
            self,
            item: ExecutionOutput,
            filename: str,
            data: bytes,
            channel_id: int,
            send_message: Callable,
    ):
        if is_image(filename) and item.tool_cache and item.cache_key is not None:
            item.tool_cache.cache_file(
                item.cache_key,
                filename,
                {
                    "description": item.result["files"][filename]["description"],
                    "bytes": data,
                },
            )
        await send_message(
            channel_id,
            file={"filename": filename, "bytes": data},
        )

    async def _deliver_stdout(
            self,
            item: ExecutionOutput,
            channel_id: int,
            send_message: Callable,
    ):
        if item.tool_cache and item.cache_key is not None:
            item.tool_cache.cache_msg(item.cache_key, item.stdout)
        await send_message(channel_id, item.stdout)

    async def cleanup(self):
        for item in self.items:
            if not isinstance(item, ExecutionOutput):
                continue
            execution_dir = item.result.get("execution_dir")
            if execution_dir:
                await item.container.cleanup_execution(execution_dir)
                item.result["execution_dir"] = None


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


def build_stats_tools(
        tool_names: list[str],
        tool_configs: dict,
        containers: dict[str, PythonExecContainer],
        sql_session,
):
    python_tools = {}
    tool_caches = []
    dataset_containers = {}

    for tool_name in tool_names:
        tool_config = tool_configs.get(tool_name)
        if not tool_config:
            continue
        if tool_config["type"] != "container_exec":
            raise NotImplementedError(
                f"Unsupported tool type: {tool_config['type']}"
            )

        container_name = tool_config["container"]
        container = containers[container_name]
        dataset_containers[container_name] = container
        cache_settings = tool_config.get("cache")
        tool_cache = None
        cache_key_builder = None

        if cache_settings is not None:
            backend = cache_settings.get("backend", "memory")
            if backend == "memory":
                tool_cache = InMemoryToolCache()
            elif backend == "database":
                tool_cache = SqlToolCache(sql_session)
            else:
                raise NotImplementedError(
                    f"Unsupported cache backend: {backend}"
                )

            prompt_path = cache_settings.get("prompt")
            if not prompt_path:
                raise ValueError(
                    f"Missing cache prompt for container_exec tool '{tool_name}'"
                )
            cache_key_builder = SemanticCacheKeyBuilder(
                client=OpenAI(),
                prompt=Path(prompt_path).read_text(),
                model=cache_settings.get("engine", "gpt-5.6-luna"),
                reasoning_effort=cache_settings.get("reasoning", "none"),
            )
            setattr(tool_cache, "_cache_source", tool_name)
            tool_caches.append(tool_cache)

        tool = PythonTools(container, tool_cache, cache_key_builder)
        python_tools[tool_name] = (
            tool,
            tool_config.get("description", tool.run_code.__doc__),
        )

    dataset_tools = DatasetTools(list(dataset_containers.values()))
    dataset_tool_names = {
        "describe_dataset",
        "send_datasets_to_user",
    }.intersection(tool_names)
    available = set(python_tools).union(dataset_tool_names)
    missing = set(tool_names).difference(available)
    if missing:
        raise KeyError(
            f"Tools unavailable to stats workflow: {', '.join(sorted(missing))}"
        )

    def build_toolbox(output: StatsOutputCollector) -> ToolBox:
        toolbox = ToolBox()

        for tool_name, (tool, description) in python_tools.items():
            def bind_python_tool(python_tool: PythonTools):
                async def run_code(code: str, user_intent: str):
                    return await python_tool.run_code(code, user_intent, output)

                return run_code

            toolbox.add_tool(
                bind_python_tool(tool),
                name=tool_name,
                description=description,
            )

        if "describe_dataset" in dataset_tool_names:
            toolbox.add_tool(
                dataset_tools.describe_dataset,
                name="describe_dataset",
                description=(
                        "Returns the full description for a dataset by filename.\n"
                        "Accepts either a filename or a path that ends in that filename.\n"
                        "Use this when you need full column-level metadata."
                        + dataset_tools.get_resource_metadata()
                ),
            )

        if "send_datasets_to_user" in dataset_tool_names:
            async def send_datasets_to_user():
                return await dataset_tools.send_datasets_to_user(output)

            toolbox.add_tool(
                send_datasets_to_user,
                name="send_datasets_to_user",
            )

        return toolbox

    return build_toolbox, tool_caches


class StatsDuckWorkflow:
    commands = []

    def __init__(
            self,
            name: str,
            introduction: str,
            agent: Agent,
            responses_api: ResponsesAPI,
            typing: Callable,
            record_message: Callable,
            record_usage: Callable,
            send_message: Callable,
            tool_names: list[str],
            tool_configs: dict,
            containers: dict,
            sql_session,
            wait_message: Callable = wait_for_message,
    ):
        self.name = name
        self._introduction = introduction
        self._build_toolbox, self.tool_caches = build_stats_tools(
            tool_names,
            tool_configs,
            containers,
            sql_session,
        )
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

    async def __call__(self, context: DuckContext):
        history: list[HistoryType] = []
        await self._send_message(context.thread_id, self._introduction)
        notify_retry = self._retry_notifier(context)

        while True:
            with StatsOutputCollector() as collector:
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
                
                # Run semantic agent to convert current history 
                # into semantic request (e.g. plot: hist, dataset: penguins, etc.)
                
                # If no result for that semantic request, create a result
                # -> An agent writes code, code is run, result is post-processed, result is stored
                
                # Send the result

                agent = replace(
                    self._agent,
                    tools=self._build_toolbox(collector),
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
                await collector.deliver(context.thread_id, self._send_message)

                result = response["result"]
                if result:
                    await self._send_message(context.thread_id, str(result))

                # await collector.cleanup() # goes in __aexit__


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
    return StatsDuckWorkflow(
        name=name,
        introduction=settings["introduction"],
        agent=build_stats_agent(settings["agent"]),
        responses_api=responses_api,
        typing=message_handler.typing,
        record_message=metrics_handler.record_message,
        record_usage=metrics_handler.record_usage,
        send_message=message_handler.send_message,
        tool_names=settings["agent"].get("tools", []),
        tool_configs=tool_configs,
        containers=containers,
        sql_session=sql_session,
    )
