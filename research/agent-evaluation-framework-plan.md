# Agent Evaluation Framework Plan

## Metadata

- Feature: General-purpose Agent Evaluation framework and prompt-comparison experimentation
- Status: planning
- Last Updated: 2026-09-22
- Specification: [Agent Evaluation Framework: Design Specification](agent-evaluation-specification.md)
- Research: [research synthesis](research-synthesis.md)
- Planner Approval: pending
- Final User Confirmation: pending
- Implementation authorization: not granted

## User intent

### Goal

Develop a framework that can produce useful, reproducible evidence about agent behavior, beginning with the motivating question: whether one prompt works better than another. The user should understand and approve the problem definition, framework model, experiment design, and staged implementation before code is written.

### Non-goals

- Do not write framework or application code during the current planning task.
- Do not presume the TesterBot, transcript judge, or pass/fail rubric battery is the target architecture.
- Do not promise a universal agent-quality score or fully automated prompt selection.
- Do not treat transcript quality as proof of student learning.
- Do not authorize production experiments or collection of additional student data.

### Constraints

- Preserve unrelated working-tree changes.
- Reuse repository assets only after checking their provenance and fitness for the new purpose.
- Support current Rubber Duck workflows without coupling the conceptual framework to Discord or one workflow implementation.
- Keep evaluation observations distinct from deployment decisions.
- Treat model nondeterminism, evaluator bias, privacy, cost, and reproducibility as design constraints.

## Facts versus assumptions

### Facts established from the repository

- Rubber Duck has conversational, tool-using, and structured workflow agents with materially different notions of success.
- Agent definitions include prompt content, model settings, tools, output format, and reasoning configuration.
- The AI client has a model/tool loop and records some tool and message activity, but not yet a framework-neutral evaluation trace.
- Existing TesterBot tests can run real Discord conversations with a model-simulated student and model assessors.
- Current assessor storage primarily represents binary pass/fail or catch/pass results with reasoning.
- Debugging practice has the richest pedagogical assessor battery and explicit workflow progression.
- Registration and parts of assignment feedback expose more deterministic state and output properties.
- Statistics workflows provide machine-checkable calculations and tool behavior in addition to semantic explanation quality.
- Production metrics record messages, token usage, and TA feedback, but are not linked to controlled candidate comparisons.
- Archived conversation suites exist, but their provenance, privacy status, and label quality have not been established.

### Working assumptions requiring confirmation

- Prompt comparison is the first high-value use case, while the framework should remain suitable for broader system comparisons.
- The first experiments may use test fixtures, test Discord resources, and model API calls, but no real student participation.
- A small amount of expert human review can eventually be made available for rubric and judge calibration.
- Prompt variants can be resolved into immutable artifacts or at least content digests.
- Tool and workflow side effects can be mocked or isolated for repeatable testing.
- An inconclusive result is acceptable when the evidence is insufficient.

## Acceptance criteria for the planning phase

- [x] Research establishes evaluation terminology, evidence types, limitations, and alternative approaches.
- [x] The relevant Rubber Duck runtime, workflows, prompts, tests, and telemetry have been inspected.
- [x] A repository-specific framework specification exists without application code changes.
- [x] The specification explicitly describes fair prompt comparisons.
- [x] The specification separates general architecture from current TesterBot mechanisms.
- [x] A staged implementation and experimentation plan exists for discussion.
- [ ] The user can explain, in their own terms, the motivating decision and why prompt text alone is not evaluated.
- [ ] The initial pilot and first real prompt comparison are selected.
- [ ] Primary measure, guardrails, human-review budget, and practical decision threshold are agreed.
- [ ] Data/privacy and execution-environment boundaries are agreed.
- [ ] The specification and plan are approved before implementation begins.

## Proposed plan

The phases below are intentionally separated by approval gates. Later phases describe prospective implementation work; none should start until the user approves the specification and preceding gate.

### Phase 0: Align on the decision and vocabulary

Purpose: ensure that the framework answers a real decision rather than merely generating scores.

- [ ] Review the specification's core entities: candidate, requirement, scenario, trial, trace, outcome, grader, observation, comparison, and decision policy.
- [ ] Agree that “prompt comparison” means only the prompt treatment changes; otherwise call it a system comparison.
- [ ] Select a concrete future prompt decision.
- [ ] Write the decision question in one sentence.
- [ ] Identify the intended users and scenario population.
- [ ] Name one primary measure, the most important guardrails, and the minimum practically meaningful improvement.
- [ ] Decide which properties are hard gates and which are trade-offs.
- [ ] Record what evidence would cause “better,” “worse,” and “inconclusive” conclusions.

Gate 0: The user approves the problem statement and conceptual model. Approval does not yet authorize production-data use or application changes.

