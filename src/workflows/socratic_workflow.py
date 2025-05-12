from conversation.conversation import GPTMessage
from conversation.conversation import HaveConversation
from quest import step


class SocraticWorkflow:
    def __init__(self,
                 conversation: HaveConversation,
                 thread_id: int,
                 engine: str,
                 message_history: list[GPTMessage],
                 timeout: int
                 ):
        self.conversation = step(conversation)
        self.thread_id = thread_id
        self.engine = engine
        self.message_history = message_history
        self.timeout = timeout

    async def __call__(self):
        # await self._have_conversation(thread_id, engine, message_history, timeout)
        await self.conversation(self.thread_id, self.engine, self.message_history, self.timeout)
