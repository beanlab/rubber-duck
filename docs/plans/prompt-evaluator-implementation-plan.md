# Experimental prompt evaluator implementation plan

## Metadata

- Feature: Response-level prompt evaluator prototype
- Status: implementing
- Last updated: 2026-09-25
- Planner approval: approved by user, 2026-09-25
- Final user confirmation: pending
- Governing specification: [prompt-evaluator-specification.md](../../research/prompt-evaluator-specification.md)
- Supporting design: [prompt-evaluator-design.md](../../research/prompt-evaluator-design.md)
- System context: [current-system-evaluation-design.md](../../research/current-system-evaluation-design.md)
- Adversarial review: [prompt-evaluator-implementation-plan-adversarial-review.md](prompt-evaluator-implementation-plan-adversarial-review.md)

## 1. Outcome

Build a small, replaceable prototype that can run two tutoring prompt candidates on the same response-level scenarios, preserve inspectable evidence, apply deterministic and semantic graders, compare paired results, and produce an exploratory report.

The prototype is an experiment, not a production evaluation platform. Its first purpose is to discover whether the proposed evidence, grading, and comparison contracts are usable. It should be possible to revise or discard its runner, grader prompt, schemas, and report without coupling those choices to Discord or the rest of the application.

The durable boundary is the experiment vocabulary: candidate, scenario, trial, artifact, grader, observation, comparison, and report.

## 2. Intent and constraints

### Goals

- Learn whether prompt behavior can be evaluated reproducibly outside Discord.
- Test the evaluator-agent approach rather than assume that an LLM judge is valid.
- Start with response-level guidance/scaffolding, subject accuracy, and answer disclosure.
- Preserve a path to the refactored completion layer and later conversation evaluation.
- Produce inspectable, regradable evidence rather than only a test pass/fail result.

### Non-goals

- A production service, web UI, or permanent database schema.
- Automatic prompt optimization or deployment.
- A universal prompt-quality score.
- Live Discord or multi-turn simulated learners in the first vertical slice.
- Confirmatory claims from development cases or an unqualified model judge.
- Refactoring the current conversation system as part of this work.

### Constraints

- The downloaded feedback-linked message export cannot reconstruct complete standard-tutor conversations.
- Historical conversation use requires explicit privacy and data-use approval.
- `origin/bean-ai-refactor` expresses the desired Discord-free boundary but is not currently a conformant, runnable replacement for `AIClient`.
- A coworker owns that refactor; evaluation integrates through an adapter rather than absorbing their work.
- Experimental outputs may contain sensitive material and must remain under ignored `data/` storage.
- Normal tests must not require provider credentials.

## 3. Working decisions

These choices allow implementation without pretending unresolved research questions are settled.

| Topic | Prototype decision | Status |
|---|---|---|
| First unit | One candidate response to one fixed learner checkpoint | Fixed for Stage 1 |
| Initial criteria | Guidance/scaffolding, subject accuracy, answer disclosure | Fixed by specification |
| Primary criterion | Guidance/scaffolding | Provisional |
| First data | Checked-in synthetic/redacted controls and manually authored checkpoints | Fixed until data approval |
| Historical data | Do not read into runs or send to a provider without an approved privacy manifest | Hard gate |
| Execution modes | Recorded responses first; standalone completions second | Fixed sequence |
| Candidate generation | Same model/settings/history; only the resolved prompt differs in a prompt-only comparison | Fixed |
| Repetitions | Configurable; three per candidate/scenario for the first costed smoke test | Provisional, not a statistical guarantee |
| Semantic grading | Criterion-specific pointwise grading first; pairwise/order-swap grading tested separately | Provisional |
| Human review | Two independent reviewers on overlapping sealed cases before decision-grade judge use | Qualification requirement |
| Early decisions | Exploratory or inconclusive only | Fixed until validation gates pass |
| Storage | Versioned JSON under `data/evaluations/<run-id>/` | Replaceable |
| Checked-in assets | Schemas, non-sensitive declarations, prompts, and development-only synthetic fixtures | Fixed |
| Discord | Deferred to a bridge experiment | Fixed for Stage 1 |

