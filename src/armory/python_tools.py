import io
import json
import pandas as pd

from .tool_cache import build_cache_key, check_if_cached, send_from_cache, cache_file, cache_msg, cache_table
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


class PythonTools:
    def __init__(self, container: PythonExecContainer, send_message: SendMessage):
        self._container = container
        self._send_message = send_message

    async def run_code(self, ctx: DuckContext, code: str, last_3_messages: str) -> dict[str, dict[str, str] | bytes]:
        """
        Takes a string of python code as input and returns the resulting stdout/stderr in the following format:
        `last_3_messages` must be a JSON array string with exactly 3 objects, each of the form
        {"role":"user|assistant","content":"..."}, ordered oldest->newest.
        :param ctx: DuckContext
        :param code:
        :param last_3_messages:
        :return:
            'code': str,
            'stdout': str,
            'stderr': str,
            'files': {
                filename: description
            }
        }
        """
        cache_key = build_cache_key(last_3_messages, code)
        duck_logger.debug(f"\nCache key:\n{json.dumps(cache_key)}")

        if check_if_cached(cache_key):
            duck_logger.debug(f" Cache HIT ".center(20,'-'))
            output = send_from_cache(cache_key)
            return output

        duck_logger.debug(f" Cache MISS ".center(19, '-'))
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
                cache_file(cache_key, filename, file)
                await self._send_message(ctx.thread_id, file=file)
            elif is_table(filename):
                table = pd.read_csv(io.StringIO(file['bytes'].decode()))
                table = table.head(100)
                col_chunk = _determine_col_chunk(table)
                table_chunks = []
                for i in range(0, table.shape[1], col_chunk):
                    md_table = table.iloc[:, i:i + col_chunk].to_markdown()
                    table_chunk = f"```\n{md_table}\n```"
                    table_chunks.append(table_chunk)
                    await self._send_message(ctx.thread_id, table_chunk)
                cache_table(cache_key, table_chunks)

        # send cleaned stdout directly
        if stdout:
            msg = _clean_stdout(stdout, files)
            cache_msg(cache_key, msg)
            await self._send_message(ctx.thread_id, msg)

        output = {
            'stdout': stdout,
            'stderr': stderr,
            'files': {filename: file['description'] for filename, file in files.items()},
        }

        if results['exit_code'] == 0:
            output = ConcludesResponse(output)

        return output
