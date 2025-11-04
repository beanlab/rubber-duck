import subprocess
import tempfile
import os
import re
from typing import Optional
from .tools import register_tool, sends_image


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
        for match in re.finditer(r'^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)', code, re.MULTILINE):
            module = match.group(1).split(".")[0]
            if module not in self.allowed_imports:
                return False
        return True


    @register_tool
    @sends_image
    async def run_python_code(self, code: str) -> tuple[str, bytes] | str:
        """
        Execute Python code in a temporary subprocess.
        If the code generates a matplotlib/seaborn plot and saves it to a file,
        returns that file as an image (a tuple with a string and bytes).
        Otherwise, returns the text output.
        """
        if not self._is_safe_code(code):
            return "Error: code imports disallowed modules."

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_file = os.path.join(tmp_dir, "script.py")
            output_path = os.path.join(tmp_dir, "plot.png")

            # Inject a forced save location for matplotlib if not specified
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
                output = result.stdout.strip() or result.stderr.strip()

                # If a plot was saved, return it as (name, bytes)
                if os.path.exists(output_path):
                    with open(output_path, "rb") as img_file:
                        return "generated_plot.png", img_file.read()

                return output or "No output generated."
            except subprocess.TimeoutExpired:
                return "Execution timed out."
