"""ExperimentSession: the active state reference
`docs/EXPERIMENT_ARCHITECTURE.md` §3.1 specifies. Immutable, exactly
like every object beneath it -- "maintaining the active state
reference" means the caller holds the latest `ExperimentSession`
returned by `experiment.step.run_experiment_step`; nothing here is ever
mutated in place. Advancing one step produces a NEW `ExperimentSession`,
the same way `materials.model_state.update` produces a new `ModelState`
rather than mutating the old one -- a deliberate choice, not an
oversight: introducing the first mutable object in this codebase at the
exact layer meant to DRIVE the immutable algebra beneath it would
undermine every determinism guarantee Phases 52-61 already proved.

`state_history` is the raw, ordered tuple of every `ModelState` this
session has passed through (starting with `initial_state`, most
commonly `materials.model_state.EMPTY_MODEL_STATE`) -- a
`materials.trajectory.ModelStateTrajectory` is deliberately NOT stored
here (it would be a derived quantity duplicated alongside its own
source, exactly what Phase 55 already established `ModelState` itself
must never do with mean/variance); a caller who wants one calls
`materials.trajectory.make_model_state_trajectory(session.state_history)`
directly -- see `trajectory_of` below, a one-line convenience, not new
math.

Never touches `EvidencePool` beyond holding a reference to it -- this
module itself calls no `put_*`/`admit_*`; that boundary is enforced by
`tests/test_experiment_boundaries.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from evidence.pool import EvidencePool
from materials.iteration import MaterialsIteration
from materials.model_state import EMPTY_MODEL_STATE, ModelState
from materials.trajectory import ModelStateTrajectory, make_model_state_trajectory
from retrieval.engine import RetrievalEngine


@dataclass(frozen=True)
class ExperimentSession:
    """S_t plus everything needed to compute the next step -- an
    `EvidencePool`/`RetrievalEngine` pair (read-only from this
    package's own perspective), the current `MaterialsIteration` (the
    engineering assessment this session's decisions are being made
    against), the current `ModelState`, `state_history` (every state
    this session has passed through, in order, starting with whatever
    `initial_state` `make_experiment_session` was given), and
    `document_id` -- an ALREADY-ADMITTED `evidence.types.Document` every
    measurement this session dispatches gets logged against as a new
    `Record` (one lab notebook, many entries -- the caller is
    responsible for having already admitted the Source/Document chain,
    exactly the same discipline `materials.results.ExperimentalResult`
    already established in Phase 44 for its own `record_id`)."""

    pool: EvidencePool
    engine: RetrievalEngine
    iteration: MaterialsIteration
    state: ModelState
    state_history: Tuple[ModelState, ...]
    document_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_history", tuple(self.state_history))


def make_experiment_session(
    pool: EvidencePool,
    engine: RetrievalEngine,
    iteration: MaterialsIteration,
    document_id: str,
    initial_state: ModelState = EMPTY_MODEL_STATE,
) -> ExperimentSession:
    """The only supported way to construct a starting `ExperimentSession`
    -- `state_history` always begins as exactly `(initial_state,)`.
    `document_id` must already be admitted in `pool` (this function does
    not check -- the same caller-responsibility discipline
    `materials.results.admit_experimental_result` already applies to
    `result.record_id`)."""
    return ExperimentSession(
        pool=pool, engine=engine, iteration=iteration, state=initial_state,
        state_history=(initial_state,), document_id=document_id,
    )


def trajectory_of(session: ExperimentSession) -> ModelStateTrajectory:
    """Convenience composition, not new math: `materials.trajectory.
    make_model_state_trajectory` applied to this session's own
    `state_history`. Reused rather than re-derived every time a caller
    wants trajectory-level analysis (`materials.trajectory.
    prediction_evolution`, `materials.diagnostics.diagnose_transitions`)
    over a session's history so far."""
    return make_model_state_trajectory(session.state_history)
