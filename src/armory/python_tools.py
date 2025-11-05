import subprocess
import tempfile
import os
import re
from typing import Optional
from .tools import register_tool, sends_image
from ..utils.logger import duck_logger


class PythonTool:
    """
    Executes Python code in a subprocess sandbox.
    Agents can call this tool to run code with access to installed libraries
    and optionally return matplotlib/seaborn plots as images.
    """

    def __init__(
            self,
            allowed_imports: Optional[list[str]] = None,
            timeout: int = 10,
            python_executable: str = "/opt/anaconda3/envs/skill-bot/bin/python"
    ):
        self.allowed_imports = set(allowed_imports) if allowed_imports else None
        self.timeout = timeout
        self.python_executable = python_executable

    def _is_safe_code(self, code: str) -> bool:
        if not self.allowed_imports:
            return True

        # Remove comments and strings to avoid false matches
        code_no_strings = re.sub(r'(\'\'\'[\s\S]*?\'\'\'|\"\"\"[\s\S]*?\"\"\"|\'[^\']*\'|\"[^\"]*\")', '', code)
        code_no_comments = re.sub(r'#.*', '', code_no_strings)

        for match in re.finditer(r'^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)', code_no_comments, re.MULTILINE):
            module = match.group(1).split('.')[0]
            if module not in self.allowed_imports:
                return False

        # Block access to builtins that can escape sandbox
        dangerous_keywords = ['os', 'sys', 'subprocess', 'shutil', 'importlib', 'eval', 'exec', '__import__']
        if any(word in code_no_comments for word in dangerous_keywords):
            return False
        return True

    @register_tool
    async def run_python_return_text(self, code: str) -> str:
        if not self._is_safe_code(code):
            return "Error: code imports disallowed modules."

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_file = os.path.join(tmp_dir, "script.py")
            with open(tmp_file, "w") as f:
                f.write(code)

            try:
                result = subprocess.run(
                    [self.python_executable, tmp_file],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                return result.stdout.strip() or result.stderr.strip() or "No output generated."
            except subprocess.TimeoutExpired:
                return "Execution timed out."

    @register_tool
    @sends_image
    async def run_python_return_img(self, code: str) -> tuple[str, bytes] | str:
        duck_logger.info(f"Executing Python code: {code}")

        if not self._is_safe_code(code):
            return "Error: code imports disallowed modules."

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_file = os.path.join(tmp_dir, "script.py")
            output_path = os.path.join(tmp_dir, "plot.png")

            # remove show and savefig lines if included
            code = re.sub(r'^\s*plt\.(show|savefig)\s*\(.*?\)\s*;?\s*(#.*)?$', '', code, flags=re.MULTILINE)

            injected_code = (
                    "import matplotlib.pyplot as plt\n"
                    "import seaborn as sns\n"
                    f"output_path = r'{output_path}'\n"
                    + code +
                    "\nif plt.get_fignums():\n"
                    "    plt.savefig(output_path, bbox_inches='tight', dpi=150)\n"
            )

            with open(tmp_file, "w") as f:
                f.write(injected_code)

            try:
                result = subprocess.run(
                    [self.python_executable, tmp_file],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                # If a plot was saved, return it as (name, bytes)
                if os.path.exists(output_path):
                    with open(output_path, "rb") as img_file:
                        return "generated_plot.png", img_file.read()

                # Otherwise return stdout/stderr
                return result.stdout.strip() or result.stderr.strip() or "No output generated."
            except subprocess.TimeoutExpired:
                return "Execution timed out."