The production baseline and first subtle prompt hypothesis remain team decisions. Before then, obvious known-bad, clear-positive, and no-effect candidates will test whether the evaluator reacts in the expected direction. Checked-in controls can test mechanics and expose regressions, but cannot serve as a sealed qualification set after their labels have influenced implementation.

## 4. Proposed repository shape

The prototype should be a normal Python package with a thin script entry point. The domain core must not import Discord, `DuckContext`, TesterBot, or SQL storage.

```text
src/evaluation/
  __init__.py
  schemas.py          # versioned Pydantic evidence envelopes
  lifecycle.py        # explicit run/trial transitions
  artifacts.py        # filesystem store and digest handling
  protocols.py        # runner and grader interfaces
  execution.py        # paired/interleaved orchestration
  grading.py          # deterministic and semantic grading
  calibration.py      # judge qualification and probes
  comparison.py       # paired analysis and decision gating
  reporting.py        # JSON summary and Markdown report
  adapters/
    recorded.py       # imports existing response artifacts
    standalone.py     # conformance-qualified completion boundary

scripts/
  prompt_eval.py      # validate, run, grade, analyze, report

evaluation_assets/
  README.md
  criteria/           # versioned rubric definitions
  controls/           # non-sensitive controls and attack cases
  examples/           # example declarations and scenarios

tests/evaluation/
  fixtures/
  test_schemas.py
  test_lifecycle.py
  test_artifacts.py
  test_execution.py
  test_grading.py
  test_calibration.py
  test_comparison.py
  test_reporting.py
  test_standalone_adapter.py
```

This is a target layout, not a requirement to create every module before its phase begins.

## 5. Core contracts

### 5.1 Versioned artifact envelope

Every stored object includes a schema version, stable object ID and type, creation time, producer/run identity, content digest, payload, lineage or supersession metadata, and sensitivity classification. IDs are independent of Discord identifiers. Serialization for digests is canonical, writes are atomic, and evidence is never silently overwritten.

Externally supplied IDs must not become filesystem paths without validation. The store rejects traversal, absolute paths, symlink escapes, digest collisions, and ambiguous Unicode identifiers. Concurrent writes use explicit collision/locking semantics, and a partially written object cannot be observed as valid evidence.

Sensitivity-aware views separate raw evidence from reports. Ignoring `data/` in Git is not a privacy control: logging, terminal output, CI artifacts, generated reports, backups, and model-provider egress each need declared handling. Before any non-synthetic data is admitted, the store must support retention dates, deletion lineage, and content removal with a non-content tombstone where lineage must remain.

### 5.2 Evaluation declaration

Before execution, a machine-readable declaration specifies:

- question, claim type, candidates, and treatment;
- fixed model/settings/tools/output contract;
- scenarios, source families, and partitions;
- criteria, guardrails, repetitions, ordering, retries, and stopping policy;
- runners and graders;
- missingness, exclusion, abstention, and failure policy;
- qualification thresholds and decision policy;
- privacy-manifest reference;
- exploratory or validation status.

It also records the code revision, dependency-lock digest, adapter version, evaluator versions, provider model identifiers or fingerprints when available, budget ceiling, and expected upper bounds on candidate and grader calls.

Validation rejects a prompt-only declaration when non-prompt candidate settings differ.

### 5.3 Candidate and scenario

A candidate stores the resolved prompt and digest, not only a path or label. It also records prompt-source and included-fragment digests so the resolver can be audited without treating a mutable file path as identity. A scenario separates model-visible history from evaluator-only references and also records learner state, permitted help, criterion applicability, slice/source-family labels, partition, provenance, and privacy status. Related checkpoints from one source family stay in one partition.

### 5.4 Trial artifact

A generated trial preserves candidate, scenario, repetition, planned and actual execution order, execution protocol, canonical request and digest, raw observable response items, projected user-visible response, usage, timing, retries, provider metadata, code revision, adapter identity, lifecycle, validity, outcome, and failure stage. Retries are events within one trial, not independent trials. Hidden reasoning is neither requested nor stored.

### 5.5 Observation

