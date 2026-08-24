"""Phase 52: materials.model_state -- the first dynamic-state layer.
Small focused test set proving the state-transition machinery end to
end: initial construction, deterministic identity, prediction from
state, observation update producing a new state, historical-state
immutability, prediction's dependence on state, uncertainty changing
only when mathematically warranted, and the InformationValueModel seam
consuming the model's own output correctly across two different states.
"""

from evidence.admission import (
    admit_claimed_relationship, admit_document, admit_observation, admit_record, admit_referent,
)
from evidence.pool import EvidencePool
from evidence.types import (
    make_claimed_relationship, make_document, make_observation, make_record, make_referent, make_source,
)
from materials.campaign import assemble_experimental_campaign
from materials.candidates import generate_candidates
from materials.decision import make_criterion
from materials.design import assemble_experimental_design
from materials.evaluation import evaluate_candidates
from materials.information import ESTIMATED, NOT_DETERMINABLE, estimate_information_value
from materials.iteration import reevaluate_program
from materials.model_state import (
    EMPTY_MODEL_STATE, ModelStateInformationValueModel, Sample, make_model_state, predict, update,
)
from materials.plan import assemble_experiment_plan
from materials.program import make_material_program_query
from materials.results import admit_experimental_result, make_experimental_result
from materials.selection import SelectionPolicy, select_candidates
from retrieval.engine import DeterministicRetrievalEngine

ENGINE = DeterministicRetrievalEngine()
TENSILE_CRITERION = make_criterion("tensile_strength", ">=", 80)
HARDNESS_CRITERION = make_criterion("hardness", ">=", 50)  # never measured

ALLOW_ALL = SelectionPolicy(
    allowed_action_classes=None, allow_already_represented_context=True,
    allow_redundant=True, allow_not_determinable_feasibility=True, max_selected=None,
)


def _setup():
    pool = EvidencePool()
    source = make_source(kind="lab_notebook", name="QC")
    pool.put_source(source)
    doc = make_document(source_id=source.id, raw_content="panel", retrieval_method="manual_entry", retrieved_at="2026-08-23T00:00:00Z")
    admit_document(pool, doc)
    pool.put_document(doc)
    process = make_referent(natural_key="process-std-190c", kind="process")
    admit_referent(pool, process)
    pool.put_referent(process)
    f1 = make_referent(natural_key="formulation-f1", kind="formulation")
    admit_referent(pool, f1)
    pool.put_referent(f1)

    for locator, value in (("ts-a", 78), ("ts-b", 84)):
        rec = make_record(document_id=doc.id, locator=locator, raw_content=locator)
        admit_record(pool, rec)
        pool.put_record(rec)
        obs = make_observation(
            record_ids=(rec.id,), extraction_method="human_transcription",
            content={"property": "tensile_strength", "value": value, "unit": "MPa"},
            confidence=1.0, extracted_at="2026-08-23T00:00:00Z",
        )
        admit_observation(pool, obs)
        pool.put_observation(obs)
        rel = make_claimed_relationship(from_referent_id=f1.id, to_referent_id=process.id, type="tested_during", observation_id=obs.id, confidence=1.0)
        admit_claimed_relationship(pool, rel)
        pool.put_claimed_relationship(rel)

    query = make_material_program_query(["formulation-f1"], "process-std-190c", ("tensile_strength", "hardness"))
    iteration = reevaluate_program(pool, ENGINE, query, (TENSILE_CRITERION, HARDNESS_CRITERION))
    candidates = generate_candidates(iteration.specification)
    conflict_candidate = next(c for c in candidates.candidates if c.action_class == "measurement:repeat")
    hardness_candidate = next(c for c in candidates.candidates if c.property == "hardness")

    evaluations = evaluate_candidates(candidates)
    selection = select_candidates(evaluations, ALLOW_ALL)
    plan = assemble_experiment_plan(selection)
    design = assemble_experimental_design(plan)
    campaign = assemble_experimental_campaign(design)
    entry = next(e for e in campaign.entries if e.candidate_id == conflict_candidate.id)
    hardness_entry = next(e for e in campaign.entries if e.candidate_id == hardness_candidate.id)

    return pool, doc, iteration, conflict_candidate, campaign, entry, hardness_entry


def _admit_result(pool, doc, campaign, entry, locator, value):
    rec = make_record(document_id=doc.id, locator=locator, raw_content=locator)
    admit_record(pool, rec)
    pool.put_record(rec)
    result = make_experimental_result(
        campaign, entry, content={"property": "tensile_strength", "value": value, "unit": "MPa"},
        record_id=rec.id, extracted_at="2026-08-23T02:00:00Z",
    )
    observation, _ = admit_experimental_result(pool, result, confidence=1.0)
    return result, observation


# -- 1/2. initial model state construction + deterministic identity -----------------------------------


def test_1_2_initial_state_construction_and_deterministic_identity():
    a = make_model_state({})
    b = make_model_state({})
    assert a.id == b.id == EMPTY_MODEL_STATE.id
    assert a.samples == {}

    key = "x"
    c = make_model_state({key: (Sample(1.0, "o1"), Sample(2.0, "o2"))})
    d = make_model_state({key: (Sample(2.0, "o2"), Sample(1.0, "o1"))})  # different insertion order
    assert c.id == d.id  # order-independent


# -- 3/6. prediction from state, and prediction depends on the state ------------------------------------


