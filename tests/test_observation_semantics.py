"""Phase 97: observation semantics and the experimental-context boundary.

INVESTIGATION RESULT -- context is NOT intentionally absent from evidence.
The repository decided years of phases ago that experimental context
lives in `Observation.content`, and the workbench does not comply.

WHAT AN OBSERVATION IS
    `evidence.types.Observation` is "a semantic, extracted fact, tied to
    the Record(s) it came from," whose `content` is "an open,
    extraction-defined mapping -- deliberately not forced into one
    schema." Identity is content_hash(record_ids, extraction_method,
    content); `confidence` and `extracted_at` are excluded on purpose.
    So an Observation is option (C) of the phase's four: a measurement
    PLUS whatever the extractor recorded about it -- context-bearing
    when the extractor supplies context, context-free when it does not.

WHERE CONTEXT IS SUPPOSED TO LIVE (settled by Phase 29, not by this one)
    `materials.analysis._comparison_context` treats every content key
    except `property` and the value key as part of the physical state
    being measured, and Phase 29's own docstring says this "splits
    viscosity's 25C/40C readings into two contexts automatically, with
    no `if property == 'viscosity'` anywhere." Its own test suite
    (tests/test_materials_comparability.py) admits observations carrying
    `temperature` directly in content, under the name
    `test_viscosity_different_conditions_not_reported_as_single_disagreement`.

    So: context belongs in Observation.content. That is design A, and it
    is already the established answer.

WHERE THE WORKBENCH LOSES IT
    `materials.results.admit_experimental_result` passes ONLY
    `result.content` to `make_observation`. The ExperimentalResult's
    `candidate_id` -- which encodes formulation + property +
    target_context -- is not carried into the Observation, and the
    ExperimentalResult itself is never stored in the pool. The workbench
    builds that content as {property, value, unit}, omitting the
    candidate's own declared `target_context`.

    The loss is therefore in what the WORKBENCH puts into content, not
    in the evidence or materials layers, both of which are complete.

CONSEQUENCE (a live false claim, not an inconvenience)
    Two valid measurements of two different conditions land in one
    ComparisonGroup and are reported as CONFLICTING_EVIDENCE with a
    spread. The evidence does not disagree with itself; it describes a
    dependence on a condition the evidence never recorded. This module
    documents that as a DEFECT rather than locking it as intent -- see
    the `known_defect` tests, which are written to fail loudly once the
    admission path is corrected, so the fix must update them knowingly.

NO PRODUCTION CHANGE IS MADE HERE. The fix is one line in
`WorkbenchState.observe`, and it changes every Observation.id,
ModelState.id and pool fingerprint the workbench produces. That is the
user's call, not a side effect of an investigation phase.
"""

from pathlib import Path

import pytest

from evidence.types import make_observation
from materials.analysis import _comparison_context
from materials.model_state import HYPOTHETICAL_SAMPLE_PREFIX, resolve_model_state_key
from workbench import theme
from workbench.cli import dispatch
from workbench.interaction import WorkbenchState, bootstrap_research_scenario

FOUR_CELL = {
    "name": "four cell context study",
    "process": "process-std-190c",
    "formulations": ["baseline", "modified"],
    "property": "tensile_strength",
    "criterion": {"operator": ">=", "target": 75.0},
    "contexts": [{"temperature_c": 25}, {"temperature_c": 100}],
}


def _clock():
    n = {"i": 0}

    def clock() -> str:
        n["i"] += 1
        return f"2026-08-25T11:{n['i']:02d}:00Z"

    return clock


@pytest.fixture(autouse=True)
def _plain():
    theme.set_color(False)
    yield
    theme.set_color(None)


def _four_cell() -> WorkbenchState:
    return bootstrap_research_scenario(dict(FOUR_CELL), clock=_clock())


@pytest.fixture()
def state() -> WorkbenchState:
    return _four_cell()


def _cell(candidate) -> str:
    return resolve_model_state_key(candidate.formulation.id, candidate.property,
                                   candidate.target_context)


# -- the four cells are distinct, and stay distinct ---------------------------------------------------


def test_four_candidate_cells_are_distinct(state: WorkbenchState):
    candidates = state.list_candidates()
    assert len(candidates) == 4
    assert len({c.id for c in candidates}) == 4
    assert len({_cell(c) for c in candidates}) == 4


def test_context_alone_distinguishes_two_cells(state: WorkbenchState):
    hot, cold = (
        next(c for c in state.list_candidates()
             if c.formulation.natural_key == "baseline"
             and dict(c.target_context) == {"temperature_c": t})
        for t in (100, 25)
    )
    assert hot.formulation.id == cold.formulation.id
    assert hot.property == cold.property
    assert _cell(hot) != _cell(cold)


def test_the_model_state_keeps_all_four_cells_apart(state: WorkbenchState):
    """The same value admitted at all four cells -- the hardest case."""
    for formulation in ("baseline", "modified"):
        for temperature in ("25", "100"):
            dispatch(state, "select", [formulation, temperature])
            dispatch(state, "observe", ["80", "MPa"])

    model_state = state.session.state
    assert len(model_state.samples) == 4
    for candidate in state.list_candidates():
        prediction = state.prediction_at(candidate, model_state)
        assert prediction.sample_count == 1
        assert prediction.predicted_value == 80.0


