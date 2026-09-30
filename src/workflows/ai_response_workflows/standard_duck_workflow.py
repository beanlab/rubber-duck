import json
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any, Callable

from openai.types.responses import EasyInputMessage
from quest import step

from ...armory.talk_tool import TalkTool
from ...gen_ai.ai_responses import Agent, ResponsesAPI
from ...utils.config_types import DuckContext, HistoryType
from ...utils.protocols import ConversationComplete


class StandardDuckWorkflow:
    def __init__(
            self,
            name: str,
            agent: Agent,
            responses_api: ResponsesAPI,
            talk_tool: TalkTool,
            typing: Callable,
            record_message: Callable,
            record_usage: Callable,
            send_message: Callable,
    ):
        self.name = name
        self._agent = agent
        self._responses_api = responses_api
        self._receive_message = step(talk_tool.receive_message_from_user)
        self._typing = typing
        self._record_message = step(record_message)
        self._record_usage = step(record_usage)
        self._send_message = step(send_message)

    async def __call__(self, context: DuckContext):
        history: list[HistoryType] = [
            EasyInputMessage(
                role="user",
                content="Hi",
                type="message",
            ).model_dump()
        ]

        notify_retry = self._retry_notifier(context)
        agent = replace(
            self._agent,
            tools={
                tool_name: partial(tool, context)
                for tool_name, tool in self._agent.tools.items()
            },
        )

        while True:
            try:
                async with self._typing(context.thread_id):
                    response = await self._responses_api.run_agent_turn(
                        agent,
                        history,
                        notify_retry,
                    )

                await self._record_response(context, response)
                history.extend(response["outputs"])

                if response["usage"]:
                    await self._record_usage(
                        context.guild_id,
                        context.parent_channel_id,
                        context.thread_id,
                        context.author_id,
                        response["usage"]["model"],
                        response["usage"]["input_tokens"],
                        response["usage"]["output_tokens"],
                        response["usage"]["cached_tokens"],
                        response["usage"]["reasoning_tokens"],
                    )

                result = response["result"]
                if result:
                    await self._send_message(context.thread_id, str(result))

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
            except ConversationComplete:
                return history

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

    def _retry_notifier(self, context: DuckContext):
        async def notify(delay_seconds: int):
            await self._send_message(
                context.thread_id,
                "I hit a temporary connection issue with an upstream server. "
                f"Retrying in {delay_seconds} seconds...",
            )

        return notify


def build_standard_agent(settings: dict[str, Any], armory) -> Agent:
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
