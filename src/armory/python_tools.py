from ..utils.python_exec_container import PythonExecContainer
from ..utils.data_store import DataStore
from ..utils.config_types import DuckContext, FileData
from ..utils.logger import duck_logger
from ..utils.protocols import SendMessage
from .tools import register_tool


class PythonTools:
    def __init__(self, container: PythonExecContainer, data_store: DataStore, send_message: SendMessage):
        self._container = container
        self._data_store = data_store
        self._send_message = send_message

    # TODO: change it so images are sent as images, csv are sent as table using our own function "send_table" what converts it to a markdown table
    # TODO: markdown tables can be displayed in discord using md code fence

    def send_table(*args):
        """sends a csv file formatted as a md table"""
        pass

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
        stdout = results.get('stdout')
        stderr = results.get('stderr')
        files = results.get('files')

        # TODO: also send std out directly to user

        # send the images directly to avoid adding them to the context
        for filename, file in files.items():
            await self._send_message(ctx.thread_id, file=FileData(filename=filename, bytes=file['bytes']))

        if files.items():
            duck_logger.info("=== PYTHON TOOLS === File descriptions:")
        for filename, file in files.items():
            duck_logger.info(f" {filename}: {file['description']}")

        # return the stdout, stderr, and image descriptions to the agent to add to context
        # TODO - prompt: do not send any of this data; stdout will be automatically sent to user
        return {
            'stdout': stdout,
            'stderr': stderr,
            'files': {filename: file['description'] for filename, file in files.items()},
            'code': code
        }

