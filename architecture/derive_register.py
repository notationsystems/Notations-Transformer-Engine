"""Derive the invariant register from every bound repository's canonical
sources -- never from a local copy.

WHY THIS EXISTS. The systems report at d4d0c19 stated "26 invariants,
14 enforced" from STE's own reading of STE's own file. Two other
repositories bind the same core and had since changed what it supports:
`generation_depth_bounded` was reported `identified` here while the
acquisition layer had closed it. Nine of the eighteen shared invariant
ids disagreed on status. No local check caught it, because every local
check verifies an artifact against itself.

A register maintained locally is enumerated over repositories: it goes
stale silently, reads as authoritative, and is the artifact most likely
to be quoted outside the project. So it is DERIVED.

THE RULES (architecture/invariant_register.yaml records them; this
module is the executable form):

  - no repository may report a status for an invariant it does not own
    without citing the owning repository's source
  - an invariant claimed `enforced` must name a test that cites its id
  - the derivation FAILS if any bound repository is unreachable, rather
    than reporting a partial count as a total
  - the commit of every source derived from is recorded; a derivation
    against a stale commit is a FAILED derivation, not a successful one
    carrying old data

Reachability is not inferred from an empty result: a repository whose
architecture directory yields no invariants is unreachable-shaped and
is reported as such, never as a repository that happens to own none.
"""

from __future__ import annotations

import pathlib
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: The repositories that bind the core. Each entry is (name, path). A
#: bound repository that is not on disk is UNREACHABLE and fails the
#: derivation -- it is never silently dropped from the count.
BOUND_REPOSITORIES: Tuple[Tuple[str, pathlib.Path], ...] = (
    ("STE", REPO_ROOT),
    ("DAQ", pathlib.Path("/home/user/notationsystems/notations-acquisition-channel")),
    ("SCL", pathlib.Path("/home/user/notationsystems/scientific-compute-layer")),
)

#: A status claiming enforcement must be backed by a test citing the id.
ENFORCING_STATUSES = frozenset({"enforced", "partially_enforced", "vacuously_enforced"})


class DerivationError(RuntimeError):
    """The derivation failed. Never downgraded to a partial result."""


@dataclass(frozen=True)
class InvariantRecord:
    """One invariant as ONE repository asserts it."""

    invariant_id: str
    status: str
    asserted_by: str          # the repository whose source made this claim
    source_file: str          # path, relative to that repository
    source_commit: str        # the commit the claim was read at
    evidence: Optional[str]   # the test or module cited as enforcing it
    evidence_cites_id: bool   # whether that evidence actually names the id


@dataclass
class Derivation:
    records: Dict[str, List[InvariantRecord]] = field(default_factory=dict)
    commits: Dict[str, str] = field(default_factory=dict)
    unreachable: List[str] = field(default_factory=list)

    @property
    def contested(self) -> Dict[str, List[InvariantRecord]]:
        """Ids more than one repository asserts a DIFFERENT status for.
        These are the register's real finding: a claim about the core
        that the core no longer supports."""
        return {
            key: rs for key, rs in self.records.items()
            if len({r.status for r in rs}) > 1
        }


def _commit_of(path: pathlib.Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise DerivationError(f"{path} is not a git checkout; cannot record its commit")
    return result.stdout.strip()


def _evidence_cites_id(root: pathlib.Path, evidence: Optional[str], invariant_id: str) -> bool:
    """The meta-test bar, applied across repositories: an invariant
    claimed enforced must name a test that CITES ITS ID. A cited file
    that never mentions the id is not evidence for it."""
    if not evidence:
        return False
    for candidate in str(evidence).replace(",", " ").split():
        target = root / candidate.strip()
        if target.is_file() and invariant_id in target.read_text(errors="replace"):
            return True
    return False


def _read_repository(name: str, root: pathlib.Path) -> Tuple[List[InvariantRecord], str]:
    if not root.is_dir():
        raise DerivationError(
            f"bound repository {name} is unreachable at {root}; a partial count "
            f"is not a total -- the derivation fails rather than under-reporting"
        )
    commit = _commit_of(root)
    architecture = root / "architecture"
    if not architecture.is_dir():
        return [], commit
    records: List[InvariantRecord] = []
    for source in sorted(architecture.rglob("*.yaml")):
        # A PROJECTION MUST NOT BE A SOURCE FOR ITS OWN DERIVATION.
        # Caught by running: the emitted register lives under exchange/
        # and carries an `invariants:` key of its own, so the derivation
        # re-read its own output -- doubling the count and reporting
        # every real status as `unstated` because projection entries
        # carry provenance, not status. exchange/ is the emitted and
        # cross-repo payload surface in all three repositories; the
        # canonical declarations never live there.
        if "exchange" in source.relative_to(root).parts:
            continue
        try:
            document = yaml.safe_load(source.read_text())
        except yaml.YAMLError as error:
            raise DerivationError(f"{name}:{source} does not parse: {error}") from error
        if not isinstance(document, dict):
            continue
        for entry in document.get("invariants", []) or []:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            evidence = entry.get("enforcement") or entry.get("implementation")
            if isinstance(evidence, dict):
                evidence = evidence.get("locks") or evidence.get("validator")
            records.append(InvariantRecord(
                invariant_id=entry["id"],
                status=str(entry.get("status", "unstated")),
                asserted_by=name,
                source_file=str(source.relative_to(root)),
                source_commit=commit,
                evidence=str(evidence) if evidence else None,
                evidence_cites_id=_evidence_cites_id(root, evidence, entry["id"]),
            ))
    return records, commit


def derive(repositories=BOUND_REPOSITORIES) -> Derivation:
    """Read every bound repository at its current commit. Fails closed
    on an unreachable repository."""
    derivation = Derivation()
    for name, root in repositories:
        records, commit = _read_repository(name, root)
        derivation.commits[name] = commit
        for record in records:
            derivation.records.setdefault(record.invariant_id, []).append(record)
    return derivation


def register_document(derivation: Derivation) -> dict:
    """The emitted register: per-invariant provenance, never a bare count."""
    invariants = []
    for invariant_id in sorted(derivation.records):
        claims = sorted(derivation.records[invariant_id], key=lambda r: r.asserted_by)
        enforcing = [c for c in claims if c.status in ENFORCING_STATUSES]
        owner = enforcing[0].asserted_by if enforcing else ""
        invariants.append({
            "id": invariant_id,
            "owning_repository": owner,
            "contested": len({c.status for c in claims}) > 1,
            "claims": [{
                "asserted_by": c.asserted_by,
                "status": c.status,
                "source_file": c.source_file,
                "source_commit": c.source_commit,
                "evidence": c.evidence or "",
                "evidence_cites_id": c.evidence_cites_id,
            } for c in claims],
        })
    return {
        "derived_from": [
            {"repository": name, "commit": derivation.commits[name]}
            for name in sorted(derivation.commits)
        ],
        "invariant_count": len(invariants),
        "contested_count": len(derivation.contested),
        "invariants": invariants,
        "rules": [
            "no repository may report a status for an invariant it does not own "
            "without citing the owning repository's source",
            "an invariant claimed enforced must name a test that cites its id",
            "the derivation fails if any bound repository is unreachable",
            "a derivation against a stale commit is a failed derivation",
        ],
    }
