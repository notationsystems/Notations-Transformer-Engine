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

STATE VARIABLES (Phase 53 resolution -- see `resolve_model_state_key`):
each cell means "evidence about `property` for `formulation` under the
experimental context a candidate/criterion explicitly declares" -- never
"all evidence about property P for formulation F regardless of
condition" (Phase 52's interim simplification, now superseded) and never
"one cell per distinct raw observation content," which would silently
promote incidental metadata (e.g. `unit`) to a predictive feature. For
each cell, the state holds the full, immutable list of `Sample`s (value
+ observation_id) seen so far. `predict` computes mean/variance from
that list ON DEMAND; nothing is incrementally accumulated, so there is
no floating-point-order-dependence to reason about, and the state's own
content-hash `id` (reusing `evidence.identity.content_hash`, no new
hashing system) is trivially order-independent because the canonical
hash payload sorts every sample list before hashing.

TWO DIFFERENT KINDS OF "CONTEXT" -- Phase 53's central finding, reached
by direct inspection of `materials.analysis`/`materials.decision`/
`materials.candidates`, not by assumption:

  EVIDENCE COMPARISON CONTEXT (`materials.analysis._comparison_context`)
  -- every `Observation`/`DerivedValue.content` key except `property`
  and the measured-value key itself, e.g. `{"unit": "MPa"}` or
  `{"temperature": 100}`. Grouped by EXACT equality
  (`materials.analysis._group_by_comparison_context`) to decide which
  raw values are safe to compute a `Disagreement` (min/max/spread)
  across. Necessarily includes incidental measurement metadata like
  `unit` alongside genuine experimental conditions like `temperature`,
  because it is derived mechanically from whatever keys a content
  mapping happens to carry -- it does not, and structurally cannot,
  distinguish the two.

  MODEL STATE CONDITIONING CONTEXT (`ActionCandidate.target_context` ==
  `EvidenceRequirement.criterion_context`, Phase 35-37) -- a caller-
  authored, deliberately curated declaration of which conditions a
  particular `Criterion` cares about, e.g. `{"temperature": 25}`. A
  caller writing a criterion about tensile strength has no reason to put
  `unit` in its `context` (a criterion asks "does the material pass
  under condition C," not "what unit was this recorded in") the same
  way `materials.decision._context_matches` already treats
  `criterion.context` as the small set of conditions that must match,
  never every content key that happens to be present.

  These overlap (both may name `temperature`) but are NOT the same
  thing, and Phase 52's bug was exactly conflating them: `predict`
  read the second (via `candidate.target_context`) while `update` read
  the first (via `_comparison_context(observation.content, "value")`),
  and comparing those two DIFFERENT representations for exact equality
  silently produced empty predictions (`{}` != `{"unit": "MPa"}`, even
  though `materials.decision`'s own subset-matching rule would call `{}`
  a match for any context).

RESOLUTION ADOPTED: `ModelState` cells are keyed by the SECOND kind --
`resolve_model_state_key(formulation_id, property, target_context)`,
where `target_context` is always `ActionCandidate.target_context`,
sourced identically on both sides of the loop (`predict` reads it
directly off the `ActionCandidate` it is given; `update` now also takes
the originating `ActionCandidate` explicitly, rather than trying to
re-derive a conditioning context from raw `Observation.content`). Using
one consistent source, compared by plain equality, sidesteps Phase 52's
mismatch WITHOUT reimplementing `materials.decision`'s subset-matching
inside this module (an earlier draft of this fix considered exactly
that, and rejected it as unnecessary complexity a "reference" model
should not need) and WITHOUT inventing a scheme to classify which
`Observation.content` keys are causal conditioning variables versus
incidental metadata (unit, instrument, etc.) -- a distinction nothing
upstream of this module records, so fabricating one here would be
exactly the invented ontology this phase's own instructions forbid.

CONSEQUENCE, verified directly by this module's tests: two candidates
for the same (formulation, property) with DIFFERENT explicitly-declared
`target_context` values (e.g. one criterion scoped to 25C, another to
100C) occupy different cells and are never pooled together. Two
candidates that both declare no context (`target_context == {}`, the
common case in this codebase's fixtures so far) share one cell
regardless of what a later observation's raw content records -- an
honest, caller-controlled coarsening (the criterion's author chose not
to distinguish by condition), not a silent bug and not a claim that
condition never matters. A caller that needs finer-grained state must
author finer-grained criteria/candidates upstream; this module has never
had, and still does not have, any basis for inferring that distinction
on its own.

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

PHASE 55 -- WHAT THIS MODEL IS, EXPLICITLY, AND WHAT IT IS NOT: it is a
deterministic empirical estimator over admitted observations -- for
each `(formulation, property, target_context)` cell, the sample mean
and (for 2+ samples) the sample variance of every value `update` has
ever added to that cell, recomputed on demand, nothing more. It is NOT
a physical model (it encodes no materials science -- see "WHY THIS IS A
REFERENCE MODEL" above), NOT a causal model (a residual computed against
its predictions, `materials.assessment.PredictionAssessment.residual`,
is documented there as carrying no causal claim), NOT a Gaussian
process, NOT a Bayesian posterior (no prior, no likelihood, no update
rule beyond appending a sample to a list), NOT a calibrated uncertainty
model (`uncertainty` is a raw sample variance, never validated against
held-out data or checked for coverage), and NOT a general surrogate
(there is exactly one implementation, and Phase 52's own investigation
deliberately deferred extracting an interface other implementations
could satisfy). Nothing in this module claims otherwise, and no field
anywhere in `ModelState`/`Prediction` implies a stronger model than this
one actually is.

STATE SUFFICIENCY (Phase 55): `predict(state, candidate)` is a pure
function of exactly its two arguments -- verified by direct inspection
of its body (reads only `state.samples`, `candidate.formulation.id`,
`candidate.property`, `candidate.target_context`, `candidate.id`) and by
this module's own tests, which prove `predict` produces bit-identical
`Prediction`s from two INDEPENDENTLY-CONSTRUCTED `ModelState`s that
merely share the same content (hence the same `.id`), and across
`PYTHONHASHSEED` values. No global variable, external mutable state,
`EvidencePool`, `RetrievalEngine`, wall-clock read, random state, or
hidden cache exists anywhere in this module for `predict` to depend on.
`ModelState.id` + `ActionCandidate.id` are therefore SUFFICIENT to
reproduce a `Prediction` exactly, with no additional context needed.

UPDATE SUFFICIENCY (Phase 55): symmetrically, `update(state, candidate,
result, observation)` is a pure function of exactly its four arguments
-- reads only `state.samples`, `candidate.id`/`.target_context`,
`result.candidate_id`/`.formulation.id`/`.property`,
`observation.content['value']`/`.id`. The same absence of hidden
dependencies holds, and this module's own tests confirm the SAME four
inputs always produce a `ModelState` with the SAME `.id`, regardless of
how the state's own internal sample-list insertion order happens to
fall out.

PREDICTION is a first-class immutable dataclass (not an ephemeral tuple)
because it is handed across a real interface boundary
(`ModelStateInformationValueModel.estimate`) and is worth naming for
provenance -- see `Prediction`'s own docstring for its exact fields and
why it carries no id of its own.

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
Phase 44's own write boundary) and the originating `ActionCandidate` as
plain input values, exactly the same way `materials.value`/
`materials.evaluation` consume already-resolved objects without ever
touching the pool themselves. `update` trusts, rather than
re-validates, that `candidate`/`result`/`observation` describe the same
measurement -- the same discipline every other `materials/` layer
already applies to caller-supplied objects -- but does assert the one
cheap, free identity check available (`candidate.id == result.candidate_id`)
since both ids are already in hand.
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


def resolve_model_state_key(formulation_id: str, property: str, target_context: Mapping[str, object]) -> str:
    """Evidence/Candidate/Context -> ModelState key -- Phase 53's
    explicit state-resolution primitive. A cell means "evidence about
    `property` for formulation `formulation_id` under the experimental
    context `target_context`."

    `target_context` must always be `ActionCandidate.target_context` (==
    `EvidenceRequirement.criterion_context`) -- a caller-curated
    declaration of which conditions matter, NEVER
    `materials.analysis._comparison_context`'s automatically-derived,
    every-remaining-content-key context (see this module's own docstring
    for why those two are different things, and why conflating them was
    Phase 52's bug). Compared by plain equality on both the `predict`
    and `update` side (both now read it from the same place, an
    `ActionCandidate`), so no subset-matching logic needs to live here.

    Deliberately takes explicit `(formulation_id, property,
    target_context)` fields rather than a single `candidate_or_observation`
    object: an `Observation` has no `target_context` of its own (only a
    raw `content` mapping mixing conditioning variables with incidental
    metadata), so accepting one polymorphically would invite exactly the
    wrong input back in through a side door. Callers extract the three
    fields from whichever object they hold (`ActionCandidate` today);
    this function itself stays a small, explicit, pure key derivation."""
    return content_hash({
        "formulation_id": formulation_id, "property": property, "target_context": dict(target_context),
    })


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
    """y_hat = G(S_t, x) -- Phase 55's clarified predictive snapshot.
    Exposes exactly the quantities the reference model's own mathematics
    supports (`predicted_value`/`uncertainty`, each `None` when the state
    holds too few samples to define them -- a single sample has a mean
    but no defined sample variance -- never defaulted to zero) plus the
    identities needed to reproduce or trace the prediction: `state_id`
    (which `ModelState` produced it, so it stays attributable forever,
    even after later states exist), `candidate_id`, and
    `model_state_key` (the exact cell -- `resolve_model_state_key(
    formulation.id, property, context)` -- this prediction was read
    from, surfaced directly rather than left for a caller to
    recompute). Deliberately carries no `confidence`/probability
    interval/calibration/likelihood/model-quality/accuracy/epistemic-
    status field: this reference model's statistics (a sample mean and,
    for 2+ samples, a population variance) do not support any of those
    claims, and none is fabricated here.

    Carries NO id of its own: `Prediction` is a pure, always-reproducible
    function of `(state.id, candidate.id)` (verified by this module's own
    tests across independently-constructed, content-equal states and
    across PYTHONHASHSEED) -- a third identity system would be
    redundant, not missing."""

    candidate_id: str
    formulation: Referent
    property: str
    context: Mapping[str, object]
    predicted_value: Optional[float]
    uncertainty: Optional[float]
    sample_count: int
    state_id: str
    model_state_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", MappingProxyType(dict(self.context)))


def predict(state: ModelState, candidate: ActionCandidate) -> Prediction:
    """Deterministic, side-effect-free -- a pure function of `state` and
    `candidate`. Never touches EvidencePool/RetrievalEngine; never
    reads `candidate.action_class`, rank, or utility -- only the
    formulation/property/target_context identity needed to select the
    right state cell."""
    key = resolve_model_state_key(candidate.formulation.id, candidate.property, candidate.target_context)
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
        sample_count=n, state_id=state.id, model_state_key=key,
    )


def update(state: ModelState, candidate: ActionCandidate, result: ExperimentalResult, observation: Observation) -> ModelState:
    """S_(t+1) = F(S_t, y_t). `candidate` is the `ActionCandidate` whose
    proposed action `result`/`observation` fulfill -- it supplies
    `target_context`, so the cell `update` writes into is resolved from
    exactly the same source `predict` reads from (see
    `resolve_model_state_key` and this module's own docstring for why
    that consistency is the actual Phase 53 fix, not a re-derivation
    from `observation.content`). `result` supplies the formulation
    identity an `Observation` alone cannot (the formulation<->observation
    link lives in a `ClaimedRelationship`, external to `Observation`
    itself -- exactly the same gap `materials.results.ExperimentalResult`
    was already built to close); `observation` supplies the real,
    content-addressed id `admit_experimental_result` assigned. All three
    should describe the same measurement -- this function trusts that,
    the same way every other `materials/` layer trusts an
    already-constructed object handed to it rather than re-validating
    substrate invariants a caller is responsible for, except for the one
    cheap identity check below.

    Never mutates `state`; always returns a new `ModelState`."""
    assert candidate.id == result.candidate_id, (
        f"candidate {candidate.id!r} does not match result.candidate_id {result.candidate_id!r} -- "
        "update() requires the ActionCandidate that this ExperimentalResult actually fulfills"
    )
    value = observation.content.get("value")
    assert isinstance(value, (int, float)), f"expected a numeric Observation.content['value'], got {value!r}"
    key = resolve_model_state_key(result.formulation.id, result.property, candidate.target_context)

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
