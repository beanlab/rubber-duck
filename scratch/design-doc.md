The debugging workflow duck in this repo uses a custom implementation of run_agent from gen_ai to run completions and validate structured output with pydantic. The issue with this is that the environment's usage of the quest package doesn't currently support this, so implementing the @step in the workflow, while necessary, is impossible. To make this possible, we need to add a serializer.py in src/storage that imports the pydantic from the workflow and creates a serializer class that can be used for quest to properly @step out anything that needs to be completed that involves pydantic type validation. This is the proposed structure of that implementation.

```
    class GeneralAssessorSerializer(TypeSerializer[GeneralAssessor]):
        async def serialize(self, obj: GeneralAssessor) -> tuple[tuple, dict]:
            return (obj.to_json(),), {}

        async def deserialize(self, *args, **kwargs) -> GeneralAssessor:
            return PriorityAssessment.from_json(*args)
            
    serializer = MasterSerializer({
        type(GeneralAssessor): GeneralAssessorSerizlier
    })

    workflow_manager = create_sql_manager(namespace, create_workflow, sql_session, serializer=serializer)
```

Assess the quest package, the implementation of the workflow, main, gen_ai, the structure of what needs to be completed, then ask questions about the implementation and be prepared to discuss additional details not in this document.