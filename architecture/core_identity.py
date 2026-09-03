"""The core, identified by its bytes rather than by its label.

WHY. `architecture/core.yaml` declares `version: 1.0.0`, and that
version moves ONLY under bend_protocol -- correctly, since a routine
release must not renumber the core. The consequence is that many
different core commits legitimately carry the same label, and a sibling
that pins `core@1.0.0` cannot tell which of them it bound.

THAT IS NOT A HYPOTHETICAL. The acquisition channel's independently
recorded census observed exactly it: two checkouts of this repository,
on different commits, three days apart, both reporting the version
string 1.0.0, with the ancestry between them undeterminable from that
machine. It recorded the finding and said plainly that it could not act
on it -- "what Phase 39 did not do, and could not, is say anything about
the OTHER parties". Naming which core a label refers to is this
repository's act, because this repository declares the label.

SO THE LABEL GAINS A DIGEST. `core@1.0.0` stays the compatibility
statement; the digest says WHICH core. A party can then check the core
it holds against the core it bound -- bytes, not trust, applied to the
version string itself, which is the one place this project had been
trusting a name.

WHAT IS HASHED, AND WHY IT IS NOT EVERYTHING. Only what a bend changes:
the core SCHEMA surface. Adding an invariant row, writing a doc, or
landing a vertical is not a bend and must not move this digest -- if it
did, the digest would move on almost every commit and would stop
distinguishing anything, which is the failure mode of a fingerprint
that covers too much.
"""

from __future__ import annotations

import hashlib
import pathlib
from typing import Dict, List, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: THE CORE SCHEMA SURFACE. These are the files whose content IS the
#: core semantics: the canonical state, its schema, its versioning, its
#: deltas, its validation, and the projection contract every downstream
#: view is a function of.
#:
#: Deliberately a DECLARED list and not a glob. A glob would silently
#: widen the core the first time somebody added a file next to these,
#: and widening the core without a bend is exactly what bend_protocol
#: forbids. Adding a path here is therefore itself a core change and
#: shows up as a moved digest.
CORE_SURFACE: Tuple[str, ...] = (
    "core/__init__.py",
    "core/canonical/__init__.py",
    "core/canonical/delta.py",
    "core/canonical/schema.py",
    "core/canonical/state.py",
    "core/canonical/validation.py",
    "core/canonical/version.py",
    "core/projection/__init__.py",
    "core/projection/project.py",
)

#: NOT hashed, and each for a stated reason -- so that a later reader
#: can tell "left out deliberately" from "forgotten".
DELIBERATELY_OUTSIDE: Dict[str, str] = {
    "architecture/invariants.yaml": (
        "invariant ROWS are added without bending; a registry that moved "
        "the core digest would move it on almost every commit"),
    "architecture/core.yaml": (
        "it declares the version this digest annotates. Hashing it would "
        "make the digest depend on the digest's own publication"),
    "architecture/exchange/": (
        "derived artifacts. A projection is not a source, and a fixed "
        "point cannot be reached by an artifact that feeds itself"),
    "structures/, materials/, evidence/, scout/, execution/": (
        "verticals and layers EXTEND the core; they never define it. A "
        "vertical that changed the core digest would mean the core had "
        "been widened to admit it, which is the thing bend_protocol "
        "forbids by name"),
}


