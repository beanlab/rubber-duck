import asyncio
from contextlib import asynccontextmanager
from typing import Any


class DiscordIORouter:
    def __init__(self, client: Any):
        self._client = client

    @asynccontextmanager
    async def typing(self, channel_id: int):
        channel = await self._get_channel(channel_id)
        async with channel.typing():
            yield

    async def _get_channel(self, channel_id: int) -> Any:
        channel = self._client.get_channel(channel_id)
        if channel is None:
            channel = await self._client.fetch_channel(channel_id)
        return channel

    async def send_message(self, channel_id: int, content: str | None = None, **kwargs: Any) -> Any:
        channel = await self._get_channel(channel_id)
        return await channel.send(content, **kwargs)

    async def wait_for_message(
        self,
        *,
        channel_id: int | None = None,
        timeout: float | None = None,
        require_content: bool = True,
    ) -> Any | None:
        def message_check(message: Any) -> bool:
            if self._is_self_user(message.author):
                return False

            if channel_id is not None and int(message.channel.id) != int(channel_id):
                return False

            if require_content and not getattr(message, "content", "").strip():
                return False

            return True

        try:
            return await self._client.wait_for(
                "message",
                check=message_check,
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return None

    async def collect_debounced_input(
        self,
        *,
        first_message: Any | None = None,
        channel_id: int | None = None,
        debounce_seconds: float,
        timeout: float | None = None,
    ) -> tuple[int, str]:
        if first_message is None:
            first_message = await self.wait_for_message(
                channel_id=channel_id,
                timeout=timeout,
            )
        if first_message is None:
            raise TimeoutError("No initial message was received.")

        messages = [first_message.content.strip()]
        reply_channel_id = int(first_message.channel.id)

        while True:
            message = await self.wait_for_message(
                channel_id=channel_id,
                timeout=debounce_seconds,
            )
            if message is None:
                return reply_channel_id, "\n".join(messages)

            content = message.content.strip()
            if content:
                messages.append(content)
                reply_channel_id = int(message.channel.id)

    def _is_self_user(self, user: Any) -> bool:
        return bool(
            self._client.user
            and int(user.id) == int(self._client.user.id)
        )
