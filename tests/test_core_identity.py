"""Locks on the core's content identity.

THE GAP THIS CLOSES was found by another party and could only be closed
here. The acquisition channel's census observed two checkouts of this
repository, different commits, three days apart, both reporting core
version 1.0.0, with the ancestry between them undeterminable from where
it stood. It recorded the finding and said plainly that it could not act
on it -- naming which core a label refers to is this repository's act,
because this repository declares the label.

So the label gains a digest. `core@1.0.0` stays the COMPATIBILITY
statement; the digest says WHICH core. The two properties that make that
worth anything are opposite and are both pinned below:

  a change to the core surface MUST move the digest
  a change that is not a bend MUST NOT move it

A digest that moved on every commit would distinguish nothing, and one
that moved on none would distinguish nothing either.
"""

from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile

import pytest
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "architecture"))

from architecture import core_identity as ci

ROOT = pathlib.Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "architecture" / "exchange" / "core_identity.yaml"


def _core_copy(directory):
    """A tree carrying only the declared surface, so a test can move one
    file without touching the repository."""
    root = pathlib.Path(directory)
    for relative in ci.CORE_SURFACE:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    (root / "architecture").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "architecture" / "core.yaml",
                    root / "architecture" / "core.yaml")
    return root


# ------------------------------------------------ it distinguishes --


def test_a_change_to_the_core_surface_moves_the_digest():
    with tempfile.TemporaryDirectory() as directory:
        root = _core_copy(directory)
        before = ci.core_digest(root)
        target = root / "core" / "canonical" / "state.py"
        target.write_text(target.read_text() + "\n# a change to the core\n")
        assert ci.core_digest(root) != before


def test_a_change_outside_the_surface_does_not_move_the_digest():
    """Adding an invariant row, writing a doc, landing a vertical --
    none of these is a bend, and a digest that moved on them would move
    on almost every commit and stop distinguishing anything."""
    with tempfile.TemporaryDirectory() as directory:
        root = _core_copy(directory)
        before = ci.core_digest(root)
        (root / "architecture" / "invariants.yaml").write_text(
            "invariants:\n  - id: something_new\n")
        (root / "docs").mkdir()
        (root / "docs" / "NOTE.md").write_text("a phase report\n")
        vertical = root / "structures"
        vertical.mkdir()
        (vertical / "ingest.py").write_text("# a vertical extends the core\n")
        assert ci.core_digest(root) == before


def test_the_digest_covers_paths_and_not_only_contents():
    """Two files whose bodies were swapped are a different core. A
    digest over the contents alone hashes a multiset, not a schema."""
    with tempfile.TemporaryDirectory() as directory:
        root = _core_copy(directory)
        before = ci.core_digest(root)
        first = root / "core" / "canonical" / "delta.py"
        second = root / "core" / "canonical" / "validation.py"
        first_text, second_text = first.read_text(), second.read_text()
        first.write_text(second_text)
        second.write_text(first_text)
        assert ci.core_digest(root) != before


def test_the_surface_is_declared_and_a_new_neighbour_does_not_widen_it():
    """A glob would have adopted this file silently. Widening the core
    without a bend is what bend_protocol forbids by name."""
    with tempfile.TemporaryDirectory() as directory:
        root = _core_copy(directory)
        before = ci.core_digest(root)
        (root / "core" / "canonical" / "extra.py").write_text("X = 1\n")
        assert ci.core_digest(root) == before


# ------------------------------------------------------- it refuses --


def test_a_missing_surface_file_refuses_rather_than_hashing_what_is_left():
    """A digest over a surface that has moved is a digest of something
    else, and computing one anyway would be worse than failing."""
    with tempfile.TemporaryDirectory() as directory:
        root = _core_copy(directory)
        (root / "core" / "canonical" / "schema.py").unlink()
        with pytest.raises(ci.CoreIdentityError):
            ci.core_digest(root)


# ------------------------------------------- a party can act on it --


