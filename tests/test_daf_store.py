"""Idempotency and temporal-history tests for `daf/store.py`.

Covers the two distinct temporal questions this layer's design exists to
separate: STATE history ("how did the resource's content change?" --
`ArtifactVersionStore`) versus OBSERVATION history ("when did DAF
observe each state?" -- `AcquisitionRecordStore`)."""

from daf.acquisition import make_acquisition_record
from daf.identity import make_artifact, make_artifact_version
from daf.store import InMemoryAcquisitionRecordStore, InMemoryArtifactVersionStore


def test_idempotent_content_collapses_to_one_version():
    """Two acquisitions of byte-identical content -- different
    source_revision, different point in time -- must collapse to one
    stored ArtifactVersion."""
    store = InMemoryArtifactVersionStore()
    artifact = make_artifact(source_id="source_1", canonical_locator="/test")
    store.put_artifact(artifact)

    content = b'{"test": "data"}'
    v1 = make_artifact_version(artifact=artifact, raw_bytes=content, source_revision="v1")
    v2 = make_artifact_version(artifact=artifact, raw_bytes=content, source_revision="v2")
    store.put_version(v1)
    store.put_version(v2)

    assert v1.id == v2.id
    versions = store.get_versions_for_artifact(artifact.id)
    assert len(versions) == 1


def test_changed_content_creates_a_second_version():
    store = InMemoryArtifactVersionStore()
    artifact = make_artifact(source_id="source_1", canonical_locator="/test")
    store.put_artifact(artifact)

    v1 = make_artifact_version(artifact=artifact, raw_bytes=b'{"version": 1}')
    v2 = make_artifact_version(artifact=artifact, raw_bytes=b'{"version": 2}')
    store.put_version(v1)
    store.put_version(v2)

    versions = store.get_versions_for_artifact(artifact.id)
    assert len(versions) == 2
    assert {v.id for v in versions} == {v1.id, v2.id}


def test_get_version_by_content_hash_enables_idempotent_acquisition_check():
    store = InMemoryArtifactVersionStore()
    artifact = make_artifact(source_id="source_1", canonical_locator="/test")
    store.put_artifact(artifact)

    version = make_artifact_version(artifact=artifact, raw_bytes=b'{"a": 1}')
    store.put_version(version)

    found = store.get_version_by_content_hash(artifact.id, version.raw_content_hash)
    assert found is not None
    assert found.id == version.id
    assert store.get_version_by_content_hash(artifact.id, "nonexistent-hash") is None


def test_state_history_vs_observation_history_are_distinct():
    version_store = InMemoryArtifactVersionStore()
    record_store = InMemoryAcquisitionRecordStore()

    artifact = make_artifact(source_id="source_1", canonical_locator="/api/data")
    version_store.put_artifact(artifact)

    v1 = make_artifact_version(artifact=artifact, raw_bytes=b'{"v": 1}')
    v2 = make_artifact_version(artifact=artifact, raw_bytes=b'{"v": 2}')
    version_store.put_version(v1)
    version_store.put_version(v2)

    # v1 observed twice (unchanged source, polled twice), then v2 observed once.
    r1 = make_acquisition_record(
        artifact=artifact, artifact_version=v1, job_id="j1", adapter_version="1.0.0",
        acquisition_time="2026-08-23T10:00:00Z",
    )
    r2 = make_acquisition_record(
        artifact=artifact, artifact_version=v1, job_id="j2", adapter_version="1.0.0",
        acquisition_time="2026-08-23T11:00:00Z",
    )
    r3 = make_acquisition_record(
        artifact=artifact, artifact_version=v2, job_id="j3", adapter_version="1.0.0",
        acquisition_time="2026-08-23T12:00:00Z",
    )
    for r in (r1, r2, r3):
        record_store.put_record(r)

    # State history: exactly two distinct content states were ever seen.
    versions = version_store.get_versions_for_artifact(artifact.id)
    assert len(versions) == 2

    # Observation history: three distinct occurrences, even though only
    # two content states exist.
    records = record_store.get_records_for_artifact(artifact.id)
    assert len(records) == 3
    assert len(record_store.get_records_for_version(v1.id)) == 2
    assert len(record_store.get_records_for_version(v2.id)) == 1


def test_acquisition_record_store_put_is_idempotent():
    record_store = InMemoryAcquisitionRecordStore()
    artifact = make_artifact(source_id="source_1", canonical_locator="/test")
    version = make_artifact_version(artifact=artifact, raw_bytes=b'{"a": 1}')
    record = make_acquisition_record(
        artifact=artifact, artifact_version=version, job_id="j1", adapter_version="1.0.0",
        acquisition_time="2026-08-23T10:00:00Z",
    )
    record_store.put_record(record)
    record_store.put_record(record)  # replay the identical record
    assert len(record_store.get_records_for_artifact(artifact.id)) == 1
