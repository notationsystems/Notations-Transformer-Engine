"""SCOUT orchestration: source -> ... -> Trust Graph attachment ->
network-state metrics -> FEP-facing signal.

This is the concrete realization of the pipeline
`docs/SCOUT_ARCHITECTURE.md` §1 describes, and of question 11's answer:
`agent -> observation -> validation boundary -> canonical state -> graph`
is preferred over `agent -> graph` directly -- except here "validation
boundary" is `evidence.admission` (not `core.canonical.validation`) and
"graph" is the Trust Graph (not `CanonicalState.edges`). SCOUT never
reaches `core.canonical` at all in this phase; see
`docs/SCOUT_ARCHITECTURE.md` for why that is a deliberate scope
boundary, not an oversight.

Every write into `pool` goes through `evidence.admission`'s gate
functions first -- there is no path in this module that calls
`pool.put_*` without a preceding `admit_*` call succeeding.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import List, Mapping, Tuple

from evidence.admission import (
    AdmissionError,
    admit_claimed_relationship,
    admit_document,
    admit_observation,
    admit_record,
    admit_referent,
)
from evidence.fep_interface import FEPSignal, compute_fep_signal
from evidence.metrics import (
    ConnectivityMetrics,
    bridge_potential,
    connectivity,
    evidence_density,
    novelty,
    observation_uncertainty,
    redundancy,
    source_diversity,
)
from evidence.pool import EvidencePool
from evidence.trust_graph import build_trust_graph
from evidence.types import (
    ClaimedRelationship,
    Document,
    Observation,
    Record,
    Referent,
    Source,
    make_claimed_relationship,
    make_document,
    make_observation,
    make_record,
    make_referent,
    make_source,
)
from scout.interface import Extractor, SourceAdapter


@dataclass(frozen=True)
class ScoutAdmissionFailure:
    stage: str
    errors: Tuple[AdmissionError, ...]


@dataclass(frozen=True)
class ScoutFinding:
    source: Source
    document: Document
    record: Record
    observation: Observation
    referents: Tuple[Referent, ...]
    relationships: Tuple[ClaimedRelationship, ...]
    connectivity: ConnectivityMetrics
    novelty: float
    redundancy: Mapping[str, int]
    source_diversity: Mapping[str, float]
    evidence_density: Mapping[str, int]
    bridge_potential: Mapping[str, bool]
    fep_signal: FEPSignal

    def __post_init__(self) -> None:
        object.__setattr__(self, "redundancy", MappingProxyType(dict(self.redundancy)))
        object.__setattr__(self, "source_diversity", MappingProxyType(dict(self.source_diversity)))
        object.__setattr__(self, "evidence_density", MappingProxyType(dict(self.evidence_density)))
        object.__setattr__(self, "bridge_potential", MappingProxyType(dict(self.bridge_potential)))


def run_scout(
    adapter: SourceAdapter, extractor: Extractor, pool: EvidencePool
) -> Tuple[Tuple[ScoutFinding, ...], Tuple[ScoutAdmissionFailure, ...]]:
    findings: List[ScoutFinding] = []
    failures: List[ScoutAdmissionFailure] = []

    for raw_doc in adapter.fetch():
        source = make_source(kind=raw_doc.source_kind, name=raw_doc.source_name)
        pool.put_source(source)

        document = make_document(
            source_id=source.id,
            raw_content=raw_doc.content,
            retrieval_method=raw_doc.retrieval_method,
            retrieved_at=raw_doc.retrieved_at,
        )
        admitted_document = admit_document(pool, document)
        if isinstance(admitted_document, list):
            failures.append(ScoutAdmissionFailure(stage="document", errors=tuple(admitted_document)))
            continue
        pool.put_document(document)

        record = make_record(document_id=document.id, locator=raw_doc.locator, raw_content=raw_doc.content)
        admitted_record = admit_record(pool, record)
        if isinstance(admitted_record, list):
            failures.append(ScoutAdmissionFailure(stage="record", errors=tuple(admitted_record)))
            continue
        pool.put_record(record)

        for candidate in extractor.extract(record):
            # docs/PHASE_14_DATA_POOL_ARCHITECTURE.md §K's non-negotiable rule,
            # enforced here rather than silently defaulted: a model-attributed
            # extraction without an explicit confidence is rejected, never
            # coerced into looking like a verbatim transcription.
            if candidate.extraction_method.startswith("model:") and candidate.confidence is None:
                failures.append(
                    ScoutAdmissionFailure(
                        stage="extraction",
                        errors=(
                            AdmissionError(
                                "ExtractionCandidate",
                                "MISSING_MODEL_CONFIDENCE",
                                f"extraction_method {candidate.extraction_method!r} names a model "
                                f"but supplied no confidence",
                            ),
                        ),
                    )
                )
                continue
            confidence = candidate.confidence if candidate.confidence is not None else 1.0

            before_graph = build_trust_graph(pool)

            observation = make_observation(
                record_ids=(record.id,),
                extraction_method=candidate.extraction_method,
                content=candidate.content,
                confidence=confidence,
                extracted_at=raw_doc.retrieved_at,
            )
            admitted_observation = admit_observation(pool, observation)
            if isinstance(admitted_observation, list):
                failures.append(
                    ScoutAdmissionFailure(stage="observation", errors=tuple(admitted_observation))
                )
                continue
            pool.put_observation(observation)

            referents: List[Referent] = []
            for entity in candidate.entities:
                referent = make_referent(natural_key=entity.label, kind=entity.kind)
                admitted_referent = admit_referent(pool, referent)
                if isinstance(admitted_referent, list):
                    failures.append(
                        ScoutAdmissionFailure(stage="referent", errors=tuple(admitted_referent))
                    )
                    continue
                pool.put_referent(referent)
                referents.append(referent)

            label_to_referent_id = {r.natural_key: r.id for r in referents}

            relationships: List[ClaimedRelationship] = []
            for relation in candidate.relations:
                from_id = label_to_referent_id.get(relation.from_label)
                to_id = label_to_referent_id.get(relation.to_label)
                if from_id is None or to_id is None:
                    failures.append(
                        ScoutAdmissionFailure(
                            stage="relationship",
                            errors=(
                                AdmissionError(
                                    "ClaimedRelationship",
                                    "UNKNOWN_LABEL",
                                    f"relation references a label not extracted as an entity "
                                    f"in the same candidate: {relation!r}",
                                ),
                            ),
                        )
                    )
                    continue
                relationship = make_claimed_relationship(
                    from_referent_id=from_id,
                    to_referent_id=to_id,
                    type=relation.type,
                    observation_id=observation.id,
                    confidence=confidence,
                )
                admitted_relationship = admit_claimed_relationship(pool, relationship)
                if isinstance(admitted_relationship, list):
                    failures.append(
                        ScoutAdmissionFailure(stage="relationship", errors=tuple(admitted_relationship))
                    )
                    continue
                pool.put_claimed_relationship(relationship)
                relationships.append(relationship)

            after_graph = build_trust_graph(pool)

            referent_ids = tuple(r.id for r in referents)
            relationship_ids = tuple(r.id for r in relationships)
            observation_novelty = novelty(before_graph, referent_ids, relationship_ids)

            finding = ScoutFinding(
                source=source,
                document=document,
                record=record,
                observation=observation,
                referents=tuple(referents),
                relationships=tuple(relationships),
                connectivity=connectivity(after_graph),
                novelty=observation_novelty,
                redundancy={r.id: redundancy(pool, r.id) for r in referents},
                source_diversity={r.id: source_diversity(pool, r.id) for r in referents},
                evidence_density={r.id: evidence_density(pool, r.id) for r in referents},
                bridge_potential={rel.id: bridge_potential(before_graph, rel) for rel in relationships},
                fep_signal=compute_fep_signal(
                    observation_id=observation.id,
                    uncertainty=observation_uncertainty(observation),
                    novelty=observation_novelty,
                ),
            )
            findings.append(finding)

    return tuple(findings), tuple(failures)
