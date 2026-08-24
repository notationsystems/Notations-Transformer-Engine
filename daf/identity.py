"""Artifact and ArtifactVersion: the acquisition layer's identity model.

Two identities, deliberately kept apart, per the same discipline
`evidence/types.py` already applies to `Source`/`Document` (an id is
always a SHA-256 digest of exactly the fields that define identity,
computed by a `make_*` factory -- never supplied by the caller):

    Artifact         "what resource are we talking about?"
                      id = H(source_id, canonical_locator) -- STABLE.
                      Never changes even if the resource's content does.

    ArtifactVersion   "what exact bytes did that resource contain?"
                      id = H(artifact_id, raw_content_hash)
                      raw_content_hash = H(raw_bytes) -- PURE: a function
                      of the bytes alone, with no acquisition metadata
                      (time, HTTP headers, job id) folded in. Two
                      acquisitions of byte-identical content, however far
                      apart in time or however differently retrieved,
                      converge on the same ArtifactVersion -- exactly the
                      "re-put is a no-op" guarantee `evidence/pool.py`
                      already relies on for every pool object.

An earlier draft of this module folded a third concept -- "when/how did
we observe this content" -- into ArtifactVersion itself, by hashing a
`version_index` or acquisition timestamp into its id. That makes the
same content, acquired twice, produce two different ids (or, if the
index is reused, silently discard the second acquisition) -- neither of
which is what "content-addressed" is supposed to mean. `AcquisitionRecord`
(`daf/acquisition.py`) is the separate identity that concept belongs to;
see that module's docstring for why keeping it separate is the fix, not
a refinement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from evidence.identity import content_hash


@dataclass(frozen=True)
class Artifact:
    """Stable identity of an acquired resource (e.g. one API endpoint,
    one file path, one database table) -- independent of what that
    resource currently contains."""

    id: str
    source_id: str  # Reference to evidence.types.Source.id
    canonical_locator: str  # e.g. "/api/v1/materials", "table:users"


def make_artifact(source_id: str, canonical_locator: str) -> Artifact:
    artifact_id = content_hash({"source_id": source_id, "canonical_locator": canonical_locator})
    return Artifact(id=artifact_id, source_id=source_id, canonical_locator=canonical_locator)


@dataclass(frozen=True)
class ArtifactVersion:
    """Immutable snapshot of an Artifact's content. `raw_bytes` never
    changes after construction (bytes is itself immutable, and this
    dataclass is frozen), and `raw_content_hash` is never recomputed --
    both are fixed the moment `make_artifact_version` returns.

    `source_revision` (e.g. a git commit, an ETag, an API version string)
    is deliberately NOT part of `raw_content_hash` or `id`: it is
    provenance about the version, not part of what makes it *this*
    version -- the same content re-served under a different revision
    label is still the same content (see `daf/store.py`'s idempotency
    tests)."""

    id: str
    artifact_id: str
    raw_content_hash: str
    raw_bytes: bytes
    source_revision: Optional[str] = None


def make_artifact_version(
    artifact: Artifact, raw_bytes: bytes, source_revision: Optional[str] = None
) -> ArtifactVersion:
    """Critical: `raw_content_hash` is a pure function of `raw_bytes`
    alone. Nothing else passed here -- not `source_revision`, not any
    caller-supplied timestamp -- ever reaches it."""
    raw_content_hash = content_hash(raw_bytes.hex())
    version_id = content_hash({"artifact_id": artifact.id, "raw_content_hash": raw_content_hash})
    return ArtifactVersion(
        id=version_id,
        artifact_id=artifact.id,
        raw_content_hash=raw_content_hash,
        raw_bytes=raw_bytes,
        source_revision=source_revision,
    )