An observation stores its artifact, criterion, grader version, typed value and scale, status, evidence references, rationale, and grader provenance. Status distinguishes observed, abstained, not applicable, missing evidence, and grader error.

Semantic citations initially reference an artifact ID and exact character or item spans. Offsets are defined over the immutable stored Unicode string, with its normalization and encoding recorded. The cited text and digest must match the artifact or the observation is unsupported.

### 5.6 Replaceable protocols

Use structural protocols or small abstract interfaces:

- `CandidateRunner.run(candidate, scenario, trial_context) -> TrialArtifact`
- `Grader.grade(artifact, criterion, grader_context) -> Observation`
- `ArtifactStore.put/get/list`

Candidate execution and semantic grading may share a low-level provider client, but they have separate configurations, histories, retry budgets, and identities.

## 6. Lifecycle state machines

Use validated enums and transition functions rather than adding a workflow dependency.

```text
Run:
draft -> validated -> prepared -> running -> executed
     -> grading -> graded -> analyzed -> reported
Any active state -> failed or cancelled

Trial:
pending -> running -> succeeded
                   -> failed
                   -> invalid
```

Validity, candidate outcome, and failure stage remain orthogonal fields rather than becoming dozens of terminal states. Invalid transitions fail loudly.

## 7. Implementation phases

### Phase 0: Freeze the first vertical slice

Deliverables:

- Approve this plan.
- Select one narrow behavior and finalize anchors for the three criteria.
- Create a non-sensitive privacy manifest for synthetic fixtures.
- Choose obvious control candidates and 6–10 synthetic or manually authored checkpoints.
- Define the cost ceiling and credentials policy for live calls.
- Record the completion-refactor revision intended for later integration.

Exit criteria:

- The first experiment requires no historical Discord data.
- Scenarios contain enough learner-state and reference evidence to be graded.
- Early reports are explicitly exploratory.

### Phase 1: Offline evidence vertical slice

Implement schemas, lifecycle validation, filesystem storage, a recorded-response adapter, simple deterministic graders, paired descriptive comparison, and JSON/Markdown reporting.

The no-network slice will:

1. Validate a declaration.
2. Import recorded candidate responses.
3. Produce deterministic observations and import manual labels.
4. Compare paired candidates.
5. Generate an evidence-linked report.
6. Regrade and reanalyze without regenerating responses.

Tests cover schema round trips and version rejection, digest mismatch, overwrite prevention, treatment isolation, lifecycle transitions, distinct missing/abstention/error states, scenario-level grouping, deterministic reanalysis, and `invalid`/`inconclusive` handling.

They also cover path traversal and symlink escape attempts, concurrent/colliding writes, interrupted writes, sensitivity-aware report rendering, and refusal to resume when the declaration, code, adapter, or evidence-schema digest has changed. A changed run must fork to a new run ID with explicit lineage.

Exit criteria:

- One no-network command recreates a report from fixtures.
- Every reported value resolves to stored evidence.
- No runtime import requires Discord or a provider key.

### Phase 2: Standalone execution and adapter conformance

Add generation through a narrow standalone adapter. Do not copy `origin/bean-ai-refactor`; integrate its successor once the coworker's public interface is ready.

Fake-provider conformance tests prove that:

- the resolved prompt is actually sent;
- ordered model-visible history matches the scenario;
- model, reasoning, tools, tool choice, and output format match the declaration;
- raw output items and usage survive without lossy conversion;
- errors, retries, and timeouts remain distinguishable;
- tool-loop ownership is explicit;
- no `DuckContext` is needed for a tool-free trial.

The orchestrator adds paired scheduling, counterbalanced order with a recorded seed, repetitions, bounded concurrency, immediate durable writes, safe resume behavior, and failure classification. It records actual start/completion order and bounded execution windows so concurrency cannot silently defeat interleaving.

Before live execution, a dry run computes the maximum candidate calls, grader calls, tokens where estimable, and monetary cost. A hard call/cost circuit breaker stops new work without deleting completed evidence. Resume is allowed only under the identical frozen declaration and implementation identities. Provider model fingerprints, request IDs, and time windows are captured when available; results from materially different provider behavior are not pooled without an explicit analysis decision.

