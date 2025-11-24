import re
from pathlib import Path

import markdowndata

from functools import reduce
import operator

import yaml

ASSIGNMENT_NAME = str
SECTION = str
SECTION_NAME = str
RUBRIC_ITEM = str
REPORT_SECTION = str
FEEDBACK = str
SATISFACTORY = bool


"""
These functions allow for the parsing of md reports based on yaml rubrics provided in the config.

Rubrics:
   - File paths are specified in the config with a project name
   - Rubrics are assumed to have correct yaml structure
   - Any sections with headers starting with '_' will be ignored.
   - Headers and rubric items cannot be mixed on the same level of nesting

Reports:
   - are loaded via markdowndata.loads()
   - All sections present in the rubric should have corresponding sections in the markdown file
       - Both the nesting and the names should align **exactly**
   - Everything in md report section under a corresponding header in the yaml with rubric items
     will be included when grading for that rubric item
   - Additional sections in the md, without corresponding headers in the yaml, will be ignored
   - Ideally, the project name provided in the config and the first level 1 header in the markdown document align.
        If not, an agent scrubs the report to determine the corresponding report.

Grading:
    - Each rubric item is graded independently of the other rubric items.
    - When a rubric item is graded, it includes whether the rubric item was met (T/F) and justification
      for if it was met
    - If the report section only contains 'fill me in' after removing any special characters, that rubric item
      will not be considered met and the justification provided is "Report section is not filled in."

See an example of a rubric in rubric/demo-fruit-rubric.yaml
See an example of a corresponding report in rubric/demo-fruit-project-report.md

"""


def is_filled_in_report(report_section):
    cleaned_report_section = re.sub(r"[^A-Za-z0-9\s]", "", str(report_section))
    return not cleaned_report_section.strip().lower() == "fill me in"


def _get_nested(d, keys):
    return reduce(operator.getitem, keys, d)


def _set_nested(d, keys, value):
    *prefix, last = keys
    parent = reduce(lambda acc, k: acc.setdefault(k, {}), prefix, d)
    parent.setdefault(last, []).append(value)


def unflatten_dictionary(results):
    unflattened = {}
    for keys, formatted in results:
        _set_nested(unflattened, keys, formatted)
    return unflattened


def flatten_report_and_rubric_items(report_contents, rubric_contents) -> list[
    tuple[list[SECTION_NAME], RUBRIC_ITEM, REPORT_SECTION]]:
    def helper_func(name, rubric_section, report_section):
        for section_name in rubric_section.keys():
            if section_name[0] == '_':  # ignore any headers that start with '_'
                continue
            name.append(section_name)
            if isinstance(rubric_section[section_name], dict):
                yield from helper_func(name, rubric_section[section_name], report_section[section_name])
            elif isinstance(rubric_section[section_name], list):
                for section_item in rubric_section[section_name]:
                    yield name[::], section_item, report_section[section_name]
            name.pop(-1)

    try:
        rubric = yaml.safe_load(rubric_contents)
        report = markdowndata.loads(report_contents)
        flattened = list(helper_func([], rubric, report))
        return flattened
    except KeyError as e:
        # TODO ask: what exception should be here? Is a vanilla exception fine? Best practice?
        raise Exception(f"Unable to find header {e} in the report. \n"
                        f"The expected format is as follows: {get_expected_md_format(rubric)}")


def get_expected_md_format(rubric):
    as_md = dict_to_md(rubric)
    return (f""
            f"```md\n"
            f"{as_md}"
            f"```")


def dict_to_md(d, level=1):
    """
    Convert a nested dict of the form
    {a: {b: [1] }}
    into markdown:

    # a
    ## b
    - 1
    """
    lines = []

    for key, value in d.items():
        header_prefix = "#" * level
        lines.append(f"{header_prefix} {key}")

        if isinstance(value, dict):
            lines.append(dict_to_md(value, level + 1))

        elif isinstance(value, list):
            for item in value:
                lines.append(f"- {item}")
        else:
            lines.append(f"- {value}")

    return "\n".join(lines)


def _extract_top_level_headers(report_contents) -> list[str]:
    report_contents = markdowndata.loads(report_contents)  # TODO: missing error handling for mdd loads failing
    top_headers = list(report_contents.keys())
    return top_headers


def find_project_name_in_report_headers(report_contents, valid_project_names):
    top_level_headers = _extract_top_level_headers(report_contents)
    for header in top_level_headers:
        if header in valid_project_names:
            return header
    return None


def load_yaml_file(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

