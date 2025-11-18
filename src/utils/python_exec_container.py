import io
import os
import tarfile
import tempfile

import docker


class PythonExecContainer():
    def __init__(self, image: str) -> None:
        self.image: str = image
        self.client = docker.from_env()
        self.container = None
        self.out_dir = tempfile.mkdtemp(prefix="sandbox_out_")

    def __enter__(self):
        # Start Docker container
        # duck_logger.info(f"Starting container from image: {self.image}")
        self.container = self.client.containers.run(
            self.image,
            command="sleep infinity",
            detach=True,
            volumes={
                self.out_dir: {"bind": "/out", "mode": "rw"}
            }
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Stop and remove container
        if self.container:
            self.container.stop()
            self.container.remove()

    def _mkdir(self, path):
        self.container.exec_run(["mkdir", "-p", path])

    def _write_files(self, files):
        for path, data in files.items():
            tarstream = io.BytesIO()
            tar = tarfile.TarFile(fileobj=tarstream, mode='w')

            info = tarfile.TarInfo(name=os.path.basename(path))
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
            tar.close()
            tarstream.seek(0)

            container_dir = os.path.dirname(path)
            self.container.put_archive(container_dir, tarstream.getvalue())

    def _read_files(self):
        out_files = {}
        for root, _, files in os.walk(self.out_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.out_dir)
                out_files[rel_path] = open(full_path, "rb").read()
        return out_files

    def _wrap_and_execute(self, code: str):
        wrapped_code = f"""
import sys
import traceback
with open('/out/stdout.txt', 'w') as f:
    sys.stdout = f
    sys.stderr = f
    try:
        exec({code!r})
    except Exception as e:
        traceback.print_exc(file=f)
"""
        return self.container.exec_run(["python3", "-u", "-c", wrapped_code])

    def run_code(self, code: str, files: dict = None):
        self._mkdir("/out")
        if files:
            self._write_files(files)
        self._wrap_and_execute(code)
        return self._read_files()


def run_code_test():
    with PythonExecContainer("byucscourseops/python-tools-sandbox:latest") as container:
        code = """
print('hello world')
open("/out/test.txt", "w").write("hi there!")
"""
        return container.run_code(code)


if __name__ == "__main__":
    print(run_code_test())
    # concurrent_test()
