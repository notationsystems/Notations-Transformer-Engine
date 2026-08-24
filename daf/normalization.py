"""Normalization: ArtifactVersion -> Parser -> NormalizedRecord.

`NormalizedRecord` is this layer's transformation-provenance guarantee:
`data = f(R, P, S)` where R (the `ArtifactVersion` parsed), P (the
parser and its version), and S (the `SchemaVersion` applied) are each
independently identifiable, and the record's own id is a pure function
of all three plus the resulting data -- re-parsing the same
ArtifactVersion with the same parser/schema always converges on the
same `NormalizedRecord.id`, the same determinism
`evidence.types.make_observation` already guarantees one layer
downstream (`tests/test_daf_normalization.py::test_reproducible_reconstruction`).

`normalized_content_hash` is a second, SEPARATE identity: a hash of
`data` alone, independent of which ArtifactVersion/parser/schema
produced it. Two differently-acquired raw byte streams that normalize to
the same semantic content converge on the same `normalized_content_hash`
even though they never converge on the same `NormalizedRecord.id` --
deliberately: `NormalizedRecord.id` still has to answer "which specific
transformation produced this," while `normalized_content_hash` answers
"have we seen this meaning before." Conflating the two would make
semantic deduplication and transformation provenance impossible to ask
about independently.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Protocol

from evidence.identity import content_hash


@dataclass(frozen=True)
class SchemaVersion:
    id: str
    name: str  # e.g. "generic_json"
    version: str  # e.g. "1.0.0"
    definition: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "definition", MappingProxyType(dict(self.definition)))


def make_schema_version(name: str, version: str, definition: Mapping[str, Any]) -> SchemaVersion:
    schema_id = content_hash({"name": name, "version": version, "definition": dict(definition)})
    return SchemaVersion(id=schema_id, name=name, version=version, definition=definition)


@dataclass(frozen=True)
class NormalizedRecord:
    id: str
    artifact_version_id: str
    schema_version_id: str
    parser_version: str
    data: Mapping[str, Any]
    normalized_content_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))


def make_normalized_record(
    artifact_version_id: str,
    schema_version_id: str,
    parser_version: str,
    data: Mapping[str, Any],
) -> NormalizedRecord:
    data_dict = dict(data)
    normalized_content_hash = content_hash(data_dict)
    record_id = content_hash(
        {
            "artifact_version_id": artifact_version_id,
            "schema_version_id": schema_version_id,
            "parser_version": parser_version,
            "normalized_content_hash": normalized_content_hash,
        }
    )
    return NormalizedRecord(
        id=record_id,
        artifact_version_id=artifact_version_id,
        schema_version_id=schema_version_id,
        parser_version=parser_version,
        data=data,
        normalized_content_hash=normalized_content_hash,
    )


class BaseParser(Protocol):
    @property
    def parser_version(self) -> str: ...

    def parse(self, artifact_version_id: str, schema_version_id: str, raw_bytes: bytes) -> NormalizedRecord: ...


class JSONParser:
    """Pass-through JSON parser proving the vertical slice's contract --
    "is this valid JSON, and is its top level an object" is the only
    check performed; a schema-validating parser is future work, same as
    a live HTTP adapter (`daf/__init__.py`'s module docstring)."""

    PARSER_VERSION = "1.0.0"

    @property
    def parser_version(self) -> str:
        return self.PARSER_VERSION

    def parse(self, artifact_version_id: str, schema_version_id: str, raw_bytes: bytes) -> NormalizedRecord:
        try:
            data = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"JSONParser could not parse raw_bytes: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("JSONParser requires a JSON object at the top level")
        return make_normalized_record(
            artifact_version_id=artifact_version_id,
            schema_version_id=schema_version_id,
            parser_version=self.parser_version,
            data=data,
        )


class NormalizedRecordStore(ABC):
    @abstractmethod
    def put_record(self, record: NormalizedRecord) -> None: ...

    @abstractmethod
    def get_record(self, record_id: str) -> Optional[NormalizedRecord]: ...

    @abstractmethod
    def get_records_by_artifact_version(self, artifact_version_id: str) -> List[NormalizedRecord]: ...

    @abstractmethod
    def get_records_by_normalized_hash(self, normalized_content_hash: str) -> List[NormalizedRecord]: ...


class InMemoryNormalizedRecordStore(NormalizedRecordStore):
    def __init__(self) -> None:
        self._records: Dict[str, NormalizedRecord] = {}
        self._by_version: Dict[str, List[NormalizedRecord]] = {}
        self._by_hash: Dict[str, List[NormalizedRecord]] = {}

    def put_record(self, record: NormalizedRecord) -> None:
        if record.id in self._records:
            return
        self._records[record.id] = record
        self._by_version.setdefault(record.artifact_version_id, []).append(record)
        self._by_hash.setdefault(record.normalized_content_hash, []).append(record)

    def get_record(self, record_id: str) -> Optional[NormalizedRecord]:
        return self._records.get(record_id)

    def get_records_by_artifact_version(self, artifact_version_id: str) -> List[NormalizedRecord]:
        return list(self._by_version.get(artifact_version_id, []))

    def get_records_by_normalized_hash(self, normalized_content_hash: str) -> List[NormalizedRecord]:
        return list(self._by_hash.get(normalized_content_hash, []))
