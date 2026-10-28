import csv
import io
import json
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, TypedDict, Mapping

from openai.types.responses import EasyInputMessage
from quest import step

from ...duck_protocols import DuckContext, DuckConversation, MessageHandler, MetricsHandler
from ...gen_ai.ai_responses import AIResponse, Agent, ResponsesAPI
from ...utils.config_types import HistoryType
from ...utils.logger import duck_logger
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
TABLE_FORMATS = {"csv"}


class Decision(TypedDict):
    analysis_requested: bool
    analysis_description: str | None
    missing_information: str | None


class DatasetOrder(TypedDict):
    action: Literal["list_datasets", "describe_dataset"]
    data: str | None


def _is_dataset_order(order):
    return 'action' in order


class PlotOrder(TypedDict):
    plot: str
    data: str | dict
    args: dict


class AnalysisOrder(TypedDict):
    data: str | dict
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


class ArtifactError(RuntimeError):
    pass


def _stage_agent(agent: Agent, stage: str, additional_prompt: str | None = None) -> Agent:
    prompt = "\n\n".join(filter(None, [
        agent.prompt,
        (PROMPT_DIRECTORY / stage).read_text(encoding="utf-8"),
        additional_prompt,
    ]))
    return replace(
        agent,
        name=f"{agent.name}_{Path(stage).stem}",
        prompt=prompt,
        tools=None,
    )


def _dataset_context(sandbox: PythonExecContainer) -> str:
    datasets = []
    for dataset in sandbox.get_dataset_inventory():
        filename = dataset["filename"]
        datasets.append({
            **dataset,
            "description": sandbox.describe_dataset(filename),
        })
    return json.dumps(datasets, indent=2)