### Phase 1: Design two bounded pilots on paper

Purpose: validate both the framework mechanics and the motivating semantic use case without trying to cover every workflow.

#### Pilot A: framework sensitivity

- [ ] Choose either statistics or registration as an objective/trace-heavy workflow.
- [ ] Define a small, reviewed scenario matrix including success, malformed input, edge, and failure-recovery cases.
- [ ] Define two controlled candidates with one known bounded behavioral difference.
- [ ] Specify exact outcome checks, trace properties, failure classification, repetitions, and operational measures.
- [ ] Define the expected direction of results without exposing it to graders that should be blind.
- [ ] State why success would demonstrate evaluator sensitivity rather than production prompt superiority.

#### Pilot B: tutoring prompt comparison

- [ ] Select a baseline prompt and a purposeful candidate prompt hypothesis.
- [ ] Build a scenario blueprint across subject, difficulty, learner state, misconception, direct-answer request, ambiguity, accessibility, and adversarial behavior.
- [ ] Define scaffolding or another agreed pedagogical property as the primary measure.
- [ ] Define accuracy, direct-answer disclosure, safety, and correct termination as guardrails.
- [ ] Define cost, latency, turns, retries, and reliability as secondary measures.
- [ ] Draft a blinded human-review protocol and model-judge calibration sample.
- [ ] Separate development scenarios from a protected validation set.

Gate 1: The user approves both experimental protocols, or explicitly narrows the first implementation to one pilot.

### Phase 2: Specify contracts and artifact schemas

Purpose: make runs reproducible and implementations replaceable before connecting them to existing runtime code.

- [ ] Define machine-readable schemas for evaluation specifications, candidates, requirements, scenarios, trial policies, trials, trace events, outcomes, graders, observations, comparisons, and decision policies.
- [ ] Define stable IDs, content digests, versioning, and compatibility rules.
- [ ] Define validation errors that distinguish invalid experiment declarations from runtime failures.
- [ ] Define runner, environment, user-driver, grader, result-store, and report contracts.
- [ ] Define the status model for completed, timed-out, infrastructure-failed, agent-failed, invalidated, missing, and abstained results.
- [ ] Define how retries remain visible.
- [ ] Define artifact layout and/or storage boundaries without choosing an irreversible backend prematurely.
- [ ] Create example declarations for both pilots and review them without executing anything.

Gate 2: Contract review confirms that a non-Discord runner and a non-LLM grader can participate without special cases.

### Phase 3: Establish privacy, security, and provenance rules

Purpose: prevent experimentation infrastructure from becoming an uncontrolled student-data or side-effect channel.

- [ ] Classify candidate prompts, student inputs, uploaded files, model outputs, traces, and grader rationales.
- [ ] Decide whether production conversations may be used for discovery, replay, or neither.
- [ ] Define redaction, access, retention, export, and deletion rules.
- [ ] Prohibit storage of hidden chain-of-thought and secrets.
- [ ] Specify least-privilege test credentials and isolated external resources.
- [ ] Define prompt-injection boundaries between scenario data, agent prompts, grader prompts, and report rendering.
- [ ] Define provenance captured for provider models that do not expose immutable versions.
- [ ] Decide how sealed holdouts are protected from prompt authors and automated optimizers.

Gate 3: The appropriate project owner approves data and side-effect boundaries before any historical or live user data is ingested.

### Phase 4: Implement the minimal experiment core

Purpose: support a small end-to-end run using synthetic fixtures and objective evidence. This is future work and remains unauthorized until the preceding gates pass.

- [ ] Implement schema validation and immutable run manifests.
- [ ] Implement orchestration of paired candidates, scenarios, and repeated trials.
- [ ] Implement a local or sandbox runner before a Discord dependency is required.
- [ ] Capture a common observable trace and final outcome.
- [ ] Implement executable outcome and trace/property graders.
- [ ] Record latency, tokens, cost where available, errors, timeouts, and retries.
- [ ] Persist immutable raw trial artifacts and typed observations.
- [ ] Produce a simple inspectable run report with drill-down.
- [ ] Add framework self-tests using deliberately known pass, fail, invalid, missing, and abstain cases.

Gate 4: Pilot A detects the known behavioral difference, classifies infrastructure versus agent failures correctly, and reproduces its analysis from saved artifacts.

### Phase 5: Add paired comparison and decision analysis

Purpose: turn trial results into a defensible comparative answer.

