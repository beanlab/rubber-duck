import asyncio
import json

from src.gen_ai.gen_ai import Agent
from src.utils.config_types import DuckContext
from src.workflows import student_duck_workflow
from src.workflows.student_duck_workflow import DEFAULT_FIRST_MESSAGE, StudentDuckWorkflow


def _ctx(content: str = "Thread title") -> DuckContext:
    return DuckContext(
        guild_id=1,
        parent_channel_id=2,
        author_id=3,
        author_mention="@user",
        content=content,
        message_id=4,
        thread_id=5,
        timeout=60,
    )


class _FakeAIClient:
    def __init__(self):
        self.calls = []

    async def run_agent(self, _context, agent, query):
        self.calls.append({"agent": agent.name, "query": query})
        if agent.name == "error":
            return json.dumps({"check_type": "error", "assessment": "No errors."})
        if agent.name == "omission":
            return json.dumps({"check_type": "omission", "assessment": "No omissions."})
        return "What does that mean?"


def _agent(name: str) -> Agent:
    return Agent(name=name, prompt="", model="", tools=[])


def test_student_duck_prompts_before_reviewing_thread_replies(monkeypatch):
    sent_messages = []
    user_messages = [{"content": "I want to learn recursion."}, None]

    async def _send_message(_thread_id, message=None, file=None, view=None):
        sent_messages.append(message)
        return 1

    async def _wait_for_message(_timeout):
        return user_messages.pop(0)

    monkeypatch.setattr(student_duck_workflow, "wait_for_message", _wait_for_message)

    ai_client = _FakeAIClient()
    workflow = StudentDuckWorkflow(
        "student_duck",
        _send_message,
        {},
        _agent("student"),
        _agent("error"),
        _agent("omission"),
        ai_client,
    )

    asyncio.run(workflow(_ctx("Thread title that should not be assessed")))

    assert sent_messages[0] == DEFAULT_FIRST_MESSAGE

    checker_calls = [
        call for call in ai_client.calls
        if call["agent"] in {"error", "omission"}
    ]
    assert len(checker_calls) == 2
    for call in checker_calls:
        payload = json.loads(call["query"])
        assert payload["user_response"] == "I want to learn recursion."
        assert "Thread title that should not be assessed" not in call["query"]


def test_student_duck_first_message_can_be_configured(monkeypatch):
    sent_messages = []

    async def _send_message(_thread_id, message=None, file=None, view=None):
        sent_messages.append(message)
        return 1

    async def _wait_for_message(_timeout):
        return None

    monkeypatch.setattr(student_duck_workflow, "wait_for_message", _wait_for_message)

    workflow = StudentDuckWorkflow(
        "student_duck",
        _send_message,
        {"first_message": "Custom first prompt."},
        _agent("student"),
        _agent("error"),
        _agent("omission"),
        _FakeAIClient(),
    )

    asyncio.run(workflow(_ctx()))

    assert sent_messages[0] == "Custom first prompt."
