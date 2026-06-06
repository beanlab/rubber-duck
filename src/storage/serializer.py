from quest import MasterSerializer
from quest.serializer import TypeSerializer

from ..workflows.debugging_duck.debugging_practice_duck_workflow import (
    GeneralAssessor,
    SubprocessCompletion,
)


class GeneralAssessorSerializer(TypeSerializer[GeneralAssessor]):
    async def serialize(self, obj: GeneralAssessor) -> tuple[tuple, dict]:
        return (obj.model_dump(mode="json"),), {}

    async def deserialize(self, data: dict) -> GeneralAssessor:
        return GeneralAssessor.model_validate(data)


class SubprocessCompletionSerializer(TypeSerializer[SubprocessCompletion]):
    async def serialize(self, obj: SubprocessCompletion) -> tuple[tuple, dict]:
        return (obj.model_dump(mode="json"),), {}

    async def deserialize(self, data: dict) -> SubprocessCompletion:
        return SubprocessCompletion.model_validate(data)


workflow_serializer = MasterSerializer({
    GeneralAssessor: GeneralAssessorSerializer(),
    SubprocessCompletion: SubprocessCompletionSerializer(),
})