# -- what survives admission --------------------------------------------------------------------------


def test_observations_remain_distinct_objects_but_lose_their_condition(state: WorkbenchState):
    """The precise answer to "are they distinguishable": YES by identity,
    NO by condition. Each observation has its own Record, so the ids
    differ -- but the contents are byte-identical, so nothing says which
    condition each belongs to."""
    for temperature in ("25", "100"):
        dispatch(state, "select", ["baseline", temperature])
        dispatch(state, "observe", ["80", "MPa"])

    observations = list(state.pool.all_observations())
    assert len(observations) == 2
    assert len({o.id for o in observations}) == 2          # distinct as objects
    assert len({o.record_ids for o in observations}) == 2  # because the records differ
    contents = [dict(o.content) for o in observations]
    assert contents[0] == contents[1]                      # identical as facts
    assert all(set(c) == {"property", "value", "unit"} for c in contents)
    assert all("temperature_c" not in c for c in contents)


def test_the_ambiguity_enters_at_grouping_not_at_identity(state: WorkbenchState):
    """Where context is lost, stated exactly."""
    for temperature in ("25", "100"):
        dispatch(state, "select", ["baseline", temperature])
        dispatch(state, "observe", ["80", "MPa"])

    contexts = [_comparison_context(o.content, "value")
                for o in state.pool.all_observations()]
    assert len({tuple(sorted(c.items())) for c in contexts}) == 1
    assert dict(contexts[0]) == {"unit": "MPa"}  # the unit, not the condition


def test_an_observation_carrying_context_would_be_a_different_fact():
    """Observation.content is an open mapping and IS part of identity, so
    the established design (context in content) works mechanically. This
    is what the workbench does not do."""
    base = {"property": "tensile_strength", "value": 80.0, "unit": "MPa"}
    with_context = dict(base, temperature_c=25)
    other_context = dict(base, temperature_c=100)
    common = dict(record_ids=("r1",), extraction_method="m", confidence=1.0, extracted_at="t")

    plain = make_observation(content=base, **common)
    cold = make_observation(content=with_context, **common)
    hot = make_observation(content=other_context, **common)
    assert len({plain.id, cold.id, hot.id}) == 3
    # and they would separate into different comparison groups
    assert _comparison_context(cold.content, "value") != _comparison_context(hot.content, "value")


# -- the defect, documented rather than endorsed ------------------------------------------------------


def test_known_defect_two_conditions_are_reported_as_conflicting_evidence(state: WorkbenchState):
    """KNOWN DEFECT, locked so the fix must update it knowingly.

    90 MPa at 25 C and 60 MPa at 100 C are two valid measurements of two
    different conditions. Because the workbench admits neither condition,
    they pool into one ComparisonGroup and the system reports that the
    evidence disagrees with itself.

    That is a FALSE CLAIM, not a limitation. Phase 29 created
    `_comparison_context` specifically to prevent it, and its own test
    `test_viscosity_different_conditions_not_reported_as_single_disagreement`
    demonstrates the correct behaviour when content carries the condition.

    WHEN FIXED: the workbench admits `temperature_c` in the observation
    content, these become two groups, and this assertion must be changed
    to expect two independent verdicts.
    """
    from materials.decision import make_criterion
    from materials.iteration import reevaluate_program

    dispatch(state, "select", ["baseline", "25"])
    dispatch(state, "observe", ["90", "MPa"])
    dispatch(state, "select", ["baseline", "100"])
    dispatch(state, "observe", ["60", "MPa"])

    # the model state has it right: two cells, two different predictions
    for temperature, expected in ((25, 90.0), (100, 60.0)):
        candidate = next(c for c in state.list_candidates()
                         if c.formulation.natural_key == "baseline"
                         and dict(c.target_context) == {"temperature_c": temperature})
        assert state.prediction_at(candidate, state.session.state).predicted_value == expected

    iteration = state.session.iteration
    decision = reevaluate_program(
        state.pool, state.engine, iteration.query,
        (make_criterion("tensile_strength", ">=", 75.0),),
    ).decision
    verdicts = [p for f in decision.formulations
                for p in f.properties if f.formulation.natural_key == "baseline"]
    assert len(verdicts) == 1
    assert verdicts[0].observed_status == "CONFLICTING_EVIDENCE"   # <- the defect
    group = verdicts[0].observed_group
    assert sorted(group.values) == [60.0, 90.0]                    # pooled across conditions
    assert group.disagreement.spread == 30.0                       # a fabricated disagreement


def test_known_defect_a_context_bearing_criterion_is_always_incomparable(state: WorkbenchState):
    """The Phase 96 symptom, from the same cause. INCOMPARABLE is the
    CORRECT verdict given context-free evidence -- the criterion's
    condition genuinely was never recorded. It stops being the answer
    once the admission path records it."""
    dispatch(state, "select", ["baseline", "25"])
    dispatch(state, "observe", ["90", "MPa"])
    decision, _ = state.evaluate_criteria()
    statuses = {p.observed_status for f in decision.formulations
                for p in f.properties if f.formulation.natural_key == "baseline"}
    assert statuses == {"INCOMPARABLE"}


