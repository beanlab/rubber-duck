from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai.types.responses import Response

    from src.duck_protocols import DuckConversation


class RecordedResponses:
    # Observe the injected provider client's create operation without replacing the model loop.
    def __init__(
        self,
        create_response: Callable[..., Awaitable[Response]],
        record: Callable[[dict], None],
    ):
        ...

    # Record actual provider requests, raw responses, usage, and errors while forwarding unchanged.
    async def create(self, **request) -> Response:
        ...


# Open an isolated test environment and release only its owned resources on exit.
@asynccontextmanager
async def open_environment(
    config: dict,
    inputs: dict,
    directory: Path,
    *,
    live: bool = False,
    scripted_responses: list[dict] | None = None,
) -> AsyncIterator[dict]:
    ...


# Resolve allowed overrides and invoke the selected production duck builder.
def build_duck(
    environment: dict, name: str, *, dataset_dir: Path | None = None
) -> DuckConversation:
    ...


# Reject prompt comparisons when observed candidate settings are missing or mismatched.
def verify_candidate(expected: dict, observed: dict) -> None:
    ...


# Execute and record one production stage within a real Quest context.
async def run_stage(
    environment: dict, operation: Callable[..., Awaitable[object]], *args, **kwargs
) -> object:
    ...


# Collect a complete reply and confirm readiness before another user turn is sent.
async def wait_for_turn(
    environment: dict, workflow_id: str, *, after_event: int, timeout: float
) -> list[dict]:
    ...


# Drive the real router, Quest manager, and orchestrator with the supplied duck and user turns.
async def run_conversation(
    environment: dict, duck: DuckConversation, turns: list[str]
) -> list[dict]:
    ...
