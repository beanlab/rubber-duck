import logging
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

quest_mod = types.ModuleType("quest")
quest_utils_mod = types.ModuleType("quest.utils")
quest_utils_mod.quest_logger = logging.getLogger("quest")


def _step(func=None, *_args, **_kwargs):
    if func is None:
        return lambda wrapped: wrapped
    return func


class _QueueStub:
    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc_val, _exc_tb):
        return None

    async def get(self):
        return None


def _queue(*_args, **_kwargs):
    return _QueueStub()


quest_mod.queue = _queue
quest_mod.step = _step
quest_mod.utils = quest_utils_mod
sys.modules.setdefault("quest", quest_mod)
sys.modules.setdefault("quest.utils", quest_utils_mod)
