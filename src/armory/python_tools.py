import io
import pandas as pd

from ..utils.protocols import ToolCache, CacheKeyBuilder
from ..utils.config_types import DuckContext
from ..utils.logger import duck_logger
from ..utils.protocols import SendMessage, ConcludesResponse
from ..utils.python_exec_container import PythonExecContainer, is_image, is_table, FileResult


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
    return stdout


async def send_table(
        send_message: SendMessage,
        channel_id: int,
        table: pd.DataFrame,
        max_rows: int = 100,
) -> list[str]:
    table = table.head(max_rows)
    col_chunk = _determine_col_chunk(table)
    table_chunks = []

    for i in range(0, table.shape[1], col_chunk):
        md_table = table.iloc[:, i:i + col_chunk].to_markdown()
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
            duck_logger.debug(f"\nCache key:\n{key}")

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
        stderr = results.get('stderr').strip()
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
