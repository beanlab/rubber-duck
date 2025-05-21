from quest import step, wrap_steps

from ..conversation.conversation import BasicSetupConversation
from ..utils.gen_ai import RetryableGenAI, RecordMessage, GPTMessage, RecordUsage
from ..utils.protocols import Message, SendMessage, IndicateTyping, AddReaction, ReportError


class MultiPromptConversation:
    def __init__(self,
                 ai_client: RetryableGenAI,
                 record_message: RecordMessage,
                 record_usage: RecordUsage,
                 typing: IndicateTyping,
                 send_message: SendMessage,
                 report_error: ReportError,
                 add_reaction: AddReaction,
                 setup_conversation: BasicSetupConversation,
                 ):
        self._ai_client = ai_client
        wrap_steps(self._ai_client, ['get_completion'])

        self._record_message = step(record_message)
        self._record_usage = step(record_usage)

        self._typing = typing
        self._send_message = step(send_message)
        self._report_error = step(report_error)
        self._add_reaction: AddReaction = step(add_reaction)

        self._setup_conversation = step(setup_conversation)

    async def __call__(self, thread_id: int, prompts: list[str], initial_message: Message, settings: dict):
        message_history = []
        user_id = initial_message['author_id']
        guild_id = initial_message['guild_id']
        channel_id = initial_message['channel_id']
        engine = settings["engine"]
        tools = settings.get("tools", [])

        # Add first user message to history
        message_history.append(GPTMessage(role="user", content=initial_message["content"]))
        await self._record_message(guild_id, thread_id, user_id, "user", initial_message["content"])

        for i, system_prompt in enumerate(prompts):
            # System prompt comes at the start
            staged_history = [GPTMessage(role="system", content=system_prompt)] + message_history

            # Get model response
            sendables = await self._ai_client.get_completion(
                guild_id,
                channel_id,
                thread_id,
                user_id,
                engine,
                staged_history,
                tools
            )

            for sendable in sendables:
                if isinstance(sendable, str):
                    await self._record_message(guild_id, thread_id, user_id, "assistant", sendable)
                    await self._send_message(thread_id, message=sendable)
                    message_history.append(GPTMessage(role="assistant", content=sendable))
                else:
                    await self._record_message(guild_id, thread_id, user_id, "assistant", f"<image {sendable[0]}>")
                    await self._send_message(thread_id, file=sendable)
                    message_history.append(GPTMessage(role="assistant", content=f"<image {sendable[0]}>"))

