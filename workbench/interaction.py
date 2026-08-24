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

PHASE 70 -- FROM DEMONSTRATION TO A GENUINELY USABLE INSTRUMENT: this
phase's own investigation (re-reading this file, `workbench/cli.py`,
`workbench/investigation.py`, `workbench/demo.py`, `experiment/step.py`,
`materials/value.py`, `materials/information.py`, `materials/utility.py`,
`materials/optimization.py`, `materials/candidates.py`, and every
existing workbench/experiment test before writing anything) found that
`predict`/`inspect_counterfactual`/`observe`/`history` (Phase 66-68)
already cover the state/prediction/counterfactual/residual/history half
of the interactive loop completely -- nothing there needed to change.
What was genuinely missing was DECISION inspection: nothing anywhere let
a human ask "which candidate does the existing optimization machinery
currently prefer, and why." `evaluate_candidate_information_values`
(Phase 46), `estimate_information_value`/`ModelStateInformationValueModel`
(Phase 50/52), `evaluate_utility_set` (Phase 47), and `optimize_candidates`
(Phase 48) already fully answer that question for any `CandidateSet` --
this phase adds no new decision mathematics, only `evaluate_decision`
below, a THIN, side-effect-free composition of those four unmodified
functions (mirroring exactly how `experiment/step.py` and `workbench/
investigation.py` already compose them), plus `WorkbenchState.decide()`,
which calls it and remembers the result for `status` to report.

`_utility_input_for`'s three-tier policy (bootstrap benefit for a wholly
unmeasured candidate; a smaller, still-positive benefit for one that has
exactly one real sample but not yet a computable uncertainty; the
model's real current uncertainty once 2+ samples make it computable) is
the SAME caller-supplied engineering policy `workbench/investigation.py`
(Phase 69) already validated end to end -- moved here as the workbench's
own canonical default so `decide`/`candidates` have a real, deterministic
policy to evaluate against out of the box, and `workbench/investigation.py`
now imports it from here rather than keeping its own copy. `materials.
utility.ExperimentUtilityInput.benefit`/`.cost` are, by that module's own
docstring, always caller judgments, never derived facts -- this policy
is exactly that: an explicit, documented choice, never a fabricated
"real" number standing in for a `None`/`NOT_DETERMINABLE` estimate.

`bootstrap_multi_candidate_scenario` is the SECOND scenario this module
now provides -- two experimental contexts (room/elevated temperature)
for one formulation/property, so `decide`/`select`/`candidates` are
meaningful the moment `python -m workbench` starts, with no external
file required. `bootstrap_default_scenario` (single candidate) is left
completely UNCHANGED and remains `workbench.demo`'s own scenario --
Phase 70's own instruction ("do not make the interactive CLI depend on
the demo") cuts both ways: the demo must not depend on the interactive
scenario changing either, so neither function was merged into the
other.

