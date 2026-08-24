"""Tests for `daf/normalization.py`: transformation provenance
(`NormalizedRecord = f(ArtifactVersion, Parser, SchemaVersion)`),
reproducible reconstruction, and semantic deduplication via
`normalized_content_hash`."""

import pytest

from daf.normalization import JSONParser, make_normalized_record, make_schema_version


def _schema():
    return make_schema_version(name="generic_json", version="1.0.0", definition={"type": "object"})


def test_schema_version_identity_deterministic():
    s1 = _schema()
    s2 = _schema()
    assert s1.id == s2.id


def test_schema_version_identity_changes_with_definition():
    s1 = make_schema_version(name="generic_json", version="1.0.0", definition={"type": "object"})
    s2 = make_schema_version(name="generic_json", version="1.0.0", definition={"type": "array"})
    assert s1.id != s2.id


def test_normalized_record_deep_immutability():
    normalized = make_normalized_record(
        artifact_version_id="version_1", schema_version_id="schema_1", parser_version="1.0.0",
        data={"test": "data", "value": 42},
    )
    with pytest.raises(AttributeError):
        normalized.parser_version = "2.0.0"
    with pytest.raises(TypeError):
        normalized.data["new_key"] = "new_value"  # type: ignore[index]


def test_transformation_provenance_carries_all_three_inputs():
    """N = f(R, P, S): all three inputs stay independently readable off
    the resulting NormalizedRecord."""
    schema = _schema()
    parser = JSONParser()
    normalized = parser.parse(
        artifact_version_id="version_1", schema_version_id=schema.id, raw_bytes=b'{"test": "data", "value": 42}'
    )
    assert normalized.artifact_version_id == "version_1"
    assert normalized.schema_version_id == schema.id
    assert normalized.parser_version == JSONParser.PARSER_VERSION


def test_reproducible_reconstruction_same_inputs_same_output():
    schema = _schema()
    parser = JSONParser()
    raw_bytes = b'{"test": "data", "value": 42}'
    n1 = parser.parse(artifact_version_id="version_1", schema_version_id=schema.id, raw_bytes=raw_bytes)
    n2 = parser.parse(artifact_version_id="version_1", schema_version_id=schema.id, raw_bytes=raw_bytes)
    assert n1.id == n2.id
    assert n1.data == n2.data
    assert n1.normalized_content_hash == n2.normalized_content_hash


def test_normalized_record_id_differs_when_source_version_differs():
    """Same semantic data, but parsed from two DIFFERENT ArtifactVersions
    -- NormalizedRecord.id must differ (it answers "which transformation
    produced this"), even though normalized_content_hash converges (it
    answers "have we seen this meaning before")."""
    schema = _schema()
    n1 = make_normalized_record(
        artifact_version_id="version_1", schema_version_id=schema.id, parser_version="1.0.0", data={"a": 1, "b": 2}
    )
    n2 = make_normalized_record(
        artifact_version_id="version_2", schema_version_id=schema.id, parser_version="1.0.0", data={"b": 2, "a": 1}
    )
    assert n1.id != n2.id
    assert n1.normalized_content_hash == n2.normalized_content_hash


def test_semantic_deduplication_via_store():
    from daf.normalization import InMemoryNormalizedRecordStore

    store = InMemoryNormalizedRecordStore()
    schema = _schema()
    n1 = make_normalized_record(
        artifact_version_id="version_1", schema_version_id=schema.id, parser_version="1.0.0", data={"a": 1, "b": 2}
    )
    n2 = make_normalized_record(
        artifact_version_id="version_2", schema_version_id=schema.id, parser_version="1.0.0", data={"b": 2, "a": 1}
    )
    store.put_record(n1)
    store.put_record(n2)

    same_meaning = store.get_records_by_normalized_hash(n1.normalized_content_hash)
    assert {r.id for r in same_meaning} == {n1.id, n2.id}


def test_json_parser_rejects_invalid_json():
    parser = JSONParser()
    with pytest.raises(ValueError):
        parser.parse(artifact_version_id="v1", schema_version_id="s1", raw_bytes=b"not json {")


def test_json_parser_rejects_non_object_top_level():
    parser = JSONParser()
    with pytest.raises(ValueError):
        parser.parse(artifact_version_id="v1", schema_version_id="s1", raw_bytes=b"[1, 2, 3]")
