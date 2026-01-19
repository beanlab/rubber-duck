import io
import pandas as pd

from ..utils.config_types import DuckContext, FileData
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
        lower = stripped.lower()

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

    async def _send_table(self, thread_id, filecontent):
        """sends a csv file formatted as a md table in chunks of 3-6 columns"""
        table = pd.read_csv(io.StringIO(filecontent))
        # limit to 100 rows
        table = table.head(100)

        col_chunk = _determine_col_chunk(table)

        for i in range(0, table.shape[1], col_chunk):
            # for each chunk of 5 columns, send those columns
            md_table = table.iloc[:, i:i + col_chunk].to_markdown()
            msg = f'```\n{md_table}\n```'
            await self._send_message(thread_id, msg)

    async def run_code(self, ctx: DuckContext, code: str) -> dict[str, dict[str, str] | bytes]:
        """
        Takes a string of python code as input and returns the resulting stdout/stderr in the following format:
        :param code:
        :return:
            'code': str,
            'stdout': str,
            'stderr': str,
            'files': {
                filename: description
            }
        }
        """
        results = await self._container.run_code(code)
        stdout = results.get('stdout').strip()
        stderr = results.get('stderr').strip()

        files = results.get('files')
        if files:
            duck_logger.debug(" files ".center(20, '-'))

        # clean stdout line by line, removing lines containing filenames and specified key words
        if stdout:
            stdout = _clean_stdout(stdout, files)

        # log created files
        for filename, file in files.items():
            duck_logger.debug(f" {filename}: {file['description']}")

        # send files directly
        for filename, file in files.items():
            if is_image(filename):
                await self._send_message(
                    ctx.thread_id,
                    file=FileData(filename=filename, bytes=file['bytes'])
                )
            elif is_table(filename):
                await self._send_table(ctx.thread_id, file['bytes'].decode())

        # send cleaned stdout directly
        if stdout:
            await self._send_message(ctx.thread_id, stdout)

        output = {
            'stdout': stdout,
            'stderr': stderr,
            'files': {filename: file['description'] for filename, file in files.items()}
        }

        if results['exit_code'] == 0:
            output = ConcludesResponse(output)

        return output