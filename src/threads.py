from protocols import Message, CreateThread, SendMessage


class SetupPrivateThread:
    def __init__(self, create_thread: CreateThread, send_message: SendMessage):
        self._create_thread = create_thread
        self._send_message = send_message

    async def __call__(self, initial_message: Message) -> int:
        thread_id = await self._create_thread(
            initial_message['channel_id'],
            initial_message['content'][:20]
        )

        # Send welcome message to add the user to the thread
        await self._send_message(thread_id, f'Hello {initial_message["author_mention"]}, how can I help you?')

        # Notify the user in the original channel of the new thread
        await self._send_message(
            initial_message['channel_id'],
            f"<@{initial_message['author_id']}> Click here to join the conversation: <#{thread_id}>"
        )

        return thread_id
