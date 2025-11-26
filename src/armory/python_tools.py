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
                "filename": {
                    "description": str,
                }
            }
        }
        """
        with PythonExecContainer(self.image, self.data_store) as container:
            results = await container.run_code(code)

        if results.get('stdout'):
            await self._send_message(ctx.thread_id, results['stdout'])

        if results.get('stderr'):
            duck_logger.warning(results['stderr'])
            await self._send_message(ctx.thread_id, f'```\n{results['stderr']}\n```')

        for name, file in results['files'].items():
            await self._send_message(ctx.thread_id, file=FileData(filename=name, bytes=file['bytes']))

        return {
            'stdout': results['stdout'],
            'stderr': results['stderr'],
            'files': {filename: file['description'] for filename, file in results['files'].items()},
        }

