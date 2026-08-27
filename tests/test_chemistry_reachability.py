"""Locks on the chemistry reachability probe.

The probe's job is to refuse to manufacture a measurement. Both ways it
could fail at that were hit while writing it, so both are pinned:

  a MALFORMED plant -- the payload trips a DIFFERENT refusal than the one
  aimed at, measuring the plant instead of the gate

  a VACUOUS confirmation -- the executed plant produces no findings, so
  nothing traverses the path, and "no refusal fired" is reported as a
  termination when nothing was tested

The second is the same shape as the acquisition layer's Phase 27
correction: an error running in the direction that makes the metric look
meaningful.
"""

from __future__ import annotations

import pathlib
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from scripts.chemistry_reachability import (
    CODES,
    REACHABLE,
    STRUCTURALLY_UNREACHABLE,
    classify_liveness,
    confirm_termination_by_execution,
    probe_liveness,
    probe_reachability,
    termination_verdict,
)

REPO = pathlib.Path(__file__).resolve().parent.parent
ARTIFACT = REPO / "architecture" / "chemistry_reachability.yaml"


def test_every_enumerated_code_is_live():
    """Reachability analysis over a gate that does not refuse is analysis
    of nothing. This is the cheap question and it is asked first."""
    probe_liveness()
    dead = [c.id for c in CODES if c.live == "DEAD"]
    assert not dead, f"gates that accepted a violating payload: {dead}"


def test_no_plant_is_malformed():
    """A plant that trips a different refusal measured the plant, not the
    gate. On the first run one did -- the DISTRIBUTION_FIELDS_MISSING
    plant passed an empty mapping and hit a refusal one line earlier. The
    fix was to ADD the code it found (STRUCTURE_STRING_ONLY), not to
    re-aim the plant quietly: a malformed plant is a finding about the
    enumeration."""
    probe_liveness()
    malformed = [(c.id, c.observed) for c in CODES if c.live == "MALFORMED_PLANT"]
    assert not malformed, f"plants that measured themselves: {malformed}"


def test_both_refusals_of_the_two_refusal_guard_are_enumerated():
    """The specific gap the malformed plant exposed, pinned so the
    enumeration cannot silently lose one again."""
    ids = {c.id for c in CODES}
    assert {"STRUCTURE_STRING_ONLY", "DISTRIBUTION_FIELDS_MISSING"} <= ids


def test_an_unreachable_verdict_carries_a_traced_termination():
    """AN UNREACHABLE VERDICT NEEDS A PATH THAT TERMINATES, not an
    absence of anyone finding one. Every non-REACHABLE verdict must name
    the mechanism that stops it."""
    probe_reachability(REPO)
    for code in CODES:
        for entry, verdict in code.entry_verdicts.items():
            if verdict != REACHABLE:
                assert code.blocked_by.get(entry), (
                    f"{code.id}/{entry}: {verdict} with no mechanism named -- "
                    f"that is an absence of a finding, not a finding")


def test_the_executed_confirmation_refuses_a_vacuous_pass():
    """Zero findings is not a termination.

    The first version of the executed plant used a line format the
    shipped extractor does not read. It produced zero findings, zero
    refusals, and the probe called it 'termination confirmed' -- nothing
    had traversed the path. The verdict now requires that something DID
    traverse and arrive admitted.
    """
    result = confirm_termination_by_execution()
    assert result["admitted_findings"] > 0, (
        "the plant must actually land an observation; a document that "
        "produces nothing measures nothing")
    assert result["vacuous"] is False
    assert result["terminated"] is True
    assert result["chemistry_refusals"] == 0


def test_a_plant_that_lands_nothing_is_not_counted_as_terminated():
    """The rule, driven over every combination -- CALLING it rather than
    restating it.

    The first version of this test recomputed the verdict inside itself
    and passed whatever the code did. A test that reimplements its
    subject tests only its own copy, which is why the mutation that
    dropped the `admitted > 0` condition survived it.
    """
    assert termination_verdict(0, 0) == {
        "admitted_findings": 0, "chemistry_refusals": 0,
        "terminated": False, "vacuous": True}, (
            "nothing traversed: not a termination")
    assert termination_verdict(1, 0)["terminated"] is True, (
        "something traversed and no gate fired: the termination, measured")
    assert termination_verdict(1, 1)["terminated"] is False, (
        "a gate fired: the path did NOT terminate, it was refused")
    assert termination_verdict(0, 1)["vacuous"] is True


def test_the_liveness_classifier_reports_a_dead_gate_as_dead():
    """Driven over a CONSTRUCTED dead gate, because the real set has
    none.

    Every one of the twenty codes is LIVE, so the classifier's DEAD arm
    never executes against production inputs and a mutation deleting it
    changed nothing observable. A check whose inputs are coincidentally
    uniform tests nothing about the selection.
    """
    verdict, observed = classify_liveness(
        plant=lambda: "accepted without complaint",
        expect=ValueError, fragment="never reached")
    assert verdict == "DEAD"
    assert "ACCEPTED" in observed


def test_the_liveness_classifier_reports_a_misaimed_plant_as_malformed():
    """Same reason, the other unexercised arm -- both the wrong-message
    and wrong-type cases."""
    wrong_message, observed = classify_liveness(
        plant=lambda: (_ for _ in ()).throw(ValueError("a different refusal")),
        expect=ValueError, fragment="the one I aimed at")
    assert wrong_message == "MALFORMED_PLANT"
    assert "wrong refusal" in observed

    wrong_type, observed = classify_liveness(
        plant=lambda: (_ for _ in ()).throw(TypeError("not even the right family")),
        expect=ValueError, fragment="anything")
    assert wrong_type == "MALFORMED_PLANT"
    assert "TypeError" in observed

    correct, _ = classify_liveness(
        plant=lambda: (_ for _ in ()).throw(ValueError("the aimed-at refusal")),
        expect=ValueError, fragment="aimed-at")
    assert correct == "LIVE", "and the LIVE arm still works"


def test_the_artifact_reports_silences_as_silences_not_as_clean():
    """A probe reporting 'clean' across the set would be twenty silences
    presented as one number. The artifact must state the reachable count
    and tie the rate's meaning to it."""
    document = yaml.safe_load(ARTIFACT.read_text())
    summary = document["summary"]
    assert summary["codes_total"] == len(CODES)
    assert summary["live"] == len(CODES)
    assert summary["reachable_from_any_entry"] == 0
    assert summary["exercised_by_real_acquisition"] == 0

    rule = document["metric_interpretation"]["rule"]
    assert "REACHABLE" in rule and str(len(CODES)) in rule
    assert document["metric_interpretation"][
        "what_a_clean_set_would_look_like_and_why_this_is_not_it"]


def test_the_artifact_records_its_own_two_corrections():
    """Both failure modes were hit while writing the probe. They are
    recorded in the artifact rather than only fixed, because a probe that
    reports how it was wrong is worth more than one that reports a
    number."""
    document = yaml.safe_load(ARTIFACT.read_text())
    corrections = document["corrections"]
    assert len(corrections) >= 2
    kinds = " ".join(c["found"] for c in corrections).lower()
    assert "malformed" in kinds and "vacuous" in kinds


def test_the_artifact_is_current():
    """Re-derive and compare: a stale measurement record is worse than
    none, because it reads as current."""
    sys.path.insert(0, str(REPO / "architecture" / "exchange"))
    from canonical_yaml import canonical_sha256

    document = yaml.safe_load(ARTIFACT.read_text())
    recorded = (REPO / "architecture" / "chemistry_reachability.sha256").read_text().strip()
    assert recorded == canonical_sha256(document)
