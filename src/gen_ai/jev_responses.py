from operator import call
from typing import TypedDict
from quest import step
from typesafe_sdk import AsyncTypeSafeClient, SystemOneResponse, Question


class Usage(TypedDict):
    model: str
    input_tokens: int
    output_tokens: int


class JevResponse(TypedDict):
    state: dict
    usage: Usage | None
    questions: dict[str, Question]
    answers: dict


class JevAPI:
    def __init__(
            self,
            client: AsyncTypeSafeClient
    ):
        self.client = client

    @step
    async def assess(self, state: dict,
                     questions: dict[str, Question],
                     model: str | None = None) -> JevResponse:
        response: SystemOneResponse = await self.client.system_one(
            state=state,
            questions=questions,
            model=model
        )

        usage: Usage = {"model": response.model,
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens}

        jev_response: JevResponse = {"state": state,
                                     "usage": usage,
                                     "questions": questions,
                                     "answers": response.answers}

        return jev_response
