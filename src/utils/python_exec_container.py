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
        for filename in os.listdir(self.out_dir):
            with open(os.path.join(self.out_dir, filename), "rb") as f:
                out_files[filename] = f.read()
        return out_files

    def _wrap_and_execute(self, code: str):
        wrapped_code = f"""
import sys
import traceback
with open('/out/stdout.txt', 'w') as f:
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

    def run_code_concurrent(self, code: str, stream_output=True):
        """
        Run Python code inside the container.
        If stream_output=True, yields output lines in real-time.
        """
        exec_instance = self.container.client.api.exec_create(
            self.container.id,
            cmd=["python3", "-u", "-c", code],
            stdout=True,
            stderr=True
        )

        if stream_output:
            for line in self.container.client.api.exec_start(exec_instance['Id'], stream=True):
                yield line.decode().strip()
        else:
            res = self.container.exec_run(cmd=["python3", "-c", code], stdout=True, stderr=True)
            yield res.output.decode().strip()


# ====== testing concurrency with streaming ====== #
from concurrent.futures import ThreadPoolExecutor


def run_task(code, task_name):
    with PythonExecContainer("byucscourseops/python-tools-sandbox:latest") as c:
        print(f"[{task_name}] Started")
        for line in c.run_code(code):
            print(f"[{task_name}] {line}")
        print(f"[{task_name}] Finished")


def run_code_test():
    with PythonExecContainer("byucscourseops/python-tools-sandbox:latest") as container:
        code = """print('hello world')"""
        result = container.run_code(code)


def concurrent_test():
    codes = [
        ("""
import time
for i in range(10):
    print(f'Code 1: 1.{i}')
    time.sleep(.1)
print('Code 1: 2')
print('Code 1 done')
    """, "Task 1"),
        ("""
import time
for i in range(10):
    print(f'Code 2: {i+1} seconds')
    time.sleep(1)
print('Code 2 done')
    """, "Task 2")
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run_task, code, name) for code, name in codes]

    # Wait for all tasks to finish
    for future in futures:
        future.result()


if __name__ == "__main__":
    run_code_test()
    # concurrent_test()
