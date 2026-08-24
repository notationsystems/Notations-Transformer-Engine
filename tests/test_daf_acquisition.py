"""Vertical-slice tests for the acquisition layer: `FixtureSourceAdapter`
(`daf/fixtures.py`) acquiring into `daf/store.py`, proving idempotence,
changed-content versioning, and failed-acquisition handling end to end."""

import pytest

from daf.acquisition import AcquisitionResult, make_acquisition_job
from daf.fixtures import FixtureSourceAdapter
from daf.store import InMemoryAcquisitionRecordStore, InMemoryArtifactVersionStore


def _job(adapter: FixtureSourceAdapter, requested_at: str = "2026-08-23T09:00:00Z"):
    return make_acquisition_job(artifact_id=adapter.artifact.id, adapter_version="1.0.0", requested_at=requested_at)


def test_successful_acquisition_round_trips_through_the_store():
    adapter = FixtureSourceAdapter(content={"test": "data", "value": 42})
    version_store = InMemoryArtifactVersionStore()
    version_store.put_artifact(adapter.artifact)

    result = adapter.acquire(_job(adapter), acquisition_time="2026-08-23T10:00:00Z")

    assert isinstance(result, AcquisitionResult)
    assert result.status == "success"
    assert result.artifact_version is not None
    assert result.error is None

    version_store.put_version(result.artifact_version)
    retrieved = version_store.get_version(result.artifact_version.id)
    assert retrieved is not None
    assert retrieved.raw_bytes == result.artifact_version.raw_bytes


def test_repeated_acquisition_of_unchanged_content_is_idempotent():
    """Two separate jobs, two separate acquisition times, identical
    content -- one ArtifactVersion, two AcquisitionRecords. This is
    exactly the case the original (broken) `version_id` design got
    wrong: see `daf/identity.py`'s module docstring."""
    adapter = FixtureSourceAdapter(content={"test": "data"})
    version_store = InMemoryArtifactVersionStore()
    record_store = InMemoryAcquisitionRecordStore()
    version_store.put_artifact(adapter.artifact)

    result1 = adapter.acquire(_job(adapter, "2026-08-23T09:00:00Z"), acquisition_time="2026-08-23T10:00:00Z")
    result2 = adapter.acquire(_job(adapter, "2026-08-23T09:30:00Z"), acquisition_time="2026-08-23T11:00:00Z")

    assert result1.artifact_version.id == result2.artifact_version.id
    assert result1.acquisition_record.id != result2.acquisition_record.id

    version_store.put_version(result1.artifact_version)
    version_store.put_version(result2.artifact_version)
    record_store.put_record(result1.acquisition_record)
    record_store.put_record(result2.acquisition_record)

    assert len(version_store.get_versions_for_artifact(adapter.artifact.id)) == 1
    assert len(record_store.get_records_for_artifact(adapter.artifact.id)) == 2


def test_changed_content_creates_a_new_version_not_a_new_artifact():
    adapter_v1 = FixtureSourceAdapter(canonical_locator="/test/data", content={"version": 1})
    adapter_v2 = FixtureSourceAdapter(canonical_locator="/test/data", content={"version": 2})

    # Same source + locator -> same Artifact identity.
    assert adapter_v1.artifact.id == adapter_v2.artifact.id

    result1 = adapter_v1.acquire(_job(adapter_v1), acquisition_time="2026-08-23T10:00:00Z")
    result2 = adapter_v2.acquire(_job(adapter_v2), acquisition_time="2026-08-23T11:00:00Z")

    assert result1.artifact_version.id != result2.artifact_version.id
    assert result1.artifact_version.raw_content_hash != result2.artifact_version.raw_content_hash


def test_provenance_preserved_through_acquisition():
    adapter = FixtureSourceAdapter(canonical_locator="/test/data", source_revision="rev-42")
    result = adapter.acquire(_job(adapter), acquisition_time="2026-08-23T10:00:00Z")

    assert result.artifact.canonical_locator == "/test/data"
    assert result.artifact_version.source_revision == "rev-42"
    assert result.acquisition_record.acquisition_time == "2026-08-23T10:00:00Z"
    assert result.acquisition_record.retrieval_metadata["method"] == "synthetic"
    assert result.provenance["source_revision"] == "rev-42"


def test_failed_acquisition_has_no_artifact_version_but_has_a_record():
    """Every acquisition attempt, success or failure, produces exactly
    one AcquisitionRecord -- a failed attempt is still an observed
    occurrence, just one that observed nothing."""
    from daf.acquisition import make_acquisition_record
    from daf.identity import make_artifact

    class FailingAdapter:
        def __init__(self) -> None:
            self._artifact = make_artifact(source_id="source_1", canonical_locator="/broken")

        @property
        def artifact(self):
            return self._artifact

        def acquire(self, job, acquisition_time):
            record = make_acquisition_record(
                artifact=self._artifact,
                artifact_version=None,
                job_id=job.id,
                adapter_version="1.0.0",
                acquisition_time=acquisition_time,
                status="failed",
                error="Simulated failure",
            )
            return AcquisitionResult(
                job_id=job.id,
                artifact=self._artifact,
                artifact_version=None,
                acquisition_record=record,
                status="failed",
                error="Simulated failure",
            )

    adapter = FailingAdapter()
    job = make_acquisition_job(artifact_id=adapter.artifact.id, adapter_version="1.0.0", requested_at="2026-08-23T09:00:00Z")
    result = adapter.acquire(job, acquisition_time="2026-08-23T10:00:00Z")

    assert result.status == "failed"
    assert result.error == "Simulated failure"
    assert result.artifact_version is None
    assert result.acquisition_record.status == "failed"
    assert result.acquisition_record.artifact_version_id is None


def test_acquisition_record_success_status_requires_a_version():
    """A malformed adapter that reports status="success" without an
    artifact_version is rejected at construction -- this is
    `AcquisitionRecord.__post_init__`'s own invariant, not something
    left to be caught downstream."""
    from daf.identity import make_artifact

    artifact = make_artifact(source_id="source_1", canonical_locator="/x")
    from daf.acquisition import make_acquisition_record

    with pytest.raises(ValueError):
        make_acquisition_record(
            artifact=artifact,
            artifact_version=None,
            job_id="job_1",
            adapter_version="1.0.0",
            acquisition_time="2026-08-23T10:00:00Z",
            status="success",
        )
