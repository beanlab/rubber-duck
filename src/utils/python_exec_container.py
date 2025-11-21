import asyncio
import io
import json
import os
import tarfile
import uuid
from textwrap import dedent, indent

import docker


class PythonExecContainer():
    def __init__(self, image: str) -> None:
        self.image: str = image
        self.client = docker.from_env()
        self.container = None
        self._working_dir = '/home/sandbox/out'

    def __enter__(self):
        # start docker container
        # duck_logger.info(f"Starting container from image: {self.image}")
        self.container = self.client.containers.run(
            self.image,
            command="sleep infinity",
            detach=True,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Stop and remove container
        if self.container:
            self.container.stop()
            self.container.remove()

    def _mkdir(self, path: str) -> str:
        """Makes a directory in the tmpfs /out directory"""
        res = self.container.exec_run(["mkdir", "-p", path])
        return path

    def _write_file(self, rel_path: str, data: bytes, container_dir: str):
        """
        Writes a dict of {relative_path: bytes} to the container directory

        Example:
            files = {
                "input.txt": b"...",
                "subdir/data.json": b"..."
            }

        container_dir should be a full container path, e.g. "/out/<uuid>"
        """
        dest_path = os.path.join(container_dir, rel_path)  # full path to file

        # make sure the directory exists in the container
        parent_dir = os.path.dirname(dest_path)
        self.container.exec_run(["mkdir", "-p", parent_dir])

        # create a tar archive containing just this file
        tarstream = io.BytesIO()
        with tarfile.open(fileobj=tarstream, mode="w") as tar:
            info = tarfile.TarInfo(name=os.path.basename(dest_path))
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

        tarstream.seek(0)

        # Send archive into the correct directory
        self.container.put_archive(parent_dir, tarstream.getvalue())

    def _get_description(self, path: str, filename: str, json_files: set[str]) -> str:
        if filename == "stdout.txt":
            return "stdout/stderr"

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
                        f"{meta.get('plot_type', 'unknown')} plot titled "
                        f"'{meta.get('title', '')}', xlabel='{meta.get('xlabel', '')}', "
                        f"ylabel='{meta.get('ylabel', '')}'"
                    )
                except Exception:
                    subplot_descriptions[json_name] = "unknown subplot"

        # ===== if subplots found, make combined description ===== #
        if subplot_descriptions:
            # sort keys by ax number
            sorted_items = sorted(
                subplot_descriptions.items(),
                key=lambda item: int(item[0].split("_ax")[-1].split(".")[0])
            )

            # Now enumerate descriptions in order
            parts = []
            for idx, desc in enumerate(sorted_items):
                parts.append(f"subplot {idx}: {desc}")

            return f"\n\t\tfigure with {len(parts)} subplots: [\n\t\t\t" + ";\n\t\t\t".join(parts) + "\n\t]"

        # ===== otherwise fall back to single json behavior ===== #
        single_json = base + ".json"
        description_path = os.path.join(path, single_json)

        if single_json in json_files:
            try:
                json_bytes = self._read_file(description_path)
                meta = json.loads(json_bytes.decode())
                return (
                    f"{meta.get('plot_type', 'unknown')} plot titled "
                    f"'{meta.get('title', '')}', xlabel='{meta.get('xlabel', '')}', "
                    f"ylabel='{meta.get('ylabel', '')}'"
                )
            except Exception:
                return "unknown image"

        # ---- 4. No metadata found ----
        return "unknown image"

    def _read_file(self, path):
        """Reads a file from a full path, e.g. '/out/<uuid>/file.txt'"""
        stream, _ = self.container.get_archive(path)
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
                    "description": dict,
                    "data": bytes
                }
            }
        """
        out_files = {}

        # Run `ls` inside container to list directory contents
        cmd = f"ls -1 {path}"
        exit_code, output = self.container.exec_run(cmd)

        if exit_code != 0:
            raise FileNotFoundError(f"Directory not found in container: {path}")

        filenames = output.decode().splitlines()
        json_files = {f for f in filenames if f.endswith(".json")}

        print("\nFiles found:")
        for filename in filenames:
            # skip json files
            print("\t",filename)
            if filename.endswith(".json"):
                continue

            if filename.endswith(".txt"):
                pass

            full_path = os.path.join(path, filename)
            file_data = self._read_file(full_path)
            description = self._get_description(path, filename, json_files)

            out_files[full_path] = {
                "description": description,
                "data": file_data
            }
        return out_files

    def _wrap_and_execute(self, code: str, path: str):
        # Ensure the output directory exists

        wrapped_code = dedent(f"""\
            import sys
            import traceback
            import os
            import json
            from pathlib import Path

            outdir = Path({path!r})  # full container path for outputs

            # ===== Redirect stdout/stderr ===== #
            stdout_path = outdir / "stdout.txt"
            sys.stdout = open(stdout_path, "w")
            sys.stderr = sys.stdout

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

        # Execute inside the container
        res = self.container.exec_run(["python3", "-u", "-c", wrapped_code])
        return res

    def _run_code(self, code: str, files: dict = None):
        id = str(uuid.uuid4())
        dir_path = self._mkdir(f'{self._working_dir}/{id}')
        if files:
            for rel_path, data in files.items():
                self._write_file(rel_path, data, dir_path)
        self._wrap_and_execute(code, dir_path)
        return self._read_files(dir_path)

    async def run_code(self, code: str, files: dict = None):
        return await asyncio.to_thread(self._run_code, code, files)


async def run_code_test():
    with PythonExecContainer("byucscourseops/python-tools-sandbox:latest") as container:
        code = dedent("""\
            import time
            import matplotlib.pyplot as plt

            # Create a 1x2 subplot layout
            fig, axs = plt.subplots(1, 2, figsize=(10, 4))

            # Left subplot – line plot
            axs[0].plot([1, 2, 3, 4], [10, 20, 25, 30])
            axs[0].set_title('Line Plot')
            axs[0].set_xlabel('X')
            axs[0].set_ylabel('Y')

            # Right subplot – bar plot
            axs[1].bar([1, 2, 3, 4], [5, 7, 3, 9])
            axs[1].set_title('Bar Plot')
            axs[1].set_xlabel('Category')
            axs[1].set_ylabel('Value')

            # Save both subplots in one figure
            plt.savefig('subplots.png')

            print("figure saved")
                """)
        return await container.run_code(code)


async def async_run_code_test():
    with PythonExecContainer("byucscourseops/python-tools-sandbox:latest") as container:
        code = dedent("""\
            import time
            import matplotlib.pyplot as plt
            print("start", time.time())
            
            plt.plot([1, 2, 3, 4], [10, 20, 25, 30])
            plt.title('Example Plot')
            plt.savefig('plot.png')
            time.sleep(1)
            print("end", time.time())
            """)

        task1 = asyncio.create_task(container.run_code(code))
        task2 = asyncio.create_task(container.run_code(code))
        results = await asyncio.gather(task1, task2)
        return results


if __name__ == "__main__":
    output = asyncio.run(run_code_test())
    print("\nOutput description content")
    for file in output:
        print("\t",file, end=": ")
        print(output[file]['description'])
    # output1 = asyncio.run(async_run_code_test())
    # for dict in output1:
    #     for file in dict:
    #         print(file, end=": ")
    #         print(dict[file]['description'])
