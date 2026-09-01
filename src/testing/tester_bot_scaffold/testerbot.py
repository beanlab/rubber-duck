import json
import re
from dataclasses import replace
from typing import Any

import discord
from openai.types.responses import EasyInputMessage

from ...armory.armory import Armory
from ...gen_ai.gen_ai import Agent, AIClient
from ...utils.config_types import DuckContext, HistoryType
from .assessments import ProgressAssessment, format_history_for_assessor
from .discord_io import DiscordIORouter


async def record_message_noop(*_args: Any, **_kwargs: Any) -> None:
    return None


async def record_usage_noop(*_args: Any, **_kwargs: Any) -> None:
    return None


class TesterBot(discord.Client):
    def __init__(
        self,
        *,
        admin_channel_id: int,
        debounce_seconds: float,
        agent: Agent,
        target_channel_id: int | None = None,
        ai_client: AIClient | None = None,
        record_usage=None,
    ):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self._admin_channel_id = admin_channel_id
        self._target_channel_id = target_channel_id
        self.agent = agent
        self.discord_io = DiscordIORouter(self)
        self._debounce_seconds = debounce_seconds
        self.last_context: DuckContext | None = None
        self.ai_client = ai_client or AIClient(
            Armory(self._send_message_for_ai_client),
            self.discord_io.typing,
            record_message_noop,
            record_usage or record_usage_noop,
            {"max_retries": 3, "delay": 1, "backoff": 2},
            self._send_message_for_ai_client,
        )

    async def _send_message_for_ai_client(
        self,
        channel_id: int,
        message: str | None = None,
        file=None,
        view=None,
    ) -> int:
        kwargs = {}
        if file is not None:
            kwargs["file"] = file
        if view is not None:
            kwargs["view"] = view
        sent_message = await self.discord_io.send_message(channel_id, message, **kwargs)
        return int(sent_message.id)

    async def send_startup_message(
        self,
        content: str = "hello world",
        channel_id: int | None = None,
    ) -> Any:
        target_channel_id = channel_id or self._target_channel_id
        if target_channel_id is None:
            raise ValueError("A channel_id is required to start a conversation.")

        return await self.discord_io.send_message(
            target_channel_id,
            content,
        )

    async def run_conversation(
        self,
        *,
        channel_id: int | None = None,
        thread_opener_channel_id: int | None = None,
        thread_opener: str = "hello world",
        base_prompt: str | None = None,
        progress_assessor: Agent | None = None,
        max_turns: int = 30,
        idle_timeout_seconds: float = 30,
    ) -> list[HistoryType]:
        conversation_agent = (
            replace(self.agent, prompt=base_prompt)
            if base_prompt is not None
            else self.agent
        )
        startup_message = await self.send_startup_message(
            thread_opener,
            channel_id=thread_opener_channel_id or channel_id,
        )
        ctx = self._make_context(startup_message, idle_timeout_seconds)
        opened_thread_id = await self._wait_for_opened_thread_id(
            parent_channel_id=int(startup_message.channel.id),
            timeout=idle_timeout_seconds,
        )
        if opened_thread_id is not None:
            ctx.thread_id = opened_thread_id
        self.last_context = ctx
        turns = 0
        history: list[HistoryType] = []

        while turns < max_turns:
            channel_filter = ctx.thread_id if opened_thread_id is not None or turns > 0 else None
            try:
                reply_channel_id, user_input = await self.discord_io.collect_debounced_input(
                    channel_id=channel_filter,
                    debounce_seconds=self._debounce_seconds,
                    timeout=idle_timeout_seconds,
                )
            except TimeoutError:
                break

            ctx.thread_id = reply_channel_id
            self.last_context = ctx
            turns += 1

            await self.ai_client._record_message(
                ctx.guild_id,
                ctx.thread_id,
                ctx.author_id,
                "message",
                json.dumps(user_input),
            )
            history.append(
                EasyInputMessage(
                    role="user",
                    content=user_input,
                    type="message",
                ).model_dump()
            )

            agent_response, agent_history, conversation_complete = await self.ai_client._run_agent(
                ctx,
                conversation_agent,
                history,
            )

            if agent_response:
                await self.discord_io.send_message(ctx.thread_id, agent_response)

            history.extend(agent_history)

            if conversation_complete:
                break

            if progress_assessor is not None:
                assessment = await self.ai_client.run_agent(
                    ctx,
                    progress_assessor,
                    format_history_for_assessor(history),
                    output_format=ProgressAssessment,
                )
                if assessment.status == "catch":
                    break

        return history

    async def _wait_for_opened_thread_id(
        self,
        *,
        parent_channel_id: int,
        timeout: float,
    ) -> int | None:
        def notification_check(message: Any) -> bool:
            if self.user and int(message.author.id) == int(self.user.id):
                return False
            if int(message.channel.id) != int(parent_channel_id):
                return False
            return bool(re.search(r"<#(\d+)>", getattr(message, "content", "")))

        try:
            message = await self.wait_for(
                "message",
                check=notification_check,
                timeout=timeout,
            )
        except TimeoutError:
            return None

        match = re.search(r"<#(\d+)>", message.content)
        if match is None:
            return None
        return int(match.group(1))

    def _make_context(self, startup_message: Any, timeout: float) -> DuckContext:
        channel = startup_message.channel
        guild = startup_message.guild or getattr(channel, "guild", None)
        author = startup_message.author
        return DuckContext(
            guild_id=int(guild.id) if guild else 0,
            parent_channel_id=int(channel.id),
            author_id=int(author.id),
            author_mention=getattr(author, "mention", ""),
            content=startup_message.content,
            message_id=int(startup_message.id),
            thread_id=int(channel.id),
            timeout=int(timeout),
        )
