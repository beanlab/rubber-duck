# Agent Evaluation: research synthesis

Research snapshot: 2026-09-22. This synthesis starts from the evaluation problem, not from Rubber Duck’s current evaluator code. Rubber Duck appears only after the general findings. The companion [research index](README.md) records source type, evidence strength, bibliographic details, direct URLs, and local PDFs.

## What Agent Evaluation is

Agent Evaluation is the disciplined production of evidence about a complete interactive AI system. The target is not just an LLM and not just a prompt. It is the model, prompt hierarchy, tools and permissions, controller, memory, retrieval, state stores, interfaces, environment, and the humans with whom the system interacts. A change to any of those can change behavior. This system boundary is consistent with current agent-evaluation practice: Anthropic explicitly treats the harness and model together and distinguishes a task, a stochastic trial, graders/assertions, and the full transcript or trace ([Anthropic, 2026](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)).

Evaluation asks both **whether constraints are satisfied** and **how well an intended purpose is achieved**. The first can include binary invariants—only authorized tools are called, a JSON schema is valid, the final database state is correct, no forbidden transition occurs. The second commonly involves degrees and trade-offs—helpfulness, pedagogical quality, accessibility, robustness, latency, cost, and user benefit. [HELM](https://arxiv.org/abs/2211.09110) is foundational here: a system can have high accuracy and poor calibration, robustness, fairness, toxicity, or efficiency. One aggregate “pass rate” loses that structure.

The surrounding terms answer different questions:

- **LLM evaluation** often evaluates a model on response-level tasks. **Agent evaluation** evaluates a system acting over time in an environment, including tool and state effects.
- **Prompt evaluation** is a controlled experiment on behavior resulting from a prompt variant. A prompt is an intervention, not the outcome being measured.
- **Testing** executes a specified procedure on selected cases. Passing tests is evidence over those cases, not proof over every possible interaction.
- **Benchmarking** uses a standardized suite for comparison. A benchmark may rank candidates without validating fitness for a local population or intended use.
- **Verification** asks whether specified requirements are met; **validation** asks whether the system meets the real intended use and stakeholder need. NIST’s proposed TEVV terminology makes this distinction explicit ([NIST zero draft, 2025](https://www.nist.gov/document/outline-proposed-zero-draft-standard-ai-testing-evaluation-verification-and-validation)).
- **Formal verification/model checking** reasons over a formal model and specification. Model checking can exhaustively determine whether a finite abstract model satisfies a temporal-logic property and produce counterexamples ([Clarke, 2009](https://doi.org/10.1145/1592761.1592781)). Its guarantee applies to the formal model and assumptions—not automatically to the full natural-language system or the correctness of the specification.
- **Runtime verification** checks an observed execution against a formal specification. It gives a strong conclusion about that trace but not unobserved executions ([Leucker & Schallhart, 2009](https://www.isp.uni-luebeck.de/research/publications/brief-account-runtime-verification)).
- **Property-based testing** generates cases or action sequences to find counterexamples to stated invariants, often shrinking failures to a minimal example ([Claessen & Hughes, 2000](https://doi.org/10.1145/351240.351266)). Unless the domain is exhaustively enumerated, this is empirical testing, not proof.
- **Simulation** replaces a costly user or environment with an executable model. It is useful only within the simulator’s validated behavioral envelope.
- **Red teaming** searches adversarially for safety, security, or policy failures. It samples the failure frontier rather than estimating average user quality.
- **Neuro-symbolic evaluation** lets neural components interpret language or propose specifications and uses symbolic rules, types, solvers, databases, or theorem provers for formalizable checks. Its weakest link is often the translation from human intent to symbols.

This leads to a crucial separation. A deterministic oracle can conclusively say that *this observed output or trace* did or did not satisfy a machine-checkable property. It cannot by itself say how often a stochastic agent will satisfy that property on the deployment distribution. Conversely, empirical evaluation can estimate behavior over sampled situations, with uncertainty, but it cannot establish a universal guarantee. A credible framework needs both.

## What quality means across different agent types

There is a stable core of quality dimensions, but their operational definitions depend on agent purpose.

| Agent type | Primary outcome | Important process/trace properties | Domain/user evidence |
|---|---|---|---|
| Question answering / feedback | Correct, relevant, supported answer | Evidence retrieval, citation fidelity, no fabricated support | Usefulness, clarity, domain-expert accuracy |
| Tool-using assistant | Correct external state or artifact | Correct tool/arguments/order, authorization, recovery, no hidden side effect | User intent fulfilled with acceptable effort |
| Stateful workflow (registration, support) | Valid terminal state under policy | Legal state transitions, confirmations, idempotency, rollback, escalation | Completion, abandonment, user comprehension |
| Tutor / Socratic coach | Learner makes progress without being misled | Diagnoses misconception, selects an appropriate move, scaffolds, does not reveal too much | Accessibility, agency, mastery, transfer, retention |
| Debugging practice | Student identifies and repairs the fault | Maintains active problem/state, recognizes partial knowledge, escalates hints appropriately | Conceptual understanding and independent debugging ability |
| Data/statistics assistant | Correct analysis and artifact from the right data | Dataset selection, valid code/tool arguments, assumptions checked, errors surfaced | Interpretability, statistical appropriateness, reproducibility |
| Autonomous research/coding agent | Correct, useful artifact | Source/test coverage, safe actions, provenance, regressions avoided | Expert acceptance and downstream utility |

Across these types, evaluation should consider at least the following.

**Task success and correctness.** Prefer direct outcome checks when the environment exposes ground truth: tests pass, the expected record exists, a calculation independently recomputes, or an artifact meets a schema. [SWE-bench](https://arxiv.org/abs/2310.06770) executes fail-to-pass and regression tests; [OSWorld](https://arxiv.org/abs/2404.07972) gives each task initial-state setup and execution-based graders; [$\tau$-bench](https://arxiv.org/abs/2406.12045) compares terminal database state with an annotated goal. These are generally stronger oracles than a judge reading a plausible transcript. They still need defense against loopholes, test tampering, and underspecified goals.

**Reliability and robustness.** A one-off success does not establish dependability. Re-run each stochastic task and report distributions: success probability, pass@1, pass^k (probability all k attempts succeed), worst/quantile latency, and failure-mode frequencies. $\tau$-bench introduced pass^k specifically because agents with similar mean success can have poor repeated-use reliability. Perturb equivalent inputs—paraphrases, typos, ordering, irrelevant context, long histories, languages, student skill levels, and tool errors. [CheckList](https://arxiv.org/abs/2005.04118) supplies minimum-functionality, invariance, and directional-expectation patterns; [PromptRobust](https://arxiv.org/abs/2306.04528) shows that semantically preserving prompt perturbations can materially change results.

**Safety, policy, and boundaries.** Measure both utility and constraint compliance; otherwise a system can “succeed” by violating a rule. Include harmful content, privacy leakage, excessive agency, unauthorized actions, refusal quality, escalation, and age/context-appropriate boundaries. Indirect prompt injection is especially relevant to tool outputs and retrieved/student-provided content ([Greshake et al., 2023](https://arxiv.org/abs/2302.12173)). [AgentDojo](https://arxiv.org/abs/2406.13352) is a useful design because it reports task utility and attack success separately rather than hiding one inside the other.

**Tool, workflow, and planning behavior.** Measure final state and the trajectory. Trace checks can detect a forbidden tool call even if the final answer appears correct; an outcome check can accept multiple valid plans rather than enforcing a brittle reference path. Useful trace measures include tool choice, argument validity, precondition/permission checks, state-transition legality, redundant steps, retry and recovery behavior, handoff cycles, and evidence-to-action links. [AgentBoard](https://arxiv.org/abs/2401.13178) adds partial-progress measures because final success alone gives little diagnostic information.

**Instruction following and injection resistance.** Test the instruction hierarchy, conflicts, irrelevant or malicious context, attempts to extract protected instructions, and policy-preserving refusal. Distinguish “the agent did the user’s task” from “the agent followed all higher-priority constraints.” Attack generation can increase coverage, but generated probes need deduplication and human/security review; [Perez et al.](https://arxiv.org/abs/2202.03286) demonstrate both the scale and limitations of model-generated red-team cases.

**User experience and domain quality.** Helpfulness is contextual. Measure clarity, actionability, tone, accessibility, cognitive load, interaction effort, appropriate uncertainty, and recovery after misunderstanding. Use behavioral anchors and examples instead of ungrounded “1–5 quality” labels. Human preference is not correctness: users may prefer confident, verbose, or answer-revealing responses.

**Educational quality.** Domain correctness is necessary but not sufficient. MRBench’s dimensions include identifying and locating mistakes, not revealing answers prematurely, guidance, actionability, coherence, tone, and human-likeness ([Maurya et al., 2025](https://aclanthology.org/2025.naacl-long.57/)). [MathTutorBench](https://aclanthology.org/2025.emnlp-main.11/) reports that solving expertise does not automatically imply teaching quality. Relevant dimensions for Rubber Duck include:

- factual/domain accuracy and honest uncertainty;
- diagnosing the learner’s current reasoning, not merely the final answer;
- contingent scaffolding: hint strength responds to attempts and preserves productive work;
- usefulness and actionability of feedback;
- accessibility across language, disability, background knowledge, and device/interface constraints;
- respect, encouragement, and learner agency without sycophancy;
- no premature answer revealing, dependency creation, or grading-policy bypass;
- learning proxies such as successful self-correction, explanation quality, reduced hint dependence, and transfer to a novel problem;
- where feasible, direct outcomes: pre/post mastery, transfer, delayed retention, and course-relevant outcomes.

Proxy measures must be validated. The preregistered [Tutor CoPilot trial](https://arxiv.org/abs/2410.03017) is important because it connects system access to student mastery and pedagogical strategies in live tutoring. It does not imply that its effect generalizes to an autonomous Discord tutor, but it demonstrates the evidence level needed before claiming learning impact.

**Operational quality.** Record end-to-end and per-step latency, time to first response, tokens, cached/reasoning tokens where observable, monetary cost under a versioned price schedule, tool/computation cost, failure and retry rates, timeouts, rate limits, and environment-reset failures. Report quality–cost–latency frontiers rather than optimizing each independently. Reproducibility requires immutable provenance: model/provider/version or snapshot, decoding and reasoning settings, prompt hashes, tool schemas/versions, code commit, data/scenario/evaluator versions, environment image, timestamps, region if material, and raw artifacts permitted by privacy policy.

## A taxonomy of evaluation approaches

No approach dominates. Each supplies evidence for a different claim.

| Approach | Typical oracle and unit | Strengths | Limitations / assumptions | Best use |
|---|---|---|---|---|
| Executable assertions | Exact match, schema, tests, independent recomputation, database/artifact state | Fast, reproducible, localizes concrete failures | Only as complete as the oracle; agents may exploit loopholes | Correct outputs, tools, state, costs, invariants |
| Reference/golden cases | Expected answer, allowed set, expert exemplar | Easy regression baseline; inspectable | Open-ended tasks have many valid outputs; references can encode annotator bias | Constrained factual or structured tasks |
| Behavioral/property/metamorphic tests | Invariant across generated or transformed inputs | Broadens input coverage; yields counterexamples | Generator realism and property correctness are critical; finite runs are not proof | Robustness, state machines, prompt invariance |
| Formal/model checking | Proof or exhaustive check on formal model | Strong guarantee within model; counterexample traces | Specification/abstraction gap; state explosion; semantics hard to formalize | Permissions, bounded workflow/state/safety properties |
| Runtime verification/enforcement | Trace events checked against temporal/rule specification | Prevents or detects violations at action time; interpretable | Only observed traces; instrumentation and event abstraction must be correct | Tool authorization, transition order, protected actions |
| Rubric + human review | Anchored ordinal/categorical judgments, pairwise preference | Handles context and tacit domain quality; reveals bad metrics | Cost, rater disagreement, fatigue, cultural/domain bias | Pedagogy, UX, ambiguous failures, calibration sets |
| LLM-as-a-judge | Classification, pairwise, scalar, reference-guided rubric | Scalable semantic grading and explanation | Position/verbosity/self bias, stochasticity, injection, limited expertise, correlated errors | Triage or a calibrated proxy—not ground truth |
| Scripted replay | Fixed turns or recorded production input | Reproducible regressions, cheap | Misses adaptive branches; may reward script matching | Known bugs, smoke tests, backward compatibility |
| Interactive simulation | User/environment model with branching | Exercises long-horizon adaptation; controllable personas | Simulator bias can dominate results; both agents may share model biases | Workflow exploration, rare/adversarial situations |
| Benchmark suite | Shared tasks and metrics | Comparability and coverage discipline | Contamination, saturation, target overfitting, poor local validity | External baselines and capability profiling |
| Red teaming / fuzzing | Attack success, policy violation, discovered counterexample | Finds unexpected and worst-case failures | Not prevalence estimation; coverage is open-ended | Security and boundary discovery |
| Production monitoring | Telemetry, samples, feedback, incidents, drift | Highest ecological validity; discovers distribution shift | Selection/confounding, delayed labels, privacy, harm already possible | Post-deployment assurance and case mining |
| Controlled user/domain study | Blinded A/B, expert review, learning/task outcome | Validates intended use and real benefit | Expensive; ethics, recruitment, power, generalization | High-stakes product claims and proxy validation |
| Hybrid neuro-symbolic | Neural interpretation plus symbolic verifier/solver | Combines language flexibility with deterministic checks | Translation errors can create false assurance; formalizable subset only | Structured policies, calculations, proofs, constraint adherence |

**Trace-level and outcome-level evaluation are complementary.** Outcome-only scoring tolerates multiple creative solutions and measures whether the task was truly completed, but can miss unsafe means and provides weak diagnosis. Trace-only scoring catches process violations and explains failures, but a “reference trajectory” can reject valid alternatives and reward performative compliance. A sensible evidence record can attach multiple graders to one trial: terminal-state assertions, trace properties, semantic rubrics, operational measurements, and later human/production labels. Graders should remain separate rather than being averaged into an uninterpretable number.

**LLM-as-a-judge needs instrument validation.** The early positive result—strong judges reached human-like agreement in selected MT-Bench comparisons—came with documented position, verbosity, self-enhancement, and reasoning biases ([Zheng et al., 2023](https://arxiv.org/abs/2306.05685)). [Wang et al.](https://arxiv.org/abs/2305.17926) specifically found order sensitivity. A serious validation protocol should:

1. define the construct and anchored rubric with expert examples;
2. create a blinded, independently human-labeled calibration set with positives, negatives, borderline cases, and all important slices;
3. measure confusion matrices, per-class precision/recall, rank correlation where appropriate, calibration, and agreement such as Cohen’s kappa or Krippendorff’s alpha—not raw agreement alone;
4. test counterfactual swaps (A/B order), length/style changes, model identity removal, prompt injection in the candidate output, and same-family/self-preference;
5. estimate repeated-run variance and define an abstain/disagreement path;
6. periodically revalidate after any judge model, prompt, rubric, or scenario change;
7. reserve human adjudication for uncertainty, high-risk cases, disagreements, and samples used to monitor drift.

Multiple judges can reduce idiosyncratic variance, but majority vote does not remove shared training-data, cultural, verbosity, or rubric biases. Judge diversity, order randomization, calibrated weighting, and human adjudication are more defensible than “three models voted.” A judge’s reasoning is useful diagnostic text, not evidence that the verdict is correct.

**Simulation also needs validation.** Compare simulated and real users on language, action distributions, persistence, misconceptions, branching, sensitivity to help, and outcomes. Calibrate distinct persona/skill models, report results per simulator, and do not let one simulator and one judge define both stimulus and success. The very recent ACL study [Simulated Students in Tutoring Dialogues: Substance or Illusion?](https://aclanthology.org/2026.acl-long.1960/) found simple prompted student simulators poor on linguistic, behavioral, and cognitive fidelity; even trained alternatives remained limited. Thus simulation is a controllable test fixture, not a stand-in for evidence of real learning.

**Statistical comparison should match the nested experiment.** Scenarios and repeated trials are separate sources of variation. For candidate A/B comparisons:

- run both candidates on the same versioned scenarios (paired design), randomizing order and blinding human/judge raters;
- repeat stochastic trials, ideally with common environmental conditions; if provider seeds are unavailable or not reproducible, record that explicitly;
- report per-candidate estimates and paired differences with uncertainty, preferably confidence intervals from a method that respects clustering by scenario and repeated trial (for example, a hierarchical/cluster bootstrap or an appropriate mixed model);
- predeclare a minimum practically important effect or non-inferiority margin, not merely a p-value threshold;
- perform power analysis for the effect and slice sizes that matter—underpowered NLP and human-rating comparisons are common ([Card et al., 2020](https://arxiv.org/abs/2010.06595));
- choose tests appropriate to paired binary, ordinal, or continuous outcomes; [Dror et al.](https://aclanthology.org/P18-1128/) provide NLP-specific guidance;
- correct or clearly qualify exploratory multiple comparisons and slices;
- show distributions and failure categories, not just means; include safety floors that cannot be traded for average helpfulness;
- distinguish statistical uncertainty from evaluator error, simulator error, and distribution mismatch.

A CI regression gate should therefore reflect practical risk: for example, a deterministic invariant may gate on any violation, while a noisy quality measure might gate only when a confidence interval crosses a predefined degradation margin. Tiny suites are valuable as smoke tests but cannot support population-level performance claims.

## What can be verified deterministically versus what must be estimated empirically

| Property | Deterministic evidence available? | What remains empirical or uncertain? |
|---|---|---|
| Output syntax/schema | Yes, for the observed output | Frequency under varied inputs/runs; whether schema semantics are correct |
| Arithmetic/statistical calculation | Often, by independent recomputation and tolerance | Whether the selected method and assumptions fit the user’s real question |
| Tool name/arguments | Yes, against schema and allowlist | Whether use was semantically necessary/helpful across distribution |
| Workflow transition/order | Yes, if state/events are instrumented and specification is complete | Whether the state model represents every real condition and user need |
| Terminal database/file state | Yes, against explicit predicates | Whether the goal state fully captures intent and excludes harmful side effects |
| No forbidden event in one trace | Yes, through trace/runtime checks | Probability of violation on unseen situations; unobserved side effects |
| Formal property of a bounded model | Yes, via proof/model checking under assumptions | Model/specification fidelity and properties outside the model |
| Factual correctness | Sometimes, with an authoritative database, tests, or computation | Open-domain truth, source quality, ambiguity, and changing facts |
| Instruction/policy adherence | Some rules can be executable | Semantic and contextual rules often require uncertain interpretation |
| Helpfulness, tone, accessibility | Rarely fully deterministic | Human/domain judgment, population and context dependence |
| Pedagogical quality | Some observable moves can be rule-checked | Appropriateness to this learner and whether learning occurs |
| Robustness/reliability | No universal one-run verdict | Estimated rates/distributions over cases and repeated trials |
| Safety | Some non-negotiable actions/content can be blocked | Open-ended harms, adversarial discovery, social context, distribution shift |
| Learning or user benefit | No transcript-only guarantee | Controlled real-user/domain study and longitudinal evidence |

Deterministic and formal checks should be used wherever the property genuinely has a trustworthy oracle. They should not be extended by wishful labeling: an LLM returning a deterministic JSON verdict is still a probabilistic semantic judge. Likewise, a binary threshold applied to a continuous score does not make the underlying measurement certain.

## Measurement dimensions and their trade-offs

An evaluation portfolio should preserve a vector of measures and policy constraints rather than optimize one composite score.

- **Success/correctness:** task completion, exact/partial progress, factual and computational correctness, artifact validity. Trade-off: strict references can reject valid alternatives; weak tests invite gaming.
- **Reliability/robustness:** repeated success, variance, recovery, perturbation sensitivity, long-context and out-of-distribution performance. Trade-off: repetitions and broader slices cost time and money.
- **Safety/security:** violation and attack-success rates, severity, exposure, refusal precision/recall, authorization. Trade-off: excessive refusal can reduce utility; report both rather than netting them out.
- **Process quality:** tool and state correctness, planning efficiency, evidence use, retries. Trade-off: prescribing one path can penalize valid innovation.
- **Human/domain quality:** usefulness, accessibility, pedagogy, trust calibration. Trade-off: judgments are expensive and context-dependent; model proxies inherit bias.
- **Operations:** latency, tokens, cost, throughput, failure/retry rates, reproducibility. Trade-off: cheaper/faster systems may sacrifice quality or reliability; best choices lie on a frontier.
- **Equity and slices:** performance by language, skill level, disability/access need, problem type, agent/workflow, length, and risk. Trade-off: small slices have wide uncertainty and raise privacy concerns, but aggregates can conceal serious failure.

Do not average a severe safety breach away with many easy successes. Keep hard constraints (“no unauthorized grade change”) separate from graded qualities (“clarity 1–5”). For continuous qualities, retain the raw anchored rating and its uncertainty; a pass threshold may be added for a release policy but should not replace the measurement.

## How to judge prompts fairly

A prompt has no quality independent of the system and use distribution. Elegant wording can perform badly; an awkward prompt can work because of model-specific behavior; a prompt that wins a small benchmark can be brittle elsewhere. Evaluate prompt variants through resulting actions, outputs, state changes, user experience, and operational cost.

An apples-to-apples prompt comparison must hold constant and record:

- exact model provider, model/version/snapshot, API, region if relevant, and availability date;
- decoding/sampling, reasoning effort, token limits, seeds where supported, stop conditions, retries, and concurrency;
- the complete instruction hierarchy and rendered prompts, including templates, few-shot examples, hidden prefixes, memory, and retrieved context;
- tool definitions, versions, permissions, sandbox/environment image, data snapshot, and external-service state;
- application/controller code, turn limits, truncation/compaction, routing, handoffs, caching, and error handling;
- scenario ID/version, simulator/persona/version, initial state, expected properties, and sampling policy;
- evaluator implementation, rubric, judge model/prompt/version/settings, human instructions, rater identity policy, and adjudication rules;
- code commit, run timestamp, raw artifacts, token/latency/cost accounting rules, and any exclusions.

Use paired cases and repeated trials; blind human and model judges to variant identity; randomize pair order; examine failure slices and practical effect sizes. If only the prompt is intended to vary, no other component should silently vary. If a production model alias changes underneath a prompt test, the experiment no longer isolates prompt effect.

Maintain separate development, validation, and final/confirmation sets. Iterating on failures turns a test set into training data for prompt developers, producing prompt overfitting even when the LLM itself is unchanged. Public benchmarks are vulnerable to model training contamination and to application developers tailoring prompts to known cases; contamination can overstate generalization ([Sainz et al., 2023](https://arxiv.org/abs/2310.18018)). Use private or rotating holdouts, newly mined production cases, paraphrased/metamorphic variants, and periodic out-of-distribution evaluations. Preserve old cases for regression, but do not mistake them for the current distribution.

Evaluator gaming is also possible. A system may produce verbose rubric keywords, flatter a judge, inject instructions into a transcript, manipulate a test harness, or reach an underspecified goal state through an unacceptable shortcut. Keep evaluator instructions isolated from candidate-controlled text, test injection against graders, use independent end-state checks, protect test artifacts, inspect traces, and audit surprising score gains. Never train/optimize indefinitely against the same judge without fresh independent human or executable validation.

## Risks and limitations

**Nondeterminism and dependency drift.** Repeated calls vary, and hosted model aliases, safety layers, tools, datasets, and APIs can change. Temperature zero is not a reproducibility guarantee. Version all controllable inputs, archive outputs and environment identifiers, use repetitions, and state which dependencies cannot be frozen.

**Judge bias and construct validity.** A reliable judge can reliably measure the wrong construct. Position, verbosity, self-preference, style, cultural assumptions, and domain ignorance all matter. Human labels also disagree and can be biased. Anchor the construct, train raters, report agreement, calibrate automated graders, and investigate disagreements rather than concealing them.

**Evaluator gaming and Goodhart effects.** Once a score is a target, agents and prompt authors optimize its loopholes. Diverse independent evidence, hidden confirmation sets, manual audits, trace/outcome cross-checks, and rotating adversarial cases reduce but do not eliminate the problem.

**Test-set overfitting and contamination.** Public cases can enter model training; internal cases enter prompt-development memory. Track case exposure, separate pools, rotate holdouts, and report when training-data visibility is unknowable.

**Distribution shift.** Offline scenarios age. Student populations, course material, policies, models, and tool APIs change. Production telemetry and sampled human review should detect new slices and feed a governed case-mining process, without automatically turning every user interaction into evaluation data.

**Privacy and ethics.** Educational conversations may contain student records, disability information, grades, code, or personally identifying data. Collection needs purpose limitation, consent/legal basis where applicable, access controls, retention/deletion rules, redaction, and careful use of external judge APIs. Human review and dataset release can expose sensitive content. Learning studies need ethical review proportional to risk and must not disadvantage students assigned to variants.

**Cost and environmental/operational burden.** Multiple trials, simulators, judges, sandboxes, and humans are expensive. Use tiered evidence: cheap deterministic smoke/regression checks frequently, statistically designed suites at change gates, deeper red-team/human studies periodically, and targeted production review continuously. Cost constraints must not silently shrink high-risk coverage.

**Reproducibility versus realism.** Hermetic environments are repeatable but may omit production failures; live Discord/API tests are realistic but externally variable. Maintain both kinds and label the inference each supports.

**Benchmark limitations.** A benchmark is a sample of tasks under a scoring protocol. Rankings can be unstable to prompt, harness, and weighting choices. External benchmarks establish comparability, while local representative and adversarial tasks establish use-case validity.

## Findings specifically relevant to this repository’s tutoring and workflow agents

### Existing evaluator-related components, factually described

Rubber Duck currently contains several distinct evidence sources:

- [`src/testing/tester_bot_scaffold/testerbot.py`](../src/testing/tester_bot_scaffold/testerbot.py) implements an LLM-driven Discord client. It starts real conversations, collects debounced messages, represents duck messages and tester responses in model history, stops on completion/timeout/turn limit, and can use a binary progress assessor to stop.
- [`src/testing/tester_bot_scaffold/assessments.py`](../src/testing/tester_bot_scaffold/assessments.py) formats message-only history, splits marked assessor batteries, runs assessors concurrently, and requests structured post-conversation outputs.
- [`src/storage/assessment_models.py`](../src/storage/assessment_models.py) defines `ProgressAssessment` as `catch/pass`, `PostConversationAssessment` as `pass/fail`, and usefulness as `useful/not useful`, each with reasoning where applicable.
- [`tests/tester_bot_tests/test_dry_run.py`](../tests/tester_bot_tests/test_dry_run.py) runs four live Discord smoke scenarios: standard tutoring, two statistics configurations, and debugging practice. It deterministically checks for normal closure/no orchestrator error and then requires model-assessor pass results. The fixture also reports tester and duck token/cost totals.
- The standard and statistics assessor prompts check a small set of scripted behaviors. The [debugging assessor](../tests/tester_bot_tests/prompts/assessors/debugging_assessor.md) is substantially richer: seven independently run criteria cover ordered advancement, incomplete and incorrect answers, combined concept/fix recognition, state/completion, guided-practice boundaries, and beginner usefulness, grounded in a course rubric.
- [`src/storage/sql_metrics.py`](../src/storage/sql_metrics.py) and [`src/metrics/`](../src/metrics/) capture production messages, token usage, and TA feedback. The TA review flow records a 1–5 reaction and optional written explanation, and reporting code aggregates use, cost, and feedback.

These facts should not be read as an architectural recommendation. They establish what evidence can presently be collected and what assumptions current tests encode.

### Ideas that are independently reusable

Several assets have value even if the future framework is entirely different:

- concrete domain scenarios and failure examples for standard, statistics, and debugging agents;
- the debugging rubric’s decomposition of workflow correctness from educational usefulness;
- the ability to exercise the deployed Discord path end to end;
- explicit closure/error assertions and token/cost collection;
- production message, usage, and TA-review data as potential case-mining and calibration inputs, subject to privacy controls;
- domain rubrics and known incomplete/incorrect-answer sequences as seed requirements, not necessarily as permanent grader prompts.

Reusing those data assets does not require preserving TesterBot, its history format, its judge, or pass/fail schemas.

### Missing evidence and limiting assumptions

Relative to the research, the current groundwork has important limitations:

- **Very small, fixed scenario sample.** One scripted dry run per configured workflow cannot estimate representative quality, robustness, or regression probability.
- **No repeated stochastic trials or statistical comparison.** A single pass provides no within-scenario reliability, confidence interval, effect size, power, or candidate difference.
- **Binary semantic compression.** Pass/fail is appropriate for some invariants, but it discards severity, partial progress, continuous pedagogical quality, and uncertainty.
- **Unvalidated judge.** There is no documented human-labeled calibration set, inter-rater agreement, confusion analysis, order/verbosity/injection stress test, abstention, or drift monitoring. Target and assessor configurations can also use the same model family, making correlated/self preference plausible.
- **Transcript is message-only.** The assessor formatter discards non-message trace events. It cannot directly verify tool choice/arguments, intermediate state, retries, permissions, or final database/artifact state.
- **Script/simulator dependence.** The tester follows designed conversations; its fidelity to real students and sensitivity across learner personas are not established. Current tutoring research specifically warns that simple prompted students can be poor simulators.
- **Live-path confounding.** Discord end-to-end execution is ecologically useful but not hermetic. Network/service/model changes can make failures hard to reproduce without richer run provenance and isolated component suites.
- **Limited safety/adversarial coverage.** There is no visible systematic prompt-injection, policy-conflict, privacy, harmful-content, excessive-agency, or tool-abuse suite in the inspected evaluator files.
- **Telemetry is not yet outcome validation.** Messages, usage, and 1–5 TA feedback are valuable signals, but selection bias, rubric ambiguity, rater disagreement, privacy, and lack of student learning outcomes limit causal conclusions.
- **Configuration provenance is incomplete as evaluation evidence.** The tests configure named models and prompts, but a general evidence record would also need immutable model/evaluator/scenario/tool/environment versions, rendered inputs, raw traces, run IDs, exclusions, and dependency drift notes.

The detailed debugging battery is more informative than the other current assessors, but it still reduces each criterion to a judge-generated bit after a single long scripted interaction. That is useful smoke/regression evidence, not a general measurement system or learning-effect validation.

### Repo-specific measurement implications

For Socratic and debugging tutors, separate correctness, workflow state, scaffolding, responsiveness, accessibility, tone, answer revealing, learner effort, and eventual self-correction. Test novice misconceptions, partial answers, repeated errors, correct-but-unexpected reasoning, ambiguity, off-topic content, accessibility needs, and long conversations. Ultimately validate transcript proxies against human experts and, where ethically feasible, learning/transfer outcomes.

For statistics agents, independently recompute results, inspect tool calls and dataset identity, verify statistical assumptions and interpretation, and retain generated code/artifacts. A fluent chi-square explanation is not evidence that the right columns/data/test were used.

For registration or other stateful workflows, terminal state, authorization, confirmations, policy compliance, idempotency, and recovery should dominate transcript aesthetics. A database/state oracle and runtime policy monitor could replace most post-hoc judging for these properties.

For assignment feedback, evaluate factual/rubric correctness, specificity, actionability, consistency across equivalent submissions, non-disclosure of protected solutions where relevant, fairness slices, and whether students can use the feedback. Human instructor calibration is essential.

## Alternative framework directions that do not depend on the current architecture

These are substantially different ways to organize Agent Evaluation. They may coexist, or one may replace the current simulated-student/transcript-judge pattern for a given claim.

| Direction | Core idea | Strengths | Limitations and assumptions | Appropriate use |
|---|---|---|---|---|
| **Executable world-state benchmark** | Each scenario provisions initial state; the agent acts through instrumented tools; graders inspect final state, artifacts, and forbidden side effects. | Objective, reproducible, accepts varied language/plans; inspired by $\tau$-bench, WebArena, OSWorld, SWE-bench. | Building resettable environments and complete oracles is costly; goal loopholes remain. | Registration, statistics, file/data workflows, debugging artifacts. |
| **Formal workflow model/model checking** | Represent controller states/transitions and verify temporal properties before running the LLM. | Exhaustive over bounded model; counterexample paths; independent of judge prose. | Does not prove the LLM’s semantic output quality; abstraction/state explosion/specification error. | Conversation lifecycle, permissions, required confirmation, termination, no illegal transitions. |
| **Runtime policy enforcement** | Intercept events/tool actions and evaluate rules before/after execution, as in AgentSpec. | Prevents non-negotiable violations; traceable and low-latency for crisp rules. | Requires complete instrumentation and formalizable policies; can block legitimate edge cases. | Tool authorization, PII boundaries, destructive actions, state invariants. |
| **Property/metamorphic test generator** | Define invariants and transformations; generate/shrink diverse inputs and action sequences. | Finds unexpected edge cases; reduces hand-authored script dependence. | Realistic generators and semantic invariants are hard; sampling offers no universal guarantee. | Paraphrase/typo robustness, equivalent student reasoning, idempotency, state sequences. |
| **Curated benchmark portfolio** | Versioned heterogeneous tasks with code, reference, judge, and human graders; external plus local suites. | Comparability, coverage accounting, stable regression history. | Contamination, benchmark overfitting, weighting disputes, maintenance. | Broad capability profiling and release comparison. |
| **Human/domain review program** | Blinded anchored ratings, expert adjudication, periodic user studies, and proxy calibration. | Best access to pedagogy, usability, and intended-use validity. | Cost, disagreement, ethics, recruitment, slow feedback. | Tutor quality, accessibility, ambiguous/high-risk cases. |
| **Learning-outcome evaluation** | Randomized/quasi-experimental pre/post, transfer, retention, and mastery measurements. | Tests intended educational purpose rather than conversational appearance. | Expensive, context-specific, causal/ethical design burden, delayed outcomes. | Claims that a tutor improves learning. |
| **Production observability and drift surveillance** | Instrument traces, sample/de-identify cases, collect structured feedback/incidents, compare distributions over time. | Real distribution and novel failures; closes offline blind spots. | Harm occurs before detection; privacy and selection/confounding; sparse labels. | Post-deployment assurance and scenario discovery. |
| **Adversarial security lab** | Separate attack corpora/generators, isolated environments, attack-success and utility scores, expert triage. | Security expertise and worst-case search remain first-class rather than diluted in quality rubrics. | No completeness; attacks evolve; generated cases vary in realism. | Prompt injection, exfiltration, unsafe tools, policy bypass. |
| **Hybrid neuro-symbolic verifier** | Neural compiler maps requirements/output to typed facts or constraints; deterministic solver checks them and exposes proof/counterexample. | More flexible than hand-coding every parser; stronger checking once grounded. | Translation/specification can be wrong; proof only covers symbolic representation; new research. | Structured domain rules, calculations, schedules, constraint-heavy feedback. |
| **Differential/canary evaluation** | Compare candidates blindly on paired real or synthetic cases, with staged shadow/canary exposure and rollback signals. | Direct product decision evidence; detects provider/model changes. | Needs enough traffic/labels; live exposure risk; attribution can be confounded. | Prompt/model/system variant selection and drift detection. |

The research does not support selecting one universal mechanism. It supports a common evidence model capable of representing different targets, scenarios, environments, traces, graders, trials, metrics, provenance, and human decisions—without forcing all of them through an LLM rubric.

## Open questions that research does not resolve

1. What is the correct evaluation boundary for each Rubber Duck workflow: base model, orchestrated agent, Discord service, or full human/course system?
2. Which behavioral requirements are true non-negotiable invariants, which are release thresholds, and which are exploratory measures where trade-offs are acceptable?
3. What deployment population and scenario distribution should define “representative,” and how should rare/high-severity cases be weighted?
4. Which pedagogical constructs are important for each course and age group, and which observable proxies are demonstrably predictive of learning, transfer, or retention?
5. How much simulator fidelity is sufficient for a decision, and what real-student data can ethically and legally validate it?
6. What human-review design, rater expertise, agreement target, and adjudication process are affordable and credible?
7. What minimum practically important difference and reliability target should govern candidate selection? Required sample size depends on those choices and observed variance.
8. Which tools and environments can be reset and graded deterministically, and where will semantic ambiguity remain unavoidable?
9. How should evolving hosted models be identified when providers do not expose immutable weights or full decoding reproducibility?
10. How should privacy-sensitive traces be minimized, de-identified, retained, and made available to judges/reviewers without losing diagnostic value?
11. How should safety floors interact with utility and accessibility trade-offs? A single weighted aggregate is unlikely to be defensible.
12. How can confirmation sets remain hidden enough to resist overfitting while results remain auditable and reproducible?
13. How often should evaluator models, simulators, rubrics, and production-derived scenario distributions be recalibrated?
14. Which formal properties are worth the specification cost, and how will the project validate that a formal abstraction matches the actual agent and user intent?
15. What governance determines when an evaluation failure blocks deployment, triggers human review, becomes a monitored risk, or causes rollback?

These are design and governance choices, not questions that a generic framework or LLM judge can answer automatically.
