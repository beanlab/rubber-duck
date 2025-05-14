import inspect
from pathlib import Path
from agents import function_tool
from .tool_registry import TOOLS_REGISTRY

# Resolve the path to the src/TOOLS.md file
README_PATH = Path(__file__).resolve().parent.parent / "TOOLS.md"

def register_tool(func):
    wrapped = function_tool(func)
    TOOLS_REGISTRY[func.__name__] = wrapped

    doc = inspect.getdoc(func) or "No description provided."
    sig = inspect.signature(func)

    # Append to the file
    with open(README_PATH, "a") as f:
        f.write(f"### `{func.__name__}`\n")
        f.write(f"**Signature**: `{func.__name__}{sig}`\n\n")
        f.write(f"{doc}\n\n")

    return wrapped

