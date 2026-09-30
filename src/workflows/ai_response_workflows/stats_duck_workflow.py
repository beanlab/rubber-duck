import io
import json
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from openai.types.responses import EasyInputMessage
from quest import step

from ...armory.python_tools import send_table
from ...armory.talk_tool import TalkTool
from ...gen_ai.ai_responses import Agent, ResponsesAPI
from ...utils.config_types import DuckContext, HistoryType
from ...utils.protocols import ConversationComplete, ToolCache
from ...utils.python_exec_container import (
    DeferredExecutionResult,
    PythonExecContainer,
    is_image,
    is_table,
)


@dataclass
class _TextOutput:
    text: str


@dataclass
class _FileOutput:
    filename: str
    data: bytes


@dataclass
class _ExecutionOutput:
    container: PythonExecContainer
    result: DeferredExecutionResult
    stdout: str
    tool_cache: ToolCache | None
    cache_key: str | None


class StatsOutputCollector:
    def __init__(self):
        self._items: list[_TextOutput | _FileOutput | _ExecutionOutput] = []

    def add_text(self, text: str):
        self._items.append(_TextOutput(text))

    async def capture(self, _channel_id: int, message: str = None, file=None, view=None):
        if message is not None:
            self._items.append(_TextOutput(message))
        if file is not None:
            self._items.append(_FileOutput(file["filename"], file["bytes"]))

    def add_execution(
            self,
            container: PythonExecContainer,
            result: DeferredExecutionResult,
            stdout: str,
            tool_cache: ToolCache | None = None,
            cache_key: str | None = None,
    ):
        self._items.append(
            _ExecutionOutput(container, result, stdout, tool_cache, cache_key)
        )

    async def deliver(self, channel_id: int, send_message: Callable):
        for item in self._items:
            if isinstance(item, _TextOutput):
                await send_message(channel_id, item.text)
                continue
            if isinstance(item, _FileOutput):
                await send_message(
                    channel_id,
                    file={"filename": item.filename, "bytes": item.data},
                )
                continue

            execution_dir = item.result.get("execution_dir")
            try:
                if execution_dir:
                    for filename in item.result.get("files", {}):
                        data = await item.container.read_artifact(execution_dir, filename)
                        if is_table(filename):
                            table = pd.read_csv(io.BytesIO(data))
                            chunks = await send_table(send_message, channel_id, table)
                            if item.tool_cache and item.cache_key is not None:
                                item.tool_cache.cache_table(
                                    item.cache_key,
                                    filename,
                                    chunks,
                                    item.result["files"][filename]["description"],
                                )
                        else:
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
                if item.stdout:
                    if item.tool_cache and item.cache_key is not None:
                        item.tool_cache.cache_msg(item.cache_key, item.stdout)
                    await send_message(channel_id, item.stdout)
            finally:
                if execution_dir:
                    await item.container.cleanup_execution(execution_dir)
                    item.result["execution_dir"] = None

    async def cleanup(self):
        for item in self._items:
            if not isinstance(item, _ExecutionOutput):
                continue
            execution_dir = item.result.get("execution_dir")
            if execution_dir:
                await item.container.cleanup_execution(execution_dir)
                item.result["execution_dir"] = None


class StatsDuckWorkflow:
    def __init__(
            self,
            name: str,
            introduction: str,
            agent: Agent,
            responses_api: ResponsesAPI,
            talk_tool: TalkTool,
            typing: Callable,
            record_message: Callable,
            record_usage: Callable,
            send_message: Callable,
    ):
        self.name = name
        self._introduction = introduction
        self._agent = agent
        self._responses_api = responses_api
        self._receive_message = step(talk_tool.receive_message_from_user)
        self._typing = typing
        self._record_message = step(record_message)
        self._record_usage = step(record_usage)
        self._send_message = step(send_message)

    async def __call__(self, context: DuckContext):
        history: list[HistoryType] = []
        await self._send_message(context.thread_id, self._introduction)
        notify_retry = self._retry_notifier(context)

        while True:
            collector = StatsOutputCollector()
            setattr(context, "_stats_output_collector", collector)
            try:
                user_message = await self._receive_message(context)
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
                    tools={
                        tool_name: partial(tool, context)
                        for tool_name, tool in self._agent.tools.items()
                    },
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
            except ConversationComplete:
                return history
            finally:
                await collector.cleanup()
                if hasattr(context, "_stats_output_collector"):
                    delattr(context, "_stats_output_collector")

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


def build_stats_agent(settings: dict[str, Any], armory) -> Agent:
    prompt = "\n".join(
        Path(prompt_file).read_text(encoding="utf-8")
        for prompt_file in settings["prompt_files"]
    )
    return Agent(
        name=settings["name"],
        model=settings["engine"],
        armory=armory,
        prompt=prompt,
        tools={
            tool_name: armory.get_specific_tool(tool_name)
            for tool_name in settings["tools"]
        },
        reasoning=settings.get("reasoning"),
    )
