import asyncio
from openai import OpenAI as OpenAIClient
from openai.types.responses import ResponseReasoningItem

from quest import step, queue

from ..conversation.conversation import BasicSetupConversation
from ..utils.config_types import ReasoningConfig
from ..utils.gen_ai import GPTMessage, GenAIException, OpenAI, Sendable
from ..utils.logger import duck_logger
from ..utils.protocols import Message


class ReasoningWorkflow:
    def __init__(self,
                 send_message,
                 get_channel,
                 fetch_guild,
                 setup_conversation: BasicSetupConversation,
                 record_message
                 ):
        self._send_message = step(send_message)
        self._get_channel = get_channel
        self._get_guild = fetch_guild
        self._record_message = step(record_message)
        self._setup_conversation = step(setup_conversation)
        self._client = OpenAIClient()

    async def _orchestrate_messages(self, sendables: [Sendable], guild_id: int, thread_id: int, user_id: int, message_history: list[GPTMessage]):
        for sendable in sendables:
            if isinstance(sendable, str):
                await self._record_message(
                    guild_id, thread_id, user_id, 'assistant', sendable)
                await self._send_message(thread_id, message=sendable)
                message_history.append(GPTMessage(role='assistant', content=sendable))

            elif isinstance(sendable, tuple):
                print(f"Tuple contents: {sendable}")  # Debug log
                if len(sendable) == 2:
                    filename, content = sendable
                    if isinstance(content, (bytes, bytearray)):
                        # Handle file attachments (filename, bytes)
                        await self._record_message(
                            guild_id, thread_id, user_id, 'assistant', f'<image {filename}>')
                        await self._send_message(thread_id, file=sendable)
                        message_history.append(GPTMessage(role='assistant', content=f'<image {filename}>'))
                    else:
                        # Convert content to string and handle as text
                        content_str = str(content)
                        await self._record_message(
                            guild_id, thread_id, user_id, 'assistant', content_str)
                        await self._send_message(thread_id, message=content_str)
                        message_history.append(GPTMessage(role='assistant', content=content_str))
                else:
                    print(f"Unexpected tuple length: {len(sendable)}")
            else:
                print(f"Unexpected sendable type: {type(sendable)}")
                continue

    def _extract_summary_text(self, response_output: ResponseReasoningItem):
        summaries = []

        if isinstance(response_output, ResponseReasoningItem):
            for summary in response_output.summary:
                if hasattr(summary, 'text'):
                    summaries.append(summary.text)
        duck_logger.debug(f"Summaries: {summaries}")

    def _extract_text(self, response_output) -> str:
        pass

    async def __call__(self, thread_id: int, settings: ReasoningConfig, initial_message):
        prompt = settings['prompt_file']
        timeout = settings['timeout']
        model = settings['engine']
        reasoning = settings['reasoning']
        max_output_tokens = settings["max_output_tokens"]
        introduction = "Welcome to Reasoning Duck!"

        message_history = await self._setup_conversation(thread_id, prompt, initial_message)

        await self._send_message(thread_id, introduction)

        async with queue('messages', None) as messages:
            while True:
                try:  # catch all errors
                    try:
                        # Waiting for a response from the user
                        message: Message = await asyncio.wait_for(messages.get(), timeout)

                    except asyncio.TimeoutError:  # Close the thread if the conversation has closed
                        break

                    if len(message['file']) > 0:
                        await self._send_message(
                            thread_id,
                            "I'm sorry, I can't read file attachments. "
                            "Please resend your message with the relevant parts of your file included in the message."
                        )
                        continue

                    message_history.append(GPTMessage(role='user', content=message['content']))

                    user_id = message['author_id']
                    guild_id = message['guild_id']

                    await self._record_message(
                        guild_id, thread_id, user_id, message_history[-1]['role'], message_history[-1]['content']
                    )

                    # To get around the blocking nature of the API, we use asyncio.to_thread
                    sendables = await asyncio.to_thread(
                        self._client.responses.create,
                        model=model,
                        reasoning=reasoning,
                        max_output_tokens=max_output_tokens,
                        input=message_history,
                    )

                    # First output is the reasoning object
                    reasoning_obj = sendables.output[0]
                    self._extract_summary_text(reasoning_obj)

                    # Second output is the response content
                    response_content = sendables.output[1]
                    
                    # Wait for complete response if status is incomplete
                    if response_content.status == 'incomplete':
                        # Get the complete response
                        complete_response = await asyncio.to_thread(
                            self._client.responses.retrieve,
                            response_content.id
                        )
                        response_content = complete_response

                    # Send the response content
                    if hasattr(response_content, 'content'):
                        for content_item in response_content.content:
                            if hasattr(content_item, 'text'):
                                await self._record_message(
                                    guild_id, thread_id, user_id, 'assistant', content_item.text)
                                await self._send_message(thread_id, message=content_item.text)
                                message_history.append(GPTMessage(role='assistant', content=content_item.text))

                except GenAIException:
                    await self._send_message(thread_id,
                                             'I\'m having trouble processing your request.'
                                             'The admins are aware. Please try again later.')
                    raise
