from typing import Callable

from .registration import Registration
from ..utils.config_types import DuckContext

class RegistrationWorkflow:
    def __init__(self,
                 name: str,
                 registration: Registration,
                 registration_bot: Callable | None,
                 send_message
                 ):
        self._name = name
        self._registration = registration
        self._registration_bot = registration_bot
        self._send_message = send_message


    async def __call__(self, context: DuckContext):
        try:
            await self._registration.run(context)
        except Exception as e:
            if self._registration_bot:
                await self._registration_bot(context, f"Hi, can you help me with registration this is the reason the workflow failed last time: {str(e)}")
            else:
                await self._send_message(context.thread_id, str(e))


