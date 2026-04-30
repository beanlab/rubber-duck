import asyncio
import os
from types import SimpleNamespace

import pytest

from src.gen_ai.gen_ai import AIClient
from src.utils.config_types import DuckContext
from src.utils.protocols import ConversationComplete
from src.workflows.registration import Registration


class DiscordServerError(Exception):
    def __init__(self, status=503):
        self.status = status
        super().__init__("503 Service Unavailable")


class _FakeOutput:
    def model_dump(self, exclude_none=True):
        return {"type": "message", "content": "ok"}


class _FakeResponse:
    def __init__(self):
        self.output = [_FakeOutput()]
        self.usage = None


class _Typing:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


def _ctx(thread_id=999) -> DuckContext:
    return DuckContext(
        guild_id=1,
        parent_channel_id=2,
        author_id=3,
        author_mention="@user",
        content="hello",
        message_id=4,
        thread_id=thread_id,
        timeout=60,
    )


def test_gen_ai_retries_discord_server_error():
    os.environ.setdefault("OPENAI_API_KEY", "test-key")

    sent_messages = []
    attempts = {"count": 0}

    async def _record_message(*_args, **_kwargs):
        return None

    async def _record_usage(*_args, **_kwargs):
        return None

    async def _send_message(_channel_id, message=None, file=None, view=None):
        if message is not None:
            sent_messages.append(message)
        return 1

    def _typing(_thread_id):
        return _Typing()

    client = AIClient(
        armory=None,
        typing=_typing,
        record_message=_record_message,
        record_usage=_record_usage,
        retry_protocol={"max_retries": 2, "delay": 0, "backoff": 1},
        send_message=_send_message,
    )

    async def _create(**_params):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise DiscordServerError()
        return _FakeResponse()

    client._client = SimpleNamespace(
        responses=SimpleNamespace(create=_create)
    )

    result = asyncio.run(
        client._get_completion(
            _ctx(),
            prompt="prompt",
            local_history=[],
            context=[],
            model="gpt-test",
            tools=[],
            tool_settings="auto",
            output_format=None,
        )
    )

    assert attempts["count"] == 2
    assert result == [{"type": "message", "content": "ok"}]
    assert sent_messages == ["I hit a temporary connection issue with an upstream server. Retrying in 0 seconds..."]


def test_registration_retries_discord_server_error_during_fetch_member():
    sent_messages = []
    fetch_attempts = {"count": 0}

    async def _send_message(_channel_id, message=None, file=None, view=None):
        if message is not None:
            sent_messages.append(message)
        return 1

    async def _fetch_guild(_guild_id):
        return guild

    class _EmailSender:
        def send_email(self, *_args, **_kwargs):
            return "123456"

    class _Role:
        def __init__(self, role_id, name):
            self.id = role_id
            self.name = name

    class _Member:
        def __init__(self):
            self.roles = []

        async def add_roles(self, *roles, reason=None):
            self.roles.extend(roles)

    class _Guild:
        def __init__(self):
            self.name = "Test Guild"
            self.roles = [_Role(10, "Authenticated")]

        async def fetch_member(self, _user_id):
            fetch_attempts["count"] += 1
            if fetch_attempts["count"] == 1:
                raise DiscordServerError()
            return member

    member = _Member()
    guild = _Guild()

    registration = Registration(
        _send_message,
        get_channel=lambda *_args, **_kwargs: None,
        fetch_guild=_fetch_guild,
        email_sender=_EmailSender(),
        settings={
            "cache_timeout": 60,
            "authenticated_user_role_name": "Authenticated",
            "email_domain": "example.edu",
            "roles": None,
            "registration_bot": "registration-bot",
            "ta_channel_id": 123,
        },
        retry_protocol={"max_retries": 2, "delay": 0, "backoff": 1},
    )

    result = asyncio.run(registration.assign_roles(_ctx()))

    assert fetch_attempts["count"] == 2
    assert result == "Authenticated"
    assert sent_messages == ["Successfully gave you the following roles: Authenticated"]


def test_registration_exhausted_discord_retry_notifies_user_and_ta(caplog):
    sent_messages = []
    fetch_attempts = {"count": 0}

    async def _send_message(channel_id, message=None, file=None, view=None):
        if message is not None:
            sent_messages.append((channel_id, message))
        return 1

    async def _fetch_guild(_guild_id):
        return guild

    class _EmailSender:
        def send_email(self, *_args, **_kwargs):
            return "123456"

    class _Role:
        def __init__(self, role_id, name):
            self.id = role_id
            self.name = name

    class _Guild:
        def __init__(self):
            self.name = "Test Guild"
            self.roles = [_Role(10, "Authenticated")]

        async def fetch_member(self, _user_id):
            fetch_attempts["count"] += 1
            raise DiscordServerError()

    guild = _Guild()
    ctx = _ctx(thread_id=456)

    registration = Registration(
        _send_message,
        get_channel=lambda *_args, **_kwargs: None,
        fetch_guild=_fetch_guild,
        email_sender=_EmailSender(),
        settings={
            "cache_timeout": 60,
            "authenticated_user_role_name": "Authenticated",
            "email_domain": "example.edu",
            "roles": None,
            "registration_bot": "registration-bot",
            "ta_channel_id": 123,
        },
        retry_protocol={"max_retries": 2, "delay": 0, "backoff": 1},
    )

    with caplog.at_level("WARNING"):
        with pytest.raises(ConversationComplete):
            asyncio.run(registration.assign_roles(ctx))

    assert fetch_attempts["count"] == 3
    assert sent_messages == [
        (
            456,
            "I'm having temporary connection issues with Discord right now. "
            "Please try again later. I've notified a TA."
        ),
        (
            123,
            "Registration hit repeated Discord connection issues "
            "during `fetch_member` in thread <#456> for user <@3>."
        ),
    ]
    assert "Discord connection issue persisted after retries during registration" in caplog.text