def as_stable_key(order) -> tuple:
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
            decision_agent: Agent,
            order_agent: Agent,
            coder_agent: Agent,
            clarification_agent: Agent,
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
        self._decision_agent = decision_agent
        self._order_agent = order_agent
        self._coder_agent = coder_agent
        self._clarification_agent = clarification_agent
        self._sandbox = sandbox
        self._message_handler = message_handler
        self._wait_message = step(wait_message)
        self._record_message = step(record_message)
        self._record_usage = step(record_usage)
        self._cache: dict[tuple, list[SendableArtifact]] = {}

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
        response = await self._responses_api.run_agent_turn(
            self._decision_agent,
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
        prompt = f"Analysis request:\n{analysis_description}"
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
        prompt = f"Order:\n{json.dumps(analysis_order, indent=2)}"
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

    def _handle_dataset_order(self, order: DatasetOrder) -> list[SendableArtifact]:
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

        elif order["action"] == "describe_dataset":
            description = self._sandbox.describe_dataset(order["data"])
            return [{
                "type": "text",
                "content": description or f"Dataset '{order['data']}' was not found.",
            }]

        else:
            raise NotImplementedError(order['action'])

    async def _handle_code_execution_order(self, context: DuckContext, analysis_order: PlotOrder | AnalysisOrder):
        code = await self._generate_code(context, analysis_order)
        result = await self._sandbox.run_code(code)
        artifacts = None
        if result["exit_code"] == 0:
            try:
                artifacts = self._artifacts_from_execution(result)
            except ArtifactError as error:
                result["stderr"] = str(error)

        if result["exit_code"] != 0 or artifacts is None:
            code = await self._generate_code(
                context,
                analysis_order,
                previous_code=code,
                error=result["stderr"],
            )
            result = await self._sandbox.run_code(code)
            artifacts = None
            if result["exit_code"] == 0:
                try:
                    artifacts = self._artifacts_from_execution(result)
                except ArtifactError as error:
                    result["stderr"] = str(error)

        if result["exit_code"] != 0 or artifacts is None:
            error = result["stderr"].strip() or "Unknown execution error"
            return [{
                "type": "text",
                "content": f"I couldn't complete the analysis: {error}",
            }]

        return artifacts

    @staticmethod
    def _artifacts_from_execution(result: Mapping[str, Any]) -> list[SendableArtifact]:
        artifacts: list[SendableArtifact] = []

        filenames = set(result.get("files", {}))
        stdout_lines = [
            line
            for line in result.get("stdout", "").splitlines()
            if line.strip() not in filenames
        ]
        stdout = "\n".join(stdout_lines).strip()
        if stdout:
            artifacts.append(SendableText(type="text", content=stdout))

        for filename, file_result in result.get("files", {}).items():
            extension = Path(filename).suffix.lower().lstrip(".")
            binary_content = file_result["bytes"]

            if extension in TABLE_FORMATS:
                rows = list(csv.reader(io.StringIO(
                    binary_content.decode("utf-8-sig"))))
                if rows:
                    artifacts.append(SendableTable(
                        type="table",
                        header=rows[0],
                        rows=rows[1:]
                    ))

            elif extension in IMAGE_FORMATS:
                artifacts.append(SendableImage(
                    type="image",
                    binary_content=binary_content,
                    filename=filename,
                    format=extension,
                ))

            else:
                duck_logger.warning(
                    f"Ignoring unsupported analysis artifact '{filename}'"
                )

        if not artifacts:
            raise ArtifactError(
                "Execution completed without producing supported text, table, or image output"
            )

        return artifacts

    @step
    async def _fulfill_order(
            self,
            context: DuckContext,
            analysis_order: StatsOrder,
    ) -> list[SendableArtifact]:
        if _is_dataset_order(analysis_order):
            return self._handle_dataset_order(analysis_order)

        return await self._handle_code_execution_order(context, analysis_order)

    @step
    async def _send_results(
            self,
            context: DuckContext,
            results: list[SendableArtifact],
    ):
        async def record_artifact(artifact):
            await self._record_message(
                context.guild_id,
                context.thread_id,
                context.author_id,
                "assistant",
                json.dumps(artifact),
            )

        for artifact in results:
            if artifact["type"] == "text":
                await self._message_handler.send_text(
                    context.thread_id,
                    artifact["content"],
                )
                await record_artifact(artifact)

            elif artifact["type"] == "image":
                await self._message_handler.send_image(
                    context.thread_id,
                    artifact["filename"],
                    artifact["binary_content"],
                )
                await record_artifact({
                    "type": "image",
                    "filename": artifact["filename"],
                    "format": artifact["format"],
                })

            elif artifact["type"] == "table":
                await self._message_handler.send_table(
                    context.thread_id,
                    artifact["header"],
                    artifact["rows"],
                )
                await record_artifact(artifact)

            else:
                raise NotImplementedError(artifact["type"])

    @step
    async def _help_user_towards_a_decision(
            self,
            context: DuckContext,
            history: list[HistoryType],
            missing_information: str,
    ) -> AIResponse:
        prompt = EasyInputMessage(
            role="system",
            content=(
                "Respond concisely according to this decision guidance: "
                f"{missing_information}"
            ),
            type="message",
        ).model_dump()
        clarification_history = history + [prompt]
        while True:
            response = await self._responses_api.run_agent_turn(
                self._clarification_agent,
                clarification_history,
                self._retry_notifier(context),
            )
            await self._record_response(context, response["outputs"])
            await self._record_response_usage(context, response)

            result = str(response["result"] or "").strip()
            if result:
                await self._message_handler.send_text(context.thread_id, result)
                return response

            clarification_history.extend(response["outputs"])
            clarification_history.append(EasyInputMessage(
                role="system",
                content=(
                    "Your previous response contained no user-facing text. "
                    "Return one concise response that follows the decision guidance."
                ),
                type="message",
            ).model_dump())

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
                        decision.get("analysis_description", ""),
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

    agent = build_stats_agent(settings["agent"])
    dataset_prompt = (
        f"Available datasets and metadata:\n{_dataset_context(sandbox)}"
    )

    return StatsDuckWorkflow(
        name=name,
        introduction=settings.get("introduction", INTRODUCTION),
        decision_agent=_stage_agent(agent, "decision.md", dataset_prompt),
        order_agent=_stage_agent(agent, "order.md", dataset_prompt),
        coder_agent=_stage_agent(agent, "coder.md", dataset_prompt),
        clarification_agent=_stage_agent(agent, "clarification.md"),
        responses_api=responses_api,
        sandbox=sandbox,
        message_handler=message_handler,
        record_message=metrics_handler.record_message,
        record_usage=metrics_handler.record_usage,
    )
