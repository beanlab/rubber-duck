import asyncio

import pytest
from pydantic import BaseModel

from src.gen_ai.gen_ai import AIClient, Agent, GenAIException
from src.utils.config_types import DuckContext
from src.utils.protocols import ConversationComplete


class Result(BaseModel):
    answer: str


class FakeArmory:
    def __init__(self, tools=None):
        self.tools = tools or {}

    def get_tool_schema(self, name):
        return {"type": "function", "name": name}

    def get_specific_tool(self, name):
        return self.tools[name]


def ctx():
    return DuckContext(
        guild_id=1,
        parent_channel_id=2,
        author_id=3,
        author_mention="@user",
        content="hello",
        message_id=4,
        thread_id=5,
        timeout=60,
    )


def make_agent(*tools):
    return Agent(
        name="test-agent",
        prompt="Test prompt",
        model="test-model",
        tools=list(tools),
    )


def call(name, call_id):
    return {
        "type": "function_call",
        "name": name,
        "arguments": "{}",
        "call_id": call_id,
    }


def msg(text):
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text}],
    }


def make_client(turns, tools=None):
    client = AIClient.__new__(AIClient)
    client._armory = FakeArmory(tools)
    count = 0

    async def get_completion(*_args, **_kwargs):
        nonlocal count
        count += 1
        return turns[count - 1]

    async def record_message(*_args, **_kwargs):
        return None

    client._get_completion = get_completion
    client._record_message = record_message

    return client, lambda: count


def test_response_complete_runs_all_tools():
    # response_complete=True ends the turn only after all tool calls in that turn run.
    calls = []

    def first(_ctx):
        calls.append("first")
        return "first", False

    def finish(_ctx):
        calls.append("finish")
        return "complete", True

    def last(_ctx):
        calls.append("last")
        return "last", False

    client, count = make_client(
        [[call("first", "call-1"), call("finish", "call-2"), call("last", "call-3")]],
        {"first": first, "finish": finish, "last": last},
    )

    response, history, complete = asyncio.run(
        client._run_agent(ctx(), make_agent("first", "finish", "last"), [])
    )

    assert calls == ["first", "finish", "last"]
    assert count() == 1
    assert response is None
    assert complete is False
    assert [item["call_id"] for item in history if item["type"] == "function_call_output"] == [
        "call-1",
        "call-2",
        "call-3",
    ]


def test_conversation_complete_runs_all_tools():
    # ConversationComplete ends the conversation only after all tool calls in that turn run.
    calls = []

    def first(_ctx):
        calls.append("first")
        return "first", False

    def finish(_ctx):
        calls.append("finish")
        raise ConversationComplete()

    def last(_ctx):
        calls.append("last")
        return "last", False

    client, count = make_client(
        [[call("first", "call-1"), call("finish", "call-2"), call("last", "call-3")]],
        {"first": first, "finish": finish, "last": last},
    )

    response, history, complete = asyncio.run(
        client._run_agent(ctx(), make_agent("first", "finish", "last"), [])
    )

    assert calls == ["first", "finish", "last"]
    assert count() == 1
    assert response is None
    assert complete is True
    assert [item["call_id"] for item in history if item["type"] == "function_call_output"] == [
        "call-1",
        "call-2",
        "call-3",
    ]


def test_message_ends_turn():
    # a message output is treated as the only output for the turn and ends the turn.
    client, count = make_client([[msg("final response")]])

    response, _history, complete = asyncio.run(
        client._run_agent(ctx(), make_agent(), [])
    )

    assert count() == 1
    assert response == "final response"
    assert complete is False


def test_output_format_is_validated():
    # supplied output_format validates message output and rejects invalid structured output.
    client, _ = make_client([[msg('{"answer": "validated"}')]])

    response, _history, complete = asyncio.run(
        client._run_agent(ctx(), make_agent(), [], output_format=Result)
    )

    assert response == Result(answer="validated")
    assert complete is False

    client, _ = make_client([[msg('{"wrong_field": "invalid"}')]])

    with pytest.raises(GenAIException) as error:
        asyncio.run(client._run_agent(ctx(), make_agent(), [], output_format=Result))

    assert error.value.web_mention == (
        "test-agent returned invalid structured output, expected Result"
    )
