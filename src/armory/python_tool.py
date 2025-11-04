import subprocess
import tempfile
from functools import partial
from typing import Optional
from .tools import register_tool, sends_image


class PythonTool:
    """
    Executes Python code in a subprocess sandbox.
    Agents can call this tool to run code with access to installed libraries.
    """

    def __init__(self, allowed_imports: Optional[list[str]] = None, timeout: int = 10,
                 python_executable: str = "/Users/tylerreese/opt/anaconda3/envs/skill-bot/bin/python"):
        # Set of allowed modules (None = no restriction)
        self.allowed_imports = set(allowed_imports) if allowed_imports else None
        self.timeout = timeout
        self.python_executable = python_executable  # can point to local miniconda python

    def _is_safe_code(self, code: str) -> bool:
        if not self.allowed_imports:
            return True
        for line in code.splitlines():
            line = line.strip()
            if line.startswith("import ") or line.startswith("from "):
                module = line.split()[1].split(".")[0]
                if module not in self.allowed_imports:
                    return False
        return True

    @register_tool
    async def run_python_code(self, code: str) -> str:
        """
        Execute Python code in a temporary file.
        Returns stdout or stderr from the execution.
        """
        if not self._is_safe_code(code):
            return "Error: code imports disallowed modules."

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(code)
            tmp.flush()
            tmp_name = tmp.name

        try:
            result = subprocess.run(
                [self.python_executable, tmp_name],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            output = result.stdout.strip() or result.stderr.strip()
        except subprocess.TimeoutExpired:
            output = "Execution timed out."
        finally:
            tmp.close()

        return output
