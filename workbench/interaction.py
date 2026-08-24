"""WorkbenchState + bootstrap_default_scenario: the session-orchestration
layer for Phase 68's interactive workbench, deliberately separate from
`workbench.cli`'s command parsing (requirement 10) so this module can be
exercised directly by tests with no stdin/stdout involved at all.

Before writing this module, `experiment/session.py`, `experiment/step.py`,
`experiment/__init__.py`, `materials/model_state.py`, `materials/
assessment.py`, `materials/counterfactual.py`, `materials/ensemble.py`,
`materials/trajectory.py`, `materials/diagnostics.py`,
`tests/test_experiment_step.py`, `tests/test_experiment_residual_loop.py`,
`tests/test_experiment_interactive_session.py`, and
`docs/EXPERIMENT_ARCHITECTURE.md` were all re-read. Finding: every
number a human would want to see interactively already has a name and a
producer -- `session.predict`, `session.inspect_counterfactual`,
`session.observe`, `experiment.session.trajectory_of`, `materials.
diagnostics.diagnose_transitions`. Nothing below computes a mean,
variance, or residual itself; every value this module returns is read
directly off the object one of those calls returned.

WHY A NEW `WorkbenchState` CLASS, NOT JUST BARE VARIABLES: something has
to hold "which candidate is currently selected" and "the growing list of
assessments produced so far this run" between one command and the next --
storage a stateless REPL loop needs somewhere. `WorkbenchState` is that
holder, and ONLY that: an interaction/orchestration object, exactly like
`ExperimentSession` itself is described as being in `experiment/
session.py`'s own docstring -- it is NOT a domain object, unlike
`ModelState`/`Prediction`/`PredictionAssessment` (immutable, exactly as
Phase 52-61 established). `WorkbenchState` is deliberately a plain
mutable dataclass: `self.session` is REASSIGNED after every real
`observe()` call, mirroring exactly the rebind
(`assessment, session = session.observe(...)`) a bare CLI-loop-local
variable would need to do -- see `observe()` below. The underlying
`ExperimentSession`/`ModelState` objects it points to are never mutated;
only which one `self.session` currently names changes.

`assessments: List[PredictionAssessment]` is NOT a new `ResidualHistory`/
`ExperimentHistory`/`SessionHistory` class (Phase 68's own explicit
prohibition) -- it is a plain, growing list of already-existing
`materials.assessment.PredictionAssessment` objects, kept for exactly one
reason: `materials.trajectory.prediction_evolution`/`materials.
diagnostics.diagnose_transitions` already accept precisely this shape
(`Tuple[PredictionAssessment, ...]`) as their own optional `assessments`
argument, and `ExperimentSession` itself deliberately does not retain a
prediction's assessment after `observe()` returns it (see `experiment/
session.py`'s own Phase 66 "declined: last-assessment storage" note) --
some caller has to hold onto it if a later `history` command is going to
be able to show residuals at all. No new dataclass, no new field on any
domain object, no new mathematics: `history()` below hands this list
straight to `diagnose_transitions`, unmodified.

CLOCK: neither `evidence.types.Document.retrieved_at` nor `materials.
results.ExperimentalResult.extracted_at` is optional -- both require a
real ISO-8601 string, and this module never fabricates one. Interactive
use (`bootstrap_default_scenario()`/`WorkbenchState.observe()` called
with no `clock` override) reads the actual wall clock
(`_utc_now_iso`) -- an honest record of when the workbench actually ran,
never a placeholder. `workbench.demo` supplies a small deterministic
clock instead, purely so repeated demo runs are byte-for-byte
reproducible; both paths go through the exact same code, never two
parallel implementations of scenario setup.

SCENARIO CONSTANTS (`DEFAULT_FORMULATION_KEY` etc.) are this module's own
fixed demonstration scenario -- the same formulation-f1/process-std-190c/
tensile_strength/">= 80"/"MPa" shape `tests/test_experiment_residual_
loop.py` and `tests/test_experiment_interactive_session.py` already
proved working, reused here rather than invented fresh. `DEFAULT_UNIT`
is this ONE scenario's own fixed unit, not a general physical inference:
`observe` accepts an explicit unit override for any other candidate a
future scenario might introduce.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple

from evidence.admission import admit_document, admit_record, admit_referent
from evidence.pool import EvidencePool
from evidence.types import make_document, make_record, make_referent, make_source
from experiment.session import ExperimentSession, make_experiment_session, trajectory_of
from materials.assessment import PredictionAssessment
from materials.campaign import ExperimentalCampaign, assemble_experimental_campaign
from materials.candidates import ActionCandidate, CandidateSet, generate_candidates
from materials.decision import make_criterion
from materials.design import assemble_experimental_design
from materials.diagnostics import StateTransitionDiagnosticSet, diagnose_transitions
from materials.ensemble import CounterfactualOutcome
from materials.evaluation import evaluate_candidates
from materials.iteration import reevaluate_program
from materials.model_state import Prediction
from materials.plan import assemble_experiment_plan
from materials.program import make_material_program_query
from materials.results import admit_experimental_result, make_experimental_result
from materials.selection import SelectionPolicy, select_candidates
from retrieval.engine import DeterministicRetrievalEngine, RetrievalEngine

DEFAULT_FORMULATION_KEY = "formulation-f1"
DEFAULT_PROCESS_KEY = "process-std-190c"
DEFAULT_PROPERTY = "tensile_strength"
DEFAULT_UNIT = "MPa"
DEFAULT_CRITERION_TARGET = 80.0

ALLOW_ALL_SELECTION_POLICY = SelectionPolicy(
    allowed_action_classes=None, allow_already_represented_context=True,
    allow_redundant=True, allow_not_determinable_feasibility=True, max_selected=None,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkbenchState:
    """The interaction-layer holder described in this module's own
    docstring -- not a domain object. See above for why `session`/
    `selected_candidate` are reassigned rather than the underlying
    `ExperimentSession`/`ModelState` ever being mutated, and why
    `assessments` is a plain list rather than a new history class."""

    pool: EvidencePool
    engine: RetrievalEngine
    document_id: str
    candidates: CandidateSet
    campaign: ExperimentalCampaign
    session: ExperimentSession
    clock: Callable[[], str]
    selected_candidate: Optional[ActionCandidate] = None
    assessments: List[PredictionAssessment] = field(default_factory=list)
    locator_counter: int = 0

    def list_candidates(self) -> Tuple[ActionCandidate, ...]:
        return self.candidates.candidates

    def select_candidate(self, index: int) -> ActionCandidate:
        candidates = self.candidates.candidates
        if not (0 <= index < len(candidates)):
            raise IndexError(f"candidate index {index} out of range (0..{len(candidates) - 1})")
        self.selected_candidate = candidates[index]
        return self.selected_candidate

    def _require_selected_candidate(self) -> ActionCandidate:
        if self.selected_candidate is None:
            raise ValueError("no candidate selected -- use `candidates` then `select <n>` first")
        return self.selected_candidate

    def _campaign_entry(self, candidate: ActionCandidate):
        entry = next((e for e in self.campaign.entries if e.candidate_id == candidate.id), None)
        if entry is None:
            raise ValueError(
                f"candidate {candidate.id!r} has no ExperimentalCampaign entry -- "
                "select a different candidate (see `candidates`)"
            )
        return entry

    def predict(self) -> Prediction:
        """y_hat_t = G(S_t, x) -- `ExperimentSession.predict`, unmodified."""
        candidate = self._require_selected_candidate()
        return self.session.predict(candidate)

    def explore(self, hypothetical_value: float) -> CounterfactualOutcome:
        """`ExperimentSession.inspect_counterfactual`, unmodified. Never
        advances `self.session` -- the returned `CounterfactualOutcome.
        projected_state` is a separate, hypothetical object; nothing here
        rebinds `self.session`."""
        candidate = self._require_selected_candidate()
        return self.session.inspect_counterfactual(candidate, hypothetical_value)

    def _next_locator(self) -> str:
        self.locator_counter += 1
        return f"workbench:observation:{self.locator_counter}"

    def observe(self, value: float, unit: Optional[str] = None) -> Tuple[PredictionAssessment, Prediction]:
        """r_t = y_t - y_hat_t, S_(t+1) = F(S_t, y_t) -- the one place
        this module admits anything, mirroring `experiment/step.py`'s own
        exact admission sequence (a raw `Record`, via `admit_record`/
        `pool.put_record`, then the sole semantic write boundary,
        `materials.results.admit_experimental_result`) as the caller
        responsibility `ExperimentSession.observe` has always required
        (see `experiment/session.py`). Reassigns `self.session` to the
        new session `ExperimentSession.observe` returns; never mutates
        the old one."""
        candidate = self._require_selected_candidate()
        entry = self._campaign_entry(candidate)
        prediction = self.session.predict(candidate)

        resolved_unit = unit if unit is not None else DEFAULT_UNIT
        locator = self._next_locator()
        record = make_record(document_id=self.document_id, locator=locator, raw_content=f"{value} {resolved_unit}")
        admitted_record = admit_record(self.pool, record)
        if isinstance(admitted_record, list):
            raise ValueError(f"observation Record was rejected by admit_record: {admitted_record!r}")
        self.pool.put_record(record)

        result = make_experimental_result(
            self.campaign, entry, content={"property": candidate.property, "value": value, "unit": resolved_unit},
            record_id=record.id, extracted_at=self.clock(),
        )
        admitted_result = admit_experimental_result(self.pool, result, confidence=1.0)
        if isinstance(admitted_result, list):
            raise ValueError(f"ExperimentalResult was rejected by admit_experimental_result: {admitted_result!r}")
        observation, _relationship = admitted_result

        assessment, new_session = self.session.observe(candidate, prediction, result, observation)
        self.session = new_session
        self.assessments.append(assessment)
        return assessment, prediction

    def history(self) -> StateTransitionDiagnosticSet:
        """Reuses `experiment.session.trajectory_of` (== `materials.
        trajectory.make_model_state_trajectory(session.state_history)`)
        and `materials.diagnostics.diagnose_transitions` directly -- no
        new history representation, per Phase 68's explicit instruction.
        `self.assessments` is handed through unmodified so residuals
        appear per transition; a transition this run never observed
        (none exist yet for a fresh session) simply has no matching
        assessment, and `diagnose_transitions` already reports that as
        `None`, not a guess."""
        candidate = self._require_selected_candidate()
        trajectory = trajectory_of(self.session)
        return diagnose_transitions(trajectory, candidate, tuple(self.assessments))


def bootstrap_default_scenario(clock: Callable[[], str] = _utc_now_iso) -> WorkbenchState:
    """Builds ONE fixed, reproducible engineering scenario -- the exact
    formulation-f1/process-std-190c/tensile_strength/criterion>=80
    fixture shape already proved working by `tests/test_experiment_
    residual_loop.py`/`tests/test_experiment_interactive_session.py` --
    using only the existing admission/specification/candidate-generation
    API. Both `workbench.cli`'s interactive entry point and `workbench.
    demo` call this SAME function; neither re-implements scenario setup
    independently."""
    pool = EvidencePool()
    engine = DeterministicRetrievalEngine()

    source = make_source(kind="lab_notebook", name="Workbench session")
    pool.put_source(source)
    doc = make_document(
        source_id=source.id, raw_content="interactive workbench session",
        retrieval_method="manual_entry", retrieved_at=clock(),
    )
    admit_document(pool, doc)
    pool.put_document(doc)
    process = make_referent(natural_key=DEFAULT_PROCESS_KEY, kind="process")
    admit_referent(pool, process)
    pool.put_referent(process)
    formulation = make_referent(natural_key=DEFAULT_FORMULATION_KEY, kind="formulation")
    admit_referent(pool, formulation)
    pool.put_referent(formulation)

    criterion = make_criterion(DEFAULT_PROPERTY, ">=", DEFAULT_CRITERION_TARGET)
    query = make_material_program_query([DEFAULT_FORMULATION_KEY], DEFAULT_PROCESS_KEY, (DEFAULT_PROPERTY,))
    iteration = reevaluate_program(pool, engine, query, (criterion,))
    candidates = generate_candidates(iteration.specification)

    evaluations = evaluate_candidates(candidates)
    selection = select_candidates(evaluations, ALLOW_ALL_SELECTION_POLICY)
    plan = assemble_experiment_plan(selection)
    design = assemble_experimental_design(plan)
    campaign = assemble_experimental_campaign(design)

    session = make_experiment_session(pool, engine, iteration, document_id=doc.id)
    return WorkbenchState(
        pool=pool, engine=engine, document_id=doc.id, candidates=candidates,
        campaign=campaign, session=session, clock=clock,
    )
