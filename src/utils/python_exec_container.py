import docker


class PythonExecContainer():
    def __init__(self, image: str) -> None:
        self.image: str = image
        self.client = docker.from_env()
        self.container = None

    def __enter__(self):
        # Start Docker container
        # duck_logger.info(f"Starting container from image: {self.image}")
        self.container = self.client.containers.run(
            self.image,
            command="sleep infinity",
            detach=True
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Stop and remove container
        if self.container:
            self.container.stop()
            self.container.remove()

    def run_code(self, code: str, stream_output=True):
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


def run_task(code):
    with PythonExecContainer("byucscourseops/python-tools-sandbox:latest") as c:
        print("Started")
        for line in c.run_code(code):
            print(line)
        print("Finished")