Exit criteria:

- Two prompts run on the same scenarios outside Discord.
- Request digests identify the prompt and history sent.
- Fake-provider tests pass in CI.
- Credentialed smoke tests are opt-in and budget limited.

Application-equivalence claims remain prohibited until a later golden-trace bridge study compares the stable refactor and application paths.

### Phase 3: Semantic evaluator and prequalification harness

Implement an isolated no-tool judge with structured criterion-level output. Candidate response, learner content, and references are typed untrusted evidence, separate from evaluator instructions.

Add pointwise graders, abstention/not-applicable output, citation validation, preserved grader errors, independent retries, blinded labels, repeats, pairwise order swaps, immutable sentinels, and human-label import.

The synthetic qualification suite covers:

- clear positive, negative, borderline, and insufficient-evidence cases;
- response and learner-text prompt injection;
- fake system messages and delimiter escapes;
- rubric impersonation and self-awarded scores;
- concise/padded and plain/polished transformations;
- cautious/unjustifiably confident tone;
- pairwise order reversal;
- generator/evaluator family or self-preference effects where a feasible comparison exists;
- known-bad, clear-positive, and no-effect controls.

Calibration reports criterion-level confusion or transition tables, uncertainty-aware agreement, severe false passes, gradable coverage, abstention, repeatability, order sensitivity, and probe failures. Raw agreement alone is insufficient.

Synthetic and checked-in labels qualify the harness mechanics, not the judge for real tutoring decisions. They may support only exploratory use until Phase 5 supplies independently created, sealed human labels. Sentinel cases run at the start and end of bounded grader batches; a material sentinel shift invalidates or separates that batch rather than being averaged away.

Exit criteria:

- Each criterion has a provisional supported use: exploratory or unsupported. Broader supported use requires Phase 5.
- A criterion that misses its frozen threshold cannot influence `better`, `not worse`, or `worse`.
- Injection and malformed-output failures remain visible.

### Phase 4: First exploratory prompt experiment

Run three checks:

1. Known-bad versus clear-positive sensitivity controls generated through the candidate adapter.
2. A no-effect control using duplicated artifacts to test grader invariance and behaviorally equivalent prompts to test the full live path.
3. The production baseline versus one purposeful variant on development scenarios.

Freeze the declaration and control expectations before execution, hold non-prompt configuration constant, interleave order, initially use three repetitions within the approved budget, keep criteria separate, retain failures and ungradable outputs, and separate generation from grading cost. Recorded or hand-authored responses can test artifact and grader mechanics but cannot demonstrate that a prompt caused the behavior.

Do not tune grader instructions, thresholds, or candidate prompts on a control and then report that same control as independent sensitivity evidence. Any post-result change creates a new development run; the original result remains preserved. Subject accuracy uses an executable or expert oracle when available rather than defaulting to the model judge.

Report paired category transitions and win/loss/tie counts rather than averaging ordinal labels. Include repetition variability, source-family grouping, and representative cases selected by declared rules.

Exit criteria:

- Controls move in the expected direction without a false no-effect difference.
- The report rebuilds from stored artifacts without provider calls.
- It can conclude `inconclusive` or `invalid` and makes no deployment-grade claim.
- The experiment records which schemas, protocols, and graders to keep, revise, or discard.

### Phase 5: Human qualification and sealed validation

Begin only when approved complete data and reviewers are available.

- Obtain data-use approval and a complete transcript source, or use independently authored domain cases.
- Have at least two qualified reviewers label an overlapping qualification set independently.
- Preserve original labels before adjudication.
- Predeclare minimum class/slice coverage and uncertainty requirements; two reviewers alone do not make a small or homogeneous set adequate.
- Freeze judge protocol and thresholds before opening qualification cases.
- Freeze prompt candidates and a separate validation declaration before opening validation cases.
- Use only qualified criteria for a validation decision; otherwise use humans or stay exploratory.

Any claim is bounded to the declared sample, model, configuration, and protocol. Human disagreement remains visible. Before private data enters the system, verify end-to-end deletion from scenarios, responses, observations, reports, caches, and backups, leaving only approved non-content tombstones.

