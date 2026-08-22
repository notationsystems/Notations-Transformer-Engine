"""§21 test 10: nested state changes produce path-level (leaf) deltas."""

import dataclasses

from core.canonical.delta import apply_changes, diff
from core.canonical.version import ProvenanceInfo


def test_single_leaf_value_change_produces_one_path_level_change(genesis_version):
    old_state = genesis_version.state
    new_fields = dict(old_state.fields)
    new_fields["mass"] = dataclasses.replace(new_fields["mass"], value=99)
    new_state = dataclasses.replace(old_state, fields=new_fields)

    provenance = ProvenanceInfo(author="test", transaction_id="tx1", source="manual_edit")
    changes = diff(old_state, new_state, provenance)

    assert len(changes) == 1
    assert changes[0].path == "fields.mass.value"
    assert changes[0].operation == "replace"
    assert changes[0].old_value == 10
    assert changes[0].new_value == 99


def test_diff_is_deterministically_ordered(genesis_version):
    old_state = genesis_version.state
    new_fields = dict(old_state.fields)
    new_fields["velocity"] = dataclasses.replace(new_fields["velocity"], value=5)
    new_fields["mass"] = dataclasses.replace(new_fields["mass"], value=99)
    new_state = dataclasses.replace(old_state, fields=new_fields)

    provenance = ProvenanceInfo(author="test", transaction_id="tx1", source="manual_edit")
    changes1 = diff(old_state, new_state, provenance)
    changes2 = diff(old_state, new_state, provenance)

    assert changes1 == changes2
    assert [c.path for c in changes1] == sorted(c.path for c in changes1)


def test_apply_changes_round_trips_diff(genesis_version):
    old_state = genesis_version.state
    new_fields = dict(old_state.fields)
    new_fields["mass"] = dataclasses.replace(new_fields["mass"], value=99)
    new_state = dataclasses.replace(old_state, fields=new_fields)

    provenance = ProvenanceInfo(author="test", transaction_id="tx1", source="manual_edit")
    changes = diff(old_state, new_state, provenance)

    from core.canonical.delta import CandidateChange

    candidate_changes = tuple(
        CandidateChange(
            path=c.path, operation=c.operation, old_value=c.old_value, new_value=c.new_value, provenance=c.provenance
        )
        for c in changes
    )
    rebuilt = apply_changes(old_state, candidate_changes)
    assert rebuilt == new_state
