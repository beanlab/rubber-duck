import asyncio
import unittest
from unittest.mock import patch, AsyncMock
from rubber_duck import RubberDuck

async def have_conversation(self, thread_id: int, engine: str, prompt: str, initial_message: Message, timeout=600):
    async with queue('messages', str(thread_id)) as messages:
        message_history = [
            GPTMessage(role='system', content=prompt)
        ]
        user_id = initial_message['author_id']
        guild_id = initial_message['guild_id']
        await self._metrics_handler.record_message(
            guild_id, thread_id, user_id, message_history[0]['role'], message_history[0]['content'])

        await self._send_message(thread_id, f'Hello {initial_message["author_mention"]}, how can I help you?')

        while True:
            # TODO - if the conversation is getting long, and the user changes the subject
            #  prompt them to start a new conversation (and close this one)
            try:
                message: Message = await asyncio.wait_for(messages.get(), timeout)

            except asyncio.TimeoutError:
                await self._send_message(thread_id, '*This conversation has been closed.*')
                return

            message_history.append(GPTMessage(role='user', content=message['content']))

            user_id = message['author_id']
            guild_id = message['guild_id']

            await self._metrics_handler.record_message(
                guild_id, thread_id, user_id, message_history[-1]['role'], message_history[-1]['content'])

            try:
                choices, usage = await self._get_completion_with_retry(thread_id, engine, message_history)
                response_message = choices[0]['message']
                response = response_message['content'].strip()

                await self._metrics_handler.record_usage(guild_id, thread_id, user_id,
                                                         engine,
                                                         usage['prompt_tokens'],
                                                         usage['completion_tokens'])

                await self._metrics_handler.record_message(
                    guild_id, thread_id, user_id, response_message['role'], response_message['content'])

                message_history.append(GPTMessage(role='assistant', content=response))

                await self._send_message(thread_id, response)

            except Exception as ex:
                error_code = str(uuid.uuid4()).split('-')[0].upper()
                logging.exception('Error getting completion: ' + error_code)
                error_message = (
                    f'😵 **Error code {error_code}** 😵'
                    f'\nhttps://discord.com/channels/{guild_id}/{thread_id}'
                    f'\n{ex}\n'
                    '\n'.join(tb.format_exception(ex))
                )

                # For server-side errors
                if isinstance(ex,
                              (openai.APITimeoutError, openai.InternalServerError, openai.UnprocessableEntityError)):
                    await self._edit_message(thread_id, self._error_message_id,
                                             'I\'m having trouble connecting to the OpenAI servers, '
                                             'please open up a separate conversation and try again')
                # For client-side errors
                elif isinstance(ex, (openai.APIConnectionError, openai.BadRequestError,
                                     openai.AuthenticationError, openai.ConflictError, openai.ConflictError,
                                     openai.NotFoundError,
                                     openai.RateLimitError)):
                    # user_ids_to_mention = [933123843038535741]
                    user_ids_to_mention = [911012305880358952, 933123843038535741, 1014286006595358791,
                                           353454081265762315,
                                           941080292557471764]  # Dr.Bean, MaKenna, Chase, YoungWoo, Molly's ID's
                    mentions = ' '.join([f'<@{user_id}>' for user_id in user_ids_to_mention])
                    openai_web_mention = "Visit https://platform.openai.com/docs/guides/error-codes/api-errors " \
                                         "for more details on how to resolve this error"
                    await self._edit_message(thread_id, self._error_message_id,
                                             'I\'m having trouble processing your request, '
                                             'I have notified your professor to look into the problem!')
                    if isinstance(ex, openai.APIConnectionError):
                        client_error_message = "*** APIConnectionError ***"
                    elif isinstance(ex, openai.BadRequestError):
                        client_error_message = "*** BadRequestError ***"
                    elif isinstance(ex, openai.AuthenticationError):
                        client_error_message = "*** AuthenticationError ***"
                    elif isinstance(ex, openai.ConflictError):
                        client_error_message = "*** ConflictError ***"
                    elif isinstance(ex, openai.NotFoundError):
                        client_error_message = "*** NotFoundError ***"
                    elif isinstance(ex, openai.PermissionDeniedError):
                        client_error_message = "*** PermissionDeniedError ***"
                    elif isinstance(ex, openai.RateLimitError):
                        client_error_message = "*** RateLimitError ***"
                    await self._report_error(f"{mentions}\n{client_error_message}\n{openai_web_mention}")
                else:
                    await self._edit_message(thread_id, self._error_message_id,
                                             f'😵 **Error code {error_code}** 😵'
                                             f'\nAn unexpected error occurred. Please contact support.'
                                             f'\nError code for reference: {error_code}'
                                             '\n*This conversation is closed*')

                await self._report_error(error_message)

                return


class TestRetryGetCompletion(unittest.TestCase):
    async def test_get_completion_with_retry_error_handling(self):
        with patch('rubber_duck.RubberDuck.get_completion_with_retry', new_callable=AsyncMock) as mock_method:
            mock_method.side_effect = Exception("Test exception")


if __name__ == '__main__':
    unittest.main()
