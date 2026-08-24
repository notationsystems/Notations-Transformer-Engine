"""The first DYNAMIC STATE in this pipeline. Everything from
`materials.analysis` through `materials.surrogate` (Phase 27-51) is a
pure function of an EvidencePool snapshot or of caller-supplied static
input; nothing carries state ACROSS calls. This module introduces the
smallest coherent state-transition abstraction that lets a predictive
model participate in the real experimental feedback loop:

    S_(t+1) = F(S_t, y_t)      -- update:  ModelState x Observation -> ModelState
    y_hat   = G(S_t, x)        -- predict: ModelState x ActionCandidate -> Prediction

where S_t is `ModelState`, y_t is a newly admitted `Observation` (via an
`ExperimentalResult`, Phase 44), x is an `ActionCandidate` (Phase 37),
and y_hat is `Prediction`.

STATE VARIABLES: for each (formulation, property) cell, the state holds
the full, immutable list of `Sample`s (value + observation_id) seen so
far for that cell. `predict` computes mean/variance from that list ON
DEMAND; nothing is incrementally accumulated, so there is no
floating-point-order-dependence to reason about, and the state's own
content-hash `id` (reusing `evidence.identity.content_hash`, no new
hashing system) is trivially order-independent because the canonical
hash payload sorts every sample list before hashing.

An earlier version of this module keyed cells by
`(formulation, property, comparison-context)`, reusing
`materials.analysis._comparison_context` to decide which observations
are "comparable." That was found, while writing this module's own
tests, to be wrong: `_comparison_context` retains every content key
except `property`/`value` (e.g. `unit`), while an `ActionCandidate`'s
declared `target_context` is a CRITERION context, which
`materials.decision._context_matches` treats as a SUBSET a group's
context must merely contain -- `{}` legitimately matches a group
carrying `{"unit": "MPa"}`. Comparing those two context values for
exact equality silently produced empty predictions. See `_state_key`
below for the resolution actually adopted: this reference model pools
by `(formulation, property)` alone and does not attempt condition-level
granularity.

WHY THIS IS A "REFERENCE" MODEL, NOT A MATERIALS-PHYSICS MODEL: `predict`
reports only what the model's OWN running statistics already contain --
the sample mean and (for 2+ samples) the population variance of
observations already admitted for that cell. It makes NO claim about
what a NOT-YET-PERFORMED experiment will produce. In particular, Phase
51's `SurrogateState(current_variance, expected_variance_after)` shape
is deliberately NOT reused here to express a "before/after" pair from
ONE state: computing `expected_variance_after` from a single state would
require inventing a probabilistic forecast of a future sample this
reference model has no honest basis for (`materials.experiment`/
`materials.decision` never model outcome probabilities either -- Phase
36 sec.G already concluded that gap). Instead, the "before vs after"
comparison Phase 52 sec.8 asks for is achieved exactly as literally
described there: `predict(state_t, candidate)` and `predict(state_t1,
candidate)` are two SEPARATE, honest readouts of CURRENT uncertainty at
two different times, compared by the CALLER (see
`ModelStateInformationValueModel` below and this module's own tests) --
never a single call fabricating a forecast.

PREDICTION is a first-class immutable dataclass (not an ephemeral tuple)
because it is handed across a real interface boundary
(`ModelStateInformationValueModel.estimate`) and is worth naming for
provenance -- but it carries NO id of its own: it is a pure, always-
reproducible function of `(state.id, candidate.id)`, so a second
identity system would be redundant machinery, not a missing one.

A generic `SurrogateModel` Protocol (with `predict`/`update` as
interface methods) was considered and deliberately deferred: with
exactly one reference implementation and no second one yet needing a
different `predict`/`update` shape, extracting that Protocol now would
be the same premature abstraction this project's own Phase 24-26/30
investigations ("structurally ready, not yet necessary, defer") already
established a discipline against. `predict`/`update` are plain
functions over `ModelState`; the moment a second, genuinely different
implementation is needed, that is the moment to extract the interface.

EPISTEMIC BOUNDARY: `update` NEVER mutates a `ModelState` -- it returns
a new one, exactly the "new object references its predecessor, nothing
mutates" discipline `evidence/types.py` already establishes for every
SCOUT object. A `Prediction` computed against `ModelState_t` remains
attributable to exactly that state (`Prediction.state_id`) forever,
even after `ModelState_(t+1)` exists; nothing here ever asserts that a
prediction "became true" because a later observation happened to agree
with it, and this module never writes to `EvidencePool` -- `update`
takes an already-admitted `Observation` (via `ExperimentalResult`,
Phase 44's own write boundary) as a plain input value, exactly the same
way `materials.value`/`materials.evaluation` consume already-resolved
objects without ever touching the pool themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from evidence.identity import content_hash
from evidence.types import Observation, Referent
from materials.candidates import ActionCandidate
from materials.results import ExperimentalResult
from materials.value import CandidateInformationValue


@dataclass(frozen=True)
class Sample:
    """One contribution to a state cell -- a measured value and the id
    of the `Observation` it came from. Never a prediction, never
    inferred: only ever added by `update` from a real, already-admitted
    `Observation`."""

    value: float
    observation_id: str


@dataclass(frozen=True)
class ModelState:
    """S_t. `id` is content-addressed (`evidence.identity.content_hash`
    over every cell's sorted sample list) -- deterministic,
    reproducible, independent of insertion order or PYTHONHASHSEED.
    Immutable: `update` always returns a NEW `ModelState`; this one is
    never touched again."""

    id: str
    samples: Mapping[str, Tuple[Sample, ...]]

    def __post_init__(self) -> None:
        normalized = {
            key: tuple(sorted(values, key=lambda s: (s.value, s.observation_id)))
            for key, values in self.samples.items()
        }
        object.__setattr__(self, "samples", MappingProxyType(normalized))


def _state_key(formulation_id: str, property: str) -> str:
    """Which state cell a sample belongs to -- formulation + property
    only, deliberately NOT further split by comparison context.

    An earlier version of this function keyed cells by
    (formulation, property, context) using
    `materials.analysis._comparison_context`'s own comparability rule.
    That is wrong for this reference model: `_comparison_context` keeps
    every content key except `property`/`value` (e.g. `unit`), while an
    `ActionCandidate.target_context` is the CRITERION's context, which
    `materials.decision._context_matches` treats as a SUBSET a group's
    context must contain -- `{}` (no context declared) legitimately
    matches a group carrying `{"unit": "MPa"}`. Replicating that
    subset-matching (including its own ambiguous-multiple-match case)
    inside a "reference" model would be exactly the kind of complexity
    this phase asks to keep minimal. Keying by (formulation, property)
    alone sidesteps it honestly: this reference model pools all observed
    values for a property regardless of condition, a real, documented
    simplification -- not a silent bug, and not a claim that condition
    never matters. A model that needed condition-level granularity would
    need to actually implement `materials.decision`'s subset-matching
    (or something equivalent), which is future work, not this phase's."""
    return content_hash({"formulation_id": formulation_id, "property": property})


def make_model_state(samples: Mapping[str, Tuple[Sample, ...]]) -> ModelState:
    """The only supported way to construct a `ModelState` with existing
    samples -- id is always derived from content, mirroring every
    `make_*` factory in `evidence/types.py`."""
    normalized = {
        key: tuple(sorted(values, key=lambda s: (s.value, s.observation_id)))
        for key, values in samples.items()
    }
    state_id = content_hash({
        key: [(s.value, s.observation_id) for s in normalized[key]] for key in sorted(normalized)
    })
    return ModelState(id=state_id, samples=samples)


EMPTY_MODEL_STATE = make_model_state({})


@dataclass(frozen=True)
class Prediction:
    """y_hat = G(S_t, x). `predicted_value`/`uncertainty` are `None`
    when the state holds zero/one sample(s) for this cell respectively
    (a single sample has a mean but no defined sample variance) --
    never defaulted to zero. `state_id` names exactly which `ModelState`
    produced this prediction, so it stays attributable forever, even
    after later states exist."""

    candidate_id: str
    formulation: Referent
    property: str
    context: Mapping[str, object]
    predicted_value: Optional[float]
    uncertainty: Optional[float]
    sample_count: int
    state_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", MappingProxyType(dict(self.context)))


def predict(state: ModelState, candidate: ActionCandidate) -> Prediction:
    """Deterministic, side-effect-free -- a pure function of `state` and
    `candidate`. Never touches EvidencePool/RetrievalEngine; never
    reads `candidate.action_class`, rank, or utility -- only the
    formulation/property/target_context identity needed to select the
    right state cell."""
    key = _state_key(candidate.formulation.id, candidate.property)
    samples = state.samples.get(key, ())
    n = len(samples)

    if n == 0:
        mean: Optional[float] = None
        variance: Optional[float] = None
    else:
        values = tuple(s.value for s in samples)
        mean = sum(values) / n
        variance = (sum((v - mean) ** 2 for v in values) / n) if n >= 2 else None

    return Prediction(
        candidate_id=candidate.id, formulation=candidate.formulation, property=candidate.property,
        context=candidate.target_context, predicted_value=mean, uncertainty=variance,
        sample_count=n, state_id=state.id,
    )


def update(state: ModelState, result: ExperimentalResult, observation: Observation) -> ModelState:
    """S_(t+1) = F(S_t, y_t). `result` supplies the formulation identity
    an `Observation` alone cannot (the formulation<->observation link
    lives in a `ClaimedRelationship`, external to `Observation` itself
    -- exactly the same gap `materials.results.ExperimentalResult` was
    already built to close); `observation` supplies the real,
    content-addressed id `admit_experimental_result` assigned. Both
    should describe the same measurement -- this function trusts that,
    the same way every other `materials/` layer trusts an
    already-constructed object handed to it rather than re-validating
    substrate invariants a caller is responsible for.

    Never mutates `state`; always returns a new `ModelState`."""
    value = observation.content.get("value")
    assert isinstance(value, (int, float)), f"expected a numeric Observation.content['value'], got {value!r}"
    key = _state_key(result.formulation.id, result.property)

    new_sample = Sample(value=float(value), observation_id=observation.id)
    existing = state.samples.get(key, ())
    updated_samples = dict(state.samples)
    updated_samples[key] = existing + (new_sample,)
    return make_model_state(updated_samples)


class ModelStateInformationValueModel:
    """Implements `materials.information.InformationValueModel`, bound
    to exactly ONE `ModelState` snapshot at construction -- a new
    instance is built for a new state, mirroring `ModelState`'s own
    immutability (there is no mutable "current state" this class tracks
    internally).

    Its `estimate()` reports CURRENT PREDICTIVE UNCERTAINTY (the sample
    variance `predict()` already computes) -- deliberately a different
    semantic from `materials.surrogate.SurrogateInformationValueModel`'s
    current-minus-after reduction, and that is fine: `InformationValueModel`
    is a generic seam, and different implementations may report numbers
    with different, clearly documented interpretations. Comparing this
    model's own output ACROSS two states (`ModelState_t` vs
    `ModelState_(t+1)`, i.e. two separate instances of this class) is
    exactly Phase 52 sec.8's "before vs after" demonstration -- never
    fabricated within one call."""

    def __init__(self, state: ModelState) -> None:
        self._state = state

    @property
    def name(self) -> str:
        return f"model_state:{self._state.id}"

    def estimate(self, information_value: CandidateInformationValue) -> Tuple[Optional[float], Optional[str]]:
        candidate = information_value.evaluation.candidate
        prediction = predict(self._state, candidate)
        if prediction.uncertainty is None:
            return None, (
                f"model state {self._state.id} has fewer than 2 samples for this "
                f"(formulation, property, context) cell -- sample_count={prediction.sample_count}"
            )
        return prediction.uncertainty, (
            f"current predictive uncertainty (sample variance) at model state {self._state.id}; "
            f"sample_count={prediction.sample_count}"
        )
