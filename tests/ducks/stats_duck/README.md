# Stats Duck tests

This guide describes the Stats pytest suite. Cases use ordinary pytest parameters
under `tests/ducks/stats_duck/`; there is no separate Stats test framework.
The live response and isolated delivery cases are implemented. The new
application-level and numerical tests remain skipped signatures.

- `test_responses.py` evaluates decisions, canonical orders, generated code,
  and fixed/model-produced stage handoffs. The handoff tests are diagnostics,
  not a replacement for production workflow control.
- `test_workflow.py` preserves the existing live delivery cases and declares
  future full-application, numerical, clarification, artifact, follow-up, cache,
  and repair checks.
- `conftest.py` supplies known dataset metadata, the live provider client, and
  the production builder with controlled dependencies.
- `fakes.py` supplies the existing message and sandbox doubles.
- `assertions.py` contains small Stats-specific checks.

Append a `pytest.param` row to add an input to an existing behavior. Add a normal
pytest function when different execution or assertions are needed. There is no
case registration, YAML action field, or stage dispatcher to update.

The commands below select live model evaluations and require `OPENAI_API_KEY`.

```bash
poetry run pytest tests/ducks/stats_duck -m prompt_eval -vv -s
poetry run pytest tests/ducks/stats_duck -k decide-ready-histogram -vv -s
poetry run pytest tests/ducks/stats_duck -k decision-to-order -vv -s
poetry run pytest tests/ducks/stats_duck -k full -vv -s
```

Existing delivery cases run the production Stats workflow directly with a fake
sandbox. They check code shape and delivery, not numerical correctness, real
application routing, or real Quest. The new shared application drivers and
workflow declarations remain signatures only. See
[the design](../../../evaluation/docs/evaluation-design.md) for the intended coverage.