def test_verify_names_the_file_that_moved_rather_than_saying_no():
    """A difference with no address leaves the reader exactly where the
    version label left them."""
    with tempfile.TemporaryDirectory() as directory:
        root = _core_copy(directory)
        expected = ci.core_digest(root)
        assert ci.verify(expected, root)["matches"] is True

        target = root / "core" / "canonical" / "version.py"
        target.write_text(target.read_text() + "\n# moved\n")
        result = ci.verify(expected, root)
        assert result["matches"] is False
        assert result["actual"] != result["expected"]
        assert any(entry["path"].endswith("version.py") for entry in result["files"])


def test_compare_reports_exactly_the_differing_paths():
    with tempfile.TemporaryDirectory() as directory:
        root = _core_copy(directory)
        theirs = ci.file_digests(root)
        assert ci.compare(theirs, root) == ()

        target = root / "core" / "canonical" / "delta.py"
        target.write_text("# a different delta\n")
        assert ci.compare(theirs, root) == ("core/canonical/delta.py",)


def test_compare_reports_a_surface_that_gained_or_lost_a_file():
    """A surface that changed shape is a bend, and the most important
    thing to say about it is which file."""
    theirs = tuple(list(ci.file_digests(ROOT)) + [("core/canonical/new.py", "abc")])
    assert "core/canonical/new.py" in ci.compare(theirs, ROOT)


# ----------------------------------------------------- the artifact --


def test_the_artifact_is_a_fixed_point():
    sys.path.insert(0, str(ROOT / "architecture" / "exchange"))
    from canonical_yaml import canonical_bytes

    assert canonical_bytes(ci.identity_document(ROOT)) == ARTIFACT.read_bytes()


def test_the_artifact_keeps_version_and_digest_as_different_things():
    """One is a compatibility statement, the other an identity. Merging
    them is what created the gap."""
    document = yaml.safe_load(ARTIFACT.read_text())
    assert document["core_version"] == "1.0.0"
    assert document["core_digest"].startswith("sha256:")
    assert "COMPATIBILITY" in document["what_each_one_is_for"]["version"]
    assert "IDENTITY" in document["what_each_one_is_for"]["digest"]


def test_the_artifact_says_what_is_outside_the_surface_and_why():
    """So a later reader can tell `left out deliberately` from
    `forgotten`."""
    document = yaml.safe_load(ARTIFACT.read_text())
    outside = document["deliberately_outside"]
    assert "architecture/invariants.yaml" in outside
    assert "bend" in outside["structures/, materials/, evidence/, scout/, execution/"]
    for reason in outside.values():
        assert len(reason) > 30, "a reason that is not a reason"


def test_the_artifact_is_not_part_of_the_surface_it_describes():
    """A projection is not a source, and a fixed point cannot be reached
    by an artifact that feeds itself."""
    paths = {entry["path"] for entry in yaml.safe_load(ARTIFACT.read_text())["surface"]}
    assert not any(p.startswith("architecture/") for p in paths)
    assert "architecture/exchange/" in yaml.safe_load(
        ARTIFACT.read_text())["deliberately_outside"]


def test_the_artifact_credits_the_party_that_found_the_gap():
    """The observation was another party's and could not be acted on
    there. Recording that is not politeness -- it is what lets a reader
    check the finding against its source."""
    document = yaml.safe_load(ARTIFACT.read_text())
    why = document["why_a_digest_as_well_as_a_version"]
    assert "census" in why and "could not act on it" in why


def test_the_surface_matches_what_is_actually_in_the_core_package():
    """If a real core file is missing from the declared surface, the
    digest is silent about a file a bend would change. Measured against
    the tree rather than trusted."""
    actual = {p.relative_to(ROOT).as_posix()
              for p in (ROOT / "core").rglob("*.py")
              if "__pycache__" not in p.parts}
    assert actual == set(ci.CORE_SURFACE), (
        f"core package and declared surface disagree: "
        f"{actual ^ set(ci.CORE_SURFACE)}")
