import argparse
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI
import yaml


class CodeDuckDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def _represent_str(dumper: yaml.Dumper, value: str):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


CodeDuckDumper.add_representer(str, _represent_str)


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return loaded


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _first_key(mapping: dict[str, Any]) -> str:
    try:
        return next(iter(mapping))
    except StopIteration:
        raise ValueError("source rubric must contain at least one topic")


def _extract_yaml(response_text: str) -> str:
    stripped = response_text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _contains_placeholder(text: str) -> bool:
    placeholders = [
        "Replace this with",
        "Buggy code example for:",
        "TODO",
        "fix me",
    ]
    return any(placeholder.lower() in text.lower() for placeholder in placeholders)


def _contains_traceback(text: str) -> bool:
    return "Traceback (most recent call last):" in text and "Error:" in text


def _validate_code_duck_rubric(rubric: Any) -> dict[str, Any]:
    if not isinstance(rubric, dict) or not rubric:
        raise ValueError("generated rubric must be a non-empty YAML mapping")

    full_project = rubric.get("full project")
    if not isinstance(full_project, str) or not full_project.strip():
        raise ValueError("generated rubric must include a non-empty 'full project' string")
    if _contains_placeholder(full_project):
        raise ValueError("generated rubric full project still contains placeholder text")

    topic_count = 0
    for topic, topic_body in rubric.items():
        if topic == "full project":
            continue

        topic_count += 1
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("generated rubric topic keys must be non-empty strings")
        if not isinstance(topic_body, dict) or not topic_body:
            raise ValueError(f"generated rubric topic '{topic}' must contain principles")

        for principle, examples in topic_body.items():
            if not isinstance(principle, str) or not principle.strip():
                raise ValueError(f"generated rubric topic '{topic}' contains an empty principle")
            if not isinstance(examples, list) or not examples:
                raise ValueError(f"generated rubric principle '{principle}' must contain example strings")
            for example in examples:
                if not isinstance(example, str) or not example.strip():
                    raise ValueError(f"generated rubric principle '{principle}' contains an empty example")
                if _contains_placeholder(example):
                    raise ValueError(f"generated rubric principle '{principle}' still contains placeholder text")
                if not _contains_traceback(example):
                    raise ValueError(f"generated rubric principle '{principle}' must include captured traceback text")

    if topic_count != 1:
        raise ValueError("generated rubric must include exactly one topic plus 'full project'")

    return rubric


def _response_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    chunks: list[str] = []
    for output in getattr(response, "output", []):
        for content in getattr(output, "content", []):
            text = getattr(content, "text", None)
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def generate_code_duck_rubric(
        source_rubric: dict[str, Any],
        style_rubric: dict[str, Any],
        prompt: str,
        topic: str | None = None,
        model: str = "gpt-5.4-mini",
        client: OpenAI | None = None,
) -> dict[str, Any]:
    client = client or OpenAI()
    target_topic = topic or _first_key(source_rubric)
    generation_input = "\n\n".join([
        f"Target topic: {target_topic}",
        "Source rubric:",
        yaml.safe_dump(source_rubric, sort_keys=False),
        "Style example:",
        yaml.safe_dump(style_rubric, sort_keys=False),
    ])

    response = client.responses.create(
        model=model,
        instructions=prompt,
        input=generation_input,
    )
    generated_yaml = _extract_yaml(_response_text(response))
    generated = yaml.safe_load(generated_yaml)
    return _validate_code_duck_rubric(generated)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a full code-duck debugging rubric from another YAML rubric."
    )
    parser.add_argument("--source", required=True, type=Path, help="Existing YAML rubric to transform.")
    parser.add_argument(
        "--style",
        type=Path,
        default=Path(__file__).with_name("example.yaml"),
        help="Style example YAML. Loaded to validate the expected rubric shape.",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        default=Path(__file__).with_name("yaml-example-gen.md"),
        help="Markdown prompt file for the rubric-generation agent.",
    )
    parser.add_argument("--model", default="gpt-5.4-mini", help="OpenAI model used by the generator agent.")
    parser.add_argument("--topic", help="Root topic key for the generated rubric. Defaults to source root key.")
    parser.add_argument("--output", type=Path, help="Output YAML path. Defaults to stdout.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    style_rubric = _load_yaml(args.style)
    source_rubric = _load_yaml(args.source)
    prompt = _load_text(args.prompt)
    generated = generate_code_duck_rubric(
        source_rubric,
        style_rubric,
        prompt,
        topic=args.topic,
        model=args.model,
    )
    output = yaml.dump(generated, Dumper=CodeDuckDumper, sort_keys=False, width=1000)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