`WorkbenchState.last_counterfactual`/`.last_decision` are plain
`Optional` references to the most recent already-existing, already-
immutable `CounterfactualOutcome`/`OptimizationResult` this session
produced -- orchestration bookkeeping exactly like `assessments` above,
never a second state model. Both are cleared exactly when they would
otherwise silently go stale: `last_counterfactual` on `select_candidate`
(a new candidate's hypothetical has nothing to do with the old one) and
on `observe` (the real state moved on); `last_decision` on `observe`
only (selecting a different candidate to inspect does not itself
invalidate a decision computed across every candidate)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Mapping, Optional, Tuple, Union

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
from materials.information import InformationValueEstimate, estimate_information_value
from materials.iteration import MaterialsIteration, reevaluate_program
from materials.model_state import ModelState, ModelStateInformationValueModel, Prediction, resolve_model_state_key
from materials.optimization import OptimizationPolicy, OptimizationResult, optimize_candidates
from materials.plan import assemble_experiment_plan
from materials.program import make_material_program_query
from materials.results import admit_experimental_result, make_experimental_result
from materials.selection import SelectionPolicy, select_candidates
from materials.utility import ExperimentUtilityInput, evaluate_utility_set
from materials.value import evaluate_candidate_information_values
from retrieval.engine import DeterministicRetrievalEngine, RetrievalEngine

DEFAULT_FORMULATION_KEY = "formulation-f1"
DEFAULT_PROCESS_KEY = "process-std-190c"
DEFAULT_PROPERTY = "tensile_strength"
DEFAULT_UNIT = "MPa"
DEFAULT_CRITERION_TARGET = 80.0

# The two experimental contexts `bootstrap_multi_candidate_scenario`
# compares -- reused verbatim from Phase 69's own already-validated
# closed-loop investigation scenario.
CONTEXT_ROOM_TEMPERATURE = {"temperature": 25}
CONTEXT_ELEVATED_TEMPERATURE = {"temperature": 100}

ALLOW_ALL_SELECTION_POLICY = SelectionPolicy(
    allowed_action_classes=None, allow_already_represented_context=True,
    allow_redundant=True, allow_not_determinable_feasibility=True, max_selected=None,
)

# The workbench's own default decision policy -- see this module's
# docstring (PHASE 70) for why these are explicit, documented caller
# judgments (materials.utility's own vocabulary), never derived facts.
DECISION_POLICY = OptimizationPolicy(max_candidates=1, allowed_action_classes=None, allow_indeterminate_utility=False)
MEASUREMENT_COST = 0.5
BOOTSTRAP_BENEFIT = 1.0
PARTIAL_EXPLORATION_BENEFIT = 0.4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sample_count(state: ModelState, candidate: ActionCandidate) -> int:
    key = resolve_model_state_key(candidate.formulation.id, candidate.property, candidate.target_context)
    return len(state.samples.get(key, ()))


def _utility_input_for(
    candidate: ActionCandidate, state: ModelState, iteration: MaterialsIteration,
) -> Tuple[ExperimentUtilityInput, InformationValueEstimate]:
    """The workbench's own default engineering policy -- see this
    module's PHASE 70 docstring section for the full rationale. Returns
    `(ExperimentUtilityInput, estimate)` so a caller can also report the
    raw model estimate (ESTIMATED/NOT_DETERMINABLE) alongside the
    resulting utility input, never silently discarding it."""
    model = ModelStateInformationValueModel(state)
    estimate = estimate_information_value(candidate, iteration, model)
    if estimate.estimate is not None:
        benefit = estimate.estimate
    elif _sample_count(state, candidate) == 0:
        benefit = BOOTSTRAP_BENEFIT
    else:
        benefit = PARTIAL_EXPLORATION_BENEFIT
    return ExperimentUtilityInput(benefit=benefit, cost=MEASUREMENT_COST), estimate


def evaluate_decision(candidates: CandidateSet, state: ModelState, iteration: MaterialsIteration) -> OptimizationResult:
    """`evaluate_utility_set()` + `optimize_candidates(max_candidates=1)`
    -- the existing decision primitives, unmodified, composed exactly as
    `experiment/step.py` and `workbench/investigation.py` already do.
    Deterministic, side-effect-free: never mutates `candidates`, `state`,
    or `iteration`, and computes nothing `materials.value`/`materials.
    information`/`materials.utility`/`materials.optimization` did not
    already compute."""
    civs = evaluate_candidate_information_values(candidates, iteration)
    utility_inputs = {c.id: _utility_input_for(c, state, iteration)[0] for c in candidates.candidates}
    utility_set = evaluate_utility_set(civs, utility_inputs)
    return optimize_candidates(utility_set, DECISION_POLICY)


@dataclass(frozen=True)
class ResearchScenario:
    """CONFIGURATION ONLY -- what a researcher intends to investigate,
    never what has been observed. Frozen, and deliberately holding no
    `ModelState`/`ExperimentSession`/`EvidencePool`/`Observation`/
    prediction/residual/history field of any kind: scientific state
    lives exactly where Phases 52-72 already put it, and this object
    never becomes a second home for it.

    Introduced in Phase 73 rather than passing a bare `Mapping` around
    because scenario configuration now has a real consumer beyond
    candidate construction: `name` has to survive into the interactive
    session so `workbench.cli` can announce which study is loaded, and a
    bare mapping handed to `bootstrap_research_scenario` would drop it
    on the floor. A small immutable value object gives that
    configuration one stable, typed home on the
    `configuration -> candidate generation -> WorkbenchState` path --
    which is exactly the bar this phase set for adding one.

    `process`/`criterion_operator`/`criterion_target` carry defaults so
    the minimal scenario shape (`name`/`formulations`/`property`/
    `contexts`) loads as-is; a scenario that wants a different process
    or acceptance criterion states them explicitly. Every default is a
    named module constant, never a silently-invented number."""

    name: str
    formulations: Tuple[str, ...]
    property: str
    contexts: Tuple[Mapping[str, object], ...]
    process: str = DEFAULT_PROCESS_KEY
    criterion_operator: str = ">="
    criterion_target: float = DEFAULT_CRITERION_TARGET

    @staticmethod
    def from_config(config: Mapping[str, object]) -> "ResearchScenario":
        """Builds a `ResearchScenario` from a plain mapping -- exactly
        what stdlib `json.load` produces for a file like
        `examples/polymer_tensile_strength.json`. Validates only what is
        structurally required to construct valid existing candidate
        objects, and rejects a malformed scenario with a clear
        `ValueError` naming the offending field. No schema framework, no
        general configuration engine."""
        for required in ("name", "formulations", "property", "contexts"):
            if required not in config:
                raise ValueError(f"scenario is missing required field {required!r}")

        name = config["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError("scenario 'name' must be a non-empty string")

        formulations = config["formulations"]
        if not isinstance(formulations, (list, tuple)) or not formulations:
            raise ValueError("scenario 'formulations' must be a non-empty list of formulation names")
        if not all(isinstance(f, str) and f.strip() for f in formulations):
            raise ValueError("every entry in scenario 'formulations' must be a non-empty string")

        property_name = config["property"]
        if not isinstance(property_name, str) or not property_name.strip():
            raise ValueError("scenario 'property' must be a non-empty string")

        contexts = config["contexts"]
        if not isinstance(contexts, (list, tuple)) or not contexts:
            raise ValueError("scenario 'contexts' must be a non-empty list of experimental contexts")
        if not all(isinstance(c, Mapping) for c in contexts):
            raise ValueError("every entry in scenario 'contexts' must be a mapping of condition -> value")

        process = config.get("process", DEFAULT_PROCESS_KEY)
        if not isinstance(process, str) or not process.strip():
            raise ValueError("scenario 'process' must be a non-empty string when supplied")

        criterion = config.get("criterion", {})
        if not isinstance(criterion, Mapping):
            raise ValueError("scenario 'criterion' must be a mapping with 'operator' and 'target' when supplied")
        operator = criterion.get("operator", ">=")
        if not isinstance(operator, str) or not operator.strip():
            raise ValueError("scenario criterion 'operator' must be a non-empty string when supplied")
        target = criterion.get("target", DEFAULT_CRITERION_TARGET)
        if not isinstance(target, (int, float)) or isinstance(target, bool):
            raise ValueError("scenario criterion 'target' must be a number when supplied")

        return ResearchScenario(
            name=name, formulations=tuple(formulations), property=property_name,
            contexts=tuple(dict(c) for c in contexts), process=process,
            criterion_operator=operator, criterion_target=float(target),
        )

    def describe_candidate_space(self) -> str:
        """`formulations x contexts` -- the candidate count this
        scenario's configuration implies, for a caller that wants to
        state it before construction. Pure arithmetic over its own
        configuration; asserts nothing about the resulting candidates,
        which `materials.candidates.generate_candidates` alone
        determines."""
        return f"{len(self.formulations)} formulation(s) x {len(self.contexts)} context(s)"


@dataclass
class WorkbenchState:
    """The interaction-layer holder described in this module's own
    docstring -- not a domain object. See above for why `session`/
    `selected_candidate` are reassigned rather than the underlying
    `ExperimentSession`/`ModelState` ever being mutated, and why
    `assessments` is a plain list rather than a new history class.

    `scenario` (Phase 73) is the immutable `ResearchScenario` this state
    was constructed from, when one was supplied -- configuration only,
    carried alongside the session purely so the interaction layer can
    report which study is loaded. It is never read by any prediction,
    residual, utility, or optimization path."""

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
    last_counterfactual: Optional[CounterfactualOutcome] = None
    last_decision: Optional[OptimizationResult] = None
    scenario: Optional[ResearchScenario] = None

    def list_candidates(self) -> Tuple[ActionCandidate, ...]:
        return self.candidates.candidates

    def select_candidate(self, index: int) -> ActionCandidate:
        candidates = self.candidates.candidates
        if not (0 <= index < len(candidates)):
            raise IndexError(f"candidate index {index} out of range (0..{len(candidates) - 1})")
        self.selected_candidate = candidates[index]
        self.last_counterfactual = None
        return self.selected_candidate

    def total_sample_count(self) -> int:
        """The number of real samples across every cell of the current
        `ModelState` -- a plain structural count read directly off
        `state.samples`, not a new statistic."""
        return sum(len(samples) for samples in self.session.state.samples.values())

    def information_value_estimate(
        self, candidate: ActionCandidate, state: Optional[ModelState] = None,
    ) -> InformationValueEstimate:
        """`estimate_information_value` bound to this session's own
        `MaterialsIteration` and, by default, its current state -- a
        thin, side-effect-free composition so `workbench.cli` never has
        to call a `materials.*` function directly (that module's own
        docstring restricts it to parsing/formatting only). Accepts an
        explicit `state` override so a caller can ask "what would the
        information value be at THIS (e.g. hypothetical) state," exactly
        the same override shape `predict`/`inspect_counterfactual`
        already established a caller might need."""
        target_state = state if state is not None else self.session.state
        model = ModelStateInformationValueModel(target_state)
        return estimate_information_value(candidate, self.session.iteration, model)

    def decide(self) -> OptimizationResult:
        """`evaluate_decision`, bound to this session's current state and
        candidate set, remembered as `self.last_decision` for `status` to
        report. A read-only inspection: never advances `self.session`,
        never changes `self.selected_candidate` -- see this module's
        PHASE 70 docstring section for why a decision recommendation and
        the human's own interaction choice (`select_candidate`) remain
        two separate things."""
        result = evaluate_decision(self.candidates, self.session.state, self.session.iteration)
        self.last_decision = result
        return result

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
        outcome = self.session.inspect_counterfactual(candidate, hypothetical_value)
        self.last_counterfactual = outcome
        return outcome

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
        self.last_counterfactual = None
        self.last_decision = None
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


def bootstrap_research_scenario(
    config: Union[ResearchScenario, Mapping[str, object]], clock: Callable[[], str] = _utc_now_iso,
) -> WorkbenchState:
    """Phase 73: builds a `WorkbenchState` from a plain, standard-
    library-representable SCENARIO DEFINITION -- what a researcher wants
    to investigate -- never from SCIENTIFIC STATE (samples/predictions/
    residuals stay exactly what `ModelState`/`ExperimentSession` already
    are; `config` describes candidates, not observations, and this
    function never admits an `Observation` or a `ClaimedRelationship`).

    The scenario's own fields are documented on `ResearchScenario`
    above; `ResearchScenario.from_config` performs all validation, so a
    plain `Mapping` (exactly what stdlib `json.load` produces for a file
    like `examples/polymer_tensile_strength.json`) is accepted directly.
    Each context becomes its own `Criterion`/`ActionCandidate`/
    `ModelState` cell -- the same criterion-context-is-part-of-the-key
    discipline Phase 53 established and Phase 72 re-verified at N>2.
    Single-property by design: `materials.candidates`/`materials.
    decision` already support multiple properties structurally
    (`properties: Iterable[str]`, per-criterion `property`), so nothing
    here would need to change to add that later.

    This is exactly the SAME composition `bootstrap_default_scenario`/
    `bootstrap_multi_candidate_scenario` (below) already use --
    `reevaluate_program` -> `generate_candidates` -> `evaluate_candidates`
    -> `select_candidates` -> `assemble_experiment_plan` -> `assemble_
    experimental_design` -> `assemble_experimental_campaign` -> `make_
    experiment_session` -- generalized to read its formulation/property/
    criterion/context inputs from `config` instead of module-level
    constants. No new candidate-generation mechanism, no new identity
    scheme: every id involved (`Referent.id`, `ActionCandidate.id`,
    `ModelState` cell keys) is derived exactly the way it always has
    been, by the exact same `materials.*` functions.

    Accepts either a `ResearchScenario` (already validated) or a plain
    `Mapping`, which is passed through `ResearchScenario.from_config`
    first -- so a caller holding raw `json.load` output and a caller
    holding a typed scenario both reach the same construction path, and
    a malformed scenario is rejected identically either way."""
    scenario = config if isinstance(config, ResearchScenario) else ResearchScenario.from_config(config)
    formulation_keys = list(scenario.formulations)

    pool = EvidencePool()
    engine = DeterministicRetrievalEngine()

    source = make_source(kind="lab_notebook", name="User-defined research scenario")
    pool.put_source(source)
    doc = make_document(
        source_id=source.id, raw_content=f"research scenario: {scenario.name}",
        retrieval_method="manual_entry", retrieved_at=clock(),
    )
    admit_document(pool, doc)
    pool.put_document(doc)
    process = make_referent(natural_key=scenario.process, kind="process")
    admit_referent(pool, process)
    pool.put_referent(process)
    for formulation_key in formulation_keys:
        formulation = make_referent(natural_key=formulation_key, kind="formulation")
        admit_referent(pool, formulation)
        pool.put_referent(formulation)

    criteria = tuple(
        make_criterion(scenario.property, scenario.criterion_operator, scenario.criterion_target, context=context)
        for context in scenario.contexts
    )
    query = make_material_program_query(formulation_keys, scenario.process, (scenario.property,))
    iteration = reevaluate_program(pool, engine, query, criteria)
    candidates = generate_candidates(iteration.specification)

    evaluations = evaluate_candidates(candidates)
    selection = select_candidates(evaluations, ALLOW_ALL_SELECTION_POLICY)
    plan = assemble_experiment_plan(selection)
    design = assemble_experimental_design(plan)
    campaign = assemble_experimental_campaign(design)

    session = make_experiment_session(pool, engine, iteration, document_id=doc.id)
    return WorkbenchState(
        pool=pool, engine=engine, document_id=doc.id, candidates=candidates,
        campaign=campaign, session=session, clock=clock, scenario=scenario,
    )


def bootstrap_multi_candidate_scenario(clock: Callable[[], str] = _utc_now_iso) -> WorkbenchState:
    """The interactive CLI's own default scenario -- two experimental
    contexts (room/elevated temperature) for one formulation/property,
    so `decide`/`select`/`candidates` are meaningful the moment `python
    -m workbench` starts, with no external file required (Phase 70
    sec.2). Reuses the exact scenario `workbench/investigation.py`
    (Phase 69) already validated end to end -- that module now calls
    this function too, rather than keeping its own copy of this
    construction. `bootstrap_default_scenario` above is left completely
    unchanged and remains `workbench.demo`'s own single-candidate
    scenario; neither function was merged into the other (Phase 70's own
    instruction that the demo and the interactive CLI stay independent
    cuts both ways).

    Phase 73: now a thin, fixed-config call into `bootstrap_research_
    scenario` above rather than its own copy of the same construction --
    behavior-preserving (re-verified against every existing test this
    function's output feeds), never a second implementation of the same
    composition."""
    scenario = ResearchScenario(
        name="default two-context tensile strength study",
        formulations=(DEFAULT_FORMULATION_KEY,),
        property=DEFAULT_PROPERTY,
        contexts=(CONTEXT_ROOM_TEMPERATURE, CONTEXT_ELEVATED_TEMPERATURE),
        process=DEFAULT_PROCESS_KEY,
        criterion_operator=">=",
        criterion_target=DEFAULT_CRITERION_TARGET,
    )
    return bootstrap_research_scenario(scenario, clock=clock)
