"""Paired, descriptive comparison without premature winner claims."""

from __future__ import annotations

from collections import Counter

from .schemas import (
    ComparisonDecision,
    ComparisonSummary,
    EvaluationDeclaration,
    Observation,
    ObservationStatus,
    PairedCriterionResult,
    TrialArtifact,
)


def _rank(value: object, ordered_values: tuple[str, ...]) -> float:
    if ordered_values:
        if not isinstance(value, str) or value not in ordered_values:
            raise ValueError(f"value {value!r} is not in the declared ordinal scale")
        return float(ordered_values.index(value))
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError("only ordinal, boolean, and numeric observations are comparable")


def compare_candidates(
    declaration: EvaluationDeclaration,
    observations: list[Observation] | tuple[Observation, ...],
    *,
    trials: list[TrialArtifact] | tuple[TrialArtifact, ...],
) -> ComparisonSummary:
    """Compare the first two candidates using matched scenario repetitions."""
    candidate_a, candidate_b = declaration.candidates[:2]
    declared_candidate_ids = {candidate_a.candidate_id, candidate_b.candidate_id}
    declared_scenarios = {
        scenario.scenario_id: scenario for scenario in declaration.scenarios
    }
    declared_criteria = {
        criterion.criterion_id: criterion for criterion in declaration.criteria
    }
    expected_trial_keys = {
        (candidate_id, scenario_id, repetition)
        for candidate_id in declared_candidate_ids
        for scenario_id in declared_scenarios
        for repetition in range(1, declaration.policy.repetitions + 1)
    }
    trial_keys: set[tuple[str, str, int]] = set()
    trials_by_id: dict[str, TrialArtifact] = {}
    invalid_reasons: list[str] = []
    for trial in trials:
        key = (trial.candidate_id, trial.scenario_id, trial.repetition)
        if trial.trial_id in trials_by_id or key in trial_keys:
            invalid_reasons.append("duplicate trials exist for a candidate/scenario/repetition")
        trials_by_id[trial.trial_id] = trial
        trial_keys.add(key)
        if trial.run_id != declaration.run_id:
            invalid_reasons.append(f"trial {trial.trial_id} belongs to a different run")
        if trial.candidate_id not in declared_candidate_ids:
            invalid_reasons.append(f"trial {trial.trial_id} uses an undeclared candidate")
        if trial.scenario_id not in declared_scenarios:
            invalid_reasons.append(f"trial {trial.trial_id} uses an undeclared scenario")
        if (
            trial.candidate_id in declared_candidate_ids
            and trial.scenario_id in declared_scenarios
        ):
            candidate = next(
                item
                for item in declaration.candidates
                if item.candidate_id == trial.candidate_id
            )
            scenario = declared_scenarios[trial.scenario_id]
            if trial.request.instructions != candidate.resolved_prompt:
                invalid_reasons.append(
                    f"trial {trial.trial_id} request differs from its candidate prompt"
                )
            if trial.request.configuration != candidate.configuration:
                invalid_reasons.append(
                    f"trial {trial.trial_id} configuration differs from its candidate"
                )
            if trial.request.history != scenario.model_visible_history:
                invalid_reasons.append(
                    f"trial {trial.trial_id} history differs from its scenario"
                )
            if trial.source_family_id != scenario.source_family_id:
                invalid_reasons.append(
                    f"trial {trial.trial_id} source family differs from its scenario"
                )
        if trial.adapter_id != declaration.adapter_id:
            invalid_reasons.append(
                f"trial {trial.trial_id} adapter differs from the declaration"
            )
        if trial.code_revision != declaration.code_revision:
            invalid_reasons.append(
                f"trial {trial.trial_id} code revision differs from the declaration"
            )
    if missing_trials := expected_trial_keys - trial_keys:
        invalid_reasons.append(
            f"{len(missing_trials)} declared candidate/scenario/repetition trials are missing"
        )
    if extra_trials := trial_keys - expected_trial_keys:
        invalid_reasons.append(
            f"{len(extra_trials)} trials are outside the declared run matrix"
        )

    indexed: dict[tuple[str, str, int, str], Observation] = {}
    duplicates: set[tuple[str, str, int, str]] = set()
    for observation in observations:
        key = (
            observation.candidate_id,
            observation.scenario_id,
            observation.repetition,
            observation.criterion_id,
        )
        if key in indexed:
            duplicates.add(key)
        indexed[key] = observation

        trial = trials_by_id.get(observation.trial_id)
        if observation.run_id != declaration.run_id:
            invalid_reasons.append(
                f"observation {observation.observation_id} belongs to a different run"
            )
        if observation.criterion_id not in declared_criteria:
            invalid_reasons.append(
                f"observation {observation.observation_id} uses an undeclared criterion"
            )
        if trial is None:
            invalid_reasons.append(
                f"observation {observation.observation_id} references a missing trial"
            )
        elif (
            observation.candidate_id,
            observation.scenario_id,
            observation.source_family_id,
            observation.repetition,
        ) != (
            trial.candidate_id,
            trial.scenario_id,
            trial.source_family_id,
            trial.repetition,
        ):
            invalid_reasons.append(
                f"observation {observation.observation_id} disagrees with its trial provenance"
            )

    limitations = [
        "This is an exploratory comparison and does not establish deployment-grade prompt superiority.",
    ]
    if any(trial.causal_source == "recorded" for trial in trials):
        limitations.append("Recorded responses do not establish prompt causality.")

    results: list[PairedCriterionResult] = []
    if duplicates:
        invalid_reasons.append("duplicate observations exist for a candidate/scenario/repetition")

    for criterion in declaration.criteria:
        expected_keys = [
            (scenario.scenario_id, repetition)
            for scenario in declaration.scenarios
            if criterion.criterion_id in scenario.applicable_criteria
            for repetition in range(1, declaration.policy.repetitions + 1)
        ]
        counts: Counter[str] = Counter()
        for scenario_id, repetition in expected_keys:
            a = indexed.get(
                (
                    candidate_a.candidate_id,
                    scenario_id,
                    repetition,
                    criterion.criterion_id,
                )
            )
            b = indexed.get(
                (
                    candidate_b.candidate_id,
                    scenario_id,
                    repetition,
                    criterion.criterion_id,
                )
            )
            a_available = a is not None and a.status == ObservationStatus.OBSERVED
            b_available = b is not None and b.status == ObservationStatus.OBSERVED
            if not a_available:
                counts["a_unavailable"] += 1
            if not b_available:
                counts["b_unavailable"] += 1
            if not a_available or not b_available:
                counts["unavailable"] += 1
                continue
            try:
                a_rank = _rank(a.value, criterion.ordered_values)
                b_rank = _rank(b.value, criterion.ordered_values)
            except ValueError as error:
                invalid_reasons.append(f"{criterion.criterion_id}: {error}")
                counts["unavailable"] += 1
                continue
            counts["compared"] += 1
            if a_rank > b_rank:
                counts["a_better"] += 1
            elif b_rank > a_rank:
                counts["b_better"] += 1
            else:
                counts["ties"] += 1

        if expected_keys and not counts["compared"]:
            invalid_reasons.append(
                f"criterion {criterion.criterion_id} has no complete paired observations"
            )
        results.append(
            PairedCriterionResult(
                criterion_id=criterion.criterion_id,
                candidate_a_id=candidate_a.candidate_id,
                candidate_b_id=candidate_b.candidate_id,
                expected_pairs=len(expected_keys),
                compared_pairs=counts["compared"],
                candidate_a_better=counts["a_better"],
                candidate_b_better=counts["b_better"],
                ties=counts["ties"],
                unavailable_pairs=counts["unavailable"],
                candidate_a_unavailable=counts["a_unavailable"],
                candidate_b_unavailable=counts["b_unavailable"],
            )
        )

    if invalid_reasons:
        decision = ComparisonDecision.INVALID
        decision_reason = "; ".join(dict.fromkeys(invalid_reasons))
    else:
        decision = ComparisonDecision.INCONCLUSIVE
        decision_reason = (
            "The prototype reports paired descriptive evidence only; qualification "
            "and a frozen validation decision policy are not yet available."
        )

    return ComparisonSummary(
        run_id=declaration.run_id,
        question=declaration.question,
        candidate_a_id=candidate_a.candidate_id,
        candidate_b_id=candidate_b.candidate_id,
        decision=decision,
        decision_reason=decision_reason,
        exploratory=declaration.exploratory,
        scenario_count=len(declaration.scenarios),
        source_family_count=len(
            {scenario.source_family_id for scenario in declaration.scenarios}
        ),
        trial_count=len(trials),
        results=tuple(results),
        limitations=tuple(limitations),
    )
