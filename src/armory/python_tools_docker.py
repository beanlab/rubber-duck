import subprocess
import shutil
import tempfile
import textwrap
import uuid
from pathlib import Path
from .tools import register_tool, sends_image
from ..utils.logger import duck_logger


class PythonToolsDocker:
    def __init__(self, docker_image: str, timeout: int):
        self.docker_image = docker_image
        self.timeout = timeout
        self.tmp_dir = Path("/tmp")  # TODO: use tempdir
        self.out_dir = self.tmp_dir / "out"
        # Ensure output directory exists
        self.out_dir.mkdir(exist_ok=True, parents=True)

    def _run_docker(self, code: str, tool_mode: str, run_id: str) -> tuple[str, str, Path | None]:
        """Runs Python code inside Docker and captures stdout/stderr and plots"""

        # Create unique input/output for the session to avoid concurrency conflicts
        run_out_dir = self.out_dir / run_id
        plots_dir = run_out_dir / "plots"

        # Write code to a unique temporary file
        with tempfile.NamedTemporaryFile() as temp_code_path: # TODO: change to temp dir and put
            # temp_code_path = self.tmp_dir / f"code_to_run_{run_id}.py"
            temp_code_path.write_text(code)

            # Docker run command
            cmd = [
                "docker", "run", "--rm",
                "--network=host",  # TODO: add datasets to docker so no imports are needed
                "--read-only",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                "--mount", f"type=bind,source={self.tmp_dir},target=/app", # TODO: copying instead of mounting
                "--mount", f"type=bind,source={run_out_dir},target=/out",
                "--security-opt", "no-new-privileges",
                "--cap-drop", "ALL",
                "--pids-limit", "128",
                "-e", f"CODE_PATH=/app/{temp_code_path.name}",
                "-e", f"OUT_DIR=/out",
                "-e", f"TOOL_MODE={tool_mode}",
                "-e", "MPLCONFIGDIR=/tmp/.matplotlib",
                "-e", "XDG_CACHE_HOME=/tmp/.cache",
                self.docker_image,
                "sh", "-c",
r            ]

            try:
                subprocess.run(cmd, check=True) # TODO: python docker client
            except subprocess.CalledProcessError as e:
                duck_logger.error(f"Docker run failed: {e}")
                # stdout.txt may still exist even if there's a failure
                pass

        # Read stdout
        stdout_path = run_out_dir / "stdout.txt"
        stdout = stdout_path.read_text() if stdout_path.exists() else ""

        # Extract errors
        stderr = ""
        if "Traceback" in stdout:
            stderr = stdout
            duck_logger.error(f"Python code errors:\n{stderr}")

        # Collect plots, but only return the first if multiple were generated
        all_plots = list(plots_dir.glob("*.png")) if plots_dir.exists() else []
        plot = all_plots[0] if all_plots else None

        return stdout, stderr, plot

    @register_tool
    def run_python_return_text(self, code: str):
        """Runs python code that returns stdout/stderr only, no images or tables"""
        run_id = uuid.uuid4().hex
        duck_logger.info(f"\nExecuting Python code in run_python_return_text:\n\n{code}\n")
        stdout, stderr, _ = self._run_docker(code, tool_mode="text", run_id=run_id)
        if stderr:
            return f"Error:\n{stderr}"
        return stdout

    @register_tool
    @sends_image
    def run_python_return_img(self, code: str) -> tuple[str, bytes] | str:
        """Runs python code that saves a single image (plot/table)"""
        # generates a unique id for the docker session
        run_id = uuid.uuid4().hex

        run_out_dir = self.out_dir / run_id
        plots_dir = run_out_dir / "plots"
        run_out_dir.mkdir(parents=True, exist_ok=True)
        plots_dir.mkdir(parents=True, exist_ok=True)

        # code preprocessing
        code = f"""
import os
import matplotlib.pyplot as plt
os.makedirs('/out/{run_id}/plots', exist_ok=True)

{code}

# Save the current figure as plot.png if any figure exists
fig = plt.gcf()
if fig.get_axes():
    fig.savefig('out/{run_id}/plots/plot.png', bbox_inches='tight')
plt.close(fig)

if os.path.exists('out/{run_id}/plots/plot.png'):
    print("Plot saved successfully!")
else:
    print("Plot was NOT saved!")
"""
        duck_logger.info(f"\nExecuting Python code in run_python_return_img:\n\n{code}\n")
        stdout, stderr, plot = self._run_docker(code, tool_mode="image", run_id=run_id)

        if stderr:
            duck_logger.error(f"Error in image tool:\n{stderr}")

        try:
            with open(plot, "rb") as f:
                data = f.read()
            name = plot.name
            return name, data
        except Exception as e:
            if duck_logger:
                duck_logger.error(f"Failed to read plot file: {e}")
            return "Plot was created but could not be read."
