import re
import markdowndata

from functools import reduce
import operator

SECTION = str
SECTION_NAME = str
RUBRIC_ITEM = str
REPORT_SECTION = str

"""
These functions allow for the parsing of md reports based on yaml rubrics provided in the config.

Rubrics:
   - File paths are specified in the config with a project name
   - Rubrics are loaded via safe_yaml.loads()
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
    return (content := cleaned_report_section.strip()) and content != 'fill me in'


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


def find_project_name_in_report_headers(report_contents: dict, valid_project_names):
    top_level_headers = list(report_contents.keys())
    for header in top_level_headers:
        if header in valid_project_names:
            return header
    return None
