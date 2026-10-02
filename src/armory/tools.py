import inspect
from functools import partial, wraps
from types import UnionType
from typing import Any, Callable, get_type_hints, Literal, get_origin, get_args, Union

from openai.types.responses import FunctionToolParam

_tools: dict[str, Callable] = {}


def register_tool(func):
    setattr(func, "is_tool", True)
    return func


def sends_image(func):
    func.sends_image = True
    func.complete_response = True
    return func


def is_optional(annotation) -> bool:
    origin = get_origin(annotation)
    args = get_args(annotation)
    return (origin is UnionType or origin is Union) and type(None) in args


def get_strict_json_schema_type(annotation) -> dict:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if is_optional(annotation):
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1:
            return get_strict_json_schema_type(non_none_args[0])
        raise TypeError(f"Unsupported Union with multiple non-None values: {annotation}")

    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }

    if annotation in type_map:
        return {"type": type_map[annotation]}

    if origin in type_map:
        return {"type": type_map[origin]}

    if origin is Literal:
        values = args
        if all(isinstance(v, (str, int, bool)) for v in values):
            return {"type": "string" if all(isinstance(v, str) for v in values) else "number", "enum": list(values)}
        raise TypeError("Unsupported Literal values in annotation")

    raise TypeError(f"Unsupported parameter type: {annotation}")


def generate_function_schema(func: Callable[..., Any]) -> FunctionToolParam:
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)

    params = {}
    required = []

    for name, param in sig.parameters.items():
        if name in {"self", "ctx"}:
            continue

        ann = type_hints.get(name, param.annotation)
        if ann is inspect._empty:
            raise TypeError(f"On func {func.__name__}: missing type annotation for parameter: {name}")

        schema_entry = get_strict_json_schema_type(ann)

        required.append(name)
        params[name] = schema_entry

    return {
        "type": "function",
        "name": func.__name__,
        "description": func.__doc__ or "",
        "parameters": {
            "type": "object",
            "properties": params,
            "required": required,
            "additionalProperties": False
        },
        "strict": True
    }


