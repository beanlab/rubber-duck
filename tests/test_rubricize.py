import pytest

from scripts.rubricize import (
    _apply_single_replacement,
    conceal_traceback_paths,
    populate_correct_code_field,
    populate_error_code_fields,
)
from yaml import safe_load


def test_conceal_traceback_paths_only_rewrites_traceback_fields(tmp_path):
    source = tmp_path / "nested" / "3b-rubric.py"
    source.parent.mkdir()
    source.write_text("print('hello')\n")

    rubric = source.with_suffix(".yaml")
    rubric.write_text(
        """
issue 1:
  traceback:
    - 'File "/mnt/c/Users/real/Documents/CS110/3b-rubric.py", line 4, in <module>'
    - "ValueError: bad input"
  required fix:
    - "Edit /mnt/c/Users/real/Documents/CS110/3b-rubric.py"
full project: |
  1 print('hello')
""".strip()
    )

    conceal_traceback_paths(rubric, source)

    contents = rubric.read_text()
    assert "/mnt/c/Users/real/Documents/CS110/3b-rubric.py" not in contents.split("required fix:")[0]
    assert "demo-user/documents/CS110/homework-3b-rubric/3b-rubric.py" in contents
    assert "Edit /mnt/c/Users/real/Documents/CS110/3b-rubric.py" in contents


def test_populate_error_code_fields_adds_missing_code_and_error_line(tmp_path):
    rubric = tmp_path / "example.yaml"
    rubric.write_text(
        """
issue 1:
  traceback:
    - |-
      Traceback (most recent call last):
        File "/tmp/example.py", line 3, in <module>
          print(Count)
      NameError: name 'Count' is not defined
  required concept:
    - Variable names are case sensitive.
  required fix:
    - Change `print(Count)` to `print(count)`.
""".strip()
    )

    populate_error_code_fields(rubric)

    contents = rubric.read_text()
    assert "code:" in contents
    assert "03| print(Count)" in contents
    assert "error line:" in contents
    assert "line 3: print(Count)" in contents


def test_populate_error_code_fields_uses_step_code_with_numbered_lines(tmp_path):
    rubric = tmp_path / "example.yaml"
    rubric.write_text(
        """
issue 1:
  traceback:
    - |-
      Traceback (most recent call last):
        File "/tmp/example.py", line 3, in <module>
          print(Count)
      NameError: name 'Count' is not defined
  intended behavior:
    - Print the current count.
  required concept:
    - Variable names are case sensitive.
  required fix:
    - Change `print(Count)` to `print(count)`.
""".strip()
    )

    populate_error_code_fields(rubric, "count = 0\nextra = 5\nprint(Count)\n")

    contents = safe_load(rubric.read_text())
    assert contents["issue 1"]["code"] == "01| count = 0\n02| extra = 5\n03| print(Count)"
    assert contents["issue 1"]["error line"] == ["line 3: print(Count)"]


def test_populate_error_code_fields_quotes_plain_scalars_with_colons(tmp_path):
    rubric = tmp_path / "example.yaml"
    rubric.write_text(
        """
issue 1:
  traceback:
    - |-
      Traceback (most recent call last):
        File "/tmp/example.py", line 2, in <module>
          password == get_credential(Set Password: )
      NameError: name 'password' is not defined
  required fix:
    - Change password == get_credential(Set Password: ) to an assignment.
""".strip()
    )

    populate_error_code_fields(rubric, "password == get_credential(Set Password: )\n")

    contents = safe_load(rubric.read_text())
    assert contents["issue 1"]["required fix"] == [
        "Change password == get_credential(Set Password: ) to an assignment."
    ]


def test_populate_correct_code_field_creates_rubric_with_numbered_lines(tmp_path):
    rubric = tmp_path / "example.yaml"

    populate_correct_code_field(rubric, "count = 0\nprint(count)\n")

    contents = safe_load(rubric.read_text())
    assert contents["correct code"] == "01| count = 0\n02| print(count)"


def test_apply_single_replacement_changes_only_requested_fragment():
    code = 'password == get_credential(Set Password: )\n'

    next_code = _apply_single_replacement(code, "==", "=")

    assert next_code == 'password = get_credential(Set Password: )\n'


def test_apply_single_replacement_rejects_ambiguous_fragments():
    code = "count == count\n"

    with pytest.raises(ValueError, match="exactly once"):
        _apply_single_replacement(code, "count", "total")
