"""DAF -> evidence.types bridge (Layer 3): the explicit, non-inventive
crossing point from acquisition/normalization identity into the
evidence pool's own types (`evidence.types.Document` / `Record` /
`Observation`).

Same discipline `scout.pipeline.run_scout` already establishes one layer
over: every write into `pool` goes through `evidence.admission`'s gate
functions first. Nothing here ever invents an id -- an earlier draft of
this design used a placeholder `record_ids = ("record_1",)`, which has
no route into an `EvidencePool` at all (`admit_observation` checks
`pool.has_record(rid)` before anything downstream can proceed); this
module exists specifically to make that route real, by building the
`Record` itself and reading its id back off the object `make_record`
just returned.

`artifact_version_to_evidence` also takes `artifact` explicitly, rather
than reaching for it off `artifact_version` -- `ArtifactVersion` only
carries `artifact_id` (a string), never a reference to the `Artifact`
object itself (`daf/identity.py`), so `artifact_version.artifact` was
never a real attribute. Callers that need the `Artifact` look it up from
whichever `ArtifactVersionStore` they used to acquire it
(`daf/store.py`) and pass it in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Union

from evidence.admission import AdmissionError, admit_document, admit_observation, admit_record
from evidence.pool import EvidencePool
from evidence.types import Document, Observation, Record, make_document, make_observation, make_record

from daf.acquisition import AcquisitionRecord
from daf.identity import Artifact, ArtifactVersion
from daf.normalization import NormalizedRecord


@dataclass(frozen=True)
class BridgeAdmissionFailure:
    stage: str
    errors: Tuple[AdmissionError, ...]


@dataclass(frozen=True)
class BridgeResult:
    document: Document
    record: Record
    observation: Optional[Observation]  # None when no NormalizedRecord was supplied


def artifact_version_to_evidence(
    pool: EvidencePool,
    artifact: Artifact,
    artifact_version: ArtifactVersion,
    acquisition_record: AcquisitionRecord,
    normalized_record: Optional[NormalizedRecord] = None,
) -> Union[BridgeResult, BridgeAdmissionFailure]:
    """Convert one acquired ArtifactVersion (+ the AcquisitionRecord that
    observed it, + optionally the NormalizedRecord parsed from it) into
    admitted SCOUT evidence.

    Requires `pool.has_source(artifact.source_id)` already -- Source
    creation is the adapter's job (`daf.fixtures.FixtureSourceAdapter.source`),
    never this bridge's: this function crosses from acquisition identity
    into evidence identity, it does not originate a Source, exactly as
    `scout.pipeline.run_scout` originates its own Source but this module
    is not `scout.pipeline`.
    """
    if artifact_version.artifact_id != artifact.id:
        raise ValueError("artifact_version.artifact_id does not match artifact.id")
    if acquisition_record.artifact_version_id != artifact_version.id:
        raise ValueError("acquisition_record does not reference this artifact_version")

    try:
        raw_content = artifact_version.raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw_content = artifact_version.raw_bytes.hex()

    document = make_document(
        source_id=artifact.source_id,
        raw_content=raw_content,
        retrieval_method=str(acquisition_record.retrieval_metadata.get("method", "daf")),
        retrieved_at=acquisition_record.acquisition_time,
    )
    admitted_document = admit_document(pool, document)
    if isinstance(admitted_document, list):
        return BridgeAdmissionFailure(stage="document", errors=tuple(admitted_document))
    pool.put_document(document)

    record = make_record(document_id=document.id, locator=artifact.canonical_locator, raw_content=raw_content)
    admitted_record = admit_record(pool, record)
    if isinstance(admitted_record, list):
        return BridgeAdmissionFailure(stage="record", errors=tuple(admitted_record))
    pool.put_record(record)

    if normalized_record is None:
        return BridgeResult(document=document, record=record, observation=None)

    if normalized_record.artifact_version_id != artifact_version.id:
        raise ValueError("normalized_record does not reference this artifact_version")

    observation = make_observation(
        record_ids=(record.id,),
        extraction_method=f"daf_normalization:{normalized_record.parser_version}",
        content=dict(normalized_record.data),
        confidence=1.0,  # deterministic normalization -- see daf.normalization module docstring
        extracted_at=acquisition_record.acquisition_time,
    )
    admitted_observation = admit_observation(pool, observation)
    if isinstance(admitted_observation, list):
        return BridgeAdmissionFailure(stage="observation", errors=tuple(admitted_observation))
    pool.put_observation(observation)

    return BridgeResult(document=document, record=record, observation=observation)
