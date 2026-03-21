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
quest_mod.utils = quest_utils_mod
sys.modules.setdefault("quest", quest_mod)
sys.modules.setdefault("quest.utils", quest_utils_mod)
