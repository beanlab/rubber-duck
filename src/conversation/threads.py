import asyncio

from .conversations import ConversationThread


class SetupConversationThread:
    def __init__(self, create_thread, send_message, conversations):
        self._create_thread = create_thread
        self._send_message = send_message
        self._conversations = conversations
        self._locks = {}

    async def __call__(self, guild_id, parent_channel_id, user_id, author_mention):
        key = guild_id, user_id, parent_channel_id
        # shortcut: this lock assumes one bot process; use a DB reservation before horizontal scaling.
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            conversation = self._conversations.get(*key)
            if conversation is None:
                thread_id = await self._create_thread(parent_channel_id, "Happy Stats Duck ")

                # Send welcome message to add the user to the thread
                await self._send_message(thread_id, author_mention)
                conversation = ConversationThread(guild_id, user_id, parent_channel_id, thread_id)
                self._conversations.add(conversation)

        # Notify the user in the original channel of the thread
        await self._send_message(
            parent_channel_id,
            f"{author_mention} Click here to join the conversation: <#{conversation.thread_id}>"
        )
        return conversation
