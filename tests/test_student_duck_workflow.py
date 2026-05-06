import asyncio
import json

from src.gen_ai.gen_ai import Agent
from src.utils.config_types import DuckContext
from src.workflows import student_duck_workflow
from src.workflows.student_duck_workflow import (
    StudentDuckRubricTools,
    StudentDuckWorkflow,
)

CONFIGURED_FIRST_MESSAGE = "What are we going to learn today?"
CONFIGURED_TOPIC_ACKNOWLEDGEMENT = "Okay!"


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


def _student_duck_settings(**overrides):
    return {
        "first_message": CONFIGURED_FIRST_MESSAGE,
        "topic_acknowledgement": CONFIGURED_TOPIC_ACKNOWLEDGEMENT,
        **overrides,
    }


def test_student_duck_rubric_selection_matches_topic_and_returns_rubric(tmp_path):
    rubric_root = tmp_path / "CS110"
    rubric_root.mkdir()
    (rubric_root / "return-demo-rubric.yaml").write_text(
        """
return:
  criteria:
    - return sends a value back
""".strip()
    )
    (rubric_root / "variables-demo-rubric.yaml").write_text(
        """
variables:
  criteria:
    - variables store values
""".strip()
    )

    rubric_tools = StudentDuckRubricTools({"rubric_roots": [str(rubric_root)]})

    response = asyncio.run(
        rubric_tools.select_rubric(_ctx("CS110"), "CS110", "returns")
    )

    payload = json.loads(response)
    assert payload["selected"] is True
    assert payload["rubric_id"] == "return-demo-rubric"
    assert payload["rubric"] == {
        "return": {
            "criteria": ["return sends a value back"],
        },
    }


def test_student_duck_rubric_selection_does_not_match_subject_only(tmp_path):
    rubric_root = tmp_path / "CS110"
    rubric_root.mkdir()
    (rubric_root / "return-demo-rubric.yaml").write_text(
        """
return:
  criteria:
    - return sends a value back
""".strip()
    )

    rubric_tools = StudentDuckRubricTools({"rubric_roots": [str(rubric_root)]})

    response = asyncio.run(
        rubric_tools.select_rubric(_ctx("CS110"), "CS110", "loops")
    )

    payload = json.loads(response)
    assert payload["selected"] is False
    assert payload["rubric"] == {}


def test_student_duck_uses_first_reply_for_rubric_selection_and_reviews_next_reply(monkeypatch, tmp_path):
    rubric_root = tmp_path / "CS110"
    rubric_root.mkdir()
    (rubric_root / "return-demo-rubric.yaml").write_text(
        """
return:
  scope:
    - return in python
  using return:
    - return lets the function send a value back to the caller
""".strip()
    )

    user_messages = [
        {"content": "I want to explain returns."},
        {"content": "Return sends a value back to the caller."},
        None,
    ]

    async def _send_message(_thread_id, message=None, file=None, view=None):
        return 1

    async def _wait_for_message(_timeout):
        return user_messages.pop(0)

    monkeypatch.setattr(student_duck_workflow, "wait_for_message", _wait_for_message)

    ai_client = _FakeAIClient()
    workflow = StudentDuckWorkflow(
        "student_duck",
        _send_message,
        _student_duck_settings(),
        _agent("student"),
        _agent("error"),
        _agent("omission"),
        ai_client,
        StudentDuckRubricTools({"rubric_roots": [str(rubric_root)]}),
    )

    asyncio.run(workflow(_ctx("CS110")))

    checker_calls = [
        call for call in ai_client.calls
        if call["agent"] in {"error", "omission"}
    ]
    assert len(checker_calls) == 2
    for call in checker_calls:
        payload = json.loads(call["query"])
        assert payload["user_response"] == "Return sends a value back to the caller."
        assert payload["rubric"] == {
            "return": {
                "scope": ["return in python"],
                "using return": ["return lets the function send a value back to the caller"],
            },
        }

    student_payload = json.loads(ai_client.calls[-1]["query"])
    assert student_payload["selected_rubric_id"] == "return-demo-rubric"
    assert student_payload["user_response"] == "Return sends a value back to the caller."


def test_student_duck_error_check_receives_conversation_context(monkeypatch):
    user_messages = [
        {"content": "I want to learn recursion."},
        {"content": "Recursion is when a function calls itself."},
        None,
    ]

    async def _send_message(_thread_id, message=None, file=None, view=None):
        return 1

    async def _wait_for_message(_timeout):
        return user_messages.pop(0)

    monkeypatch.setattr(student_duck_workflow, "wait_for_message", _wait_for_message)

    ai_client = _FakeAIClient()
    workflow = StudentDuckWorkflow(
        "student_duck",
        _send_message,
        _student_duck_settings(),
        _agent("student"),
        _agent("error"),
        _agent("omission"),
        ai_client,
    )

    asyncio.run(workflow(_ctx()))

    error_payload = json.loads(ai_client.calls[0]["query"])
    omission_payload = json.loads(ai_client.calls[1]["query"])

    assert ai_client.calls[0]["agent"] == "error"
    assert error_payload["conversation_context"] == [
        {"role": "user", "content": "Recursion is when a function calls itself."}
    ]
    assert omission_payload["conversation_context"] == [
        {"role": "user", "content": "Recursion is when a function calls itself."}
    ]


