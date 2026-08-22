"""EvidencePool: in-memory, append-only store for pool objects.

Same shape as `core/canonical/version.py::InMemoryVersionStore` --
single-writer, in-process, v1 only (§S: no real database is implied or
required yet). The one deliberate difference: `VersionStore` has one
head; `EvidencePool` has none, because unlike `CanonicalState` there is
no single "current" evidence state -- conflicting, coexisting
Observations are the point (§E), not a bug to resolve here.

Nothing is ever deleted. Because every id is content-addressed
(`evidence/identity.py`), re-putting an object that already exists is a
no-op by construction -- there is no way to construct two *different*
objects that collide on the same id, so unlike
`core.canonical.state.CanonicalState`'s `fields[key].id` check, there is
no possible mismatch to detect here.
"""

from __future__ import annotations

from typing import Dict, Tuple

from evidence.types import ClaimedRelationship, Document, Observation, Record, Referent, Source


class EvidencePool:
    def __init__(self) -> None:
        self._sources: Dict[str, Source] = {}
        self._documents: Dict[str, Document] = {}
        self._records: Dict[str, Record] = {}
        self._observations: Dict[str, Observation] = {}
        self._referents: Dict[str, Referent] = {}
        self._claimed_relationships: Dict[str, ClaimedRelationship] = {}

    # -- put: idempotent, append-only, never overwrites with different content (impossible by
    #    construction since ids are content hashes -- see module docstring) --

    def put_source(self, source: Source) -> None:
        self._sources[source.id] = source

    def put_document(self, document: Document) -> None:
        self._documents[document.id] = document

    def put_record(self, record: Record) -> None:
        self._records[record.id] = record

    def put_observation(self, observation: Observation) -> None:
        self._observations[observation.id] = observation

    def put_referent(self, referent: Referent) -> None:
        self._referents[referent.id] = referent

    def put_claimed_relationship(self, relationship: ClaimedRelationship) -> None:
        self._claimed_relationships[relationship.id] = relationship

    # -- get --

    def get_source(self, source_id: str) -> Source:
        return self._sources[source_id]

    def get_document(self, document_id: str) -> Document:
        return self._documents[document_id]

    def get_record(self, record_id: str) -> Record:
        return self._records[record_id]

    def get_observation(self, observation_id: str) -> Observation:
        return self._observations[observation_id]

    def get_referent(self, referent_id: str) -> Referent:
        return self._referents[referent_id]

    def has_referent(self, referent_id: str) -> bool:
        return referent_id in self._referents

    def has_document(self, document_id: str) -> bool:
        return document_id in self._documents

    def has_record(self, record_id: str) -> bool:
        return record_id in self._records

    def has_source(self, source_id: str) -> bool:
        return source_id in self._sources

    def has_observation(self, observation_id: str) -> bool:
        return observation_id in self._observations

    # -- query: every Observation/ClaimedRelationship ever admitted, unfiltered and
    #    un-deduplicated -- §E requires conflicting evidence to coexist, so these
    #    intentionally never collapse to "the" value for anything --

    def observations_about(self, referent_id: str) -> Tuple[Observation, ...]:
        rel_obs_ids = {
            rel.observation_id
            for rel in self._claimed_relationships.values()
            if referent_id in (rel.from_referent_id, rel.to_referent_id)
        }
        return tuple(self._observations[oid] for oid in sorted(rel_obs_ids))

    def relationships_touching(self, referent_id: str) -> Tuple[ClaimedRelationship, ...]:
        return tuple(
            rel
            for rel in sorted(self._claimed_relationships.values(), key=lambda r: r.id)
            if referent_id in (rel.from_referent_id, rel.to_referent_id)
        )

    def all_referents(self) -> Tuple[Referent, ...]:
        return tuple(self._referents[k] for k in sorted(self._referents))

    def all_claimed_relationships(self) -> Tuple[ClaimedRelationship, ...]:
        return tuple(self._claimed_relationships[k] for k in sorted(self._claimed_relationships))

    def all_observations(self) -> Tuple[Observation, ...]:
        return tuple(self._observations[k] for k in sorted(self._observations))

    def __len__(self) -> int:
        return (
            len(self._sources)
            + len(self._documents)
            + len(self._records)
            + len(self._observations)
            + len(self._referents)
            + len(self._claimed_relationships)
        )
