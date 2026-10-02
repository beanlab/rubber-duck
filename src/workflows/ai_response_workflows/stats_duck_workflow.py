import io
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from openai.types.responses import EasyInputMessage
from quest import step

from ...armory.tools import build_stats_toolbox, send_table
from ...gen_ai.ai_responses import Agent, ResponsesAPI
from ...storage.stats_output_types import ExecutionOutput, FileOutput, TextOutput
from ...utils.config_types import DuckContext, HistoryType
from ...utils.message_utils import wait_for_message
from ...utils.python_exec_container import is_image, is_table


class StatsOutputCollector:
    def __init__(self):
        self.items: list[TextOutput | FileOutput | ExecutionOutput] = []

    async def capture(self, _channel_id: int, message: str = None, file=None, view=None):
        if message is not None:
            self.items.append(TextOutput(message))
        if file is not None:
            self.items.append(FileOutput(file["filename"], file["bytes"]))

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


class StatsDuckWorkflow:
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
        toolbox, self.tool_caches = build_stats_toolbox(
            tool_names,
            tool_configs,
            containers,
            send_message,
            sql_session,
        )
        self._agent = replace(agent, tools=toolbox)
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
            collector = StatsOutputCollector()
            setattr(context, "_stats_output_collector", collector)
            try:
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

                agent = replace(
                    self._agent,
                    tools=self._agent.tools.bind_context(context),
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
            finally:
                await collector.cleanup()
                if hasattr(context, "_stats_output_collector"):
                    delattr(context, "_stats_output_collector")
