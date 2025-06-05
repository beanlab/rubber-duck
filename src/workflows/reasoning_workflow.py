import asyncio

import httpx
from openai import OpenAI as OpenAIClient

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

    async def _orchestrate_messages(self, sendables: [Sendable], guild_id: int, thread_id: int, user_id: int,
                                    message_history: list[GPTMessage]):
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

    def _extract_summary_text(self, response_output: dict):
        duck_logger.debug(response_output['text'])

    def _extract_text(self, response_output) -> str:
        pass

    async def _async_create_response(self, model, reasoning, max_output_tokens, input):
        url = "https://api.openai.com/v1/responses"
        headers = {
            "Authorization": f"Bearer {self._client.api_key}",  # assumes OpenAIClient was initialized with key
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "reasoning": reasoning,
            "max_output_tokens": max_output_tokens,
            "input": input,  # assuming input is a list of dictionaries
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def _async_retrieve_response(self, response_id: str):
        url = f"https://api.openai.com/v1/responses/{response_id}"
        headers = {
            "Authorization": f"Bearer {self._client.api_key}"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def __call__(self, thread_id: int, settings: ReasoningConfig, initial_message):
        prompt = settings['prompt_file']
        timeout = settings['timeout']
        model = settings['engine']
        reasoning = settings['reasoning']
        max_output_tokens = settings["max_output_tokens"]
        introduction = "Welcome to Reasoning Duck! Ask a question to get started."

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
                    sendables = await self._async_create_response(
                        model=model,
                        reasoning=reasoning,
                        max_output_tokens=max_output_tokens,
                        input=message_history
                    )

                    # First output is the reasoning object
                    reasoning_obj = sendables['output'][0]
                    self._extract_summary_text(reasoning_obj)

                    # Second output is the response content
                    response_content = sendables['output'][1]

                    # Wait for complete response if status is incomplete
                    if response_content['status'] == 'incomplete':
                        # Get the complete response
                        complete_response = await self._async_retrieve_response(response_content['id'])
                        response_content = complete_response

                    # Send the response content
                    if 'content' in response_content:
                        for content_item in response_content['content']:
                            if 'text' in content_item:
                                await self._record_message(
                                    guild_id, thread_id, user_id, 'assistant', content_item['text'])
                                await self._send_message(thread_id, message=content_item['text'])
                                message_history.append(GPTMessage(role='assistant', content=content_item['text']))

                except GenAIException:
                    await self._send_message(thread_id,
                                             'I\'m having trouble processing your request.'
                                             'The admins are aware. Please try again later.')
                    raise
