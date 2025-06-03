import asyncio

from agents import AgentsException
from quest import queue, step

from ..armory.tools import register_tool
from ..utils.gen_ai import RecordMessage
from ..utils.protocols import SendMessage, Message, IndicateTyping


class AgentTools:
    def __init__(self,
                 record_message: RecordMessage,
                 send_message: SendMessage,
                 typing: IndicateTyping,
                 guild_id: int,
                 thread_id: int,
                 user_id: int,
                 timeout: int = 30,
                 ):
        self._record_message = record_message
        self._send_message = send_message
        self._typing = typing
        self._guild_id = guild_id
        self._thread_id = thread_id
        self._user_id = user_id
        self._timeout = timeout


    @register_tool
    async def talk_to_user(self, query: str) -> str:
        try:
            async with self._typing(self._thread_id):
                await self._send_message(self._thread_id, query)
            await self._record_message(
                self._guild_id, self._thread_id, self._user_id, 'assistant', query)
            async with queue('messages', None) as messages:

                message: Message = await asyncio.wait_for(messages.get(), self._timeout)
                await self._record_message(self._guild_id, self._thread_id, self._user_id, 'user', message['content'])
            return message['content']
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError("Timeout while waiting for user response")

