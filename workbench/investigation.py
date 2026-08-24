"""Phase 69: `run_investigation()` -- one concrete, deterministic
materials-development investigation exercising the FULL closed loop
(state -> prediction -> decision -> observation -> residual -> updated
state -> next decision) through the existing algebra, end to end, with
no new primitive.

WHY A SEPARATE MODULE, NOT A NEW METHOD ON `WorkbenchState`: this
investigation's central question -- "does the closed loop change what
the system recommends doing next" -- requires comparing TWO candidates'
utility/optimization side by side at every decision point.
`WorkbenchState` (Phase 68) deliberately holds exactly ONE `selected_
candidate` at a time and deliberately declined to expose utility/
information-value/optimization inspection (see `workbench/interaction.py`'s
own Phase 66 "declined" list, inherited from `experiment/session.py`) --
retrofitting multi-candidate decision machinery into that single-
candidate interactive surface would be exactly "adding another
architectural layer merely to make the system look more complete,"
which this phase's own instructions forbid. Multi-candidate decision
composition already has a home: `experiment.step.run_experiment_step`
performs exactly this composition today, fully automated. This module
does the SAME composition -- predict, structural information value,
model-driven information estimate, utility, `optimize_candidates(...,
max_candidates=1)` -- but INLINE and NARRATED rather than behind one
opaque call, because the deliverable here is a human-readable
investigation transcript, not another automation entry point. No
decision primitive is added: every one of these calls is the same
unmodified `materials.*` function `experiment/step.py` itself already
calls internally.

ONE OBSERVED, NON-BLOCKING LIMITATION (documented rather than "fixed,"
since the underlying algebra remains fully sufficient by direct
composition -- see this module's own investigation report): `experiment.
policy.ExperimentPolicy.utility_input_source`'s signature is
`Callable[[InformationValueEstimate], ExperimentUtilityInput]` -- it
receives only the already-computed information-value ESTIMATE, not the
candidate's raw sample count. The utility policy this investigation
needs (see `_utility_input_for` below) must distinguish "zero real
samples" (an unexplored candidate, worth an exploratory bootstrap
benefit) from "one real sample" (partially explored, uncertainty not
yet computable, but no longer a wholly fresh unknown) -- a distinction
`InformationValueEstimate` alone cannot answer (its `estimate`/`.basis`
free-text string is not something a caller should parse to recover a
number; `materials.model_state.ModelStateInformationValueModel.estimate`
reports the same `None` for zero samples and for one sample alike).
This means a policy shaped like this investigation's could not be
plugged into `run_experiment_step` via that one callback alone; it
could still be expressed by composing the same underlying primitives
directly, exactly as this module does, and exactly as `run_experiment_step`
itself does internally. This is worth recording, but it is NOT the
"genuinely missing primitive" Phase 69 sec.12 asks about: it is a
narrower callback shape on one particular composition helper, not a gap
in `predict`/`estimate_information_value`/`evaluate_utility_set`/
`optimize_candidates` themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Tuple

from evidence.admission import admit_document, admit_record, admit_referent
from evidence.pool import EvidencePool
from evidence.types import make_document, make_record, make_referent, make_source
from experiment.session import ExperimentSession, make_experiment_session
from materials.assessment import PredictionAssessment
from materials.campaign import assemble_experimental_campaign
from materials.candidates import ActionCandidate, CandidateSet, generate_candidates
from materials.decision import make_criterion
from materials.design import assemble_experimental_design
from materials.diagnostics import StateTransitionDiagnosticSet, diagnose_transitions
from materials.ensemble import (
    CounterfactualInformationValue, CounterfactualOutcome, CounterfactualSet,
    evaluate_counterfactual_information_value, make_counterfactual_set, project_outcome,
)
from materials.evaluation import evaluate_candidates
from materials.information import estimate_information_value
from materials.iteration import MaterialsIteration, reevaluate_program
from materials.model_state import ModelStateInformationValueModel, resolve_model_state_key
from materials.optimization import OptimizationPolicy, OptimizationResult, optimize_candidates
from materials.plan import assemble_experiment_plan
from materials.program import make_material_program_query
from materials.results import admit_experimental_result, make_experimental_result
from materials.selection import SelectionPolicy, select_candidates
from materials.trajectory import make_model_state_trajectory
from materials.utility import ExperimentUtilityInput, evaluate_utility_set
from materials.value import evaluate_candidate_information_values
from retrieval.engine import DeterministicRetrievalEngine

FORMULATION_KEY = "formulation-f1"
PROCESS_KEY = "process-std-190c"
PROPERTY = "tensile_strength"
UNIT = "MPa"
CRITERION_TARGET = 80.0

# The two experimental contexts this investigation compares -- a real
# materials-engineering question ("does tensile strength at this
# formulation/process meet the same target at both a room-temperature
# and an elevated-temperature service condition?"), each producing its
# own EvidenceRequirement/ActionCandidate (materials.candidates keys a
# candidate by, among other things, the criterion's own context --
# empirically confirmed, not assumed, before writing this module).
CONTEXT_ROOM_TEMPERATURE = {"temperature": 25}
CONTEXT_ELEVATED_TEMPERATURE = {"temperature": 100}

ALLOW_ALL_SELECTION_POLICY = SelectionPolicy(
    allowed_action_classes=None, allow_already_represented_context=True,
    allow_redundant=True, allow_not_determinable_feasibility=True, max_selected=None,
)
DECISION_POLICY = OptimizationPolicy(max_candidates=1, allowed_action_classes=None, allow_indeterminate_utility=False)

# The fixed, caller-judged cost of running one measurement in this
# scenario -- an engineering policy constant (materials.utility.
# ExperimentUtilityInput.cost is, by that module's own docstring, always
# a caller judgment, never a derived fact), identical for both
# candidates so it never asymmetrically favors one context over the
# other on its own.
MEASUREMENT_COST = 0.5

# The exploratory bootstrap benefit for a candidate with ZERO real
# samples (mirrors the same explicit, documented "explore once" constant
# Phase 65 already established for exactly this bootstrap case) and the
# smaller, still-positive benefit for a candidate with exactly ONE real
# sample (partially explored -- its uncertainty is not yet computable,
# but it is no longer a wholly fresh unknown either). Both are caller
# policy choices, not derived facts -- see this module's own docstring
# for why `InformationValueEstimate` alone cannot express this
# distinction and why that is a callback-shape limitation of
# `run_experiment_step`, not a gap in the underlying algebra this
# investigation instead composes directly.
BOOTSTRAP_BENEFIT = 1.0
PARTIAL_EXPLORATION_BENEFIT = 0.4


def _fixed_clock() -> Callable[[], str]:
    counter = {"n": 0}

    def clock() -> str:
        n = counter["n"]
        counter["n"] += 1
        return f"2026-08-24T02:{n:02d}:00Z"

    return clock


@dataclass(frozen=True)
class DecisionRecord:
    """One point in the investigation where a real decision was made --
    embeds the complete, unmodified `OptimizationResult` (full
    provenance: every candidate's utility/status, not just the chosen
    one) plus the `ActionCandidate` `optimize_candidates` actually
    selected. `label` is a human-readable tag for the transcript/report
    only; it carries no semantics of its own."""

    label: str
    optimization: OptimizationResult
    selected_candidate: ActionCandidate


@dataclass
class InvestigationResult:
    """Everything this investigation produced, embedded whole -- the
    test file asserts against these real objects directly rather than
    re-parsing printed narration text."""

    candidate_room: ActionCandidate
    candidate_elevated: ActionCandidate
    iteration: MaterialsIteration
    sessions: List[ExperimentSession] = field(default_factory=list)
    assessments: List[PredictionAssessment] = field(default_factory=list)
    decisions: List[DecisionRecord] = field(default_factory=list)
    counterfactual_outcomes: Tuple[CounterfactualOutcome, ...] = ()
    counterfactual_set: CounterfactualSet = None  # type: ignore[assignment]
    counterfactual_information_value: CounterfactualInformationValue = None  # type: ignore[assignment]
    diagnostics: StateTransitionDiagnosticSet = None  # type: ignore[assignment]


def _bootstrap_investigation_scenario(clock: Callable[[], str]) -> Tuple[ExperimentSession, CandidateSet, MaterialsIteration, object]:
    """Builds the pool/session for THIS investigation's own scenario --
    two experimental contexts for one formulation/property, zero prior
    evidence (the explicit bootstrap case, per Phase 69 sec.2). A
    separate function from `workbench.interaction.bootstrap_default_
    scenario` (Phase 68's single-candidate demo scenario) so neither
    file changes the other's behavior."""
    pool = EvidencePool()
    engine = DeterministicRetrievalEngine()

    source = make_source(kind="lab_notebook", name="Closed-loop investigation")
    pool.put_source(source)
    doc = make_document(
        source_id=source.id, raw_content="closed-loop materials investigation",
        retrieval_method="manual_entry", retrieved_at=clock(),
    )
    admit_document(pool, doc)
    pool.put_document(doc)
    process = make_referent(natural_key=PROCESS_KEY, kind="process")
    admit_referent(pool, process)
    pool.put_referent(process)
    formulation = make_referent(natural_key=FORMULATION_KEY, kind="formulation")
    admit_referent(pool, formulation)
    pool.put_referent(formulation)

    criterion_room = make_criterion(PROPERTY, ">=", CRITERION_TARGET, context=CONTEXT_ROOM_TEMPERATURE)
    criterion_elevated = make_criterion(PROPERTY, ">=", CRITERION_TARGET, context=CONTEXT_ELEVATED_TEMPERATURE)
    query = make_material_program_query([FORMULATION_KEY], PROCESS_KEY, (PROPERTY,))
    iteration = reevaluate_program(pool, engine, query, (criterion_room, criterion_elevated))
    candidates = generate_candidates(iteration.specification)

    evaluations = evaluate_candidates(candidates)
    selection = select_candidates(evaluations, ALLOW_ALL_SELECTION_POLICY)
    plan = assemble_experiment_plan(selection)
    design = assemble_experimental_design(plan)
    campaign = assemble_experimental_campaign(design)

    session = make_experiment_session(pool, engine, iteration, document_id=doc.id)
    return session, candidates, iteration, campaign


def _sample_count(state, candidate: ActionCandidate) -> int:
    key = resolve_model_state_key(candidate.formulation.id, candidate.property, candidate.target_context)
    return len(state.samples.get(key, ()))


def _utility_input_for(candidate: ActionCandidate, state, iteration: MaterialsIteration):
    """The investigation's own engineering policy (a caller judgment,
    never a derived fact -- see module docstring): prefer the model's
    real current uncertainty once it is computable; otherwise treat a
    wholly unmeasured candidate as worth an exploratory bootstrap benefit,
    and a once-measured-but-not-yet-determinable candidate as worth a
    smaller, still-positive continued benefit. Returns
    `(ExperimentUtilityInput, estimate)` so the caller can also report
    the raw model estimate (ESTIMATED/NOT_DETERMINABLE) alongside the
    resulting utility input."""
    model = ModelStateInformationValueModel(state)
    estimate = estimate_information_value(candidate, iteration, model)
    if estimate.estimate is not None:
        benefit = estimate.estimate
    elif _sample_count(state, candidate) == 0:
        benefit = BOOTSTRAP_BENEFIT
    else:
        benefit = PARTIAL_EXPLORATION_BENEFIT
    return ExperimentUtilityInput(benefit=benefit, cost=MEASUREMENT_COST), estimate


def _decide(candidates: CandidateSet, state, iteration: MaterialsIteration, label: str) -> DecisionRecord:
    """evaluate_utility_set() + optimize_candidates(max_candidates=1) --
    the existing decision primitives, unmodified, called directly
    (Phase 69 sec.3: 'do not create a new decision primitive')."""
    civs = evaluate_candidate_information_values(candidates, iteration)
    utility_inputs = {c.id: _utility_input_for(c, state, iteration)[0] for c in candidates.candidates}
    utility_set = evaluate_utility_set(civs, utility_inputs)
    optimization = optimize_candidates(utility_set, DECISION_POLICY)
    selected = [o for o in optimization.optimizations if o.status == "SELECTED"]
    if len(selected) != 1:
        raise ValueError(f"expected exactly one SELECTED candidate at decision {label!r}; got {len(selected)}")
    selected_candidate = next(c for c in candidates.candidates if c.id == selected[0].candidate_id)
    return DecisionRecord(label=label, optimization=optimization, selected_candidate=selected_candidate)


def _observe(
    session: ExperimentSession, campaign, candidate: ActionCandidate, value: float, locator: str, clock: Callable[[], str],
) -> Tuple[PredictionAssessment, ExperimentSession]:
    """The one place this investigation admits anything -- the same
    admit_record/admit_experimental_result sequence `experiment/step.py`
    and `workbench/interaction.py` already use. `value` is always an
    externally supplied experimental observation, never fabricated by
    this module's own computation."""
    entry = next(e for e in campaign.entries if e.candidate_id == candidate.id)
    prediction = session.predict(candidate)
    record = make_record(document_id=session.document_id, locator=locator, raw_content=f"{value} {UNIT}")
    admitted_record = admit_record(session.pool, record)
    if isinstance(admitted_record, list):
        raise ValueError(f"observation Record was rejected by admit_record: {admitted_record!r}")
    session.pool.put_record(record)
    result = make_experimental_result(
        campaign, entry, content={"property": candidate.property, "value": value, "unit": UNIT},
        record_id=record.id, extracted_at=clock(),
    )
    admitted = admit_experimental_result(session.pool, result, confidence=1.0)
    if isinstance(admitted, list):
        raise ValueError(f"ExperimentalResult was rejected by admit_experimental_result: {admitted!r}")
    observation, _relationship = admitted
    return session.observe(candidate, prediction, result, observation)


def _print_decision(decision: DecisionRecord) -> None:
    print(f"  decision: {decision.label}")
    for o in decision.optimization.optimizations:
        candidate = next(
            c for c in decision.optimization.utility_set.candidate_information_values.candidate_set.candidates
            if c.id == o.candidate_id
        )
        print(
            f"    {dict(candidate.target_context)}: utility={o.utility.utility} "
            f"(benefit-cost, {o.utility.utility_status})  status={o.status}"
        )
    print(f"    -> selected: {dict(decision.selected_candidate.target_context)}")


def run_investigation() -> InvestigationResult:
    """The full closed-loop investigation, narrated. Deterministic
    (fixed clock); every printed number is read directly off a real
    domain object -- nothing here recomputes a mean/variance/residual
    by hand."""
    clock = _fixed_clock()
    session, candidates, iteration, campaign = _bootstrap_investigation_scenario(clock)
    candidate_room = next(c for c in candidates.candidates if c.target_context.get("temperature") == 25)
    candidate_elevated = next(c for c in candidates.candidates if c.target_context.get("temperature") == 100)
    result = InvestigationResult(
        candidate_room=candidate_room, candidate_elevated=candidate_elevated, iteration=iteration,
    )
    result.sessions.append(session)

    print("=" * 70)
    print("CLOSED-LOOP MATERIALS INVESTIGATION")
    print(f"formulation={FORMULATION_KEY!r} process={PROCESS_KEY!r} property={PROPERTY!r}")
    print(f"candidates: room-temperature (25C)={candidate_room.id[:12]}...  "
          f"elevated-temperature (100C)={candidate_elevated.id[:12]}...")
    print("=" * 70)

    print("\n--- INITIAL STATE ---")
    print(f"ModelState.id = {session.state.id[:12]}...")
    for c in (candidate_room, candidate_elevated):
        prediction = session.predict(c)
        print(
            f"  {dict(c.target_context)}: predicted_value={prediction.predicted_value} "
            f"uncertainty={prediction.uncertainty} sample_count={prediction.sample_count}"
        )

    print("\n--- COUNTERFACTUAL EXPLORATION (before the first real experiment) ---")
    outcome_high = project_outcome(session.state, candidate_room, 88.0, probability=0.5)
    outcome_low = project_outcome(session.state, candidate_room, 70.0, probability=0.5)
    cf_set = make_counterfactual_set((outcome_high, outcome_low))
    civ = evaluate_counterfactual_information_value(cf_set, candidate_room, iteration)
    outcome_high_repeat = project_outcome(session.state, candidate_room, 88.0, probability=0.5)
    print(f"  hypothetical branch (88.0): projected_state={outcome_high.projected_state_id[:12]}... "
          f"prediction_after={outcome_high.prediction_after.predicted_value}")
    print(f"  hypothetical branch (70.0): projected_state={outcome_low.projected_state_id[:12]}... "
          f"prediction_after={outcome_low.prediction_after.predicted_value}")
    print(f"  expected_information_value = {civ.expected_information_value} ({civ.expected_information_value_status})")
    print(f"  source state unchanged: {session.state.id == result.sessions[0].state.id}")
    print(f"  identical hypothetical input is deterministic: "
          f"{outcome_high.projected_state.id == outcome_high_repeat.projected_state.id}")
    result.counterfactual_outcomes = (outcome_high, outcome_low)
    result.counterfactual_set = cf_set
    result.counterfactual_information_value = civ

    decision_1 = _decide(candidates, session.state, iteration, "D1 (initial)")
    print("\n--- DECISION 1 ---")
    _print_decision(decision_1)
    result.decisions.append(decision_1)

    print("\n--- OBSERVATION 1 (externally supplied experimental observation) ---")
    value_1 = 88.0
    print(f"  measuring {dict(decision_1.selected_candidate.target_context)}: observed value = {value_1} {UNIT}")
    assessment_1, session = _observe(session, campaign, decision_1.selected_candidate, value_1, "obs-1", clock)
    result.sessions.append(session)
    result.assessments.append(assessment_1)
    print("\n--- RESIDUAL 1 ---")
    print(f"  prediction={assessment_1.predicted_value}  observed={assessment_1.observed_value}  "
          f"residual={assessment_1.residual}  absolute_residual={assessment_1.absolute_residual}")
    print(f"\n--- UPDATED STATE --- ModelState.id = {session.state.id[:12]}...")

    decision_2 = _decide(candidates, session.state, iteration, "D2 (after observation 1)")
    print("\n--- DECISION 2 ---")
    _print_decision(decision_2)
    changed_1_to_2 = decision_1.selected_candidate.id != decision_2.selected_candidate.id
    print(f"  decision changed from D1: {changed_1_to_2}")
    result.decisions.append(decision_2)

    print("\n--- OBSERVATION 2 (externally supplied experimental observation) ---")
    value_2 = 65.0
    print(f"  measuring {dict(decision_2.selected_candidate.target_context)}: observed value = {value_2} {UNIT}")
    assessment_2, session = _observe(session, campaign, decision_2.selected_candidate, value_2, "obs-2", clock)
    result.sessions.append(session)
    result.assessments.append(assessment_2)
    print(f"  residual={assessment_2.residual}")

    print("\n--- OBSERVATION 3 (second real sample, room-temperature candidate) ---")
    value_3 = 102.0
    print(f"  measuring {dict(candidate_room.target_context)}: observed value = {value_3} {UNIT}")
    assessment_3, session = _observe(session, campaign, candidate_room, value_3, "obs-3", clock)
    result.sessions.append(session)
    result.assessments.append(assessment_3)
    print("--- RESIDUAL 3 ---")
    print(f"  prediction={assessment_3.predicted_value}  observed={assessment_3.observed_value}  "
          f"residual={assessment_3.residual}  absolute_residual={assessment_3.absolute_residual}")

    decision_3 = _decide(candidates, session.state, iteration, "D3 (after observation 3)")
    print("\n--- DECISION 3 ---")
    _print_decision(decision_3)
    result.decisions.append(decision_3)

    print("\n--- OBSERVATION 4 (third real sample, room-temperature candidate) ---")
    value_4 = 70.0
    print(f"  measuring {dict(candidate_room.target_context)}: observed value = {value_4} {UNIT}")
    assessment_4, session = _observe(session, campaign, candidate_room, value_4, "obs-4", clock)
    result.sessions.append(session)
    result.assessments.append(assessment_4)
    print("--- RESIDUAL 4 ---")
    print(f"  prediction={assessment_4.predicted_value}  observed={assessment_4.observed_value}  "
          f"residual={assessment_4.residual}  absolute_residual={assessment_4.absolute_residual}")

    decision_4 = _decide(candidates, session.state, iteration, "D4 (final)")
    print("\n--- DECISION 4 (final) ---")
    _print_decision(decision_4)
    result.decisions.append(decision_4)

    print("\n--- TRAJECTORY DIAGNOSTICS (room-temperature candidate) ---")
    trajectory = make_model_state_trajectory(tuple(s.state for s in result.sessions))
    diagnostics = diagnose_transitions(trajectory, candidate_room, tuple(result.assessments))
    result.diagnostics = diagnostics
    for i, d in enumerate(diagnostics.diagnostics, start=1):
        observed = "no observation recorded for this transition" if d.assessment is None else d.observation_value
        residual = "n/a" if d.assessment is None else d.residual_against_previous_prediction
        print(
            f"  [{i}] {d.predecessor_state_id[:8]}... -> {d.successor_state_id[:8]}...  "
            f"prev_pred={d.previous_prediction.predicted_value}  new_pred={d.new_prediction.predicted_value}  "
            f"delta={d.delta_predicted_value}  observed={observed}  residual={residual}"
        )

    print("\n" + "=" * 70)
    print("INVESTIGATION COMPLETE")
    print("=" * 70)
    return result


if __name__ == "__main__":
    run_investigation()
