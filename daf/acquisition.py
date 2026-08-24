"""Acquisition occurrence and the adapter boundary.

`AcquisitionRecord` is the third identity this layer's model needs
(`daf/identity.py`'s docstring names the split): a record of *one*
attempt to acquire an Artifact, distinct from the ArtifactVersion (if
any) it observed. Its id is content-addressed like every other identity
in this module -- deliberately not a random UUID, even though it is
closer to an "event" than a "fact": a UUID would make every
AcquisitionRecord-touching test in this codebase nondeterministic, which
is the one property every other identity here (and every identity in
`evidence/types.py`) is built to guarantee. Hashing (artifact_id,
artifact_version_id, job_id, acquisition_time, status) keeps two truly
distinct occurrences distinct, while still making a *replayed* call --
the same job re-observing the same artifact at the same declared time --
collapse deterministically to one record, exactly the "re-put is a
no-op" property `evidence/pool.py` relies on for every other object.

`acquisition_time` (and `AcquisitionJob.requested_at`) are caller-
supplied, never wall-clock (`datetime.utcnow()` inside a factory) --
the same discipline `evidence.types.Document.retrieved_at` and
`scout.interface.RawDocument.retrieved_at` already establish: a
factory's output must be a pure function of its arguments, or nothing
built on top of it -- tests foremost -- can be deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional, Protocol

from evidence.identity import content_hash

from daf.identity import Artifact, ArtifactVersion

_VALID_STATUSES = ("success", "failed", "skipped")


@dataclass(frozen=True)
class AcquisitionJob:
    """A single request to acquire one Artifact. Deliberately minimal --
    scheduling, retries, and a real job queue are future work (§ this
    module's docstring), out of scope for the vertical slice this layer
    proves."""

    id: str
    artifact_id: str
    adapter_version: str
    requested_at: str  # ISO-8601 UTC, caller-supplied


def make_acquisition_job(artifact_id: str, adapter_version: str, requested_at: str) -> AcquisitionJob:
    job_id = content_hash(
        {"artifact_id": artifact_id, "adapter_version": adapter_version, "requested_at": requested_at}
    )
    return AcquisitionJob(id=job_id, artifact_id=artifact_id, adapter_version=adapter_version, requested_at=requested_at)


@dataclass(frozen=True)
class AcquisitionRecord:
    """"When/how did we observe this?" -- separate from both Artifact
    ("what resource") and ArtifactVersion ("what content"). Every
    acquisition attempt, success or failure, produces exactly one of
    these; `retrieval_metadata` is deeply immutable (`MappingProxyType`,
    not just a frozen dataclass field pointing at a mutable dict --
    mirrors `evidence.types.Observation.content`'s own
    `__post_init__` freeze)."""

    id: str
    artifact_id: str
    artifact_version_id: Optional[str]
    job_id: str
    adapter_version: str
    acquisition_time: str  # ISO-8601 UTC, caller-supplied
    status: str  # "success" | "failed" | "skipped"
    error: Optional[str]
    retrieval_metadata: Mapping[str, Any]
    source_revision: Optional[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "retrieval_metadata", MappingProxyType(dict(self.retrieval_metadata)))
        if self.status not in _VALID_STATUSES:
            raise ValueError(f"AcquisitionRecord.status must be one of {_VALID_STATUSES}, got {self.status!r}")
        if self.status == "success" and self.artifact_version_id is None:
            raise ValueError("AcquisitionRecord.status == 'success' requires an artifact_version_id")


def make_acquisition_record(
    artifact: Artifact,
    artifact_version: Optional[ArtifactVersion],
    job_id: str,
    adapter_version: str,
    acquisition_time: str,
    status: str = "success",
    error: Optional[str] = None,
    retrieval_metadata: Optional[Mapping[str, Any]] = None,
    source_revision: Optional[str] = None,
) -> AcquisitionRecord:
    artifact_version_id = artifact_version.id if artifact_version is not None else None
    metadata = dict(retrieval_metadata or {})
    record_id = content_hash(
        {
            "artifact_id": artifact.id,
            "artifact_version_id": artifact_version_id,
            "job_id": job_id,
            "acquisition_time": acquisition_time,
            "status": status,
        }
    )
    return AcquisitionRecord(
        id=record_id,
        artifact_id=artifact.id,
        artifact_version_id=artifact_version_id,
        job_id=job_id,
        adapter_version=adapter_version,
        acquisition_time=acquisition_time,
        status=status,
        error=error,
        retrieval_metadata=metadata,
        source_revision=source_revision,
    )


@dataclass(frozen=True)
class AcquisitionResult:
    """Adapter x AcquisitionJob -> AcquisitionResult: the clean functional
    boundary an adapter is judged against, one layer upstream of
    `scout.interface.SourceAdapter.fetch()`. `artifact` is always
    present (an adapter always knows its own target's identity, success
    or failure); `artifact_version` is `None` exactly when `status !=
    "success"`."""

    job_id: str
    artifact: Artifact
    artifact_version: Optional[ArtifactVersion]
    acquisition_record: AcquisitionRecord
    status: str
    error: Optional[str] = None
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))


class BaseAcquisitionAdapter(Protocol):
    """Protocol for acquisition adapters (mirrors
    `scout.interface.SourceAdapter`'s Protocol-only boundary one layer
    downstream). An adapter's only job is acquisition -- it never
    constructs a `NormalizedRecord` or an `evidence.types` object
    directly."""

    @property
    def artifact(self) -> Artifact: ...

    def acquire(self, job: AcquisitionJob, acquisition_time: str) -> AcquisitionResult: ...