- [ ] Aggregate at the scenario level while retaining repetition variance.
- [ ] Calculate paired deltas and uncertainty intervals appropriate to each measurement type.
- [ ] Report practical effect sizes, not only significance.
- [ ] Support prespecified slices and clearly label exploratory slices.
- [ ] Implement hard gates and non-inferiority guardrails separately from optimization measures.
- [ ] Support better, not-worse, worse, inconclusive, and invalid conclusions.
- [ ] Surface missingness, exclusions, invalid trials, and protocol deviations.
- [ ] Verify analysis on synthetic datasets with known outcomes and edge cases.

Gate 5: A reviewer can trace every comparison result to scenario-level values and raw evidence, and the system can correctly return “inconclusive.”

### Phase 6: Add semantic and human evaluation

Purpose: measure open-ended tutoring quality without representing a model judge as truth.

- [ ] Implement structured semantic grader outputs with evidence references and abstention.
- [ ] Blind graders to candidate identity and counterbalance pairwise order where used.
- [ ] Create tests for position, verbosity, self-preference, and prompt-injection susceptibility.
- [ ] Define human-review import or review workflow with randomized/blinded assignments.
- [ ] Measure inter-reviewer agreement and adjudicate a sample.
- [ ] Compare model graders against human labels overall and by important slice.
- [ ] Establish grader acceptance or limitation criteria before it informs a release decision.
- [ ] Preserve disagreements rather than resolving every case through majority vote.

Gate 6: The semantic grader's supported uses and failure modes are documented from domain-specific calibration evidence.

### Phase 7: Run the exploratory tutoring prompt pilot

Purpose: answer the original prompt-comparison question with explicitly bounded evidence.

- [ ] Freeze candidates, suite, evaluator, protocol, and analysis before running the validation set.
- [ ] Interleave candidate trials to reduce provider/time confounding.
- [ ] Execute repeated paired trials within the approved budget.
- [ ] Review infrastructure failures before unblinding comparative results.
- [ ] Apply deterministic, trace, semantic, and sampled human evaluation.
- [ ] Produce the complete comparative report.
- [ ] Conduct qualitative failure analysis without changing the frozen result.
- [ ] Label the conclusion exploratory unless the sample, validation, and calibration support a stronger claim.
- [ ] Record any next prompt hypothesis against a new development cycle rather than retuning on the holdout.

Gate 7: The user reviews the evidence and decides whether it is decision-grade, useful but preliminary, or insufficient.

### Phase 8: Add high-fidelity and workflow adapters selectively

Purpose: expand only where a concrete evaluation question requires it.

- [ ] Add a Discord end-to-end adapter for transport/orchestration risks not represented locally.
- [ ] Adapt TesterBot as one optional simulated-user policy, with explicit model and prompt provenance.
- [ ] Add branching scripted-user policies for reproducible multi-turn cases.
- [ ] Add workflow-specific trace semantics for debugging and registration.
- [ ] Add reference calculation and artifact checks for statistics.
- [ ] Add structured rubric evidence checks for assignment feedback.
- [ ] Audit archived suites before importing any case.
- [ ] Link production telemetry to candidate/workflow versions where permitted.

Gate 8: Each adapter justifies its complexity with a risk or decision that lower-fidelity modes cannot cover.

### Phase 9: Operationalize proportionate evaluation

Purpose: match evaluation cost and fidelity to the change and decision stakes.

- [ ] Define a fast deterministic smoke suite for routine changes.
- [ ] Define a repeated regression suite for prompt/model/tool changes.
- [ ] Define scheduled reliability and adversarial suites.
- [ ] Define a release suite with sealed cases and human escalation rules.
- [ ] Define production surveillance for drift, operational failures, and newly discovered cases.
- [ ] Establish change-control rules for scenarios, graders, thresholds, and holdouts.
- [ ] Establish ownership for failures, waivers, and framework maintenance.

Gate 9: CI and release policies are based on measured stability and cost rather than an arbitrary universal score.

## Proposed first-pilot decision matrix

| Candidate pilot | What it validates well | Main weakness | Recommended role |
|---|---|---|---|
| Statistics | Tool traces, reference calculations, artifact checks, explanation quality | Fixture/container complexity | Strong candidate for Pilot A |
| Registration | State transitions, permissions, mocked side effects, error recovery | Less directly about prompt quality | Strong alternative for Pilot A |
| Standard/Socratic tutor | Original prompt-comparison value, pedagogy, multi-turn behavior | Subjective oracles and simulator dependence | Pilot B after grader protocol exists |
| Debugging practice | Rich rubric and workflow progression | Many interacting prompts/assessors complicate treatment isolation | Later profile or carefully scoped prompt experiment |
| Assignment feedback | Structured outputs and rubric alignment | Requires representative documents and expert labels | Later domain-specific suite |

Recommendation: use statistics or registration to prove the framework can detect observable differences, then use a standard tutoring prompt comparison to establish whether semantic and human evidence supports the project's original decision need.

