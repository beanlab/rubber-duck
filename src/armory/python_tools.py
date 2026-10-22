"""Compatibility exports for statistical tools moved to :mod:`src.armory.tools`."""

from typing import Protocol, runtime_checkable

from ..duck_protocols import DuckContext
from ..utils.protocols import ConcludesResponse, SendMessage
from ..utils.python_exec_container import PythonExecContainer

from .tools import (
    DatasetTools as RefactoredDatasetTools,
    PythonTools,
    _clean_stdout,
    _determine_col_chunk,
    _estimate_column_widths,
    _format_rounded_decimal,
    _format_table_values,
    _remove_scientific_notation,
    send_table,
)


@runtime_checkable
class TextOutput(Protocol):
    def capture_text(self, message: str) -> None: ...


class DatasetTools(RefactoredDatasetTools):
    """Expose the refactored tools while supporting legacy Discord delivery."""

    def __init__(
            self,
            containers: list[PythonExecContainer],
            send_message: SendMessage | None = None,
    ) -> None:
        super().__init__(containers)
        self._send_message = send_message

    async def send_datasets_to_user(
            self,
            output: object,
    ) -> str | ConcludesResponse:
        if isinstance(output, TextOutput):
            return await super().send_datasets_to_user(output)

        if not isinstance(output, DuckContext):
            raise TypeError("Expected a text output collector or DuckContext")
        if self._send_message is None:
            raise RuntimeError("Legacy dataset delivery requires send_message")

        dataset_names = self._get_sorted_dataset_names()
        message = (
            "\n".join(
                ["Available datasets:"] + [f"- {name}" for name in dataset_names]
            )
            if dataset_names
            else "No datasets are currently available."
        )
        await self._send_message(output.thread_id, message)
        result = (
            f"Sent {len(dataset_names)} dataset names."
            if dataset_names
            else message
        )
        return ConcludesResponse(result)


__all__ = ["DatasetTools", "PythonTools", "send_table"]
