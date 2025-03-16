import logging

from openai import AsyncOpenAI, APITimeoutError, InternalServerError, UnprocessableEntityError, APIConnectionError, \
    BadRequestError, AuthenticationError, ConflictError, NotFoundError, RateLimitError
from openai.types.chat import ChatCompletion
from conversation import GenAIException, RetryableException


class OpenAI():
    def __init__(self, openai_api_key: str):
        self._client = AsyncOpenAI(api_key=openai_api_key)

    async def get_completion(self, engine, message_history) -> tuple[list, dict]:
        try:
            completion: ChatCompletion = await self._client.chat.completions.create(
                model=engine,
                messages=message_history
            )
            logging.debug(f"Completion: {completion}")
            completion_dict = completion.dict()
            choices = completion_dict['choices']
            usage = completion_dict['usage']
            return choices, usage
        except (
            APITimeoutError, InternalServerError,
            UnprocessableEntityError) as ex:
            raise RetryableException(ex, 'I\'m having trouble connecting to the OpenAI servers, '
                                             'please open up a separate conversation and try again')
        except (APIConnectionError, BadRequestError,
                        AuthenticationError, ConflictError, NotFoundError,
                        RateLimitError) as ex:
            raise GenAIException(ex, "Visit https://platform.openai.com/docs/guides/error-codes/api-errors " \
                                         "for more details on how to resolve this error")