class ToolBox:
    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._schemas: dict[str, FunctionToolParam] = {}

    def add_tool(self, tool_function: Callable, name=None, description=None):
        name = name or tool_function.__name__
        description = description if description is not None else tool_function.__doc__

        @wraps(tool_function)
        async def tool(*args, **kwargs):
            result = tool_function(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
            return result

        tool.__name__ = name
        tool.__doc__ = description
        self._tools[name] = tool
        self._schemas[name] = generate_function_schema(tool)

    def bind_context(self, context) -> "ToolBox":
        toolbox = ToolBox()
        for name, tool in self._tools.items():
            toolbox._tools[name] = partial(tool, context)
            toolbox._schemas[name] = self._schemas[name]
        return toolbox

    def get_tool_schemas(self) -> list[FunctionToolParam]:
        return list(self._schemas.values())

    def get_tool(self, tool_name: str) -> Callable:
        if tool_name in self._tools:
            return self._tools[tool_name]
        raise KeyError(f"Tool '{tool_name}' not found in toolbox.")


# Statistical tools shared by legacy and AI Responses workflows.
import io
import re
from pathlib import Path
from decimal import Decimal, InvalidOperation
import pandas as pd
from pandas.api.types import is_numeric_dtype

from ..storage.stats_output_types import ExecutionOutput, TextOutput
from ..utils.protocols import ToolCache, CacheKeyBuilder
from ..utils.config_types import DuckContext
from ..utils.logger import duck_logger
from ..utils.protocols import SendMessage, ConcludesResponse
from ..utils.python_exec_container import PythonExecContainer, is_image, is_table, FileResult
from .tool_cache import InMemoryToolCache, SemanticCacheKeyBuilder, SqlToolCache
from openai import OpenAI


_SCI_NOTATION_PATTERN = re.compile(
    r"(?<![\w.])([+-]?(?:\d+(?:\.\d*)?|\.\d+)[eE][+-]?\d+)(?![\w.])"
)


def _to_plain_decimal(token: str) -> str:
    try:
        value = Decimal(token)
    except InvalidOperation:
        return token

    if not value.is_finite():
        return token

    formatted = format(value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    if formatted in {"", "-0", "+0"}:
        return "0"
    return formatted


def _remove_scientific_notation(text: str) -> str:
    return _SCI_NOTATION_PATTERN.sub(lambda m: _to_plain_decimal(m.group(1)), text)


def _format_rounded_decimal(value: float, places: int = 4) -> str:
    formatted = format(float(value), f".{places}f")
    formatted = formatted.rstrip("0").rstrip(".")
    return formatted if formatted else "0"


def _format_table_values(table: pd.DataFrame) -> pd.DataFrame:
    formatted_table = table.copy()
    for col in formatted_table.columns:
        if not is_numeric_dtype(formatted_table[col]):
            continue
        formatted_table[col] = formatted_table[col].map(
            lambda value: _format_rounded_decimal(value, 4) if pd.notna(value) else ""
        )
    return formatted_table


def _estimate_column_widths(df, sample_rows=20):
    widths = {}
    for col in df.columns:
        header_width = len(str(col))
        sample_width = (
            df[col]
            .astype(str)
            .head(sample_rows)
            .map(len)
            .max()
        )
        widths[col] = max(header_width, sample_width)
    return widths


def _determine_col_chunk(df, max_table_width=90):
    col_widths = _estimate_column_widths(df)

    current_width = 0
    current_chunk = 0

    for width in col_widths.values():
        # +3 accounts for markdown separators and padding
        projected = current_width + width + 4

        if projected > max_table_width and current_chunk > 0:
            break

        current_width = projected
        current_chunk += 1

    # ensure it's between 2 and 6
    return max(2, min(current_chunk, 6))


def _clean_stdout(stdout: str, files: dict[str, FileResult]) -> str:
    file_names = set(files.keys())

    filtered_lines = []
    for line in stdout.splitlines():
        stripped = line.strip()

        # drop filename echoes
        if stripped in file_names:
            continue

        # drop lines mentioning filenames
        if any(name in stripped for name in file_names):
            continue

        filtered_lines.append(line)

    stdout = "\n".join(filtered_lines).strip()
    return _remove_scientific_notation(stdout)


async def send_table(
        send_message: SendMessage,
        channel_id: int,
        table: pd.DataFrame,
        max_rows: int = 100,
) -> list[str]:
    table = _format_table_values(table.head(max_rows))
    col_chunk = _determine_col_chunk(table)
    table_chunks = []

    for i in range(0, table.shape[1], col_chunk):
        md_table = table.iloc[:, i:i + col_chunk].to_markdown(disable_numparse=True)
        table_chunk = f"```\n{md_table}\n```"
        table_chunks.append(table_chunk)
        await send_message(channel_id, table_chunk)

    return table_chunks


class PythonTools:
    def __init__(
            self,
            container: PythonExecContainer,
            send_message: SendMessage,
            tool_cache: ToolCache | None,
            cache_key_builder: CacheKeyBuilder | None
    ):
        self._container = container
        self._send_message = send_message
        self._tool_cache = tool_cache
        self._cache_key_builder = cache_key_builder

    async def run_code(self, ctx: DuckContext, code: str, user_intent: str) -> dict[str, str | dict[str, str]]:
        """
        Takes python code and the user's intent, executes it, and returns stdout/stderr/files.

        :param ctx: DuckContext
        :param code: Python code to execute
        :param user_intent: Short description of what the user is trying to do.
        :return:
            'code': str,
            'stdout': str,
            'stderr': str,
            'files': {
                filename: description
            }
        """
        collector = getattr(ctx, "_stats_output_collector", None)
        if collector is not None:
            key = None
            if self._tool_cache and self._cache_key_builder:
                cache_key = self._cache_key_builder.build_cache_key(user_intent, code)
                key = self._tool_cache.get_key(cache_key)
                duck_logger.debug(f"Cache key: {key}")
                if self._tool_cache.check_if_cached(key):
                    duck_logger.debug(f" Cache HIT ".center(20, '-'))
                    return await self._tool_cache.send_from_cache(
                        key,
                        collector.capture,
                        ctx.thread_id,
                    )
                duck_logger.debug(f" Cache MISS ".center(19, '-'))

            results = await self._container.run_code_deferred(code)
            files = results.get("files", {})
            stdout = _clean_stdout(results.get("stdout", "").strip(), files)
            stderr = _remove_scientific_notation(results.get("stderr", "").strip())
            collector.items.append(
                ExecutionOutput(
                    self._container,
                    results,
                    stdout,
                    self._tool_cache,
                    key,
                )
            )
            return {
                "stdout": stdout,
                "stderr": stderr,
                "files": {
                    filename: file["description"]
                    for filename, file in files.items()
                },
            }

        key = None
        if self._tool_cache and self._cache_key_builder:
            cache_key = self._cache_key_builder.build_cache_key(user_intent, code)
            key = self._tool_cache.get_key(cache_key)
            duck_logger.debug(f"Cache key: {key}")

            if self._tool_cache.check_if_cached(key):
                duck_logger.debug(f" Cache HIT ".center(20, '-'))
                output = await self._tool_cache.send_from_cache(
                    key,
                    self._send_message,
                    ctx.thread_id
                )
                return ConcludesResponse(output)

            duck_logger.debug(f" Cache MISS ".center(19, '-'))
        else:
            duck_logger.debug(f" Cache DISABLED ".center(21, '-'))
        results = await self._container.run_code(code)

        stdout = results.get('stdout').strip()
        stderr = _remove_scientific_notation(results.get('stderr').strip())
        files = results.get('files', {})

        # log created files
        if files:
            duck_logger.debug(" files ".center(20, '-'))
            for filename, file in files.items():
                duck_logger.debug(f" {filename}: {file['description']}")

        # send files directly
        for filename, file in files.items():
            if is_image(filename):
                if self._tool_cache and key is not None:
                    self._tool_cache.cache_file(key, filename, file)
                await self._send_message(
                    ctx.thread_id,
                    file={
                        "filename": filename,
                        "bytes": file["bytes"],
                    }
                )
            elif is_table(filename):
                table = pd.read_csv(io.StringIO(file['bytes'].decode()))
                table_chunks = await send_table(
                    self._send_message,
                    ctx.thread_id,
                    table,
                )
                if self._tool_cache and key is not None:
                    self._tool_cache.cache_table(key, filename, table_chunks, file.get("description", ""))

        # send cleaned stdout directly
        stdout = _clean_stdout(stdout, files)
        if stdout:
            if self._tool_cache and key is not None:
                self._tool_cache.cache_msg(key, stdout)
            await self._send_message(ctx.thread_id, stdout)

        output = {
            'stdout': stdout,
            'stderr': stderr,
            'files': {filename: file['description'] for filename, file in files.items()},
        }

        if results['exit_code'] == 0:
            output = ConcludesResponse(output)

        return output


class DatasetTools:
    def __init__(self, containers: list[PythonExecContainer], send_message: SendMessage):
        self._containers = containers
        self._send_message = send_message

    def _get_sorted_dataset_names(self) -> list[str]:
        seen: set[str] = set()
        dataset_names: list[str] = []
        for container in self._containers:
            for dataset in container.get_dataset_inventory():
                display_name = dataset.get("dataset_name") or dataset.get("filename")
                if not display_name or display_name in seen:
                    continue
                seen.add(display_name)
                dataset_names.append(display_name)
        return sorted(dataset_names, key=str.casefold)

    def get_resource_metadata(self) -> str:
        lines = ["\n### Available Datasets:"]
        for container in self._containers:
            for dataset in container.get_dataset_inventory():
                dataset_name = dataset.get("dataset_name", dataset["filename"])
                lines.append(f"Name: {dataset_name}")
                lines.append(f"\nFilepath: {dataset['path']}")
        return "\n".join(lines)

    async def send_datasets_to_user(self, ctx: DuckContext) -> ConcludesResponse | str:
        """
        Sends the full canonical dataset-name list directly to the user.
        """
        dataset_names = self._get_sorted_dataset_names()
        if not dataset_names:
            message = "No datasets are currently available."
        else:
            message = "\n".join(["Available datasets:"] + [f"- {name}" for name in dataset_names])

        collector = getattr(ctx, "_stats_output_collector", None)
        if collector is not None:
            collector.items.append(TextOutput(message))
            return f"Prepared {len(dataset_names)} dataset names for delivery."

        await self._send_message(ctx.thread_id, message)
        if dataset_names:
            return ConcludesResponse(f"Sent {len(dataset_names)} dataset names.")
        return ConcludesResponse(message)

    async def describe_dataset(self, ctx: DuckContext, dataset_filename: str) -> str:
        """
        Returns the full dataset description for a dataset filename.
        Accepts either the exact staged filename or any path ending in that filename.
        Do not use Dataset Name values.
        """
        duck_logger.debug(f"describe_dataset called with dataset_name={dataset_filename!r}")
        normalized_filename = Path(dataset_filename).name
        for container in self._containers:
            description = container.describe_dataset(normalized_filename)
            if description:
                duck_logger.debug(f"\n{description}")
                return description

        available = sorted({
            filename
            for container in self._containers
            for filename in container.get_dataset_filenames()
        })
        if not available:
            duck_logger.debug(f"describe_dataset no datasets available for dataset_name={dataset_filename!r}")
            return "No datasets are currently available."

        message = (
            f"Dataset '{dataset_filename}' not found. "
            f"Available dataset filenames: {', '.join(available)}"
        )
        duck_logger.debug(f"describe_dataset no match for dataset_name={dataset_filename!r}; {message}")
        return message


def build_stats_toolbox(
        tool_names: list[str],
        tool_configs: dict,
        containers: dict[str, PythonExecContainer],
        send_message: SendMessage,
        sql_session,
) -> tuple[ToolBox, list[ToolCache]]:
    toolbox = ToolBox()
    tool_caches: list[ToolCache] = []
    dataset_containers: dict[str, PythonExecContainer] = {}

    for tool_name in tool_names:
        tool_config = tool_configs.get(tool_name)
        if not tool_config:
            continue
        if tool_config["type"] != "container_exec":
            raise NotImplementedError(f"Unsupported tool type: {tool_config['type']}")

        container = containers[tool_config["container"]]
        dataset_containers[tool_config["container"]] = container
        cache_settings = tool_config.get("cache")
        tool_cache = None
        cache_key_builder = None
        if cache_settings is not None:
            backend = cache_settings.get("backend", "memory")
            if backend == "memory":
                tool_cache = InMemoryToolCache()
            elif backend == "database":
                tool_cache = SqlToolCache(sql_session)
            else:
                raise NotImplementedError(f"Unsupported cache backend: {backend}")

            prompt_path = cache_settings.get("prompt")
            if not prompt_path:
                raise ValueError(
                    f"Missing cache prompt for container_exec tool '{tool_name}'. "
                    f"Set tools.{tool_name}.cache.prompt."
                )
            cache_key_builder = SemanticCacheKeyBuilder(
                client=OpenAI(),
                prompt=Path(prompt_path).read_text(),
                model=cache_settings.get("engine", "gpt-5.6-luna"),
                reasoning_effort=cache_settings.get("reasoning", "none"),
            )
            setattr(tool_cache, "_cache_source", tool_name)
            tool_caches.append(tool_cache)

        python_tools = PythonTools(
            container,
            send_message,
            tool_cache,
            cache_key_builder,
        )
        toolbox.add_tool(
            python_tools.run_code,
            name=tool_name,
            description=tool_config.get("description", python_tools.run_code.__doc__),
        )

    dataset_tool_names = {
        "describe_dataset",
        "send_datasets_to_user",
    }.intersection(tool_names)
    if dataset_tool_names:
        dataset_tools = DatasetTools(list(dataset_containers.values()), send_message)
        if "describe_dataset" in dataset_tool_names:
            description = (
                "Returns the full description for a dataset by filename.\n"
                "Accepts either a filename or a path that ends in that filename.\n"
                "Use this when you need full column-level metadata."
                + dataset_tools.get_resource_metadata()
            )
            toolbox.add_tool(
                dataset_tools.describe_dataset,
                name="describe_dataset",
                description=description,
            )
        if "send_datasets_to_user" in dataset_tool_names:
            toolbox.add_tool(
                dataset_tools.send_datasets_to_user,
                name="send_datasets_to_user",
            )

    missing = set(tool_names).difference(toolbox._tools)
    if missing:
        raise KeyError(f"Tools unavailable to stats workflow: {', '.join(sorted(missing))}")

    return toolbox, tool_caches

