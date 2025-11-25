from armory.tools import register_tool, sends_image
from utils.python_exec_container import PythonExecContainer


class PythonTools:
    def __init__(self, container: PythonExecContainer):
        self.container = container

    @register_tool
    async def run_code_return_text(self, code: str) -> dict[str, dict[str, str] | bytes]:
        return await self.container.run_code(code)

    @register_tool
    @sends_image
    async def run_code_return_image(self, code: str) -> dict[str, dict[str, str] | bytes]:
        return await self.container.run_code(code)
