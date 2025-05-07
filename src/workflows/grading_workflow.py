import asyncio

from quest import step, alias, queue

from conversation.conversation import GPTMessage
from metrics.feedback import GetConvoFeedback
from workflows.basic_prompt_workflow import SetupThread, HaveTAConversation

from utils.protocols import Message



class GradingWorkflow:
    def __init__(self,
                 setup_thread: SetupThread,
                 have_conversation: HaveTAConversation,
                 ):

        # Make a rubber duck per channel
        self._setup_thread = step(setup_thread)
        self._have_conversation = step(have_conversation)

    async def queue_initializer(queue_name: str, identity: str):
        async with queue(queue_name, identity):
            await asyncio.Event().wait()

    async def __call__(self, channel_id: int, initial_message: Message, timeout=600):

        thread_id = await self._setup_thread(initial_message)

        message_history = [GPTMessage]
        async with alias(str(thread_id)):
            await self._have_conversation(thread_id, message_history, timeout)

        guild_id = initial_message['guild_id']
        user_id = initial_message['author_id']