class CoreIdentityError(RuntimeError):
    """The declared core surface does not match the tree."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digests(root: pathlib.Path = REPO_ROOT) -> Tuple[Tuple[str, str], ...]:
    """Each surface file, hashed. Sorted by path so the result does not
    depend on how the filesystem happens to enumerate."""
    missing: List[str] = []
    digests: List[Tuple[str, str]] = []
    for relative in sorted(CORE_SURFACE):
        candidate = root / relative
        if not candidate.is_file():
            missing.append(relative)
            continue
        digests.append((relative, _sha256(candidate.read_bytes())))
    if missing:
        raise CoreIdentityError(
            f"the declared core surface names files that are not here: "
            f"{missing}. A digest over a surface that has moved is a digest "
            f"of something else, and computing one anyway would be worse "
            f"than failing")
    return tuple(digests)


def core_digest(root: pathlib.Path = REPO_ROOT) -> str:
    """One digest over the whole surface.

    Over the PATH AND THE CONTENT of each file, not the content alone:
    two files whose bodies were swapped are a different core, and a
    digest that could not tell them apart would be hashing a multiset
    rather than a schema.
    """
    joined = "\n".join(f"{path}:{digest}" for path, digest in file_digests(root))
    return "sha256:" + _sha256(joined.encode("utf-8"))


def verify(expected: str, root: pathlib.Path = REPO_ROOT) -> Dict[str, object]:
    """Check the core HELD against the core BOUND.

    This is the function a binding party runs. It answers the question
    the version string cannot: not "is this core 1.0.0" -- many are --
    but "is this the 1.0.0 I bound".

    Returns the per-file comparison rather than a bare boolean, because
    a mismatch that cannot say WHICH file moved leaves the reader with
    the same problem the label left them: a difference with no address.
    """
    actual = core_digest(root)
    return {
        "matches": actual == expected,
        "expected": expected,
        "actual": actual,
        "files": [{"path": path, "sha256": digest}
                  for path, digest in file_digests(root)],
    }


def compare(other: Tuple[Tuple[str, str], ...],
            root: pathlib.Path = REPO_ROOT) -> Tuple[str, ...]:
    """Which surface files differ from another party's reading of them.

    A party holding a core that does not match can call this with its
    own file digests and be told exactly which files moved. Paths
    present on one side only are reported too -- a surface that gained
    or lost a file is a bend, and the most important thing to say about
    it is which file.
    """
    mine = dict(file_digests(root))
    theirs = dict(other)
    differing = [path for path in sorted(set(mine) | set(theirs))
                 if mine.get(path) != theirs.get(path)]
    return tuple(differing)


# --------------------------------------------------------------- emit --


def identity_document(root: pathlib.Path = REPO_ROOT) -> dict:
    import re

    core_yaml = (root / "architecture" / "core.yaml").read_text()
    match = re.search(r"^version:\s*\"?([\w.\-]+)\"?", core_yaml, re.MULTILINE)
    version = match.group(1) if match else ""

    digests = file_digests(root)
    empty = [path for path, digest in digests
             if digest == _sha256(b"")]

    return {
        "extends": f"core@{version}",
        "generated_by": "architecture/core_identity.py",
        "artifact": "core_identity",
        "owner": "STE",
        "core_version": version,
        "core_digest": core_digest(root),
        "why_a_digest_as_well_as_a_version": (
            "the version moves ONLY under bend_protocol, so many different "
            "core commits legitimately carry one label and a party pinning "
            "core@" + version + " cannot tell which of them it bound. The "
            "acquisition channel's census OBSERVED this -- two checkouts of "
            "this repository, different commits, three days apart, both "
            "reporting " + version + ", ancestry undeterminable from there. "
            "It could not act on it: naming which core a label refers to is "
            "this repository's act, because this repository declares the "
            "label"),
        "what_each_one_is_for": {
            "version": "the COMPATIBILITY statement -- what a party may rely on",
            "digest": "the IDENTITY -- which core that statement was made about",
        },
        "surface": [{"path": path, "sha256": digest} for path, digest in digests],
        "surface_is_declared_not_globbed": (
            "a glob would silently widen the core the first time a file was "
            "added beside these, and widening the core without a bend is "
            "what bend_protocol forbids. Adding a path to the surface is "
            "therefore itself a core change, and shows up as a moved digest"),
        "empty_surface_files": empty,
        "deliberately_outside": dict(DELIBERATELY_OUTSIDE),
        "how_a_party_checks_it": (
            "architecture/core_identity.py::verify(expected_digest, root) "
            "over its own copy of the core. A mismatch returns the per-file "
            "digests, so the answer is WHICH FILE moved rather than a bare "
            "no -- a difference with no address leaves the reader where the "
            "label left them"),
        "what_this_does_not_claim": (
            "that a matching digest means two parties agree about anything "
            "beyond these bytes. It is an identity, not a warrant: it says "
            "which core, and says nothing about whether that core is right"),
    }


def emit(root: pathlib.Path = REPO_ROOT) -> pathlib.Path:
    import sys as _sys
    _sys.path.insert(0, str(root / "architecture" / "exchange"))
    from canonical_yaml import canonical_bytes, canonical_sha256

    document = identity_document(root)
    out = root / "architecture" / "exchange" / "core_identity.yaml"
    out.write_bytes(canonical_bytes(document))
    (root / "architecture" / "exchange" / "core_identity.sha256").write_text(
        canonical_sha256(document) + "\n")
    return out


def main() -> int:
    import sys
    print("=== CORE IDENTITY ===")
    document = identity_document()
    print(f"  version : {document['core_version']}")
    print(f"  digest  : {document['core_digest']}")
    print(f"  surface : {len(document['surface'])} files, "
          f"{len(document['empty_surface_files'])} of them empty")
    for entry in document["surface"]:
        print(f"      {entry['path']:34} {entry['sha256'][:16]}")
    print("\n  a party pinning a version alone cannot tell WHICH core it")
    print("  bound; with the digest it can, and a mismatch names the file.")
    if "--emit" in sys.argv:
        out = emit()
        print(f"\n  wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
