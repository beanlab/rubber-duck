import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import yaml

from src.gen_ai.gen_ai import Agent
from src.utils.config_types import DuckContext
from src.workflows import code_duck_workflow
from src.workflows.code_duck_workflow import CodeDuckWorkflow


YAML_EXAMPLE_GEN_PATH = (
    Path(__file__).resolve().parents[1] / "rubrics" / "CS110" / "code-duck" / "yaml-example-gen.py"
)


def _load_yaml_example_gen():
    spec = importlib.util.spec_from_file_location("yaml_example_gen", YAML_EXAMPLE_GEN_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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
        return "Why does assigning the value back fix it?"


class _CompletingFakeAIClient(_FakeAIClient):
    async def run_agent(self, _context, agent, query):
        self.calls.append({"agent": agent.name, "query": query})
        return ""


def _agent(name: str) -> Agent:
    return Agent(name=name, prompt="", model="", tools=[])


def _code_duck_settings(**overrides):
    return {
        "first_message": "My code prints 0 instead of 1. What should I change?",
        **overrides,
    }


def test_code_duck_routes_turn_through_conversation_review(monkeypatch, tmp_path):
    rubric = tmp_path / "variables.yaml"
    rubric.write_text(
        """
variables:
  assignment:
    - count + 1 does not update count unless the result is assigned back
full project: |-
  count = 0
  count + 1
  print(count)
""".strip()
    )

    user_messages = [
        {"content": "I would change count + 1 to count = count + 1 because the new value must be assigned."},
        None,
    ]

    sent_messages = []

    async def _send_message(_thread_id, message=None, file=None, view=None):
        sent_messages.append(message)
        return 1

    async def _wait_for_message(_timeout):
        return user_messages.pop(0)

    monkeypatch.setattr(code_duck_workflow, "wait_for_message", _wait_for_message)

    ai_client = _FakeAIClient()
    workflow = CodeDuckWorkflow(
        "code_duck",
        _send_message,
        _code_duck_settings(rubric_path=str(rubric)),
        _agent("review"),
        ai_client,
    )

    asyncio.run(workflow(_ctx("Debug variables")))

    assert sent_messages[0] == (
        "My code prints 0 instead of 1. What should I change?\n\n"
        "```python\n"
        "count = 0\n"
        "count + 1\n"
        "print(count)\n"
        "```"
    )
    assert ai_client.calls[0]["agent"] == "review"

    review_calls = [call for call in ai_client.calls if call["agent"] == "review"]
    assert len(review_calls) == 1

    review_context = review_calls[0]["query"]
    assert isinstance(review_context, str)
    assert "Rubric and traceback scenarios:" in review_context
    assert "Current full project:" in review_context
    assert "Conversation:" in review_context
    assert "Student: My code prints 0 instead of 1. What should I change?" in review_context
    assert (
        "TA: I would change count + 1 to count = count + 1 because the new value must be assigned."
        in review_context
    )
    assert '"role": "user"' not in review_context
    assert '"role": "assistant"' not in review_context
    assert ai_client.calls == review_calls
    assert sent_messages[-1] == "Why does assigning the value back fix it?"


def test_code_duck_preserves_conversation_review_tools():
    agent = _agent("review")
    agent.tools = ["conclude_conversation"]

    CodeDuckWorkflow(
        "code_duck",
        lambda *_args, **_kwargs: None,
        _code_duck_settings(rubric_path="rubric.yaml"),
        agent,
        _FakeAIClient(),
    )

    assert agent.tools == ["conclude_conversation"]


def test_code_duck_full_review_turns_runs_until_timeout(monkeypatch, tmp_path):
    rubric = tmp_path / "variables.yaml"
    rubric.write_text(
        """
variables:
  assignment:
    - count + 1 does not update count unless the result is assigned back
""".strip()
    )

    user_messages = [
        {"content": "I would change it to count = count + 1."},
        {"content": "That works because assignment stores the new value in count."},
        None,
    ]

    async def _send_message(_thread_id, message=None, file=None, view=None):
        return 1

    async def _wait_for_message(_timeout):
        return user_messages.pop(0)

    monkeypatch.setattr(code_duck_workflow, "wait_for_message", _wait_for_message)

    ai_client = _FakeAIClient()
    workflow = CodeDuckWorkflow(
        "code_duck",
        _send_message,
        _code_duck_settings(rubric_path=str(rubric), review_turns="full"),
        _agent("review"),
        ai_client,
    )

    asyncio.run(workflow(_ctx("Debug variables")))

    review_calls = [call for call in ai_client.calls if call["agent"] == "review"]
    assert len(review_calls) == 2


def test_code_duck_stops_when_conversation_review_returns_no_question(monkeypatch, tmp_path):
    rubric = tmp_path / "variables.yaml"
    rubric.write_text(
        """
variables:
  assignment:
    - count + 1 does not update count unless the result is assigned back
full project: count + 1
""".strip()
    )

    user_messages = [
        {"content": "I would assign the result back and I know why that works."},
        {"content": "This should not be read."},
    ]
    sent_messages = []

    async def _send_message(_thread_id, message=None, file=None, view=None):
        sent_messages.append(message)
        return 1

    async def _wait_for_message(_timeout):
        return user_messages.pop(0)

    monkeypatch.setattr(code_duck_workflow, "wait_for_message", _wait_for_message)

    ai_client = _CompletingFakeAIClient()
    workflow = CodeDuckWorkflow(
        "code_duck",
        _send_message,
        _code_duck_settings(rubric_path=str(rubric), review_turns="full"),
        _agent("review"),
        ai_client,
    )

    asyncio.run(workflow(_ctx("Debug variables")))

    assert sent_messages == [
        "My code prints 0 instead of 1. What should I change?\n\n```python\ncount + 1\n```",
    ]
    assert user_messages == [{"content": "This should not be read."}]


def test_code_duck_passes_script_transcript_to_later_review_turns(monkeypatch, tmp_path):
    rubric = tmp_path / "variables.yaml"
    rubric.write_text(
        """
variables:
  assignment:
    - count + 1 does not update count unless the result is assigned back
full project: |-
  count = 0
  count + 1
  print(count)
""".strip()
    )

    user_messages = [
        {"content": "I would assign the result back."},
        {"content": "That works because assignment stores the new value."},
        None,
    ]

    async def _send_message(_thread_id, message=None, file=None, view=None):
        return 1

    async def _wait_for_message(_timeout):
        return user_messages.pop(0)

    monkeypatch.setattr(code_duck_workflow, "wait_for_message", _wait_for_message)

    ai_client = _FakeAIClient()
    workflow = CodeDuckWorkflow(
        "code_duck",
        _send_message,
        _code_duck_settings(rubric_path=str(rubric), review_turns="full"),
        _agent("review"),
        ai_client,
    )

    asyncio.run(workflow(_ctx("Debug variables")))

    review_contexts = [
        call["query"]
        for call in ai_client.calls
        if call["agent"] == "review"
    ]

    assert "TA: I would assign the result back." in review_contexts[0]
    assert "Student: Why does assigning the value back fix it?" not in review_contexts[0]
    assert "TA: That works because assignment stores the new value." not in review_contexts[0]

    assert "TA: I would assign the result back." in review_contexts[1]
    assert "Student: Why does assigning the value back fix it?" in review_contexts[1]
    assert "TA: That works because assignment stores the new value." in review_contexts[1]
    assert "count = 0\ncount + 1\nprint(count)" in review_contexts[1]


def test_yaml_example_generator_creates_code_duck_rubric_shape():
    yaml_example_gen = _load_yaml_example_gen()
    generated_yaml = """
variables:
  assignment stores values:
    - |-
      # score_report.py excerpt
      count = 0
      count + 1
      print(count)

      Traceback (most recent call last):
        File "/tmp/code-duck-score-report/score_report.py", line 3, in <module>
          print(total)
                ^^^^^
      NameError: name 'total' is not defined
full project: |-
  # score_report.py
  count = 0
  count + 1
  print(count)
""".strip()

    class _FakeResponses:
        def __init__(self):
            self.call = None

        def create(self, **kwargs):
            self.call = kwargs
            return SimpleNamespace(output_text=generated_yaml)

    class _FakeClient:
        def __init__(self):
            self.responses = _FakeResponses()

    source = {
        "variables": {
            "definition": ["a variable stores data values"],
            "using variables": ["variable names are case sensitive"],
        },
    }
    style = {
        "topic": {
            "principle 1": ["code example with bug"],
        },
    }
    client = _FakeClient()

    generated = yaml_example_gen.generate_code_duck_rubric(
        source,
        style,
        "Generate a rubric.",
        topic="variables",
        model="test-model",
        client=client,
    )

    assert list(generated) == ["variables", "full project"]
    assert list(generated["variables"]) == ["assignment stores values"]
    assert "count + 1" in generated["variables"]["assignment stores values"][0]
    assert "full project" in generated
    assert "score_report.py" in generated["full project"]
    assert client.responses.call["model"] == "test-model"
    assert "Source rubric:" in client.responses.call["input"]
    assert "Style example:" in client.responses.call["input"]
    assert yaml.safe_load(yaml.safe_dump(generated)) == generated


def test_yaml_example_generator_rejects_placeholder_output():
    yaml_example_gen = _load_yaml_example_gen()

    try:
        yaml_example_gen._validate_code_duck_rubric({
            "variables": {
                "assignment": ["# Replace this with a real example.\nTraceback (most recent call last):\nNameError:"],
            },
            "full project": "print('hello')",
        })
    except ValueError as error:
        assert "placeholder" in str(error)
    else:
        raise AssertionError("placeholder output should be rejected")


def test_yaml_example_generator_requires_full_project():
    yaml_example_gen = _load_yaml_example_gen()

    try:
        yaml_example_gen._validate_code_duck_rubric({
            "variables": {
                "assignment": ["count = 0\ncount + 1\nprint(count)\nTraceback (most recent call last):\nNameError:"],
            },
        })
    except ValueError as error:
        assert "full project" in str(error)
    else:
        raise AssertionError("missing full project should be rejected")


def test_yaml_example_generator_requires_traceback_text():
    yaml_example_gen = _load_yaml_example_gen()

    try:
        yaml_example_gen._validate_code_duck_rubric({
            "variables": {
                "assignment": ["count = 0\ncount + 1\nprint(count)"],
            },
            "full project": "count = 0\ncount + 1\nprint(count)",
        })
    except ValueError as error:
        assert "traceback" in str(error)
    else:
        raise AssertionError("missing traceback text should be rejected")


def test_cs110_variables_rubric_contains_complete_project_and_tracebacks():
    rubric_path = Path(__file__).resolve().parents[1] / "rubrics" / "CS110" / "code-duck" / "variables.yaml"
    rubric = yaml.safe_load(rubric_path.read_text())

    assert "full project" in rubric
    assert "grade_summary.py" in rubric["full project"]
    assert "print(Student_Name)" in rubric["full project"]

    examples = [
        example
        for topic, principles in rubric.items()
        if topic != "full project"
        for example_list in principles.values()
        for example in example_list
    ]

    assert len(examples) == 3
    assert all("Traceback (most recent call last):" in example for example in examples)
    assert all("Required concept:" in example for example in examples)
    assert all("Required fix:" in example for example in examples)
    assert any("NameError: name 'Student_Name' is not defined" in example for example in examples)
    assert any("TypeError: unsupported operand type(s) for +: 'int' and 'str'" in example for example in examples)
    assert any("NameError: name 'missing_assignments' is not defined" in example for example in examples)
    assert any("Change `print(Student_Name)` to `print(student_name)`." in example for example in examples)
    assert any('Change `extra_credit = "5"` to `extra_credit = 5`.' in example for example in examples)
    assert any("Move `missing_assignments = 7` before `print(missing_assignments)`." in example for example in examples)
