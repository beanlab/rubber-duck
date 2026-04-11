import io
import re
from pathlib import Path
from decimal import Decimal, InvalidOperation
import pandas as pd
from pandas.api.types import is_numeric_dtype

from ..utils.protocols import ToolCache, CacheKeyBuilder
from ..utils.config_types import DuckContext
from ..utils.logger import duck_logger
from ..utils.protocols import SendMessage, ConcludesResponse
from ..utils.python_exec_container import PythonExecContainer, is_image, is_table, FileResult


_SCI_NOTATION_PATTERN = re.compile(
    r"(?<![\w.])([+-]?(?:\d+(?:\.\d*)?|\.\d+)[eE][+-]?\d+)(?![\w.])"
)


def _to_plain_decimal(token: str) -> str:
    try:
        value = Decimal(token)
    except InvalidOperation:
        return token

    if not value.is_finite():
        return token

    formatted = format(value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    if formatted in {"", "-0", "+0"}:
        return "0"
    return formatted


def _remove_scientific_notation(text: str) -> str:
    return _SCI_NOTATION_PATTERN.sub(lambda m: _to_plain_decimal(m.group(1)), text)


def _format_rounded_decimal(value: float, places: int = 4) -> str:
    formatted = format(float(value), f".{places}f")
    formatted = formatted.rstrip("0").rstrip(".")
    return formatted if formatted else "0"


def _format_table_values(table: pd.DataFrame) -> pd.DataFrame:
    formatted_table = table.copy()
    for col in formatted_table.columns:
        if not is_numeric_dtype(formatted_table[col]):
            continue
        formatted_table[col] = formatted_table[col].map(
            lambda value: _format_rounded_decimal(value, 4) if pd.notna(value) else ""
        )
    return formatted_table


def _estimate_column_widths(df, sample_rows=20):
    widths = {}
    for col in df.columns:
        header_width = len(str(col))
        sample_width = (
            df[col]
            .astype(str)
            .head(sample_rows)
            .map(len)
            .max()
        )
        widths[col] = max(header_width, sample_width)
    return widths


def _determine_col_chunk(df, max_table_width=90):
    col_widths = _estimate_column_widths(df)

    current_width = 0
    current_chunk = 0

    for width in col_widths.values():
        # +3 accounts for markdown separators and padding
        projected = current_width + width + 4

        if projected > max_table_width and current_chunk > 0:
            break

        current_width = projected
        current_chunk += 1

    # ensure it's between 2 and 6
    return max(2, min(current_chunk, 6))


def _clean_stdout(stdout: str, files: dict[str, FileResult]) -> str:
    file_names = set(files.keys())

    filtered_lines = []
    for line in stdout.splitlines():
        stripped = line.strip()

        # drop filename echoes
        if stripped in file_names:
            continue

        # drop lines mentioning filenames
        if any(name in stripped for name in file_names):
            continue

        filtered_lines.append(line)

    stdout = "\n".join(filtered_lines).strip()
    return _remove_scientific_notation(stdout)


async def send_table(
        send_message: SendMessage,
        channel_id: int,
        table: pd.DataFrame,
        max_rows: int = 100,
) -> list[str]:
    table = _format_table_values(table.head(max_rows))
    col_chunk = _determine_col_chunk(table)
    table_chunks = []

    for i in range(0, table.shape[1], col_chunk):
        md_table = table.iloc[:, i:i + col_chunk].to_markdown(disable_numparse=True)
        table_chunk = f"```\n{md_table}\n```"
        table_chunks.append(table_chunk)
        await send_message(channel_id, table_chunk)

    return table_chunks


class PythonTools:
    def __init__(
            self,
            container: PythonExecContainer,
            send_message: SendMessage,
            tool_cache: ToolCache | None,
            cache_key_builder: CacheKeyBuilder | None
    ):
        self._container = container
        self._send_message = send_message
        self._tool_cache = tool_cache
        self._cache_key_builder = cache_key_builder

    async def run_code(self, ctx: DuckContext, code: str, user_intent: str) -> dict[str, str | dict[str, str]]:
        """
        Takes python code and the user's intent, executes it, and returns stdout/stderr/files.

        :param ctx: DuckContext
        :param code: Python code to execute
        :param user_intent: Short description of what the user is trying to do.
        :return:
            'code': str,
            'stdout': str,
            'stderr': str,
            'files': {
                filename: description
            }
        """
        key = None
        if self._tool_cache and self._cache_key_builder:
            cache_key = self._cache_key_builder.build_cache_key(user_intent, code)
            key = self._tool_cache.get_key(cache_key)
            duck_logger.debug(f"Cache key: {key}")

            if self._tool_cache.check_if_cached(key):
                duck_logger.debug(f" Cache HIT ".center(20, '-'))
                output = await self._tool_cache.send_from_cache(
                    key,
                    self._send_message,
                    ctx.thread_id
                )
                return ConcludesResponse(output)

            duck_logger.debug(f" Cache MISS ".center(19, '-'))
        else:
            duck_logger.debug(f" Cache DISABLED ".center(21, '-'))
        results = await self._container.run_code(code)

        stdout = results.get('stdout').strip()
        stderr = _remove_scientific_notation(results.get('stderr').strip())
        files = results.get('files', {})

        # log created files
        if files:
            duck_logger.debug(" files ".center(20, '-'))
            for filename, file in files.items():
                duck_logger.debug(f" {filename}: {file['description']}")

        # send files directly
        for filename, file in files.items():
            if is_image(filename):
                if self._tool_cache and key is not None:
                    self._tool_cache.cache_file(key, filename, file)
                await self._send_message(
                    ctx.thread_id,
                    file={
                        "filename": filename,
                        "bytes": file["bytes"],
                    }
                )
            elif is_table(filename):
                table = pd.read_csv(io.StringIO(file['bytes'].decode()))
                table_chunks = await send_table(
                    self._send_message,
                    ctx.thread_id,
                    table,
                )
                if self._tool_cache and key is not None:
                    self._tool_cache.cache_table(key, filename, table_chunks, file.get("description", ""))

        # send cleaned stdout directly
        stdout = _clean_stdout(stdout, files)
        if stdout:
            if self._tool_cache and key is not None:
                self._tool_cache.cache_msg(key, stdout)
            await self._send_message(ctx.thread_id, stdout)

        output = {
            'stdout': stdout,
            'stderr': stderr,
            'files': {filename: file['description'] for filename, file in files.items()},
        }

        if results['exit_code'] == 0:
            output = ConcludesResponse(output)

        return output


class DatasetTools:
    def __init__(self, containers: list[PythonExecContainer]):
        self._containers = containers

    def get_resource_metadata(self) -> str:
        lines = ["\n### Available Datasets:"]
        for container in self._containers:
            for dataset in container.get_dataset_inventory():
                dataset_name = dataset.get("dataset_name", dataset["filename"])
                lines.append(f"Name: {dataset_name}")
                lines.append(f"\nFilepath: {dataset['path']}")
        return "\n".join(lines)

    async def describe_dataset(self, ctx: DuckContext, dataset_filename: str) -> str:
        """
        Returns the full dataset description for a dataset filename.
        Accepts either the exact staged filename or any path ending in that filename.
        Do not use Dataset Name values.
        """
        duck_logger.debug(f"describe_dataset called with dataset_name={dataset_filename!r}")
        normalized_filename = Path(dataset_filename).name
        for container in self._containers:
            description = container.describe_dataset(normalized_filename)
            if description:
                duck_logger.debug(f"\n{description}")
                return description

        available = sorted({
            filename
            for container in self._containers
            for filename in container.get_dataset_filenames()
        })
        if not available:
            duck_logger.debug(f"describe_dataset no datasets available for dataset_name={dataset_filename!r}")
            return "No datasets are currently available."

        message = (
            f"Dataset '{dataset_filename}' not found. "
            f"Available dataset filenames: {', '.join(available)}"
        )
        duck_logger.debug(f"describe_dataset no match for dataset_name={dataset_filename!r}; {message}")
        return message