### Phase 6: Conversation and application integration

After the response-level contracts prove useful:

- Add a scripted or branching in-memory learner that owns history.
- Extend trials with ordered trace events and outcomes.
- Use state-machine checks for tool pairing, workflow transitions, and termination.
- Compare local and application golden traces.
- Use TesterBot selectively for Discord routing, delivery, thread lifecycle, and fidelity.

Extend or migrate response schemas instead of stretching them into an ambiguous conversation record.

## 8. Prototype analysis and decision policy

Required outputs are scenario/source-family counts, trial completion by candidate, separate criterion distributions, paired transitions, pairwise win/loss/tie/abstain counts where applicable, candidate-specific failures and missingness, within-scenario variability, cost/latency/usage, grader qualification, and evidence-linked disagreements. Standard reports default to redacted excerpts or artifact IDs according to sensitivity; access to a report never implies access to raw evidence.

Small convenience samples do not justify population estimates. Any interval must resample the declared independent scenario or source-family cluster rather than individual repetitions.

Decision gates run in order:

1. Protocol and provenance valid?
2. Required evidence and coverage present?
3. Applicable semantic graders qualified?
4. Hard guardrails satisfied?
5. Frozen comparison rule and practical margin satisfied?
6. Otherwise `inconclusive`; use `invalid` when the requested claim cannot be made.

During Phases 1–4, grader qualification deliberately blocks confirmatory labels while retaining exploratory comparisons.

## 9. Test strategy

### Unit and contract tests

- Schemas, versions, canonicalization, and digests.
- State transitions and orthogonal failure fields.
- Treatment-isolation validation.
- Adapter request construction and raw response preservation.
- Grader parsing, abstention, citation bounds, and injection fixtures.
- Paired grouping, missingness, and ordinal analysis.
- Deterministic reports from frozen artifacts.
- Safe configuration parsing: no arbitrary object construction, code execution, path escape, or unrestricted includes.
- Budget preflight, hard circuit breaking, and partial-run reporting.
- Sensitivity-aware logs/reports and deletion-lineage propagation.

### Metamorphic judge tests

- Candidate renaming must not change a grade.
- Content-preserving style changes should not materially change pointwise grades.
- Pairwise A/B swaps must expose reversals.
- Adding rubric language without better behavior must not improve a grade.
- Embedded evidence instructions must not change the evaluator task.

### Integration tests

- Offline fixture-to-report vertical slice.
- Fake-provider generation followed by saved-artifact grading.
- Regrading with a new grader version while retaining old observations.
- Interrupted-run resume without lost or duplicated trials.

Live provider and Discord tests are separately marked and skipped by default. They require explicit credentials, budget limits, and retention settings.

## 10. Existing code reuse

Reuse Pydantic structured-output patterns from `src/storage/assessment_models.py`, assessor/history-formatting lessons from `src/testing/tester_bot_scaffold/assessments.py`, TesterBot cost concepts, and retry utilities only when retry events remain observable. TesterBot later becomes a transport adapter, not the evaluator core.

Do not reuse the broad pass/fail assessor result as the observation model or call private `AIClient._client` methods. The standalone adapter depends on a public refactor contract or a narrowly owned provider adapter.

## 11. Principal risks

| Risk | Mitigation |
|---|---|
| Infrastructure precedes evidence that criteria are gradeable | Deliver controls and an offline slice first |
| Refactor interface changes | Isolate it behind `CandidateRunner` |
| Judge looks precise but disagrees with humans | Require sealed, criterion-specific qualification |
| Prompt injection manipulates the judge | Isolate evidence, remove tools, and run attacks |
| Typed evidence boundaries are mistaken for an injection guarantee | Treat them as one defense and require observed attack-suite behavior |
| A small sample looks conclusive | Use exploratory labels and explicit scope limits |
| Repetitions are counted as independent | Group by scenario/source family in schemas and analysis |
| Candidate failures disappear through exclusion | Report by candidate under a frozen missingness policy |
| Sensitive data reaches Git or providers | Privacy manifests, ignored artifacts, and hard gates |
| Raw evidence leaks through logs, reports, CI, caches, or backups | Sensitivity-aware rendering plus end-to-end retention/deletion tests |
| Offline behavior differs from Rubber Duck | Require conformance and a golden-trace bridge |
| Early evidence schemas prove weak | Version and migrate them rather than promise permanence |
| A live run exceeds its intended cost | Preflight call bounds and enforce a runtime circuit breaker |
| Resume mixes changed code or declarations into one run | Require identity matches or fork a lineage-linked run |

