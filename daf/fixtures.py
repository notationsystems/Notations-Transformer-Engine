"""Deterministic synthetic source, structurally satisfying
`BaseAcquisitionAdapter` -- mirrors `scout/fixtures.py`'s own "no live
network access anywhere, every timestamp caller-supplied" discipline, so
a DAF acquisition run over this adapter is fully reproducible.

`FixtureSourceAdapter` is the only adapter implementation in this package,
deliberately: `scout/fixtures.py` cites "do NOT attempt to build a giant
crawler" for the same reason. A live HTTP/API adapter implements the
same `BaseAcquisitionAdapter` shape later without changing anything in
`daf.bridge` or `evidence/`.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from evidence.types import Source, make_source

from daf.acquisition import AcquisitionJob, AcquisitionResult, make_acquisition_record
from daf.identity import Artifact, make_artifact, make_artifact_version

ADAPTER_VERSION = "1.0.0"

DEFAULT_CONTENT: Mapping[str, Any] = {"message": "Hello, DAF!", "value": 42}


class FixtureSourceAdapter:
    """Adapter for a synthetic/test source: acquiring it always returns
    the same `content` (serialized to canonical JSON bytes) the adapter
    was constructed with -- construct two instances with different
    `content` to simulate the source's content changing between
    acquisitions (`tests/test_daf_acquisition.py::test_changed_content_creates_new_version`)."""

    def __init__(
        self,
        source_name: str = "test_source_v1",
        source_kind: str = "synthetic",
        canonical_locator: str = "/test/data",
        content: Optional[Mapping[str, Any]] = None,
        source_revision: str = "1.0",
    ) -> None:
        self._source = make_source(kind=source_kind, name=source_name)
        self._artifact = make_artifact(source_id=self._source.id, canonical_locator=canonical_locator)
        self._content: Mapping[str, Any] = dict(content) if content is not None else dict(DEFAULT_CONTENT)
        self._source_revision = source_revision

    @property
    def source(self) -> Source:
        return self._source

    @property
    def artifact(self) -> Artifact:
        return self._artifact

    def acquire(self, job: AcquisitionJob, acquisition_time: str) -> AcquisitionResult:
        raw_bytes = json.dumps(self._content, sort_keys=True).encode("utf-8")
        artifact_version = make_artifact_version(
            artifact=self._artifact, raw_bytes=raw_bytes, source_revision=self._source_revision
        )
        acquisition_record = make_acquisition_record(
            artifact=self._artifact,
            artifact_version=artifact_version,
            job_id=job.id,
            adapter_version=ADAPTER_VERSION,
            acquisition_time=acquisition_time,
            status="success",
            retrieval_metadata={"method": "synthetic"},
            source_revision=self._source_revision,
        )
        return AcquisitionResult(
            job_id=job.id,
            artifact=self._artifact,
            artifact_version=artifact_version,
            acquisition_record=acquisition_record,
            status="success",
            provenance={"adapter_type": "test", "source_revision": self._source_revision},
        )
