"""§21 tests 11-13: every accepted update creates a new version, versions
have parent relationships, and previous versions remain recoverable."""

from core.canonical.delta import CandidateChange, CandidateDelta
from core.canonical.validation import validate_candidate
from core.canonical.version import InMemoryVersionStore, ProvenanceInfo


def _accept_mass_change(schema, base_version, new_value, tx_id):
    provenance = ProvenanceInfo(author="test", transaction_id=tx_id, source="manual_edit")
    candidate = CandidateDelta(
        version_from=base_version.id,
        transaction_id=tx_id,
        timestamp="2026-08-22T00:01:00Z",
        changes=(
            CandidateChange(
                path="fields.mass.value",
                operation="replace",
                old_value=base_version.state.fields["mass"].value,
                new_value=new_value,
                provenance=provenance,
            ),
        ),
    )
    result = validate_candidate(schema, base_version.state, candidate)
    assert not isinstance(result, list), result
    return result


def test_every_accepted_update_creates_a_new_version(sample_schema, genesis_version):
    store = InMemoryVersionStore()
    store.put(genesis_version)
    assert len(store) == 1

    v1 = _accept_mass_change(sample_schema, genesis_version, 42, "tx1")
    store.put(v1)
    assert len(store) == 2
    assert v1.id != genesis_version.id


def test_versions_have_parent_relationships(sample_schema, genesis_version):
    v1 = _accept_mass_change(sample_schema, genesis_version, 42, "tx1")
    assert v1.parent == genesis_version.id

    v2 = _accept_mass_change(sample_schema, v1, 7, "tx2")
    assert v2.parent == v1.id
    assert v2.parent != genesis_version.id


def test_previous_versions_remain_recoverable(sample_schema, genesis_version):
    # Version/CanonicalState are immutable, so holding the original
    # `genesis_version` reference and comparing against it later is a
    # valid recoverability check -- nothing in this codebase has a way
    # to mutate it in place.
    store = InMemoryVersionStore()
    store.put(genesis_version)

    v1 = _accept_mass_change(sample_schema, genesis_version, 42, "tx1")
    store.put(v1)
    v2 = _accept_mass_change(sample_schema, v1, 7, "tx2")
    store.put(v2)

    recovered = store.get(genesis_version.id)
    assert recovered == genesis_version

    chain = store.parent_chain(v2.id)
    assert [v.id for v in chain] == [v2.id, v1.id, genesis_version.id]