## Verification strategy for the future implementation

The evaluator itself must be evaluated. Planned verification should include:

- Schema fixtures for valid and invalid declarations.
- Synthetic traces with known invariant violations and state-machine paths.
- Hand-calculated paired-comparison fixtures.
- Deliberate infrastructure, timeout, retry, missing-evidence, and grader-abstention cases.
- Metamorphic tests such as candidate-label renaming and response-order swapping.
- Golden report fixtures that check provenance and denominators rather than prose wording.
- Reanalysis from saved artifacts without rerunning agents.
- Calibration sets with independent human labels for semantic graders.
- Sensitivity tests with known prompt defects.
- Negative tests ensuring a multi-variable change is not labeled prompt-only.

## Risks and mitigations

- Risk: The scenario suite becomes a hidden product specification and prompts overfit it.
  - Mitigation: Development/validation separation, sealed holdouts, case refresh, tracked experiment history, and distribution-shift checks.
- Risk: A model judge rewards its own style or can be manipulated by candidate output.
  - Mitigation: Blinding, counterbalancing, evidence citation, injection isolation, bias tests, human calibration, and abstention.
- Risk: Simulated users create unrealistic or correlated behavior.
  - Mitigation: Branching scripts, multiple validated personas, real-user case discovery where permitted, human studies for high-stakes claims, and explicit simulator provenance.
- Risk: Nondeterminism makes small differences look meaningful.
  - Mitigation: Paired scenarios, repetitions, interleaved runs, uncertainty intervals, practical thresholds, and inconclusive outcomes.
- Risk: Aggregate improvement hides a critical subgroup or safety regression.
  - Mitigation: Hard gates, prespecified slices, worst-case review, and no unrestricted weighted total.
- Risk: End-to-end tests are slow, flaky, expensive, or have external side effects.
  - Mitigation: A layered fidelity model, isolated resources, deterministic local checks, and selective Discord runs.
- Risk: Evaluation data exposes student or institutional information.
  - Mitigation: Synthetic-first fixtures, approval before production use, data classification, redaction, retention, and access controls.
- Risk: Provider model aliases drift and invalidate reproducibility claims.
  - Mitigation: Record provider metadata and time, interleave variants, use pinned versions where available, and rerun anchors to detect drift.
- Risk: Framework complexity delays useful experimentation.
  - Mitigation: Two bounded pilots, minimal contracts, explicit gates, and expansion only for concrete decisions.
- Risk: Existing assets are preserved by default even when they encode weak assumptions.
  - Mitigation: Treat them as candidate adapters/data sources and require the same contracts and validation as replacements.

## Open questions requiring user direction

1. What exact prompt hypothesis should the first real experiment test?
2. Would statistics or registration be the more understandable objective pilot for the team?
3. Is scaffolding the right primary tutoring measure, or is another outcome more important?
4. What regression in correctness, answer disclosure, latency, or cost would be unacceptable?
5. Who can provide domain-expert human ratings, and roughly how much review is feasible?
6. Can de-identified historical conversations inform scenario design, or should the first suite be fully synthetic?
7. Is the first useful target a development tool, a CI regression gate, a release gate, or a research instrument?
8. How important is live Discord fidelity in the first implementation compared with fast local repetition?
9. Who will own scenario/holdout governance and final prompt-deployment decisions?

## Decisions log

- 2026-09-22
  - Decision: Keep this plan in planning status and make no implementation changes.
  - Why: The user explicitly wants to understand and approve the problem, system, specification, and plan first.
- 2026-09-22
  - Proposed decision: Make controlled prompt comparison the first product use case within a more general evidence model.
  - Why: It preserves the original motivation while avoiding a framework tied only to prompt text or transcript judges.
- 2026-09-22
  - Proposed decision: Use two pilots, one objective/trace-heavy and one pedagogy-heavy.
  - Why: A semantic tutoring pilot alone cannot distinguish framework plumbing failures from grader-validity failures.

## Handoffs after approval

- Planner to experiment owner: Approved decision question, protocol, primary measure, guardrails, and suite blueprint.
- Experiment owner to schema/runner implementer: Frozen conceptual contracts, fixture requirements, and privacy boundaries.
- Implementer to reviewer: Synthetic self-test results, Pilot A artifacts, provenance, and known deviations.
- Reviewer to semantic-evaluation owner: Verified experiment core and approved human-calibration protocol.
- Semantic-evaluation owner to decision owner: Pilot B comparison report, calibration results, limitations, and unresolved disagreements.

## Change log

- 2026-09-22
  - Created the planning document from the research synthesis and repository inspection.
  - No application or evaluator code was changed.
