import logging
import sys
import types
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# quest shims
quest_mod = types.ModuleType("quest")
quest_utils_mod = types.ModuleType("quest.utils")
quest_extras_mod = types.ModuleType("quest.extras")
quest_extras_sql_mod = types.ModuleType("quest.extras.sql")
quest_manager_mod = types.ModuleType("quest.manager")
quest_persistence_mod = types.ModuleType("quest.persistence")
quest_utils_mod.quest_logger = logging.getLogger("quest")


@contextmanager
def _these(value):
    yield value


def _passthrough_decorator(*args, **_kwargs):
    if args and callable(args[0]) and len(args) == 1:
        return args[0]

    def _wrap(func):
        return func

    return _wrap


class _WorkflowManager:
    pass


class _NoopSerializer:
    def __call__(self, value):
        return value


class _Placeholder:
    pass


def _none(*_args, **_kwargs):
    return None


class _SqlBlobStorage:
    def __init__(self, *_args, **_kwargs):
        pass


quest_mod.these = _these
quest_mod.step = _passthrough_decorator
quest_mod.task = _passthrough_decorator
quest_mod.alias = _passthrough_decorator
quest_mod.wrap_steps = _passthrough_decorator
quest_mod.queue = _passthrough_decorator
quest_mod.WorkflowManager = _WorkflowManager
quest_mod.BlobStorage = _Placeholder
quest_mod.StepSerializer = _Placeholder
quest_mod.PersistentHistory = _Placeholder
quest_mod.NoopSerializer = _NoopSerializer
quest_mod.History = _Placeholder
quest_mod.WorkflowFactory = _Placeholder
quest_extras_sql_mod.SqlBlobStorage = _SqlBlobStorage
quest_extras_mod.sql = quest_extras_sql_mod
quest_manager_mod.find_workflow_manager = _none
quest_persistence_mod.BlobStorage = _Placeholder
quest_mod.utils = quest_utils_mod
sys.modules.setdefault("quest", quest_mod)
sys.modules.setdefault("quest.utils", quest_utils_mod)
sys.modules.setdefault("quest.extras", quest_extras_mod)
sys.modules.setdefault("quest.extras.sql", quest_extras_sql_mod)
sys.modules.setdefault("quest.manager", quest_manager_mod)
sys.modules.setdefault("quest.persistence", quest_persistence_mod)

# third-party stubs
boto3_mod = types.ModuleType("boto3")


class _DummyBotoClient:
    pass


def _dummy_boto3_client(*_args, **_kwargs):
    return _DummyBotoClient()


boto3_mod.client = _dummy_boto3_client
sys.modules.setdefault("boto3", boto3_mod)
sys.modules.setdefault("markdowndata", types.ModuleType("markdowndata"))
jsonpath_ng_mod = types.ModuleType("jsonpath_ng")
jsonpath_ng_mod.parse = _none
sys.modules.setdefault("jsonpath_ng", jsonpath_ng_mod)

# src adapter stubs
discord_bot_mod = types.ModuleType("src.bot.discord_bot")


class _DiscordBot:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


discord_bot_mod.DiscordBot = _DiscordBot
sys.modules.setdefault("src.bot.discord_bot", discord_bot_mod)
