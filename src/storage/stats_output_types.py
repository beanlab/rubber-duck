from dataclasses import dataclass

from ..utils.protocols import ToolCache
from ..utils.python_exec_container import DeferredExecutionResult, PythonExecContainer


@dataclass
class TextOutput:
    text: str


@dataclass
class FileOutput:
    filename: str
    data: bytes


@dataclass
class ExecutionOutput:
    container: PythonExecContainer
    result: DeferredExecutionResult
    stdout: str
    tool_cache: ToolCache | None
    cache_key: str | None
