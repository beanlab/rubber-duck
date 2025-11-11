import subprocess
import shutil
from pathlib import Path
from .tools import register_tool, sends_image

class PythonToolsDocker:
    def __init__(self, docker_image: str, timeout: int):
        self.docker_image = docker_image
        self.timeout = timeout
        self.tmp_dir = Path("/tmp")  # temp directory for code and outputs
        self.out_dir = self.tmp_dir / "out"

    def _cleanup_out_dir(self):
        """Remove and recreate /tmp/out to ensure a clean environment."""
        if self.out_dir.exists():
            shutil.rmtree(self.out_dir)
        self.out_dir.mkdir(exist_ok=True)

    def _run_docker(self, code: str, tool_mode: str):
        """Runs the docker with a given mode ('text' or 'image')"""
        # Cleans /tmp/out before running
        self._cleanup_out_dir()

        # Writes code to temporary file
        temp_code_path = self.tmp_dir / "code_to_run.py"
        temp_code_path.write_text(code)

        # Docker command
        cmd = [
            "docker", "run", "--rm",
            "--network=none",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--tmpfs", "/out:rw,noexec,nosuid,size=64m",
            "-e", f"CODE_PATH=/app/code_to_run.py",
            "-e", f"OUT_DIR=/out",
            "-e", f"TOOL_MODE={tool_mode}",
            self.docker_image
        ]
        subprocess.run(cmd, check=True)

        # Reads results
        stdout = (self.out_dir / "stdout.txt").read_text() if (self.out_dir / "stdout.txt").exists() else ""
        stderr = (self.out_dir / "stderr.txt").read_text() if (self.out_dir / "stderr.txt").exists() else ""
        plots = list(self.out_dir.joinpath("plots").glob("*.png")) if (self.out_dir / "plots").exists() else []

        return stdout, stderr, plots

    @register_tool
    def run_python_return_text(self, code: str):
        """Runs python code in a docker that returns stdout/stderr only, no images or tables"""
        stdout, stderr, _ = self._run_docker(code, tool_mode="text")
        if stderr:
            # Optionally raise or return error text
            return f"Error:\n{stderr}"
        return stdout

    @register_tool
    @sends_image
    def run_python_return_img(self, code: str):
        """Runs python code in a docker that saves a single image only (plots/tables)"""
        _, stderr, plots = self._run_docker(code, tool_mode="image")
        if stderr:
            # Include error messages if needed
            print(f"Error in image tool:\n{stderr}")
        return plots
