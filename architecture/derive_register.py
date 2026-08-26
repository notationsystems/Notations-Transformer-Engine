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

THREE PARTIES, AND ONE OF THEM HAS NO INVARIANT SOURCE. The compute
layer holds no `invariants.yaml` and no probe. That is not an error and
not an absence to route around: it is a BINDING MODE. A party can bind
the core by declaring `extends: core@<v>` in its own artifacts while
declaring no invariants of its own, and the derivation must be able to
say so in the register rather than contributing a silent zero that
reads identically to a party it failed to read. The two are
distinguished by evidence, never by assumption:

  invariant_registry  the party declares invariants; records derive from
                      them
  extends_only        the party declares NO invariants and demonstrates
                      its binding by `extends` declarations, which are
                      named in the register

A party with neither invariants nor `extends` declarations is not
"bound with no source" -- it is not demonstrably bound at all, and that
FAILS. Zero records is a claim requiring evidence like any other.

THE RULES (architecture/invariant_register.yaml records them; this
module is the executable form):

  - no repository may report a status for an invariant it does not own
    without citing the owning repository's source
  - an invariant claimed `enforced` must name a test that cites its id
  - the derivation FAILS if any bound repository is unreachable, rather
    than reporting a partial count as a total
  - the commit of every source derived from is recorded, and CURRENCY IS
    ESTABLISHED AGAINST THE REMOTE, not the local clone. A local commit
    proves authorship; only the remote HEAD proves the clone is current.
    Measured 2026-08-26: both sibling clones were behind their remotes at
    the moment the previous derivation recorded their local HEADs as the
    commits it derived from. The register said which commits it read and
    was still stale, because it had recorded the wrong side of the
    question.
  - a party's NAME is read from that party's own artifacts, never
    assigned by this repository. The labels below are local handles for
    the join; they are not the parties' names. The acquisition layer
    calls itself `daf` and the compute layer addresses it as `daq` --
    one party, two names, which stayed invisible in both repositories
    until something joined on the token. This derivation joins on a
    THIRD name, so it records each party's self-declaration beside the
    local label rather than asserting the label is the name.

