"""MaterialQuestion -> MaterialPropertyAnswer: the one supported
operation of this application layer.

Composes exactly the steps demonstrated by hand in Phase 26's workload
script -- resolve a Referent by natural key, run existing retrieval for
measured evidence, scan existing DerivedGroundings for predictions, call
the existing `ancestry_of` for each prediction's support -- into one
deterministic, side-effect-free function. Nothing here is a new SCOUT
capability: every step below was already possible with the public API
at db44142; this module only gives that composition a name and a
result shape, at the application layer, not the evidence layer.

OBSERVED / DERIVED / GROUNDING / PROVENANCE are never collapsed into a
single "value" or "truth": `MaterialPropertyAnswer` keeps `observed`
(raw `Observation`s) and `predictions` (each an unmodified `DerivedValue`
paired with its own `ProvenanceAncestry`) as separate tuples, and
computes descriptive disagreement statistics only -- min/max/spread,
never an average, a ranking, or a chosen "winner". Resolving or
adjudicating a disagreement is explicitly out of scope: nothing here
decides which measurement or prediction is correct.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from evidence.pool import EvidencePool
from evidence.provenance import ProvenanceAncestry, ancestry_of
from evidence.types import DerivedValue, Observation, Referent
from retrieval.engine import RetrievalEngine
from retrieval.query import make_retrieval_query

# The fixture shape this layer targets (Phase 26): a material/process
# Referent is connected to a shared process Referent one hop away via a
# ClaimedRelationship, so a bounded traversal must reach that second
# node for the relationship's own endpoint check to pass -- depth 0
# alone would see the seed referent only and match zero relationships.
# Not exposed as a MaterialQuestion field: no workload examined here
# needs a different depth, so none is offered speculatively.
_TRAVERSAL_DEPTH = 1


@dataclass(frozen=True)
class MaterialQuestion:
    """The smallest request shape this application layer needs --
    exactly the two things Phase 26's workload used: which entity, which
    property. Free text is deliberately not accepted here (no goal
    ontology exists to interpret it against, per the Phase 22
    investigation) -- `property` matches against the same open,
    caller-defined `content["property"]` key every Observation/
    DerivedValue.content already uses; there is no controlled
    vocabulary to validate it against, so none is invented here."""

    material_natural_key: str
    property: str


@dataclass(frozen=True)
class Disagreement:
    """A purely descriptive summary -- application interpretation, never
    computed or stored by SCOUT itself."""

    minimum: float
    maximum: float
    spread: float


@dataclass(frozen=True)
class GroundedPrediction:
    """One DerivedValue, unmodified, paired with its own provenance.
    Never merged with any other prediction's ancestry."""

    derived_value: DerivedValue
    provenance: ProvenanceAncestry


@dataclass(frozen=True)
class MaterialPropertyAnswer:
    material: Referent
    property: str
    observed: Tuple[Observation, ...]
    predictions: Tuple[GroundedPrediction, ...]
    observed_disagreement: Optional[Disagreement]
    predicted_disagreement: Optional[Disagreement]

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed", tuple(self.observed))
        object.__setattr__(self, "predictions", tuple(self.predictions))


def _resolve_referent(pool: EvidencePool, natural_key: str) -> Referent:
    """No dedicated lookup exists in EvidencePool for this (confirmed,
    Phases 24-26) -- a full scan over `all_referents()` is the existing,
    already-public way to do it. Convenience friction, not a capability
    gap: recorded here rather than added to EvidencePool."""
    matches = [r for r in pool.all_referents() if r.natural_key == natural_key]
    if not matches:
        raise KeyError(f"no Referent with natural_key {natural_key!r} in pool")
    return matches[0]


def _groundings_for(pool: EvidencePool, referent_id: str):
    """Same finding: no `derived_values_about`-style method exists.
    A full scan over `all_derived_groundings()` is the existing way."""
    return [g for g in pool.all_derived_groundings() if referent_id in g.referent_ids]


def _matches_property(content: Mapping[str, object], property_name: str) -> bool:
    return content.get("property") == property_name


def _as_float(value: object) -> float:
    """content values are an open `Mapping[str, object]` by design
    (`evidence/types.py`) -- this asserts the numeric shape this
    application layer actually requires, rather than silently coercing
    or suppressing the type check."""
    assert isinstance(value, (int, float)), f"expected a numeric content value, got {value!r}"
    return float(value)


def _disagreement(values: Tuple[float, ...]) -> Optional[Disagreement]:
    if len(values) < 2:
        return None
    return Disagreement(minimum=min(values), maximum=max(values), spread=max(values) - min(values))


def analyze(pool: EvidencePool, engine: RetrievalEngine, question: MaterialQuestion) -> MaterialPropertyAnswer:
    """Deterministic, side-effect-free: same evidence + same question
    always produces an equal `MaterialPropertyAnswer` (proven by
    `tests/test_materials_consumer.py`'s insertion-order and
    PYTHONHASHSEED tests). Calls only existing, unmodified evidence/
    retrieval public API -- no `pool.put_*`, no admission, no mutation."""
    referent = _resolve_referent(pool, question.material_natural_key)

    query = make_retrieval_query(entity_natural_keys=(question.material_natural_key,), traversal_depth=_TRAVERSAL_DEPTH)
    result = engine.retrieve(pool, query)
    observed = tuple(
        obs
        for obs in (pool.get_observation(oid) for oid in result.observation_ids)
        if _matches_property(obs.content, question.property)
    )

    predictions = tuple(
        GroundedPrediction(derived_value=dv, provenance=ancestry_of(pool, dv.id))
        for dv in (pool.get_derived_value(g.derived_value_id) for g in _groundings_for(pool, referent.id))
        if _matches_property(dv.content, question.property)
    )

    observed_values = tuple(_as_float(o.content["value"]) for o in observed)
    predicted_values = tuple(_as_float(p.derived_value.content["predicted_value"]) for p in predictions)

    return MaterialPropertyAnswer(
        material=referent,
        property=question.property,
        observed=observed,
        predictions=predictions,
        observed_disagreement=_disagreement(observed_values),
        predicted_disagreement=_disagreement(predicted_values),
    )
