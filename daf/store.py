"""In-memory storage for the acquisition layer (v1 scope only -- a real
backend, e.g. object storage for raw bytes plus a SQL metadata index, is
future work, the same deferral `evidence/pool.py`'s own docstring makes
for `core.canonical`'s eventual real database).

Idempotency is the whole point of `ArtifactVersionStore`:
`put_version` is keyed by `(artifact_id, raw_content_hash)`, not by
`ArtifactVersion.id` alone -- though the two coincide by construction
(`ArtifactVersion.id = H(artifact_id, raw_content_hash)`,
`daf/identity.py`), keeping the index explicit makes the invariant a
property of this store's own logic rather than an accident of how ids
happen to be computed. Replaying the identical acquisition (same
artifact, same bytes) never creates a second stored version, exactly
`evidence/pool.py`'s "re-put is a no-op" guarantee.

`AcquisitionRecordStore` is append-only in a different sense: every
*distinct* occurrence (distinct in job/time/status -- see
`daf/acquisition.py`) is kept, on purpose -- this is what lets a caller
ask "when did we observe this ArtifactVersion" as a question separate
from "what versions has this Artifact ever had" (`tests/test_daf_store.py`
covers both).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from daf.acquisition import AcquisitionRecord
from daf.identity import Artifact, ArtifactVersion


class ArtifactVersionStore(ABC):
    @abstractmethod
    def put_artifact(self, artifact: Artifact) -> None: ...

    @abstractmethod
    def put_version(self, version: ArtifactVersion) -> None: ...

    @abstractmethod
    def get_artifact(self, artifact_id: str) -> Optional[Artifact]: ...

    @abstractmethod
    def get_version(self, version_id: str) -> Optional[ArtifactVersion]: ...

    @abstractmethod
    def get_version_by_content_hash(self, artifact_id: str, raw_content_hash: str) -> Optional[ArtifactVersion]: ...

    @abstractmethod
    def get_versions_for_artifact(self, artifact_id: str) -> List[ArtifactVersion]: ...


class InMemoryArtifactVersionStore(ArtifactVersionStore):
    def __init__(self) -> None:
        self._artifacts: Dict[str, Artifact] = {}
        self._versions: Dict[str, ArtifactVersion] = {}
        self._by_artifact: Dict[str, List[ArtifactVersion]] = {}
        self._by_content_hash: Dict[Tuple[str, str], str] = {}

    def put_artifact(self, artifact: Artifact) -> None:
        if artifact.id not in self._artifacts:
            self._artifacts[artifact.id] = artifact
            self._by_artifact[artifact.id] = []

    def put_version(self, version: ArtifactVersion) -> None:
        key = (version.artifact_id, version.raw_content_hash)
        if key in self._by_content_hash:
            return
        self._versions[version.id] = version
        self._by_artifact.setdefault(version.artifact_id, []).append(version)
        self._by_content_hash[key] = version.id

    def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        return self._artifacts.get(artifact_id)

    def get_version(self, version_id: str) -> Optional[ArtifactVersion]:
        return self._versions.get(version_id)

    def get_version_by_content_hash(self, artifact_id: str, raw_content_hash: str) -> Optional[ArtifactVersion]:
        version_id = self._by_content_hash.get((artifact_id, raw_content_hash))
        return self._versions.get(version_id) if version_id else None

    def get_versions_for_artifact(self, artifact_id: str) -> List[ArtifactVersion]:
        return list(self._by_artifact.get(artifact_id, []))


class AcquisitionRecordStore(ABC):
    @abstractmethod
    def put_record(self, record: AcquisitionRecord) -> None: ...

    @abstractmethod
    def get_record(self, record_id: str) -> Optional[AcquisitionRecord]: ...

    @abstractmethod
    def get_records_for_artifact(self, artifact_id: str) -> List[AcquisitionRecord]: ...

    @abstractmethod
    def get_records_for_version(self, artifact_version_id: str) -> List[AcquisitionRecord]: ...


class InMemoryAcquisitionRecordStore(AcquisitionRecordStore):
    def __init__(self) -> None:
        self._records: Dict[str, AcquisitionRecord] = {}
        self._by_artifact: Dict[str, List[AcquisitionRecord]] = {}
        self._by_version: Dict[str, List[AcquisitionRecord]] = {}

    def put_record(self, record: AcquisitionRecord) -> None:
        if record.id in self._records:
            return
        self._records[record.id] = record
        self._by_artifact.setdefault(record.artifact_id, []).append(record)
        if record.artifact_version_id is not None:
            self._by_version.setdefault(record.artifact_version_id, []).append(record)

    def get_record(self, record_id: str) -> Optional[AcquisitionRecord]:
        return self._records.get(record_id)

    def get_records_for_artifact(self, artifact_id: str) -> List[AcquisitionRecord]:
        return list(self._by_artifact.get(artifact_id, []))

    def get_records_for_version(self, artifact_version_id: str) -> List[AcquisitionRecord]:
        return list(self._by_version.get(artifact_version_id, []))