Reachability is not inferred from an empty result: a repository whose
architecture directory yields no invariants is checked for a binding
before it is reported as a party that declares none.
"""

from __future__ import annotations

import pathlib
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: The repositories that bind the core. The string is a LOCAL LABEL used
#: to join claims, not the party's name -- see the module docstring. A
#: bound repository that is not on disk is UNREACHABLE and fails the
#: derivation; it is never silently dropped from the count.
BOUND_REPOSITORIES: Tuple[Tuple[str, pathlib.Path], ...] = (
    ("STE", REPO_ROOT),
    ("DAQ", pathlib.Path("/home/user/notationsystems/notations-acquisition-channel")),
    ("SCL", pathlib.Path("/home/user/notationsystems/scientific-compute-layer")),
)

#: A status claiming enforcement must be backed by a test citing the id.
ENFORCING_STATUSES = frozenset({"enforced", "partially_enforced", "vacuously_enforced"})

#: The two ways a party can be bound. Both are successful outcomes; they
#: differ in what the party contributes, not in whether it is bound.
INVARIANT_REGISTRY = "invariant_registry"
EXTENDS_ONLY = "extends_only"

#: A claim about the claiming repository's own state, rather than about
#: the invariant. Excluded from contests; see Derivation.contested.
LOCAL_SCOPE = "this_repository"
PROJECT_SCOPE = "project"


def _is_contested(claims) -> bool:
    """Disagreement among the claims that are ABOUT THE INVARIANT."""
    statuses = {c.status for c in claims if c.scope != LOCAL_SCOPE}
    return len(statuses) > 1


class DerivationError(RuntimeError):
    """The derivation failed. Never downgraded to a partial result."""


@dataclass(frozen=True)
class InvariantRecord:
    """One invariant as ONE repository asserts it."""

    invariant_id: str
    status: str
    asserted_by: str          # the LOCAL LABEL of the repository claiming this
    source_file: str          # path, relative to that repository
    source_commit: str        # the commit the claim was read at
    evidence: Optional[str]   # the test or module cited as enforcing it
    evidence_cites_id: bool   # whether that evidence actually names the id
    scope: str                # project | this_repository
    owner_elsewhere: Optional[str]  # the party that owns this invariant


@dataclass(frozen=True)
class RepositoryBinding:
    """How one party is bound, and what it contributed.

    `binding_mode` is the load-bearing field: it is what lets a party
    that declares no invariants be represented as such instead of as an
    absence indistinguishable from a read failure.
    """

    label: str
    binding_mode: str
    bound_core: str
    local_commit: str
    branch: str
    remote_commit: Optional[str]  # None when remotes were not checked
    currency: Optional[str]       # in_sync / local_ahead_of_remote / None
    binding_files: Tuple[str, ...]    # files declaring `extends: core@<v>`
    invariant_sources: Tuple[str, ...]
    record_count: int
    self_declared_names: Tuple[str, ...]


@dataclass
class Derivation:
    records: Dict[str, List[InvariantRecord]] = field(default_factory=dict)
    commits: Dict[str, str] = field(default_factory=dict)
    bindings: Dict[str, RepositoryBinding] = field(default_factory=dict)
    remotes_checked: bool = False

    @property
    def contested(self) -> Dict[str, List[InvariantRecord]]:
        """Ids more than one repository asserts a DIFFERENT status for AT
        THE SAME SCOPE. These are the register's real finding: a claim
        about the core that the core no longer supports.

        SCOPE IS WHAT MAKES THE FINDING MEAN ANYTHING, and the first
        derivation did not have it. Joining nine disagreeing rows on the
        id alone put three different things in one bucket: an invariant
        one party owns and another reports stale (the defect), a
        development-process rule whose state is genuinely per-repository
        and differs truthfully in each (not a defect), and a real
        disagreement about a shared claim (the defect the register is
        for). Averaging those into "nine contested" overstates two
        thirds of it.

        A claim declaring `scope: this_repository` is a statement about
        its own repository's state, so it is excluded from the contest
        entirely rather than compared against anything -- two such
        claims differing is two repositories being in different states,
        which is a fact. A contest is a disagreement among the claims
        that are ABOUT THE INVARIANT: the project-scoped ones.

        The DEFAULT is `project`. An undeclared claim is read as a claim
        about the invariant globally, so an unscoped row that disagrees
        still contests. That direction is deliberate: scope must be
        declared to be relied upon, and silence must not buy the
        exemption.

        (The first implementation grouped BY scope and flagged any group
        that disagreed, which is a different rule wearing the same
        words: two claims both scoped `this_repository` still contested.
        The planted-disagreement test found it, which is the argument
        for planting one.)
        """
        return {
            key: claims for key, claims in self.records.items()
            if _is_contested(claims)
        }

    @property
    def scoped_local(self) -> Dict[str, List[InvariantRecord]]:
        """Ids where some claim is scoped to its own repository. These
        are surfaced BECAUSE the scope declaration is what stops them
        contesting: a reader can see how much of a zero contested-count
        was reached by agreement and how much by scoping, instead of
        having to take the zero on faith."""
        return {
            key: [c for c in claims if c.scope == LOCAL_SCOPE]
            for key, claims in self.records.items()
            if any(c.scope == LOCAL_SCOPE for c in claims)
        }

    @property
    def deferrals(self) -> Dict[str, List[InvariantRecord]]:
        """Claims that name an owner elsewhere. The point of the pointer
        is that this repository never writes the owner's status down --
        it names the owner, and the register resolves the live value at
        derivation time. A copied status is the exact artifact that went
        two corrections stale while every local suite stayed green."""
        return {
            key: [c for c in claims if c.owner_elsewhere]
            for key, claims in self.records.items()
            if any(c.owner_elsewhere for c in claims)
        }

    @property
    def sourceless_parties(self) -> List[str]:
        """Parties bound with no invariant source. Surfaced as a fact of
        the derivation, so that "declares none" can never be read off
        the same silence as "was not read"."""
        return sorted(
            label for label, b in self.bindings.items()
            if b.binding_mode == EXTENDS_ONLY
        )


def _git(path: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True,
    )


def _commit_of(path: pathlib.Path) -> str:
    result = _git(path, "rev-parse", "HEAD")
    if result.returncode != 0:
        raise DerivationError(f"{path} is not a git checkout; cannot record its commit")
    return result.stdout.strip()


def _remote_head(path: pathlib.Path, branch: str) -> Optional[str]:
    """The REMOTE's head for this branch, or None if it cannot be asked.
    A local commit proves authorship; only this proves currency."""
    if not branch:
        return None
    result = _git(path, "ls-remote", "origin", f"refs/heads/{branch}")
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.strip().split("\t")[0]


def _is_origin_copy(root: pathlib.Path, document: dict) -> bool:
    """Is this party the AUTHOR of this artifact, or does it hold a
    mirror of another party's?

    Found by running, and it is the one-party-two-names defect arriving
    in this derivation rather than in the pair that first hit it. The
    compute layer holds a byte-identical mirror of the acquisition
    layer's requirement response, which carries the acquisition layer's
    `also_known_as`. Scanning for self-declarations without asking whose
    artifact it is attributed the acquisition layer's name to the
    compute layer -- one party's name reported as another's, by a
    derivation whose whole subject is not trusting one repository's
    account of another.

    Mirrors are byte-identical to their origins BY DESIGN, so content
    cannot distinguish them. What can: an emitted artifact names its
    generator, and only the origin repository holds that generator. An
    artifact naming no generator is hand-authored in place and counts as
    origin -- absent is not false.
    """
    generator = document.get("generated_by")
    if not isinstance(generator, str) or not generator:
        return True
    return (root / generator).exists()


def _currency(path: pathlib.Path, local: str, remote: str) -> Optional[str]:
    """How this clone stands against its remote, or None if it is behind.

    The question is DIRECTIONAL, and collapsing it to equality gets one
    of the two directions wrong. A clone that does not CONTAIN the
    remote head is stale: it is missing state the party has published,
    which is exactly the failure this check exists for. A clone that is
    ahead holds unpushed local commits -- for the deriving repository
    that is the normal case, because the register is emitted from the
    working tree and committed alongside the state it describes, so
    demanding equality would make it impossible to ever derive one.

    Both outcomes are recorded rather than one being silently treated as
    the other; `local_ahead_of_remote` on a SIBLING means this session
    edited another party's clone, which is visible here instead of
    passing as in-sync.
    """
    if local == remote:
        return "in_sync"
    contains = _git(path, "merge-base", "--is-ancestor", remote, local)
    return "local_ahead_of_remote" if contains.returncode == 0 else None


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


def _architecture_documents(root: pathlib.Path):
    """Every parsed architecture document, with its relative path."""
    architecture = root / "architecture"
    if not architecture.is_dir():
        return
    for source in sorted(architecture.rglob("*.yaml")):
        try:
            document = yaml.safe_load(source.read_text())
        except yaml.YAMLError as error:
            raise DerivationError(f"{source} does not parse: {error}") from error
        if isinstance(document, dict):
            yield source.relative_to(root), document


def _read_repository(label: str, root: pathlib.Path, check_remote: bool):
    if not root.is_dir():
        raise DerivationError(
            f"bound repository {label} is unreachable at {root}; a partial count "
            f"is not a total -- the derivation fails rather than under-reporting"
        )
    local_commit = _commit_of(root)
    branch = _git(root, "branch", "--show-current").stdout.strip()

    remote_commit: Optional[str] = None
    currency: Optional[str] = None
    if check_remote:
        remote_commit = _remote_head(root, branch)
        if remote_commit is None:
            raise DerivationError(
                f"{label}: cannot reach origin/{branch or '<detached>'} to establish "
                f"currency. A derivation that cannot ask the remote must not claim "
                f"the clone is current -- run with check_remotes=False to derive "
                f"from the local clone with the register recording that it did"
            )
        currency = _currency(root, local_commit, remote_commit)
        if currency is None:
            raise DerivationError(
                f"{label}: clone is at {local_commit[:12]} but origin/{branch} is at "
                f"{remote_commit[:12]}, which this clone does not contain. A "
                f"derivation against a stale commit is a FAILED derivation, not a "
                f"successful one carrying old data -- fetch first. (This is not "
                f"hypothetical: on 2026-08-26 both sibling clones were behind at the "
                f"moment a derivation recorded their local HEADs as the commits it "
                f"had derived from, and one of them moved again between the fetch "
                f"and the next derivation.)"
            )

    records: List[InvariantRecord] = []
    invariant_sources: List[str] = []
    binding_files: List[str] = []
    bound_cores = set()
    self_names: List[str] = []

    for relative, document in _architecture_documents(root):
        # A PROJECTION MUST NOT BE A SOURCE FOR ITS OWN DERIVATION.
        # Caught by running: the emitted register lives under exchange/
        # and carries an `invariants:` key of its own, so the derivation
        # re-read its own output -- doubling the count and reporting
        # every real status as `unstated` because projection entries
        # carry provenance, not status. exchange/ is the emitted and
        # cross-repo payload surface in all three repositories; the
        # canonical declarations never live there.
        #
        # The BINDING and NAME scans below are deliberately not subject
        # to this exclusion, and the difference is not an oversight. A
        # projection must not be read for what it claims about the core;
        # an artifact a party publishes IS evidence of which core that
        # party binds and of what that party calls itself. The compute
        # layer's binding evidence and the acquisition layer's
        # `also_known_as` both live under exchange/, and refusing to
        # read them there would be refusing a party's own declaration
        # about itself on the grounds of where it filed it.
        is_projection_surface = "exchange" in relative.parts

        declared = document.get("extends")
        if isinstance(declared, str) and declared.startswith("core@"):
            binding_files.append(str(relative))
            bound_cores.add(declared)
        known_as = document.get("also_known_as")
        if isinstance(known_as, str) and _is_origin_copy(root, document):
            self_names.append(known_as)

        if is_projection_surface:
            continue
        entries = document.get("invariants") or []
        if not isinstance(entries, list):
            continue
        contributed = False
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            evidence = entry.get("enforcement") or entry.get("implementation")
            if isinstance(evidence, dict):
                evidence = evidence.get("locks") or evidence.get("validator")
            owner = entry.get("owner_elsewhere")
            records.append(InvariantRecord(
                invariant_id=entry["id"],
                status=str(entry.get("status", "unstated")),
                asserted_by=label,
                source_file=str(relative),
                source_commit=local_commit,
                evidence=str(evidence) if evidence else None,
                evidence_cites_id=_evidence_cites_id(root, evidence, entry["id"]),
                scope=str(entry.get("scope", "project")),
                owner_elsewhere=str(owner) if owner else None,
            ))
            contributed = True
        if contributed:
            invariant_sources.append(str(relative))

    if len(bound_cores) > 1:
        raise DerivationError(
            f"{label} declares more than one core version {sorted(bound_cores)}; a "
            f"party binds one core, and a split binding is a bend nobody recorded"
        )
    if not records and not binding_files:
        # THE DISTINCTION THIS BRANCH EXISTS FOR. A party that declares
        # no invariants is representable (extends_only). A party that
        # declares neither invariants nor a binding is not a party with
        # no source -- there is nothing establishing it is bound at all,
        # and reporting it as a bound contributor of zero would be the
        # register asserting a binding on the party's behalf.
        raise DerivationError(
            f"{label} declares no invariants AND no `extends: core@<version>`; it "
            f"is not demonstrably bound. Zero records is a claim needing evidence "
            f"like any other -- this is not the extends_only case"
        )

    binding = RepositoryBinding(
        label=label,
        binding_mode=INVARIANT_REGISTRY if records else EXTENDS_ONLY,
        bound_core=next(iter(bound_cores)) if bound_cores else "",
        local_commit=local_commit,
        branch=branch,
        remote_commit=remote_commit,
        currency=currency,
        binding_files=tuple(binding_files),
        invariant_sources=tuple(invariant_sources),
        record_count=len(records),
        self_declared_names=tuple(sorted(set(self_names))),
    )
    return records, binding


def derive(repositories: Sequence[Tuple[str, pathlib.Path]] = BOUND_REPOSITORIES,
           check_remotes: bool = True) -> Derivation:
    """Read every bound repository at its current commit.

    Fails closed on an unreachable repository, on a party that is not
    demonstrably bound, and -- when `check_remotes` is set -- on a clone
    that is behind its remote. `check_remotes=False` derives from the
    local clones and the emitted register records that currency was NOT
    established, so an offline derivation can never be mistaken for one
    that checked.
    """
    derivation = Derivation(remotes_checked=check_remotes)
    for label, root in repositories:
        records, binding = _read_repository(label, root, check_remotes)
        derivation.commits[label] = binding.local_commit
        derivation.bindings[label] = binding
        for record in records:
            derivation.records.setdefault(record.invariant_id, []).append(record)
    _check_deferrals(derivation)
    return derivation


def _check_deferrals(derivation: Derivation) -> None:
    """A pointer to an owner is only worth more than a copied status if
    the pointer RESOLVES. An `owner_elsewhere` naming a party this
    derivation does not read is worse than no pointer at all: it reads
    as deference while deferring to nobody, and nothing would ever
    contradict it."""
    known = set(derivation.bindings)
    for invariant_id, claims in derivation.records.items():
        for claim in claims:
            if not claim.owner_elsewhere:
                continue
            if claim.owner_elsewhere not in known:
                raise DerivationError(
                    f"{claim.asserted_by}:{invariant_id} defers to "
                    f"{claim.owner_elsewhere!r}, which is not a bound party "
                    f"{sorted(known)}. A pointer to a party nobody reads is not "
                    f"deference -- it is an unfalsifiable claim wearing deference's "
                    f"shape"
                )
            if claim.scope != "this_repository":
                raise DerivationError(
                    f"{claim.asserted_by}:{invariant_id} names an owner elsewhere "
                    f"but claims scope {claim.scope!r}. A claim that defers is a "
                    f"claim about its OWN repository's state; asserting project "
                    f"scope while deferring is asserting the owner's answer and "
                    f"pointing at the owner in the same breath"
                )
            if not any(c.asserted_by == claim.owner_elsewhere
                       for c in claims):
                raise DerivationError(
                    f"{claim.asserted_by}:{invariant_id} defers to "
                    f"{claim.owner_elsewhere}, but that party asserts nothing for "
                    f"this id. The deferral would resolve to silence and read as "
                    f"settled"
                )


def register_document(derivation: Derivation) -> dict:
    """The emitted register: per-invariant provenance, never a bare count."""
    invariants = []
    for invariant_id in sorted(derivation.records):
        claims = sorted(derivation.records[invariant_id], key=lambda r: r.asserted_by)
        enforcing = [c for c in claims if c.status in ENFORCING_STATUSES]
        owner = enforcing[0].asserted_by if enforcing else ""
        entry = {
            "id": invariant_id,
            "owning_repository": owner,
            "contested": _is_contested(claims),
            "claims": [{
                "asserted_by": c.asserted_by,
                "status": c.status,
                "scope": c.scope,
                "defers_to": c.owner_elsewhere or "",
                # RESOLVED AT DERIVATION TIME, NEVER COPIED. A deferring
                # repository writes the owner's NAME; this field is
                # filled in from the owner's live source on every run,
                # so it cannot go stale the way a transcribed status
                # did while every local suite stayed green.
                "owner_status_resolved": next(
                    (o.status for o in claims if o.asserted_by == c.owner_elsewhere),
                    "") if c.owner_elsewhere else "",
                "source_file": c.source_file,
                "source_commit": c.source_commit,
                "evidence": c.evidence or "",
                "evidence_cites_id": c.evidence_cites_id,
            } for c in claims],
        }
        invariants.append(entry)
    derived_from = []
    for label in sorted(derivation.bindings):
        binding = derivation.bindings[label]
        derived_from.append({
            "repository": label,
            "label_is_a_local_handle_not_the_party_s_name": True,
            "self_declared_names": list(binding.self_declared_names),
            "binding_mode": binding.binding_mode,
            "bound_core": binding.bound_core,
            "branch": binding.branch,
            "commit": binding.local_commit,
            "remote_commit": binding.remote_commit or "",
            "currency": binding.currency or "not_checked",
            "binding_files": list(binding.binding_files),
            "invariant_sources": list(binding.invariant_sources),
            "invariants_contributed": binding.record_count,
        })
    return {
        "derived_from": derived_from,
        "currency_established_against_remotes": derivation.remotes_checked,
        "bound_parties": len(derivation.bindings),
        "parties_with_no_invariant_source": derivation.sourceless_parties,
        "invariant_count": len(invariants),
        "contested_count": len(derivation.contested),
        "deferred_count": len(derivation.deferrals),
        # HOW THE CONTESTED COUNT GOT WHERE IT IS. A bare zero cannot be
        # told apart from a detector that finds nothing, so the register
        # states how many rows carry a local-scope claim -- the rows a
        # reader should check for themselves rather than take on the
        # count's word.
        "rows_with_a_local_scope_claim": sorted(derivation.scoped_local),
        "invariants": invariants,
        "rules": [
            "no repository may report a status for an invariant it does not own "
            "without citing the owning repository's source",
            "an invariant claimed enforced must name a test that cites its id",
            "the derivation fails if any bound repository is unreachable",
            "a derivation against a stale commit is a failed derivation; currency "
            "is established against the remote head, not the local clone",
            "a party that declares no invariants is recorded as bound extends_only, "
            "with the files that bind it named; a party that declares neither "
            "invariants nor a binding fails the derivation",
            "a claim scoped to this_repository is a statement about its own "
            "repository's state; two such claims differing is a fact, not a "
            "contest. scope defaults to project, so silence never buys the "
            "exemption",
            "a repository reporting an invariant another party owns names that "
            "party and never transcribes its status; the owner's live status is "
            "resolved on every derivation, and a deferral that does not resolve "
            "fails",
            "the repository labels in this register are local handles for the join, "
            "not the parties' names; each party's own name is recorded beside its "
            "label and is never assigned by the deriving repository",
        ],
    }


#: Fields recorded at EMISSION, describing the remote check rather than
#: the sources read. A faithfulness comparison must exclude exactly these
#: and nothing more -- `commit` in particular stays in, because it is the
#: identity of what was read and is the whole point of the artifact.
CURRENCY_FIELDS = ("currency", "remote_commit")


def without_currency(document: dict) -> dict:
    """The document minus its emission-time currency record.

    Faithfulness ("the register is what derivation produces from the
    commits it names") is checkable offline and forever. Currency ("those
    commits are still the remote heads") stops being true the moment
    someone else pushes. Comparing the two together makes an honest
    artifact read as corrupt, so the comparison excludes precisely the
    fields that record the remote check -- and excluding MORE than that
    would let a real drift hide in the gap, which is why the field list
    is a constant rather than a filter written at each call site.
    """
    stripped = dict(document)
    stripped.pop("currency_established_against_remotes", None)
    stripped["derived_from"] = [
        {k: v for k, v in entry.items() if k not in CURRENCY_FIELDS}
        for entry in document.get("derived_from", [])
    ]
    return stripped
