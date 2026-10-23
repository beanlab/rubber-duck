import csv
import io
import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, TypedDict

from openai.types.responses import EasyInputMessage
from quest import step

from ...duck_protocols import DuckContext, DuckConversation, MessageHandler, MetricsHandler
from ...gen_ai.ai_responses import AIResponse, Agent, ResponsesAPI
from ...utils.config_types import HistoryType
from ...utils.message_utils import wait_for_message
from ...utils.python_exec_container import PythonExecContainer

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


PROMPT_DIRECTORY = Path(__file__).parents[2] / "prompts" / "stats-duck"
INTRODUCTION = (
    "I can perform many statistical operations on a list of provided datasets. "
    "If you want more specifics, please ask. How can I help you with stats?"
)
IMAGE_FORMATS = {"gif", "jpeg", "jpg", "png", "svg", "webp"}


class Decision(TypedDict):
    analysis_requested: bool
    analysis_description: str | None
    missing_information: str | None


class DatasetOrder(TypedDict):
    action: Literal["list_datasets", "describe_dataset"]
    data: str | None


class PlotOrder(TypedDict):
    plot: str
    data: str | dict
    args: dict


class AnalysisOrder(TypedDict):
    data: str
    analysis: str
    args: dict


StatsOrder = DatasetOrder | PlotOrder | AnalysisOrder


class SendableText(TypedDict):
    type: Literal["text"]
    content: str


class SendableImage(TypedDict):
    type: Literal["image"]
    binary_content: bytes
    filename: str
    format: str


class SendableTable(TypedDict):
    type: Literal["table"]
    header: list[str]
    rows: list[list[str]]


SendableArtifact = SendableText | SendableImage | SendableTable


def _load_stage_prompt(filename: str) -> str:
    return (PROMPT_DIRECTORY / filename).read_text(encoding="utf-8")


def _stage_agent(agent: Agent, stage: str) -> Agent:
    prompt = "\n\n".join(
        filter(None, [agent.prompt, _load_stage_prompt(stage)]))
    return replace(agent, name=f"{agent.name}_{Path(stage).stem}", prompt=prompt, tools=None)


def as_stable_key(order: dict) -> tuple:
    def freeze(value):
        if isinstance(value, dict):
            return tuple(
                (key, freeze(item))
                for key, item in sorted(value.items())
            )
        if isinstance(value, list):
            return tuple(freeze(item) for item in value)
        return value

    return freeze(order)


def format_results_as_history(results: list[SendableArtifact]) -> list[HistoryType]:
    history = []
    for artifact in results:
        if artifact["type"] == "text":
            content = artifact["content"]
        elif artifact["type"] == "image":
            content = (
                f"Sent image {artifact['filename']} "
                f"({artifact['format']} format) to the user."
            )
        else:
            content = json.dumps({
                "delivered_table": {
                    "header": artifact["header"],
                    "rows": artifact["rows"],
                }
            })
        history.append(EasyInputMessage(
            role="assistant",
            content=content,
            type="message",
        ).model_dump())
    return history


