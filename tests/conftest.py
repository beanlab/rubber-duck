import logging
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

boto3_stub = types.ModuleType("boto3")
boto3_stub.client = lambda *_args, **_kwargs: types.SimpleNamespace()
sys.modules.setdefault("boto3", boto3_stub)

botocore_stub = types.ModuleType("botocore")
botocore_exceptions_stub = types.ModuleType("botocore.exceptions")


class _ClientError(Exception):
    pass


botocore_exceptions_stub.ClientError = _ClientError
botocore_stub.exceptions = botocore_exceptions_stub
sys.modules.setdefault("botocore", botocore_stub)
sys.modules.setdefault("botocore.exceptions", botocore_exceptions_stub)

try:
    import discord  # noqa: F401
except ModuleNotFoundError:
    discord_stub = types.ModuleType("discord")

    class _Forbidden(Exception):
        pass

    class _Guild:
        pass

    class _Member:
        pass

    class _Utils:
        @staticmethod
        def get(iterable, **attrs):
            for item in iterable:
                if all(getattr(item, key, None) == value for key, value in attrs.items()):
                    return item
            return None

    discord_stub.Forbidden = _Forbidden
    discord_stub.Guild = _Guild
    discord_stub.Member = _Member
    discord_stub.utils = _Utils()
    sys.modules.setdefault("discord", discord_stub)

quest_mod = types.ModuleType("quest")
quest_utils_mod = types.ModuleType("quest.utils")
quest_utils_mod.quest_logger = logging.getLogger("quest")
quest_mod.step = lambda fn: fn


class _QueueStub:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def get(self):
        return None


quest_mod.queue = lambda *_args, **_kwargs: _QueueStub()
quest_mod.utils = quest_utils_mod
sys.modules.setdefault("quest", quest_mod)
sys.modules.setdefault("quest.utils", quest_utils_mod)