# -- the predicted side (sec.9) -----------------------------------------------------------------------


def test_nothing_in_production_ever_creates_a_derived_value():
    """Why predicted-side evaluation is INSUFFICIENT_EVIDENCE: the pool
    contains no DerivedValues, because no production code makes one. A
    ModelState Prediction is not a DerivedValue and must not silently
    become one -- that would be admitting a model output as evidence,
    a new epistemic claim with its own provenance requirements."""
    import ast
    repo = Path(__file__).resolve().parent.parent
    for package in ("materials", "experiment", "evidence", "retrieval", "workbench", "scout"):
        directory = repo / package
        if not directory.exists():
            continue
        for path in directory.rglob("*.py"):
            if path.name == "types.py" and package == "evidence":
                continue  # the factory's own definition
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    assert node.func.id != "make_derived_value", f"{path} creates a DerivedValue"


def test_the_predicted_side_has_no_evidence_to_evaluate(state: WorkbenchState):
    dispatch(state, "select", ["baseline", "25"])
    dispatch(state, "observe", ["90", "MPa"])
    # a real ModelState prediction exists
    assert state.session.predict(state.selected_candidate).predicted_value == 90.0
    # and the pool still holds no predicted evidence at all
    decision, _ = state.evaluate_criteria()
    predicted = {p.predicted_status for f in decision.formulations for p in f.properties}
    assert predicted == {"INSUFFICIENT_EVIDENCE"}


# -- epistemic invariants (sec.8) ---------------------------------------------------------------------


def test_identity_is_content_derived_and_never_minted(state: WorkbenchState):
    import re
    for temperature in ("25", "100"):
        dispatch(state, "select", ["baseline", temperature])
        dispatch(state, "observe", ["80", "MPa"])
    hexadecimal = re.compile(r"^[0-9a-f]{64}$")
    for observation in state.pool.all_observations():
        assert hexadecimal.match(observation.id), observation.id
    for model_state in state.session.state_history:
        assert hexadecimal.match(model_state.id)
    for candidate in state.list_candidates():
        assert hexadecimal.match(candidate.id)


def test_no_context_is_ever_silently_inferred(state: WorkbenchState):
    """The workbench must not guess a condition onto evidence that lacks
    one -- the failure mode this phase exists to NOT fix by improvisation."""
    dispatch(state, "select", ["baseline", "25"])
    dispatch(state, "observe", ["90", "MPa"])
    for observation in state.pool.all_observations():
        assert "temperature_c" not in observation.content
        assert set(observation.content) == {"property", "value", "unit"}


def test_hypothetical_samples_never_enter_the_pool(state: WorkbenchState):
    dispatch(state, "select", ["baseline", "25"])
    fingerprint = state.pool.fingerprint()
    dispatch(state, "explore", ["999"])
    assert state.pool.fingerprint() == fingerprint
    branch = state.branches[0]
    sample = next(iter(branch.projected_state.samples.values()))[0]
    assert sample.observation_id.startswith(HYPOTHETICAL_SAMPLE_PREFIX)
    assert all(o.id != sample.observation_id for o in state.pool.all_observations())


def test_historical_states_stay_immutable_across_admissions(state: WorkbenchState):
    dispatch(state, "select", ["baseline", "25"])
    candidate = state.selected_candidate
    dispatch(state, "observe", ["90", "MPa"])
    held = state.session
    held_id = held.state.id
    held_value = held.predict(candidate).predicted_value

    dispatch(state, "select", ["baseline", "100"])
    dispatch(state, "observe", ["60", "MPa"])
    assert held.state.id == held_id
    assert held.predict(candidate).predicted_value == held_value


def test_the_pool_changes_only_through_the_semantic_write_boundary(state: WorkbenchState):
    before = state.pool.fingerprint()
    for command, args in (("predict", []), ("decide", []), ("timeline", []),
                          ("state", []), ("criterion", []), ("candidates", [])):
        dispatch(state, "select", ["baseline", "25"])
        dispatch(state, command, args)
        assert state.pool.fingerprint() == before, command
    dispatch(state, "observe", ["90", "MPa"])
    assert state.pool.fingerprint() != before


# -- determinism ---------------------------------------------------------------------------------------


def test_the_same_admissions_produce_the_same_evidence_identities():
    def run():
        st = _four_cell()
        for formulation in ("baseline", "modified"):
            for temperature in ("25", "100"):
                dispatch(st, "select", [formulation, temperature])
                dispatch(st, "observe", ["80", "MPa"])
        return (
            tuple(sorted(o.id for o in st.pool.all_observations())),
            st.pool.fingerprint(),
            tuple(s.id for s in st.session.state_history),
            tuple(sorted(st.session.state.samples)),
        )

    assert run() == run()
