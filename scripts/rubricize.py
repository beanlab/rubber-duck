from pathlib import Path
import re
import sys

from myteam.workflow import run_agent
from yaml import safe_dump, safe_load

AGENT_PROMPT = """# Error Fix

You will be provided with a target-script that is likely to throw a traceback error.
Run the script, then capture the error. The code may have many other issues; 
your scope is only the fix related to the error you observe when you run the script.

Errors are to be cataloged and described in a file with a filename you will be provided, 
where target-script is the name of the script throwing errors. 

The shape of the yaml should be this exactly:

```
issue 1:
    traceback:
        - complete captured traceback error
    error line:
        - explicit location of the error, including the source line number and line of code that caused the error
    intended behavior:
        - what the error-producing line appears intended to do in the program
    required concept:
        - what the traceback error means in this scenario
    required fix:
        - the exact code change made to correct the error
```

The file may already be written to. 
In this case, append the appropriate missing issue with traceback, error line, intended behavior, required concept, and required fix.

Do not write a `code` field. The workflow will add it deterministically from the code for the current step.

You are permitted to edit only the yaml rubric.

If there were no errors, do not edit the yaml rubric. Set `error` to false and return the code you were passed as `next_code`.

## Implementing a Fix

After writing the appropriate fields to the rubric, provide a new version of the same script with a single fix for the error observed.

Your singular fix to the code should prioritize the direct fix for the error rather than exception handling to catch error scenarios. 
Prioritize the minimal fix for every code spot that causes an error.
There may be multiple errors in the same line of code. You are to fix only the error that must be causing that exact traceback.
Making more than one fix is out of scope, and so prohibited.

## Interactive Programs

Some programs may have interactive flow. 
In this case, it is appropriate to interact with them as prompted to see if they proceed to completion without error.
"""

TRACEBACK_PATH_PATTERN = re.compile(
    r"(?P<quote>[\"'])(?P<path>(?:[A-Za-z]:[\\/]|/)[^\"']*[\\/](?P<filename>[^\\/\"']+))(?P=quote)"
)
TRACEBACK_LOCATION_PATTERN = re.compile(r'File "(?P<path>[^"]+)", line (?P<line>\d+)')


def fetch_content(infile: str) -> str:
    with open(infile) as file:
        return file.read()


def id_issues(md_prompt: str, code: str, yaml_filename: str):
    curr_step = run_agent(
        agent='codex',
        input={
            "code": code,
            "filename": yaml_filename
        },
        output={
            "error": "true if running the code threw a traceback error, else false",
            "next_code": "The code after a single fix is implemented"
        },
        prompt=md_prompt
    )

    if curr_step.status != "completed":
        raise RuntimeError(
            f"Agent failed: {curr_step.error_type}: {curr_step.error_message}"
        )

    next_code = str(curr_step.output.get("next_code", ""))

    if str(curr_step.output["error"]).lower() == "true":
        populate_error_code_fields(Path(yaml_filename), code)
        return id_issues(md_prompt, next_code, yaml_filename)

    populate_correct_code_field(Path(yaml_filename), next_code)
    return


def populate_error_code_fields(rubric_path: Path, source_code: str | None = None) -> None:
    rubric = _load_rubric(rubric_path)
    populated_rubric = _populate_error_code_fields(rubric, source_code)
    rubric_path.write_text(safe_dump(populated_rubric, sort_keys=False))


def populate_correct_code_field(rubric_path: Path, source_code: str | None = None) -> None:
    if not source_code:
        return

    rubric = _load_rubric(rubric_path)
    if "correct code" not in rubric:
        rubric["correct code"] = _number_code_lines(source_code)
    rubric_path.write_text(safe_dump(rubric, sort_keys=False))


def _load_rubric(rubric_path: Path) -> dict:
    if not rubric_path.exists():
        return {}
    return safe_load(rubric_path.read_text()) or {}


