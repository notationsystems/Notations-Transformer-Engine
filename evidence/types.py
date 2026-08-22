"""Pool object types (`docs/PHASE_14_DATA_POOL_ARCHITECTURE.md` §B/§D).

Naming deliberately follows that document's own collision warning:
`Referent` (not `Entity` -- `morpho/ir.py` already owns that name) and
`ClaimedRelationship` (not `Relationship` -- ditto for `MorphoRelation`).

Every type here is immutable once constructed, exactly like
`core/canonical/state.py`'s `Field`/`EdgeRecord`/`CanonicalState`: an
"update" is always a *new* object referencing its predecessor by id,
never an in-place edit. Nothing in this module is ever deleted by
anything in this repository -- see `evidence/pool.py`.

The ONLY supported way to construct one of these is its `make_*`
factory below -- exactly the discipline `core/canonical/version.py`'s
`make_version` already establishes ("the id is always derived from
content, never supplied by the caller, so an object's id can never
disagree with its own content"). Constructing a dataclass directly with
a hand-picked `id` bypasses that guarantee and is a caller error, not a
supported path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from evidence.identity import content_hash


@dataclass(frozen=True)
class Source:
    """Origin of documents (§B). Identity is independent of any one
    document, so two documents from "the same place" naturally converge
    on one Source record rather than being silently duplicated."""

    id: str
    kind: str  # "paper" | "patent" | "github_repo" | "documentation" | ...
    name: str


def make_source(kind: str, name: str) -> Source:
    source_id = content_hash({"kind": kind, "name": name})
    return Source(id=source_id, kind=kind, name=name)


@dataclass(frozen=True)
class Document:
    """A retrieved artifact (§B). Immutable once ingested -- a changed
    source produces a *new* Document, exactly mirroring how a changed
    CanonicalState produces a new Version rather than mutating the old
    one. `raw_content` is kept on the object (not just its hash) because,
    unlike CanonicalState, nothing downstream reconstructs it from
    elsewhere -- this pool is its own store of record for raw evidence."""

    id: str
    source_id: str
    raw_content: str
    retrieval_method: str
    retrieved_at: str  # ISO-8601 UTC, caller-supplied -- never wall-clock


def make_document(source_id: str, raw_content: str, retrieval_method: str, retrieved_at: str) -> Document:
    content = content_hash(raw_content)
    doc_id = content_hash(
        {"source_id": source_id, "content_hash": content, "retrieval_method": retrieval_method}
    )
    return Document(
        id=doc_id,
        source_id=source_id,
        raw_content=raw_content,
        retrieval_method=retrieval_method,
        retrieved_at=retrieved_at,
    )


@dataclass(frozen=True)
class Record:
    """One raw structural unit within a Document (§B) -- still mechanical,
    not yet a semantic claim. `locator` is deliberately loosely typed
    (§D): a page/table/row description, a byte range, a section heading
    -- whatever is meaningful for the source format, validated only by
    convention, never forced into one universal locator schema."""

    id: str
    document_id: str
    locator: str
    raw_content: str


def make_record(document_id: str, locator: str, raw_content: str) -> Record:
    record_id = content_hash({"document_id": document_id, "locator": locator, "raw_content": raw_content})
    return Record(id=record_id, document_id=document_id, locator=locator, raw_content=raw_content)


@dataclass(frozen=True)
class Observation:
    """A semantic, extracted fact (§B), tied to the Record(s) it came
    from. Identity covers only what makes it *this* fact -- the source
    records, the extraction method, and the extracted content itself --
    never `confidence` or `extracted_at`, which are epistemic/temporal
    annotations that can differ between two otherwise-identical
    re-extractions without them being "different facts." This is what
    makes "same source, same extraction configuration -> same canonical
    observation" (this phase's determinism requirement) hold: re-running
    a deterministic extractor over the same Record always yields the
    same `Observation.id`, even if `extracted_at` differs.

    `content` is an open, extraction-defined mapping (e.g.
    {"property": "melt_viscosity", "value": 1250, "unit": "Pa.s"} or
    {"subject": "FEP", "predicate": "used_in", "object": "extrusion"})
    -- deliberately not forced into one schema, mirroring `Locator`'s own
    open-payload choice (§D) and this project's repeated conclusion
    (Phase 12, Phase 13 §L) that a universal ontology is not a
    prerequisite for representing heterogeneous evidence."""

    id: str
    record_ids: Tuple[str, ...]
    extraction_method: str  # "human_transcription" | "regex:<name>" | "model:<name>" | ...
    content: Mapping[str, object]
    confidence: float  # required, always a float -- see admit_observation for the model-source rule
    extracted_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_ids", tuple(self.record_ids))
        object.__setattr__(self, "content", MappingProxyType(dict(self.content)))
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Observation.confidence must be in [0, 1], got {self.confidence!r}")


def make_observation(
    record_ids: Tuple[str, ...],
    extraction_method: str,
    content: Mapping[str, object],
    confidence: float,
    extracted_at: str,
) -> Observation:
    record_ids = tuple(sorted(record_ids))
    obs_id = content_hash(
        {"record_ids": list(record_ids), "extraction_method": extraction_method, "content": dict(sorted(content.items()))}
    )
    return Observation(
        id=obs_id,
        record_ids=record_ids,
        extraction_method=extraction_method,
        content=content,
        confidence=confidence,
        extracted_at=extracted_at,
    )


@dataclass(frozen=True)
class Referent:
    """The specific material/instrument/process/sample/concept a Claim is
    *about* (§B, called `Referent` rather than `Entity` to avoid
    colliding with `morpho.ir.Entity`). Identity is a deterministic
    function of an explicit `natural_key` the caller supplies (e.g. a
    normalized label) -- there is NO fuzzy entity resolution here.
    Two observations naming the identical natural_key converge on one
    Referent; two observations naming "FEP" and "Teflon FEP" do NOT
    automatically merge, because entity resolution is an explicitly
    unresolved research question (`docs/PHASE_14_DATA_POOL_ARCHITECTURE.md`
    §S) -- a proposed merge belongs in a `same_as`-typed
    ClaimedRelationship, itself just evidence, never an automatic
    collapse of two ids into one."""

    id: str
    natural_key: str
    kind: str  # "material" | "instrument" | "process" | "sample" | "concept" | ...


def make_referent(natural_key: str, kind: str) -> Referent:
    ref_id = content_hash({"natural_key": natural_key, "kind": kind})
    return Referent(id=ref_id, natural_key=natural_key, kind=kind)


@dataclass(frozen=True)
class ClaimedRelationship:
    """An asserted connection between two Referents (§B, `Relationship`
    renamed for the same collision-avoidance reason as `Referent`).
    Identity includes the source `observation_id` -- not just
    (from, to, type) -- because two sources can claim different, even
    contradictory, relationships between the same two Referents, and
    §E's conflict model requires both claims to coexist rather than one
    silently overwriting the other."""

    id: str
    from_referent_id: str
    to_referent_id: str
    type: str
    observation_id: str
    confidence: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"ClaimedRelationship.confidence must be in [0, 1], got {self.confidence!r}")


def make_claimed_relationship(
    from_referent_id: str, to_referent_id: str, type: str, observation_id: str, confidence: float
) -> ClaimedRelationship:
    rel_id = content_hash(
        {
            "from_referent_id": from_referent_id,
            "to_referent_id": to_referent_id,
            "type": type,
            "observation_id": observation_id,
        }
    )
    return ClaimedRelationship(
        id=rel_id,
        from_referent_id=from_referent_id,
        to_referent_id=to_referent_id,
        type=type,
        observation_id=observation_id,
        confidence=confidence,
    )
