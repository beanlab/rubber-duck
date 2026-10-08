# Coding Guidelines

## Python typing

- Never use `Any`, including `typing.Any`, implicit `Any`, or unparameterized containers.
- Use the actual SDK type, a concrete application type, `Protocol`, `TypedDict`, or a dataclass.
- At genuinely unknown boundaries, accept `object` and validate or narrow it before use.
- Do not use `cast`, `# type: ignore`, or an overly broad type merely to silence a type error. Fix the type contract instead.