class StatsDuckWorkflow:
    commands = []
    tool_caches = []

    def __init__(
            self,
            name: str,
            introduction: str,
            agent: Agent,
            responses_api: ResponsesAPI,
            sandbox: PythonExecContainer,
            message_handler: MessageHandler,
            record_usage: Callable,
            record_message: Callable,
            wait_message: Callable = wait_for_message,
    ):
        self.name = name
        self._introduction = introduction
        self._responses_api = responses_api
        self._decision_agent = _stage_agent(agent, "decision.md")
        self._order_agent = _stage_agent(agent, "order.md")
        self._coder_agent = _stage_agent(agent, "coder.md")
        self._clarification_agent = _stage_agent(agent, "clarification.md")
        self._sandbox = sandbox
        self._message_handler = message_handler
        self._wait_message = step(wait_message)
        self._record_message = step(record_message)
        self._record_usage = step(record_usage)
        self._cache: dict[tuple, list[SendableArtifact]] = {}

    def _dataset_context(self) -> str:
        datasets = []
        for dataset in self._sandbox.get_dataset_inventory():
            filename = dataset["filename"]
            datasets.append({
                **dataset,
                "description": self._sandbox.describe_dataset(filename),
            })
        return json.dumps(datasets, indent=2)

    async def _record_response(self, context: DuckContext, outputs: list[HistoryType]):
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

    async def _record_response_usage(self, context: DuckContext, response: AIResponse):
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
            await self._message_handler.send_text(
                context.thread_id,
                "I hit a temporary connection issue with an upstream server. "
                f"Retrying in {delay_seconds} seconds...",
            )
        return notify

    @step
    async def _decide(self, context: DuckContext, history: list[HistoryType]) -> Decision:
        agent = replace(
            self._decision_agent,
            prompt=(
                f"{self._decision_agent.prompt}\n\n"
                f"Available datasets and metadata:\n{self._dataset_context()}"
            ),
        )
        response = await self._responses_api.run_agent_turn(
            agent,
            history,
            self._retry_notifier(context),
        )
        await self._record_response(context, response["outputs"])
        await self._record_response_usage(context, response)
        return json.loads(response["result"].strip())

    @step
    async def _order_from_menu(
            self,
            context: DuckContext,
            analysis_description: str,
    ) -> StatsOrder:
        prompt = (
            f"Available datasets and metadata:\n{self._dataset_context()}\n\n"
            f"Analysis request:\n{analysis_description}"
        )
        response = await self._responses_api.run_agent_turn(
            self._order_agent,
            [EasyInputMessage(role="user", content=prompt,
                              type="message").model_dump()],
            self._retry_notifier(context),
        )
        await self._record_response(context, response["outputs"])
        await self._record_response_usage(context, response)
        return json.loads(response["result"].strip())

    async def _generate_code(
            self,
            context: DuckContext,
            analysis_order: StatsOrder,
            previous_code: str | None = None,
            error: str | None = None,
    ) -> str:
        prompt = (
            f"Available datasets and metadata:\n{self._dataset_context()}\n\n"
            f"Order:\n{json.dumps(analysis_order, indent=2)}"
        )
        if previous_code is not None:
            prompt += f"\n\nPrevious code:\n```python\n{previous_code}\n```"
        if error is not None:
            prompt += f"\n\nExecution error to correct:\n{error}"
        response = await self._responses_api.run_agent_turn(
            self._coder_agent,
            [EasyInputMessage(role="user", content=prompt,
                              type="message").model_dump()],
            self._retry_notifier(context),
        )
        await self._record_response(context, response["outputs"])
        await self._record_response_usage(context, response)
        code = response["result"].strip()
        if not code:
            raise ValueError("The coder agent returned no Python code")
        return code

    def _dataset_order_results(self, order: DatasetOrder) -> list[SendableArtifact]:
        if order["action"] == "list_datasets":
            names = sorted(
                dataset["dataset_name"]
                for dataset in self._sandbox.get_dataset_inventory()
            )
            content = (
                "Available datasets:\n" +
                "\n".join(f"- {name}" for name in names)
                if names
                else "No datasets are currently available."
            )
            return [{"type": "text", "content": content}]

        description = self._sandbox.describe_dataset(order["data"] or "")
        return [{
            "type": "text",
            "content": description or f"Dataset '{order['data']}' was not found.",
        }]

    @staticmethod
    def _artifacts_from_execution(result: dict[str, Any]) -> list[SendableArtifact]:
        artifacts: list[SendableArtifact] = []
        filenames = set(result.get("files", {}))
        stdout_lines = [
            line
            for line in result.get("stdout", "").splitlines()
            if line.strip() not in filenames
        ]
        stdout = "\n".join(stdout_lines).strip()
        if stdout:
            artifacts.append({"type": "text", "content": stdout})

        for filename, file_result in result.get("files", {}).items():
            extension = Path(filename).suffix.lower().lstrip(".")
            binary_content = file_result["bytes"]
            if extension == "csv":
                rows = list(csv.reader(io.StringIO(
                    binary_content.decode("utf-8-sig"))))
                if rows:
                    artifacts.append({
                        "type": "table",
                        "header": rows[0],
                        "rows": rows[1:],
                    })
            elif extension in IMAGE_FORMATS:
                artifacts.append({
                    "type": "image",
                    "binary_content": binary_content,
                    "filename": filename,
                    "format": extension,
                })
            else:
                artifacts.append({
                    "type": "text",
                    "content": f"Generated unsupported file '{filename}'.",
                })

        if not artifacts:
            artifacts.append({
                "type": "text",
                "content": "The analysis completed without producing output.",
            })
        return artifacts

    @step
    async def _fulfill_order(
            self,
            context: DuckContext,
            analysis_order: StatsOrder,
    ) -> list[SendableArtifact]:
        if "action" in analysis_order:
            return self._dataset_order_results(analysis_order)

        code = await self._generate_code(context, analysis_order)
        result = await self._sandbox.run_code(code)
        if result["exit_code"] != 0:
            code = await self._generate_code(
                context,
                analysis_order,
                previous_code=code,
                error=result["stderr"],
            )
            result = await self._sandbox.run_code(code)

        if result["exit_code"] != 0:
            error = result["stderr"].strip() or "Unknown execution error"
            return [{
                "type": "text",
                "content": f"I couldn't complete the analysis: {error}",
            }]
        return self._artifacts_from_execution(result)

    @step
    async def _send_results(
            self,
            context: DuckContext,
            results: list[SendableArtifact],
    ):
        for artifact in results:
            if artifact["type"] == "text":
                await self._message_handler.send_text(
                    context.thread_id,
                    artifact["content"],
                )
                recorded_artifact = artifact
            elif artifact["type"] == "image":
                await self._message_handler.send_image(
                    context.thread_id,
                    artifact["filename"],
                    artifact["binary_content"],
                )
                recorded_artifact = {
                    "type": "image",
                    "filename": artifact["filename"],
                    "format": artifact["format"],
                }
            else:
                await self._message_handler.send_table(
                    context.thread_id,
                    artifact["header"],
                    artifact["rows"],
                )
                recorded_artifact = artifact

            await self._record_message(
                context.guild_id,
                context.thread_id,
                context.author_id,
                "assistant",
                json.dumps(recorded_artifact),
            )

    @step
    async def _help_user_towards_a_decision(
            self,
            context: DuckContext,
            history: list[HistoryType],
            missing_information: str,
    ) -> AIResponse:
        prompt = EasyInputMessage(
            role="user",
            content=(
                "Respond concisely according to this decision guidance: "
                f"{missing_information}"
            ),
            type="message",
        ).model_dump()
        response = await self._responses_api.run_agent_turn(
            self._clarification_agent,
            history + [prompt],
            self._retry_notifier(context),
        )
        await self._record_response(context, response["outputs"])
        await self._record_response_usage(context, response)
        return response

    async def __call__(self, context: DuckContext):
        history: list[HistoryType] = []
        await self._message_handler.send_text(context.thread_id, self._introduction)

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
            history.append(EasyInputMessage(
                role="user",
                content=user_message,
                type="message",
            ).model_dump())

            async with self._message_handler.typing(context.thread_id):
                decision = await self._decide(context, history)
                if decision["analysis_requested"]:
                    order = await self._order_from_menu(
                        context,
                        decision["analysis_description"] or "",
                    )
                    key = as_stable_key(order)
                    if key not in self._cache:
                        self._cache[key] = await self._fulfill_order(context, order)
                    results = self._cache[key]
                    await self._send_results(context, results)
                    history.extend(format_results_as_history(results))
                else:
                    response = await self._help_user_towards_a_decision(
                        context,
                        history,
                        decision["missing_information"] or "the requested analysis",
                    )
                    history.extend(response["outputs"])
                    if response["result"]:
                        await self._message_handler.send_text(
                            context.thread_id,
                            str(response["result"]),
                        )


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
        introduction=settings.get("introduction", INTRODUCTION),
        agent=build_stats_agent(settings["agent"]),
        responses_api=responses_api,
        sandbox=sandbox,
        message_handler=message_handler,
        record_message=metrics_handler.record_message,
        record_usage=metrics_handler.record_usage,
    )