def test_student_duck_configured_rubric_path_is_not_overridden(monkeypatch, tmp_path):
    configured_rubric = tmp_path / "configured-rubric.yaml"
    configured_rubric.write_text(
        """
configured:
  criteria:
    - use this rubric
""".strip()
    )
    rubric_root = tmp_path / "CS110"
    rubric_root.mkdir()
    (rubric_root / "return-demo-rubric.yaml").write_text(
        """
return:
  criteria:
    - do not override configured rubric path
""".strip()
    )

    user_messages = [
        {"content": "I want to explain returns."},
        {"content": "Return sends a value back to the caller."},
        None,
    ]

    async def _send_message(_thread_id, message=None, file=None, view=None):
        return 1

    async def _wait_for_message(_timeout):
        return user_messages.pop(0)

    monkeypatch.setattr(student_duck_workflow, "wait_for_message", _wait_for_message)

    ai_client = _FakeAIClient()
    workflow = StudentDuckWorkflow(
        "student_duck",
        _send_message,
        _student_duck_settings(rubric_path=str(configured_rubric)),
        _agent("student"),
        _agent("error"),
        _agent("omission"),
        ai_client,
        StudentDuckRubricTools({"rubric_roots": [str(rubric_root)]}),
    )

    asyncio.run(workflow(_ctx("CS110")))

    checker_payload = json.loads(ai_client.calls[0]["query"])
    assert checker_payload["rubric"] == {
        "configured": {
            "criteria": ["use this rubric"],
        },
    }


def test_student_duck_prompts_before_reviewing_thread_replies(monkeypatch):
    sent_messages = []
    user_messages = [
        {"content": "I want to learn recursion."},
        {"content": "Recursion is when a function calls itself."},
        None,
    ]

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
        _student_duck_settings(),
        _agent("student"),
        _agent("error"),
        _agent("omission"),
        ai_client,
    )

    asyncio.run(workflow(_ctx("Thread title that should not be assessed")))

    assert sent_messages[0] == CONFIGURED_FIRST_MESSAGE
    assert sent_messages[1] == CONFIGURED_TOPIC_ACKNOWLEDGEMENT

    checker_calls = [
        call for call in ai_client.calls
        if call["agent"] in {"error", "omission"}
    ]
    assert len(checker_calls) == 2
    for call in checker_calls:
        payload = json.loads(call["query"])
        assert payload["user_response"] == "Recursion is when a function calls itself."
        assert "I want to learn recursion." not in call["query"]
        assert "Thread title that should not be assessed" not in call["query"]


def test_student_duck_topic_acknowledgement_can_be_configured(monkeypatch):
    sent_messages = []
    user_messages = [{"content": "I want to learn recursion."}, None]

    async def _send_message(_thread_id, message=None, file=None, view=None):
        sent_messages.append(message)
        return 1

    async def _wait_for_message(_timeout):
        return user_messages.pop(0)

    monkeypatch.setattr(student_duck_workflow, "wait_for_message", _wait_for_message)

    workflow = StudentDuckWorkflow(
        "student_duck",
        _send_message,
        _student_duck_settings(topic_acknowledgement="Custom topic ack."),
        _agent("student"),
        _agent("error"),
        _agent("omission"),
        _FakeAIClient(),
    )

    asyncio.run(workflow(_ctx()))

    assert sent_messages[1] == "Custom topic ack."


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
        _student_duck_settings(first_message="Custom first prompt."),
        _agent("student"),
        _agent("error"),
        _agent("omission"),
        _FakeAIClient(),
    )

    asyncio.run(workflow(_ctx()))

    assert sent_messages[0] == "Custom first prompt."


def test_student_duck_full_review_turns_runs_until_timeout(monkeypatch):
    user_messages = [
        {"content": "I want to learn recursion."},
        {"content": "Recursion is when a function calls itself."},
        {"content": "It needs a base case so it can stop."},
        None,
    ]

    async def _send_message(_thread_id, message=None, file=None, view=None):
        return 1

    async def _wait_for_message(_timeout):
        return user_messages.pop(0)

    monkeypatch.setattr(student_duck_workflow, "wait_for_message", _wait_for_message)

    ai_client = _FakeAIClient()
    workflow = StudentDuckWorkflow(
        "student_duck",
        _send_message,
        _student_duck_settings(review_turns="full"),
        _agent("student"),
        _agent("error"),
        _agent("omission"),
        ai_client,
    )

    asyncio.run(workflow(_ctx()))

    checker_calls = [
        call for call in ai_client.calls
        if call["agent"] in {"error", "omission"}
    ]
    assert len(checker_calls) == 4
