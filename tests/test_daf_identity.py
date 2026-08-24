"""Identity/determinism tests for `daf/identity.py` and
`daf/acquisition.py` -- the DAF-layer equivalent of
`tests/test_evidence_identity.py`'s coverage one layer downstream.

The central claim under test: Artifact identity, ArtifactVersion (content)
identity, and AcquisitionRecord (occurrence) identity are three
DIFFERENT things, and mixing any two of them together is exactly the bug
this module's design was revised to avoid (see `daf/identity.py` and
`daf/acquisition.py` module docstrings)."""

import pytest

from daf.acquisition import AcquisitionRecord, make_acquisition_job, make_acquisition_record
from daf.identity import make_artifact, make_artifact_version


def test_artifact_identity_stable_for_same_source_and_locator():
    a1 = make_artifact(source_id="source_1", canonical_locator="/api/data")
    a2 = make_artifact(source_id="source_1", canonical_locator="/api/data")
    assert a1.id == a2.id


def test_artifact_identity_changes_with_locator():
    a1 = make_artifact(source_id="source_1", canonical_locator="/api/data")
    a2 = make_artifact(source_id="source_1", canonical_locator="/api/data/v2")
    assert a1.id != a2.id


def test_artifact_identity_changes_with_source():
    a1 = make_artifact(source_id="source_1", canonical_locator="/api/data")
    a2 = make_artifact(source_id="source_2", canonical_locator="/api/data")
    assert a1.id != a2.id


def test_raw_content_hash_is_pure_ignores_source_revision():
    """Same bytes, different `source_revision` -- raw_content_hash (and
    therefore ArtifactVersion.id) must be identical: source_revision is
    provenance, not content."""
    artifact = make_artifact(source_id="source_1", canonical_locator="/test")
    v1 = make_artifact_version(artifact=artifact, raw_bytes=b'{"test": "data"}', source_revision="v1")
    v2 = make_artifact_version(artifact=artifact, raw_bytes=b'{"test": "data"}', source_revision="v2")
    assert v1.raw_content_hash == v2.raw_content_hash
    assert v1.id == v2.id


def test_raw_content_hash_differs_for_different_bytes():
    artifact = make_artifact(source_id="source_1", canonical_locator="/test")
    v1 = make_artifact_version(artifact=artifact, raw_bytes=b'{"version": 1}')
    v2 = make_artifact_version(artifact=artifact, raw_bytes=b'{"version": 2}')
    assert v1.raw_content_hash != v2.raw_content_hash
    assert v1.id != v2.id


def test_artifact_version_id_scoped_to_artifact():
    """The identical bytes acquired under two different Artifacts must
    NOT collapse to one ArtifactVersion -- content identity is always
    scoped to a resource, never global."""
    a1 = make_artifact(source_id="source_1", canonical_locator="/a")
    a2 = make_artifact(source_id="source_1", canonical_locator="/b")
    content = b'{"same": "bytes"}'
    v1 = make_artifact_version(artifact=a1, raw_bytes=content)
    v2 = make_artifact_version(artifact=a2, raw_bytes=content)
    assert v1.raw_content_hash == v2.raw_content_hash  # same content
    assert v1.id != v2.id  # different artifact -> different version


def test_artifact_version_immutable():
    artifact = make_artifact(source_id="source_1", canonical_locator="/test")
    version = make_artifact_version(artifact=artifact, raw_bytes=b'{"test": "data"}')
    with pytest.raises(AttributeError):
        version.raw_bytes = b'{"modified": "data"}'


def test_acquisition_record_deep_immutability():
    artifact = make_artifact(source_id="source_1", canonical_locator="/test")
    version = make_artifact_version(artifact=artifact, raw_bytes=b'{"test": "data"}')
    record = make_acquisition_record(
        artifact=artifact,
        artifact_version=version,
        job_id="job_1",
        adapter_version="1.0.0",
        acquisition_time="2026-08-23T00:00:00Z",
        retrieval_metadata={"status_code": 200},
    )
    with pytest.raises(AttributeError):
        record.status = "failed"
    with pytest.raises(TypeError):
        record.retrieval_metadata["status_code"] = 500  # type: ignore[index]


def test_acquisition_record_id_deterministic_for_same_occurrence():
    """Same artifact + version + job + time + status -> same
    AcquisitionRecord.id, even called twice independently -- the
    determinism `evidence.types.make_observation` already guarantees is
    extended to this layer's occurrence records too."""
    artifact = make_artifact(source_id="source_1", canonical_locator="/test")
    version = make_artifact_version(artifact=artifact, raw_bytes=b'{"test": "data"}')
    kwargs = dict(
        artifact=artifact,
        artifact_version=version,
        job_id="job_1",
        adapter_version="1.0.0",
        acquisition_time="2026-08-23T00:00:00Z",
    )
    r1 = make_acquisition_record(**kwargs, retrieval_metadata={"status_code": 200})
    r2 = make_acquisition_record(**kwargs, retrieval_metadata={"status_code": 200})
    assert r1.id == r2.id


def test_acquisition_record_id_differs_for_different_occurrence_time():
    """Same artifact + version + job, but a different declared
    acquisition_time -- a genuinely different occurrence -- must NOT
    collapse to one AcquisitionRecord (this is exactly the contradiction
    the original ArtifactVersion.id design had: this module's fix moves
    that distinction here, where it belongs)."""
    artifact = make_artifact(source_id="source_1", canonical_locator="/test")
    version = make_artifact_version(artifact=artifact, raw_bytes=b'{"test": "data"}')
    r1 = make_acquisition_record(
        artifact=artifact, artifact_version=version, job_id="job_1", adapter_version="1.0.0",
        acquisition_time="2026-08-23T10:00:00Z",
    )
    r2 = make_acquisition_record(
        artifact=artifact, artifact_version=version, job_id="job_1", adapter_version="1.0.0",
        acquisition_time="2026-08-23T11:00:00Z",
    )
    assert r1.id != r2.id
    # But both point at the SAME content state -- that is the point.
    assert r1.artifact_version_id == r2.artifact_version_id


def test_acquisition_record_success_requires_artifact_version_id():
    with pytest.raises(ValueError):
        AcquisitionRecord(
            id="x",
            artifact_id="a",
            artifact_version_id=None,
            job_id="j",
            adapter_version="1.0.0",
            acquisition_time="t",
            status="success",
            error=None,
            retrieval_metadata={},
            source_revision=None,
        )


def test_acquisition_record_rejects_unknown_status():
    with pytest.raises(ValueError):
        AcquisitionRecord(
            id="x",
            artifact_id="a",
            artifact_version_id=None,
            job_id="j",
            adapter_version="1.0.0",
            acquisition_time="t",
            status="bogus",
            error=None,
            retrieval_metadata={},
            source_revision=None,
        )


def test_acquisition_job_id_deterministic():
    j1 = make_acquisition_job(artifact_id="a1", adapter_version="1.0.0", requested_at="2026-08-23T00:00:00Z")
    j2 = make_acquisition_job(artifact_id="a1", adapter_version="1.0.0", requested_at="2026-08-23T00:00:00Z")
    assert j1.id == j2.id
