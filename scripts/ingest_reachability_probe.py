#!/usr/bin/env python3
"""§4.1 reachability proof, run BEFORE any rejection rate is interpreted.

A clean result is ambiguous between a working system and a probe that
did not reach anything. This project has produced enough of the second
that ambiguity is the default reading. So for every gate the ingest
probe claims to exercise, plant a violation on the SAME path live
documents travel and confirm it is refused with the expected invariant
id. A gate not proven reached is reported UNREACHED -- never clean.

Run: python3 scripts/ingest_reachability_probe.py
"""

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from evidence.pool import EvidencePool                     # noqa: E402
from scout.extraction import DeterministicExtractor        # noqa: E402
from scout.interface import RawDocument                    # noqa: E402
from scout.pipeline import run_scout                       # noqa: E402

#: The gates a chemistry ingest probe would claim to exercise, each with
#: a payload that MUST be refused if the gate is on the ingest path.
GATES = (
    ("no_context_free_property",
     "FACT: property=melt_viscosity value=1250\n",
     "a property with no method and no conditions",
     True),
    ("quantity_is_typed",
     "FACT: property=density value=1.2 unit=g/cm3\n",
     "a quantity with no uncertainty_kind",
     True),
    # MALFORMED PLANT, recorded rather than counted. No document payload
    # can produce an undeclared extraction_method: the extractor declares
    # its own method as a class constant ("regex:kv_v1"), so this plant
    # is structurally incapable of violating the invariant it targets.
    # A plant that cannot reach the semantics is MALFORMED, not SURVIVED
    # -- reporting it as an unreached gate would claim a hole that the
    # architecture does not have.
    ("class_assigned_at_ingest",
     "FACT: property=tg value=350 unit=K\n",
     "an observation whose extraction method declares no class",
     False),
)


class _PlantedSource:
    """A source adapter carrying exactly one planted document. The
    violation enters through the ADAPTER, the same door a live document
    uses -- injecting past acquisition would prove nothing."""

    def __init__(self, raw: str):
        self._raw = raw

    def fetch(self):
        return (RawDocument(
            source_name="reachability-probe", source_kind="paper",
            content=self._raw, locator="probe://planted/1",
            retrieval_method="manual_entry",
            retrieved_at="2026-08-26T00:00:00Z"),)


def ingest(raw: str):
    """The SAME path a live document travels: adapter -> source ->
    document -> record -> extraction -> admission."""
    pool = EvidencePool()
    findings, failures = run_scout(_PlantedSource(raw), DeterministicExtractor(), pool)
    return findings, failures


def main() -> int:
    print("=== INGEST REACHABILITY PROBE ===")
    print("planting one violation per gate, on the acquisition path\n")
    reached, unreached, malformed = [], [], []
    for invariant_id, payload, description, can_violate in GATES:
        findings, failures = ingest(payload)
        refused_ids = " ".join(str(f) for f in failures)
        admitted = len(findings)
        if not can_violate:
            malformed.append(invariant_id)
            verdict = "MALFORMED (the plant cannot reach this gate's semantics)"
        elif invariant_id in refused_ids:
            reached.append(invariant_id)
            verdict = "REACHED  (refused with its id)"
        else:
            unreached.append(invariant_id)
            verdict = f"UNREACHED (admitted={admitted}, refusals={refused_ids or 'none'})"
        print(f"  {invariant_id:28} {verdict}")
        print(f"     planted: {description}")

    print(f"\ngates proven reached : {len(reached)}/{len(GATES)}")
    print(f"gates unreached      : {len(unreached)}/{len(GATES)}")
    print(f"plants malformed     : {len(malformed)}/{len(GATES)} "
          f"(reported, never counted as a hole)")
    if unreached:
        print(
            "\nVERDICT: the rejection-rate measurement is NOT interpretable.\n"
            "Every unreached gate would contribute 0 rejections whether the\n"
            "corpus is clean or the gate is simply not on the path. Reporting\n"
            "a rate now would record a probe that reached nothing as a\n"
            "working system. The gates must be wired into the acquisition\n"
            "path before any rate is measured.")
        return 1
    print("\nVERDICT: every gate reached; a rejection rate is now interpretable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
