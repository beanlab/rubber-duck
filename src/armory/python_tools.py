from ..utils.python_exec_container import PythonExecContainer
from ..utils.data_store import DataStore
from ..utils.config_types import DuckContext, FileData
from ..utils.logger import duck_logger
from ..utils.protocols import SendMessage
from .tools import register_tool


class PythonTools:
    def __init__(self, image: str, data_store: DataStore, send_message: SendMessage):
        self.image = image
        self.data_store = data_store
        self._send_message = send_message


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
        with PythonExecContainer(self.image, self.data_store) as container:
            results = await container.run_code(code)
        stdout = results.get('stdout')
        stderr = results.get('stderr')
        files = results.get('files')

        # send the images directly to avoid adding them to the context
        for filename, file in files.items():
            await self._send_message(ctx.thread_id, file=FileData(filename=filename, bytes=file['bytes']))

        duck_logger.info("=== PYTHON TOOLS ===\nFile descriptions:")
        for filename, file in files.items():
            duck_logger.info(f" {filename}: {file['description']}")

        # return the stdout, stderr, and image descriptions to the agent to add to context
        return {
            'stdout': stdout,
            'stderr': stderr,
            'files': {filename: file['description'] for filename, file in files.items()},
            'code': code
        }