def test_3_6_prediction_from_state_and_depends_on_state():
    pool, doc, iteration, candidate, campaign, entry, hardness_entry = _setup()
    empty_prediction = predict(EMPTY_MODEL_STATE, candidate)
    assert empty_prediction.sample_count == 0
    assert empty_prediction.predicted_value is None
    assert empty_prediction.uncertainty is None
    assert empty_prediction.state_id == EMPTY_MODEL_STATE.id

    result1, obs1 = _admit_result(pool, doc, campaign, entry, "ts-80", 80)
    state1 = update(EMPTY_MODEL_STATE, result1, obs1)
    prediction1 = predict(state1, candidate)
    assert prediction1.sample_count == 1
    assert prediction1.predicted_value == 80.0
    assert prediction1.uncertainty is None  # a single sample has no defined variance
    assert prediction1.state_id == state1.id != EMPTY_MODEL_STATE.id


# -- 4/5. observation update produces a NEW state; historical state unchanged ---------------------------


def test_4_5_update_produces_new_state_historical_unchanged():
    pool, doc, iteration, candidate, campaign, entry, hardness_entry = _setup()
    result1, obs1 = _admit_result(pool, doc, campaign, entry, "ts-80", 80)
    state1 = update(EMPTY_MODEL_STATE, result1, obs1)
    before_state0_repr = repr(EMPTY_MODEL_STATE)

    result2, obs2 = _admit_result(pool, doc, campaign, entry, "ts-90", 90)
    state2 = update(state1, result2, obs2)

    assert state2.id != state1.id
    assert repr(EMPTY_MODEL_STATE) == before_state0_repr  # never mutated
    assert predict(state1, candidate).sample_count == 1  # state1 itself never changed by the later update
    assert predict(state2, candidate).sample_count == 2


# -- 7. uncertainty changes only when mathematically warranted --------------------------------------------


def test_7_uncertainty_changes_only_when_warranted():
    pool, doc, iteration, candidate, campaign, entry, hardness_entry = _setup()
    result1, obs1 = _admit_result(pool, doc, campaign, entry, "ts-80", 80)
    state1 = update(EMPTY_MODEL_STATE, result1, obs1)
    result2, obs2 = _admit_result(pool, doc, campaign, entry, "ts-90", 90)
    state2 = update(state1, result2, obs2)

    prediction2 = predict(state2, candidate)
    assert prediction2.predicted_value == 85.0
    assert prediction2.uncertainty == 25.0  # ((80-85)^2 + (90-85)^2) / 2

    # An update to a DIFFERENT (formulation, property, context) cell must not
    # change this candidate's prediction at all -- same state content for the
    # tensile_strength/f1 cell, so the same uncertainty, not a guessed drift.
    rec = make_record(document_id=doc.id, locator="hard-a", raw_content="hard-a")
    admit_record(pool, rec)
    pool.put_record(rec)
    result3 = make_experimental_result(
        campaign, hardness_entry, content={"property": "hardness", "value": 55, "unit": "Shore D"},
        record_id=rec.id, extracted_at="2026-08-23T03:00:00Z",
    )
    obs3, _ = admit_experimental_result(pool, result3, confidence=1.0)
    state3 = update(state2, result3, obs3)

    prediction3 = predict(state3, candidate)
    assert prediction3.uncertainty == prediction2.uncertainty == 25.0
    assert prediction3.predicted_value == prediction2.predicted_value == 85.0
    assert prediction3.sample_count == prediction2.sample_count == 2
    assert state3.id != state2.id  # the state itself did change (a new cell was added)


# -- 8. information-value seam consumes the model output correctly, across two states -----------------------


def test_8_information_value_seam_before_and_after():
    pool, doc, iteration, candidate, campaign, entry, hardness_entry = _setup()
    result1, obs1 = _admit_result(pool, doc, campaign, entry, "ts-80", 80)
    state1 = update(EMPTY_MODEL_STATE, result1, obs1)

    estimate_before = estimate_information_value(candidate, iteration, ModelStateInformationValueModel(state1))
    assert estimate_before.estimate is None
    assert estimate_before.estimate_status == NOT_DETERMINABLE  # only 1 sample -- honestly undetermined

    result2, obs2 = _admit_result(pool, doc, campaign, entry, "ts-90", 90)
    state2 = update(state1, result2, obs2)
    estimate_after = estimate_information_value(candidate, iteration, ModelStateInformationValueModel(state2))
    assert estimate_after.estimate == 25.0
    assert estimate_after.estimate_status == ESTIMATED

    assert estimate_before.estimate != estimate_after.estimate
    # full provenance preserved through the embedded structural facts
    requirement = estimate_after.information_value.evaluation.targeted_requirements[0]
    assert requirement.formulation.natural_key == "formulation-f1"


# -- 9. deterministic behavior across PYTHONHASHSEED ---------------------------------------------------------


def test_9_pythonhashseed_determinism():
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    script = (
        "from materials.model_state import Sample, make_model_state, predict, update\n"
        "from materials.candidates import make_action_candidate\n"
        "from evidence.types import make_referent\n"
        "f1 = make_referent(natural_key='formulation-f1', kind='formulation')\n"
        "candidate = make_action_candidate(action_class='measurement:repeat', requirement_ids=('r1',), "
        "formulation=f1, property='tensile_strength', role='OBSERVED', target_context={})\n"
        "state = make_model_state({})\n"
        "key_samples = {}\n"
        "from materials.model_state import _state_key\n"
        "key = _state_key(f1.id, 'tensile_strength')\n"
        "state = make_model_state({key: (Sample(80.0, 'o1'), Sample(90.0, 'o2'))})\n"
        "prediction = predict(state, candidate)\n"
        "print(state.id, prediction.predicted_value, prediction.uncertainty, prediction.sample_count)\n"
    )
    outputs = set()
    for seed in ("0", "1", "12345"):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=repo_root,
            env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        outputs.add(proc.stdout)
    assert len(outputs) == 1, f"model_state differed across PYTHONHASHSEED values: {outputs}"
