import io
import os.path

import pandas as pd

from .tools import register_tool
from ..utils.config_types import DuckContext, FileData
from ..utils.data_store import DataStore
from ..utils.logger import duck_logger
from ..utils.protocols import SendMessage, ConcludesResponse
from ..utils.python_exec_container import PythonExecContainer


def is_image(filename):
    _, ext = os.path.splitext(filename)
    return ext[1:] in ['png', 'svg', 'jpg', 'jpeg', 'tiff']


def is_table(filename):
    _, ext = os.path.splitext(filename)
    return ext[1:] in ['csv']


def is_text(filename):
    _, ext = os.path.splitext(filename)
    return ext[1:] in ['txt']


class PythonTools:
    def __init__(self, container: PythonExecContainer, data_store: DataStore, send_message: SendMessage):
        self._container = container
        self._data_store = data_store
        self._send_message = send_message

    async def _send_table(self, thread_id, filecontent):
        """sends a csv file formatted as a md table"""
        table = pd.read_csv(io.StringIO(filecontent))
        for i in range(0, table.shape[1], 3):
            # for each chunk of 3 columns, send those columns
            md_table = table.iloc[:, i:i + 3].to_markdown()
            msg = f'```md\n{md_table}\n```'
            await self._send_message(thread_id, msg)

    @register_tool
    async def run_code(self, ctx: DuckContext, code: str) -> dict[str, dict[str, str] | bytes]:
        """
        Takes a string of python code as input and returns the resulting stdout/stderr in the following format:
        :param code:
        :return:
            'stdout': str,
            'stderr': str,
            'files': {
                "filename": str (description)
            }
        }
        """
        results = await self._container.run_code(code)
        stdout = results.get('stdout').strip()
        stderr = results.get('stderr').strip()

        files = results.get('files')
        if files:
            duck_logger.debug(" files ".center(20, '-'))

        for filename, file in files.items():
            duck_logger.debug(f" {filename}: {file['description']}")

        # send files directly to avoid adding them to the context
        for filename, file in files.items():
            if is_image(filename):
                await self._send_message(ctx.thread_id, file=FileData(filename=filename, bytes=file['bytes']))

            elif is_table(filename):
                await self._send_table(ctx.thread_id, file['bytes'].decode())

            elif is_text(filename):
                await self._send_message(ctx.thread_id, message=file['bytes'].decode())

        # return the stdout, stderr, and image descriptions to the agent to add to context
        if stdout:
            await self._send_message(ctx.thread_id, stdout)

        output = {
            'stdout': stdout,
            'stderr': stderr,
            'files': {filename: file['description'] for filename, file in files.items()},
            'code': code
        }

        if results['exit_code'] == 0:
            # If there was no error, conclude the result
            # This keeps the LLM from running again after this tool
            # But if there was an error, the LLM gets to run again before the user has a chance to provide input
            # This lets the LLM correct the errors in the code and try again
            output = ConcludesResponse(output)

        return output
