from typing import Literal

from pydantic import BaseModel, ConfigDict


class ProgressAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    status: Literal["catch", "pass"]


class PostConversationAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    status: Literal["pass", "fail"]


class ConversationUsefulnessAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str
    classification: Literal["useful", "not useful"]
