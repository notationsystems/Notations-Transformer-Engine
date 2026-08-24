"""ActionDispatcher: the external action-dispatch seam
`docs/EXPERIMENT_ARCHITECTURE.md` §3.3 specifies -- the one and only
place a physical experiment would actually be performed. Mirrors
`scout.interface.SourceAdapter`/`Extractor` and `materials.information.
InformationValueModel` exactly: a `Protocol`, not a base class, so a
real implementation is fully substitutable and this package never
depends on which one is plugged in. No implementation shipped anywhere
in this codebase, present or future, is a live lab-automation
integration -- only deterministic, fixture/demo-oriented ones (see
`tests/test_experiment_step.py`'s own `ScriptedDispatcher`).

`dispatch` is the ONLY method: given the one `ActionCandidate` a policy
selected, produce the raw measurement obtained by actually performing
that candidate's proposed action. It is not this module's job to know
HOW that happens (a real instrument, a human transcribing a lab
notebook, a simulation) -- only that it does, deterministically enough
for the caller's own purposes, and that the result comes back in the
one shape `experiment.step.run_experiment_step` needs to build a real
`materials.results.ExperimentalResult` from.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol

from materials.candidates import ActionCandidate


@dataclass(frozen=True)
class DispatchedMeasurement:
    """What `ActionDispatcher.dispatch` hands back -- pre-identity,
    pre-pool, exactly the same "acquisition's job is acquisition, not
    identity assignment" discipline `scout.interface.RawDocument`
    already establishes for source ingestion. `content`/`record_locator`/
    `record_raw_content` are turned into a real `evidence.types.Record`
    and `materials.results.ExperimentalResult` by
    `experiment.step.run_experiment_step`, never by the dispatcher
    itself.

    `extracted_at` is required, never defaulted to a wall-clock read --
    the same "caller-supplied, never wall-clock" discipline
    `scout.interface.RawDocument.retrieved_at` already established;
    a deterministic dispatcher supplies a deterministic string."""

    content: Mapping[str, object]
    record_locator: str
    record_raw_content: str
    extracted_at: str
    extraction_method: str = "measurement:campaign_execution"

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", MappingProxyType(dict(self.content)))


class ActionDispatcher(Protocol):
    """The seam. Implementations plug in below this Protocol; nothing
    in `experiment/` depends on which one is supplied."""

    def dispatch(self, candidate: ActionCandidate) -> DispatchedMeasurement:
        """Perform the physical action `candidate` proposes and return
        the resulting raw measurement. Whether this call is fast,
        slow, synchronous, or backed by a human in the loop is entirely
        up to the implementation -- this Protocol makes no promise
        about latency, only about the shape of what comes back."""
        ...
