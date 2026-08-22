"""§21 test 4: identity remains stable, including across a value change."""

from core.canonical.delta import CandidateChange, CandidateDelta
from core.canonical.validation import validate_candidate
from core.canonical.version import ProvenanceInfo
from morpho.identity import cell_id, geometry_id, node_id, visual_id


def test_identity_chain_equals_field_name(genesis_version):
    for field_id in genesis_version.state.fields:
        assert geometry_id(field_id) == field_id
        assert visual_id(field_id) == field_id
        assert cell_id(field_id) == field_id
        assert node_id(field_id) == field_id


def test_identity_stable_across_value_change(sample_schema, genesis_version):
    provenance = ProvenanceInfo(author="test", transaction_id="tx1", source="manual_edit")
    candidate = CandidateDelta(
        version_from=genesis_version.id,
        transaction_id="tx1",
        timestamp="2026-08-22T00:01:00Z",
        changes=(
            CandidateChange(
                path="fields.mass.value", operation="replace", old_value=10, new_value=99, provenance=provenance
            ),
        ),
    )
    result = validate_candidate(sample_schema, genesis_version.state, candidate)
    assert not isinstance(result, list), result
    new_version = result

    assert new_version.id != genesis_version.id
    assert geometry_id("mass") == visual_id("mass") == cell_id("mass") == node_id("mass") == "mass"
    assert new_version.state.fields["mass"].value == 99
