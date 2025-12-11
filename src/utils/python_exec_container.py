import asyncio
import io
import json
import os
import tarfile
import uuid
import boto3
import botocore.exceptions
from pathlib import Path
from textwrap import dedent, indent
from typing import TypedDict

import docker
from docker.errors import NotFound

from .config_types import Config
from .logger import duck_logger


class FileResult(TypedDict):
    description: str
    bytes: bytes


class ExecutionResult(TypedDict):
    exit_code: int
    stdout: str
    stderr: str
    files: dict[str, FileResult]


class PythonExecContainer:
    def __init__(self, image: str, name: str, mounts: list[dict[str, str]]):
        self._image = image
        self._name = name
        self._mount_data = mounts
        self._resource_metadata = []
        self._client: docker.Client = docker.from_env()
        self._container = None
        self._data_dir = '/home/sandbox/datasets'
        self._working_dir = "/home/sandbox/out"

    def name_in_use(self, name: str) -> bool:
        try:
            # Docker treats names as "/name" internally, but the SDK matches automatically
            self._client.containers.get(name)
            return True
        except NotFound:
            return False

    def __enter__(self):
        # start container
        if self.name_in_use(self._name):
            cont = self._client.containers.get(self._name)
            cont.stop()
            cont.remove()

        self._mount_files()

        self._container = self._client.containers.run(
            self._image,
            name=self._name,
            command="sleep infinity",
            detach=True,
        )
        duck_logger.info("Container started")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Stop and remove container
        if self._container:
            self._container.stop()
            self._container.remove()

    def _get_local_bytes(self, path: str) -> bytes:
        """Read raw bytes from a local file."""
        return Path(path).read_bytes()

    def _get_s3_bytes(self, path: str) -> bytes:
        """Read raw bytes from an S3 path s3://bucket/key"""
        s3_client = boto3.client("s3")
        bucket, key = self._get_s3_info(path)
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()

    def _get_s3_info(self, path: str) -> tuple[str, str]:
        """Return (bucket, key) for s3://bucket/key path."""
        path = path.replace("s3://", "")
        bucket, key = path.split("/", 1)
        return bucket, key

    def _get_dataset_description(self, path: str) -> str:
        """Return dataset description from a .meta.json file if present."""
        meta_bytes = None
        if is_s3(path):
            bucket, key = self._get_s3_info(path)
            meta_key = key.rsplit(".", 1)[0] + ".meta.json"
            s3_client = boto3.client("s3")
            try:
                obj = s3_client.get_object(Bucket=bucket, Key=meta_key)
                meta_bytes = obj["Body"].read()
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] not in ["404", "NoSuchKey"]:
                    raise
        else:
            meta_path = Path(path).with_suffix(".meta.json")
            if meta_path.exists():
                meta_bytes = meta_path.read_bytes()

        if meta_bytes:
            try:
                return json.dumps(json.loads(safe_decode(meta_bytes)), indent=2)
            except Exception:
                return "Failed to parse metadata JSON."
        return "No metadata available."

    def _mount_files(self):
        for mount in self._mount_data:
            remote_path = mount["source"]
            container_path = mount["target"]

            filename = os.path.basename(remote_path)
            remote_bytes = (
                self._get_s3_bytes(remote_path)
                if is_s3(remote_path)
                else self._get_local_bytes(remote_path)
            )

            dest_path = self._write_file(filename, remote_bytes, container_path)
            description = self._get_dataset_description(remote_path)

            self._resource_metadata.append({
                "path": dest_path,
                "description": description
            })

    def _mkdir(self, path: str) -> str:
        """Makes a directory in the tmpfs /out directory and returns the path"""
        self._container.exec_run(["mkdir", "-p", path])
        return path

    def _write_file(self, filename: str, data: bytes, container_dir: str) -> str:
        """
        Writes a dict of {relative_path: bytes} to the container directory and returns the destination path

        Example:
            files = {
                "input.txt": b"...",
                "subdir/data.json": b"..."
            }

        container_dir should be a full container path, e.g. "/out/<uuid>"
        """
        dest_path = os.path.join(container_dir, filename)  # full path to file
        # make sure the directory exists in the container
        parent_dir = os.path.dirname(dest_path)
        self._container.exec_run(["mkdir", "-p", parent_dir])

        # create a tar archive containing just this file
        tarstream = io.BytesIO()
        with tarfile.open(fileobj=tarstream, mode="w") as tar:
            info = tarfile.TarInfo(name=os.path.basename(dest_path))
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        tarstream.seek(0)

        # Send archive into the correct directory
        self._container.put_archive(parent_dir, tarstream.getvalue())
        return dest_path

    def _get_plot_description(self, path: str, filename: str, json_files: set[str]) -> str:
        """Returns the description of a plot contained in its corresponding json file"""
        # filename without file extension
        base = filename.rsplit(".", 1)[0]

        # ===== find subplot json files: <imagename>_ax<index>.json ===== #
        subplot_descriptions = {}
        for json_name in json_files:
            if json_name.startswith(base + "_ax") and json_name.endswith(".json"):
                try:
                    json_bytes = self._read_file(os.path.join(path, json_name))
                    meta = json.loads(json_bytes.decode())

                    subplot_descriptions[json_name] = (
                        f"{meta.get('plot_type', 'unknown type of')} plot titled "
                        f"'{meta.get('title', '')}', xlabel='{meta.get('xlabel', '')}', "
                        f"ylabel='{meta.get('ylabel', '')}'"
                    )
                except Exception:
                    subplot_descriptions[json_name] = "subplot without description"

        # ===== if subplots found, make combined description ===== #
        if subplot_descriptions:
            # sort keys by ax number
            sorted_items = sorted(
                subplot_descriptions.items(),
                key=lambda item: int(item[0].split("_ax")[-1].split(".")[0])
            )

            # enumerate descriptions in order
            parts = []
            for idx, desc in enumerate(sorted_items):
                parts.append(f"subplot {idx}: {desc}")

            return f"figure with {len(parts)} subplots: {{" + "; ".join(parts) + "}"
            # return f"figure with {len(parts)} subplots: {{\n\t\t\t" + ";\n\t\t\t".join(parts) + "\n\t\t}"

        # ===== otherwise fall back to single json behavior ===== #
        single_json = base + ".json"
        description_path = os.path.join(path, single_json)

        if single_json in json_files:
            try:
                json_bytes = self._read_file(description_path)
                meta = json.loads(json_bytes.decode())
                return (
                    f"{meta.get('plot_type', 'unknown type of')} plot titled "
                    f"'{meta.get('title', '')}', xlabel='{meta.get('xlabel', '')}', "
                    f"ylabel='{meta.get('ylabel', '')}'"
                )
            except Exception:
                return "image without description"

        # if no metadata found
        return "image without description"

    def _get_file_description(self, path: str, filename: str, json_files: set[str]) -> str:
        """Returns the description of a file"""
        if is_image(filename):
            return self._get_plot_description(path, filename, json_files)
        elif is_table(filename):
            name, ext = os.path.splitext(filename)
            return f"table titled '{name}'"
        else:
            return "file without saved description"

    def _read_file(self, path) -> bytes:
        """Reads a file from a full path, e.g. '/out/<uuid>/file.txt' and returns its contents"""
        stream, _ = self._container.get_archive(path)
        tar_bytes = b"".join(stream)
        tarstream = io.BytesIO(tar_bytes)

        with tarfile.open(fileobj=tarstream, mode="r:*") as tar:
            for member in tar.getmembers():
                if file := tar.extractfile(member):
                    return file.read()

        raise FileNotFoundError(f"File not found in container: {path}")

    def _read_files(self, path: str) -> dict[str, dict[str, str] | bytes]:
        """
        Reads all files inside a directory given by `path`, e.g. "/out/<uuid>"
        Returns:
            {
                "path/filename": {
                    "description": str,
                    "data": bytes
                }
            }
        """
        out_files = {}

        # run ls inside container to list directory contents
        exit_code, dirs = self._container.exec_run(f"ls -1 {path}")

        if exit_code != 0:
            raise FileNotFoundError(f"Directory not found in container: {path}")

        filenames = dirs.decode().splitlines()
        json_files = {f for f in filenames if f.endswith(".json")}

        for filename in filenames:
            # skip json files
            if filename.endswith(".json"):
                continue

            full_path = os.path.join(path, filename)
            file_data = self._read_file(full_path)
            description = self._get_file_description(path, filename, json_files)

            out_files[filename] = {
                "description": description,
                "bytes": file_data
            }
        return out_files

    def _wrap_and_execute(self, code: str, path: str) -> tuple[int, str, str]:
        """Wraps the code before execution and returns the stdout/stderr"""
        wrapped_code = dedent(f"""\
            import sys
            import traceback
            import os
            import json
            from pathlib import Path

            
            outdir = Path({path!r})  # full container path for outputs

            # ===== Patch matplotlib to auto-save metadata ===== #
            try:
                import matplotlib.pyplot as plt

                _original_savefig = plt.Figure.savefig

                def detect_plot_type(ax):
                    if ax.lines:
                        return "line"
                    if ax.collections:
                        return "scatter_or_heatmap"
                    if ax.patches:
                        return "bar_or_hist"
                    if ax.images:
                        return "image"
                    return "unknown"

                def savefig_with_metadata(self, *args, **kwargs):
                    if args:
                        orig = args[0]
                        new_path = str(outdir / os.path.basename(orig))
                        args = (new_path, *args[1:])
                    else:
                        orig = kwargs.get("fname", "figure.png")
                        new_path = os.path.join(str(outdir), os.path.basename(orig))
                        kwargs["fname"] = new_path

                    _original_savefig(self, *args, **kwargs)

                    for i, ax in enumerate(self.axes):
                        metadata = {{
                            "title": ax.get_title(),
                            "xlabel": ax.get_xlabel(),
                            "ylabel": ax.get_ylabel(),
                            "plot_type": detect_plot_type(ax)
                        }}
                        if len(self.axes) == 1:
                            meta_path = os.path.splitext(new_path)[0] + ".json"
                        else:
                            base, ext = os.path.splitext(new_path)
                            meta_path = f"{{base}}_ax{{i}}.json"
                        with open(meta_path, "w") as f:
                            json.dump(metadata, f)

                plt.Figure.savefig = savefig_with_metadata
            except ImportError:
                pass

            # ===== Execute user code safely ===== #
            try:
{indent(code, '                ')}
            except Exception:
                traceback.print_exc(file=sys.stdout)
            finally:
                sys.stdout.flush()
                sys.stdout.close()
        """)

        # execute inside the container
        result = self._container.exec_run(
            ["python3", "-u", "-c", wrapped_code],
            workdir=path,
            demux=True
        )
        stdout_bytes, stderr_bytes = result.output
        stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        return result.exit_code, stdout, stderr

    def _run_code(self, code: str, files: dict = None) -> ExecutionResult:
        unique_id = str(uuid.uuid4())
        dir_path = self._mkdir(f'{self._working_dir}/{unique_id}')
        duck_logger.debug(f'Running code in {self._container.name}:\n{code}')

        if files:
            for rel_path, data in files.items():
                self._write_file(rel_path, data, dir_path)
        exit_code, stdout, stderr = self._wrap_and_execute(code, dir_path)

        duck_logger.debug(f'Exit code: {exit_code}')
        duck_logger.debug(' stdout '.center(20, '-'))
        duck_logger.debug(stdout)
        duck_logger.debug(' stderr '.center(20, '-'))
        duck_logger.debug(stderr)

        files = self._read_files(dir_path)

        output = {
            'exit_code': exit_code,
            'stdout': stdout,
            'stderr': stderr,
            'files': files
        }
        return output

    async def run_code(self, code: str, files: dict = None) -> ExecutionResult:
        """Takes python code to execute and an optional dict of files to reference"""
        return await asyncio.to_thread(self._run_code, code, files)

    def get_resource_descriptions(self) -> str:
        """Return prompt content describing each file mounted in the container"""
        return 'Available Files:\n'


def build_containers(config: Config) -> dict[str, PythonExecContainer]:
    # setup container dictionary
    config_containers = config.get('containers', [])
    container_config = {}
    for c in config_containers:
        container_config[c['name']] = PythonExecContainer(c['image'], c['name'], c['mounts'])
    return container_config


def is_image(filename) -> bool:
    _, ext = os.path.splitext(filename)
    return ext[1:] in ['png', 'svg', 'jpg', 'jpeg', 'tiff']


def is_table(filename) -> bool:
    _, ext = os.path.splitext(filename)
    return ext[1:] in ['csv']


def is_text(filename) -> bool:
    _, ext = os.path.splitext(filename)
    return ext[1:] in ['txt']


def is_s3(path: str) -> bool:
    return path.startswith("s3://")


def safe_decode(data: bytes) -> str:
    """Try multiple encodings to decode bytes into a string."""
    for encoding in ["utf-8", "utf-16", "latin-1"]:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("Unable to decode bytes with tried encodings.")