## 12. Acceptance criteria

- [ ] A declaration records treatment, fixed configuration, scenarios, graders, policies, and exploratory status.
- [ ] Treatment-isolation validation rejects mismatched non-prompt settings.
- [ ] Synthetic/recorded fixtures run end to end without Discord, credentials, or private data.
- [ ] Two prompts run through a conformance-tested standalone adapter on the same scenarios.
- [ ] Requests, responses, usage, retries, timing, failures, and provenance are stored.
- [ ] Deterministic and semantic observations remain separate and evidence-linked.
- [ ] Guidance, accuracy, and disclosure are reported separately.
- [ ] Responses can be regraded and reanalyzed without rerunning candidates.
- [ ] Judge qualification measures human agreement, severe errors, repeatability, order/style effects, and injection resistance.
- [ ] Unqualified criteria cannot create a confirmatory prompt decision.
- [ ] Analysis respects scenario repetitions and source-family clustering.
- [ ] Candidate-specific missingness and failures remain visible.
- [ ] Reports support `inconclusive` and `invalid`.
- [ ] Known-bad, clear-positive, and no-effect controls are demonstrated.
- [ ] Recorded-response results are never represented as causal prompt evidence.
- [ ] Development controls and sealed qualification cases remain distinct.
- [ ] Budget preflight and circuit breaking preserve a reportable partial run.
- [ ] Artifact IDs, configuration input, concurrent writes, and resume paths pass adversarial storage tests.
- [ ] Reports, logs, caches, and deletion lineage respect sensitivity policy.
- [ ] Live tests are opt-in and budget bounded.
- [ ] Sensitive artifacts remain ignored under `data/evaluations/`.
- [ ] No application-equivalence claim precedes the bridge study.

## 13. Approval checkpoints

Implementation pauses for decisions at:

1. **Plan approval:** scope, repository boundary, and phase order.
2. **Live-call approval:** models, repetitions, preflight call counts, and cost ceiling.
3. **Data approval:** privacy manifest, historical source, report access, retention, deletion, backup, and provider-egress policy.
4. **Validation approval:** frozen rubrics, thresholds, prompts, sample, and decision policy.

These checkpoints do not block Phase 1 or fake-provider work in Phase 2.

## 14. First code change after approval

The first change includes only:

1. Minimal candidate, scenario, declaration, trial, grader, and observation schemas.
2. Filesystem storage under an injected root.
3. A recorded-response runner.
4. One deterministic evidence-integrity grader.
5. Paired descriptive comparison supporting `inconclusive` and `invalid`.
6. JSON and Markdown reports.
7. Synthetic known-bad, clear-positive, and no-effect fixtures.
8. No-network tests for the complete fixture-to-report path.
9. Adversarial filesystem/configuration and sensitivity-aware report tests.

Semantic calls, the completion adapter, historical data, multi-turn state, and Discord stay outside this first change. This tests the evidence architecture before external behavior makes failures harder to diagnose.

## 15. Decisions log

- 2026-09-25: Treat this as an experimental prototype with an intended integration path, not a production subsystem.
- 2026-09-25: Separate response-level evaluation from later conversation-level evaluation.
- 2026-09-25: Treat evaluator agents as measurement instruments requiring human calibration.
- 2026-09-25: Begin with recorded and synthetic evidence because the available historical export is incomplete.
- 2026-09-25: Keep Discord and completion details behind replaceable adapters.

## 16. Change log

- 2026-09-25: Initial plan derived from the evaluator specification, system design, adversarial review, tests, and completion-refactor inspection.
- 2026-09-25: Phase 1 offline vertical slice implemented with strict artifacts, recorded responses, deterministic integrity checks, paired comparison, aggregate reports, and synthetic controls.
