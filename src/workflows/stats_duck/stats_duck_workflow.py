import json
from pathlib import Path
from typing import Any, Callable, TypedDict, Literal

from openai.types.responses import EasyInputMessage
from quest import step
from requests import Session

from .armory.tools import ToolBox
from .gen_ai.ai_responses import ResponsesAPI, Agent
from .gen_ai.jev_responses import JevAPI
from .utils.config_types import HistoryType
from .utils.message_utils import wait_for_message
from .utils.python_exec_container import FileResult, PythonExecContainer
from ...duck_protocols import DuckContext, DuckConversation, MessageHandler, MetricsHandler
from ...gen_ai.ai_responses import AIResponse

INTRODUCTION = ("I can perform many statistical operations on a list of provided datasets."
                "If you want more specifics, please ask. How can I help you with stats?")


class Decision(TypedDict):
    analysis_requested: bool
    analysis_description: str | None
    missing_information: str | None


class PlotOrder(TypedDict):
    """
    {
        "plot": "seaborn.boxplot",
        "data": {
            "base": "penguins",
            "description": "Keep only rows where sex is male."
        },
        "args": {
            "x": "species",
            "y": "flipper_length"
        }
    }
    """
    plot: str
    data: str | dict
    args: dict


class AnalysisOrder(TypedDict):
    """
    {
        "data": "penguins.flipper_length",
        "analysis": "quantile",
        "args": {"q": [0, 0.25, 0.5, 0.75, 1]}
    }
    """
    data: str
    analysis: str
    args: dict


StatsOrder = PlotOrder | AnalysisOrder


class SendableText(TypedDict):
    type: Literal['text']
    content: str


class SendableImage(TypedDict):
    type: Literal['image']
    binary_content: bytes
    filename: str
    format: str  # png, svg, etc.


class SendableTable(TypedDict):
    type: Literal['table']
    header: list[str]
    rows: list[list[str]]


SendableArtifact = SendableText | SendableImage | SendableTable


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


def as_stable_key(order: dict) -> tuple:
    """Converts the JSON into a stable, deterministic tuple"""
    # dict -> list[sorted items]
    # list -> tuple


def format_results_as_history(results: list[SendableArtifact]) -> list[HistoryType]:
    """Format the artifacts as system prompt notices that those artifacts were created and sent to the user."""
    return []


class StatsDuckWorkflow:
    commands = []

    def __init__(
            self,
            name: str,
            agent: Agent,
            responses_api: ResponsesAPI,
            jev_api: JevAPI,
            sandbox: PythonExecContainer,
            message_handler: MessageHandler,
            record_usage: Callable,
            record_message: Callable,
    ):
        self.name = name
        self._jev = jev_api
        self._responses_api = responses_api
        self._agent = agent
        self._sandbox = sandbox
        self._message_handler = message_handler
        self._record_message = step(record_message)
        self._record_usage = step(record_usage)

        self._cache: dict[tuple, list[SendableArtifact]] = {}

    async def _record_response(self, context: DuckContext, outputs: list):
        for output in outputs:
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

    @step
    async def _decide(self, history: list[HistoryType]) -> Decision:
        pass  # Is an analysis requested and ready to fulfill?
        # TODO - prompt: what options are available, what is the output formats

    @step
    async def _order_from_menu(self, analysis_description: str) -> StatsOrder:
        pass  # Formalize the analysis request into one of the provided schemas
        # TODO - prompt: avoid custom data, avoid custom analyses

    @step
    async def _fulfill_order(self, analysis_order: StatsOrder) -> list[SendableArtifact]:
        agent = self._coder_agent
        response = await self._responses_api.run_agent_turn(agent, ...)
        code = response['output']
        result = self._execution.run_code(code)

        pass  # Call agent with code exec tool to build the request artifacts
        # Look at code execution result (files and stdout) and build SendableArtifacts
        # looks kind of like _deliver_result

    @step
    async def _send_results(self, context: DuckContext, results: list[SendableArtifact]):
        # TODO - accuracy
        for artifact in results:
            if artifact['type'] == 'text':
                await self._message_handler.send_text(context.thread_id, artifact['content'])

            elif artifact['type'] == 'image':
                await self._message_handler.send_image(context.thread_id, artifact['filename'], artifact['data_bytes'])

            elif artifact['type'] == 'table':
                await self._message_handler.send_table(context.thread_id, artifact['header'], artifact['rows'])

    @step
    async def _help_user_towards_a_decision(
            self, context: DuckContext, history: list[HistoryType], missing_information: str
    ) -> AIResponse:
        pass  # look at history, missing information and prompt the user in the right direction

    async def __call__(self, context: DuckContext):
        history: list[HistoryType] = []
        await self._send_message(context.thread_id, INTRODUCTION)
        # notify_retry = self._retry_notifier(context)

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

            async with self._typing(context.thread_id):
                decision = await self._decide(context, history)
                # record decision as system message

                if decision['analysis_requested']:
                    order = await self._order_from_menu(decision['analysis_description'])
                    # record order as system message
                    key = as_stable_key(order)
                    if key not in self._cache:
                        self._cache[key] = await self._fulfill_order(context, order)
                    results = self._cache[key]
                    history.extend(format_results_as_history(results))
                    # record results as system messages

                    await self._send_results(context, results)

                else:
                    response = await self._help_user_towards_a_decision(context, history,
                                                                        decision['missing_information'])
                    await self._record_response(context, response)
                    history.extend(response["outputs"])
                    await self._record_response_usage(context, response)

                    result = response["result"]
                    if result:
                        await self._send_message(context.thread_id, str(result))


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
