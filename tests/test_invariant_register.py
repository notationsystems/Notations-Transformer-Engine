"""Derived-register locks: the register is a projection of every bound
repository, and a stale projection is a FAILED derivation.

The defect these exist to catch actually occurred: the systems report
at d4d0c19 stated `generation_depth_bounded: identified` while the
acquisition layer had closed it, and eight further shared invariants
disagreed. No local check caught it, because every local check verifies
an artifact against itself.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from architecture.derive_register import (
    BOUND_REPOSITORIES,
    DerivationError,
    derive,
    register_document,
)
from architecture.exchange.canonical_yaml import canonical_bytes, canonical_sha256

REPO = pathlib.Path(__file__).resolve().parent.parent
EXCHANGE = REPO / "architecture" / "exchange"
PEERS_PRESENT = all(root.is_dir() for _, root in BOUND_REPOSITORIES)
peers_only = pytest.mark.skipif(
    not PEERS_PRESENT,
    reason="bound peer repositories not cloned here; environment gap, not an "
           "architectural pass -- the derivation itself fails closed on them",
)


# -- the fail-closed contract (always runs, no peers needed) -----------------------------------------


def test_unreachable_bound_repository_fails_the_derivation():
    """A partial count is not a total. A bound repository that cannot be
    read fails the derivation rather than quietly shrinking it."""
    bogus = (("STE", REPO), ("GHOST", pathlib.Path("/nonexistent/repo")))
    with pytest.raises(DerivationError, match="unreachable"):
        derive(bogus)


def test_enforced_claims_must_cite_their_own_id(tmp_path):
    """The meta-test bar, applied across repositories: a claim of
    enforcement must name a file that CITES the invariant id. A cited
    file that never mentions it is not evidence for it."""
    fake = tmp_path / "repo"
    (fake / "architecture").mkdir(parents=True)
    (fake / "tests").mkdir()
    (fake / "tests" / "cites.py").write_text("# covers widget_is_bounded\n")
    (fake / "tests" / "silent.py").write_text("# covers something else\n")
    (fake / "architecture" / "invariants.yaml").write_text(
        "invariants:\n"
        "  - id: widget_is_bounded\n    status: enforced\n"
        "    enforcement: tests/cites.py\n"
        "  - id: gadget_is_bounded\n    status: enforced\n"
        "    enforcement: tests/silent.py\n"
    )
    subprocess.run(["git", "init", "-q", str(fake)], check=True)
    subprocess.run(["git", "-C", str(fake), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(fake), "-c", "user.email=t@t", "-c",
                    "user.name=t", "commit", "-qm", "x"], check=True)

    records = derive((("FAKE", fake),)).records
    assert records["widget_is_bounded"][0].evidence_cites_id is True
    assert records["gadget_is_bounded"][0].evidence_cites_id is False, (
        "a cited file that never names the id must not pass as evidence")


def test_every_derived_record_carries_the_commit_it_was_read_at():
    derivation = derive((("STE", REPO),))
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    assert derivation.commits["STE"] == head
    for claims in derivation.records.values():
        for claim in claims:
            assert claim.source_commit == head, "staleness is recorded per claim"


# -- the core-version mislabel this phase corrected --------------------------------------------------


def test_declared_core_version_matches_this_repository_s_own_pyproject():
    """STE alone asserted core@0.1 -- about ITSELF -- while its own
    pyproject read 1.0.0 and both peers had bound core@1.0.0 by
    inspecting that same file."""
    declared = yaml.safe_load((REPO / "architecture" / "invariants.yaml").read_text())
    pyproject = (REPO / "pyproject.toml").read_text()
    version = next(line.split("=")[1].strip().strip('"')
                   for line in pyproject.splitlines() if line.startswith("version"))
    assert declared["core"]["version"] == version


# -- the cross-repo derivation itself ----------------------------------------------------------------


@peers_only
def test_register_is_current_against_every_bound_repository():
    """The anti-staleness gate: re-derive and compare. This is the check
    whose absence let the systems report go stale."""
    document = register_document(derive())
    committed = (EXCHANGE / "invariant_register.yaml").read_bytes()
    assert committed == canonical_bytes(document), (
        "committed register differs from re-derivation -- a derivation "
        "against a stale commit is a failed derivation")
    assert (EXCHANGE / "invariant_register.sha256").read_text().strip() == \
        canonical_sha256(document)


@peers_only
def test_contested_invariants_are_surfaced_not_averaged():
    """An id two repositories assert different statuses for is the
    register's real finding. It is reported as contested, never resolved
    silently to whichever copy was read last."""
    derivation = derive()
    contested = derivation.contested
    assert "generation_depth_bounded" in contested, (
        "the row that started this phase must be visible as contested")
    statuses = {c.asserted_by: c.status for c in contested["generation_depth_bounded"]}
    assert statuses["DAQ"] == "enforced" and statuses["STE"] == "identified"
    # the owner is the repository that actually enforces it
    document = register_document(derivation)
    entry = next(i for i in document["invariants"]
                 if i["id"] == "generation_depth_bounded")
    assert entry["owning_repository"] == "DAQ"
    assert entry["contested"] is True


@peers_only
def test_no_repository_reports_a_status_for_an_invariant_it_does_not_own():
    """Every claim in the register names the repository that made it and
    the file it was read from -- so a status can always be traced to a
    source rather than to the register's own reading."""
    document = register_document(derive())
    for entry in document["invariants"]:
        for claim in entry["claims"]:
            assert claim["asserted_by"] and claim["source_file"]
            assert len(claim["source_commit"]) == 40


def test_emitted_projections_are_never_read_as_canonical_sources():
    """The same defect appeared on two surfaces this phase: the derived
    register lives under architecture/ and was picked up BOTH by its own
    derivation (doubling the count, every status `unstated`) and by the
    core-closure lint (which demanded an `extends` a projection cannot
    honestly carry). Both excluded exchange/; this pins the rule so a
    third surface cannot reacquire it."""
    from architecture.conformance import check_core_closure
    from architecture.derive_register import derive

    register = EXCHANGE / "invariant_register.yaml"
    assert register.exists(), "the projection under test must be present"

    # the derivation does not read its own output
    ids = derive((("STE", REPO),)).records
    document = yaml.safe_load(register.read_text())
    projection_ids = {i["id"] for i in document["invariants"]}
    canonical_ids = set(ids)
    assert len(canonical_ids) < len(projection_ids), (
        "the projection spans repositories; STE's own canonical sources "
        "must be strictly fewer -- equality means self-ingestion")

    # the core-closure lint does not demand a binding from a projection
    checked = {p.name for p in check_core_closure()}
    assert "invariant_register.yaml" not in checked
