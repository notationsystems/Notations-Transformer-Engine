"""End-to-end DAF tests: FixtureSourceAdapter -> AcquisitionResult ->
JSONParser -> NormalizedRecord -> daf.bridge -> admitted EvidencePool
objects. Covers the two concrete bugs the v2 design review flagged in
the bridge (`daf/bridge.py`'s module docstring): no invented ids, and no
reliance on a nonexistent `ArtifactVersion.artifact` attribute."""

from evidence.admission import AdmissionError
from evidence.pool import EvidencePool

from daf.acquisition import make_acquisition_job
from daf.bridge import BridgeResult, artifact_version_to_evidence
from daf.fixtures import FixtureSourceAdapter
from daf.normalization import JSONParser, make_schema_version


def _acquire(adapter: FixtureSourceAdapter, acquisition_time: str = "2026-08-23T10:00:00Z"):
    job = make_acquisition_job(artifact_id=adapter.artifact.id, adapter_version="1.0.0", requested_at="2026-08-23T09:00:00Z")
    return adapter.acquire(job, acquisition_time=acquisition_time)


def test_bridge_produces_document_and_record_without_normalization():
    pool = EvidencePool()
    adapter = FixtureSourceAdapter(content={"message": "hello"})
    pool.put_source(adapter.source)

    result = _acquire(adapter)
    bridged = artifact_version_to_evidence(
        pool=pool,
        artifact=adapter.artifact,
        artifact_version=result.artifact_version,
        acquisition_record=result.acquisition_record,
    )

    assert isinstance(bridged, BridgeResult)
    assert bridged.observation is None
    assert pool.has_document(bridged.document.id)
    assert pool.has_record(bridged.record.id)
    assert bridged.document.source_id == adapter.source.id
    assert bridged.record.document_id == bridged.document.id


def test_bridge_produces_observation_referencing_the_real_record_id():
    """The specific failure mode flagged in review: a bridge that
    invents `record_ids=("record_1",)` instead of using the id of the
    Record it actually built and admitted."""
    pool = EvidencePool()
    adapter = FixtureSourceAdapter(content={"message": "hello", "value": 42})
    pool.put_source(adapter.source)

    result = _acquire(adapter)
    schema = make_schema_version(name="generic_json", version="1.0.0", definition={"type": "object"})
    parser = JSONParser()
    normalized = parser.parse(
        artifact_version_id=result.artifact_version.id,
        schema_version_id=schema.id,
        raw_bytes=result.artifact_version.raw_bytes,
    )

    bridged = artifact_version_to_evidence(
        pool=pool,
        artifact=adapter.artifact,
        artifact_version=result.artifact_version,
        acquisition_record=result.acquisition_record,
        normalized_record=normalized,
    )

    assert isinstance(bridged, BridgeResult)
    assert bridged.observation is not None
    assert bridged.observation.record_ids == (bridged.record.id,)
    assert pool.has_observation(bridged.observation.id)
    assert dict(bridged.observation.content) == dict(normalized.data)
    assert bridged.observation.extraction_method == f"daf_normalization:{JSONParser.PARSER_VERSION}"


def test_bridge_rejects_document_when_source_not_yet_in_pool():
    """`admit_document` requires the Source to already be admitted --
    the bridge does not silently create one on the caller's behalf."""
    pool = EvidencePool()
    adapter = FixtureSourceAdapter()
    # Deliberately do NOT pool.put_source(adapter.source).

    result = _acquire(adapter)
    bridged = artifact_version_to_evidence(
        pool=pool,
        artifact=adapter.artifact,
        artifact_version=result.artifact_version,
        acquisition_record=result.acquisition_record,
    )

    from daf.bridge import BridgeAdmissionFailure

    assert isinstance(bridged, BridgeAdmissionFailure)
    assert bridged.stage == "document"
    assert any(isinstance(e, AdmissionError) and e.code == "UNKNOWN_SOURCE" for e in bridged.errors)


def test_repeated_bridging_of_the_same_content_converges_on_one_document_and_record():
    """Two acquisitions of byte-identical content bridge to the SAME
    Document/Record (evidence.types identity is itself content-
    addressed) -- re-admission is a no-op, matching
    `evidence/pool.py`'s own guarantee."""
    pool = EvidencePool()
    adapter = FixtureSourceAdapter(content={"stable": "content"})
    pool.put_source(adapter.source)

    result1 = _acquire(adapter, acquisition_time="2026-08-23T10:00:00Z")
    result2 = _acquire(adapter, acquisition_time="2026-08-23T10:00:00Z")

    bridged1 = artifact_version_to_evidence(
        pool=pool, artifact=adapter.artifact, artifact_version=result1.artifact_version,
        acquisition_record=result1.acquisition_record,
    )
    bridged2 = artifact_version_to_evidence(
        pool=pool, artifact=adapter.artifact, artifact_version=result2.artifact_version,
        acquisition_record=result2.acquisition_record,
    )

    assert isinstance(bridged1, BridgeResult) and isinstance(bridged2, BridgeResult)
    assert bridged1.document.id == bridged2.document.id
    assert bridged1.record.id == bridged2.record.id