def _populate_error_code_fields(value, source_code: str | None = None):
    if isinstance(value, dict):
        populated = {
            key: _populate_error_code_fields(nested_value, source_code)
            for key, nested_value in value.items()
        }
        if "traceback" in populated:
            line_number, code_line = _traceback_error_location(populated["traceback"])
            if not populated.get("code"):
                populated["code"] = _code_field(source_code, line_number, code_line)
            if line_number and code_line and not populated.get("error line"):
                populated["error line"] = [f"line {line_number}: {code_line}"]
        return populated

    if isinstance(value, list):
        return [
            _populate_error_code_fields(item, source_code)
            for item in value
        ]

    return value


def _code_field(source_code: str | None, line_number: str, code_line: str) -> str:
    if source_code:
        return _number_code_lines(source_code)

    if line_number and code_line:
        return f"{int(line_number):02}| {code_line}"

    return ""


def _number_code_lines(source_code: str) -> str:
    return "\n".join(
        f"{line_number:02}| {line}"
        for line_number, line in enumerate(source_code.splitlines(), start=1)
    )


def _traceback_error_location(value) -> tuple[str, str]:
    lines = _rubric_text(value).splitlines()
    for index, line in enumerate(lines):
        location_match = TRACEBACK_LOCATION_PATTERN.search(line)
        if not location_match:
            continue

        code_line = _next_traceback_code_line(lines[index + 1:])
        return location_match.group("line"), code_line

    return "", ""


def _rubric_text(value) -> str:
    if isinstance(value, str):
        return value

    if isinstance(value, list):
        return "\n".join(_rubric_text(item) for item in value)

    if isinstance(value, dict):
        return "\n".join(_rubric_text(item) for item in value.values())

    if value is None:
        return ""

    return str(value)


def _next_traceback_code_line(lines: list[str]) -> str:
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("^"):
            continue
        return stripped_line
    return ""


def conceal_traceback_paths(rubric_path: Path, source_path: Path) -> None:
    rubric = safe_load(rubric_path.read_text()) or {}
    concealed_root = _concealed_root(rubric_path)
    concealed_rubric = _conceal_traceback_values(rubric, concealed_root, source_path.name)
    rubric_path.write_text(safe_dump(concealed_rubric, sort_keys=False))


def _concealed_root(rubric_path: Path) -> str:
    return f"demo-user/documents/CS110/homework-{rubric_path.stem}"


def _conceal_traceback_values(value, concealed_root: str, fallback_filename: str):
    if isinstance(value, dict):
        return {
            key: _conceal_traceback_field(nested_value, concealed_root, fallback_filename)
            if key == "traceback"
            else _conceal_traceback_values(nested_value, concealed_root, fallback_filename)
            for key, nested_value in value.items()
        }

    if isinstance(value, list):
        return [
            _conceal_traceback_values(item, concealed_root, fallback_filename)
            for item in value
        ]

    return value


def _conceal_traceback_field(value, concealed_root: str, fallback_filename: str):
    if isinstance(value, str):
        return _conceal_paths(value, concealed_root, fallback_filename)

    if isinstance(value, list):
        return [
            _conceal_traceback_field(item, concealed_root, fallback_filename)
            for item in value
        ]

    if isinstance(value, dict):
        return {
            key: _conceal_traceback_field(nested_value, concealed_root, fallback_filename)
            for key, nested_value in value.items()
        }

    return value


def _conceal_paths(text: str, concealed_root: str, fallback_filename: str) -> str:
    def replace(match: re.Match) -> str:
        filename = match.group("filename") or fallback_filename
        return f'{match.group("quote")}{concealed_root}/{filename}{match.group("quote")}'

    return TRACEBACK_PATH_PATTERN.sub(replace, text)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python rubricize.py <project_file.py>")

    code_path = Path(sys.argv[1])

    code_text = fetch_content(code_path)
    rubric = code_path.parent / f"{code_path.stem}.yaml"
    id_issues(AGENT_PROMPT, code_text, str(rubric))
    populate_error_code_fields(rubric)
    conceal_traceback_paths(rubric, code_path)
    print(f'Rubric saved to {rubric}')


if __name__ == "__main__":
    main()
