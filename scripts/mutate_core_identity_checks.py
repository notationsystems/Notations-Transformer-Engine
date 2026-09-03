#!/usr/bin/env python3
"""Probe the core identity's refusals."""

import os
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
IDENTITY = REPO / "architecture" / "core_identity.py"
ARTIFACT = REPO / "architecture" / "exchange" / "core_identity.yaml"
SUITE = "tests/test_core_identity.py"

MUTATIONS = [
    # -- it must distinguish ----------------------------------------------
    ("the digest stops covering paths, so swapped files look identical", IDENTITY,
     lambda s: s.replace('    joined = "\\n".join(f"{path}:{digest}" for path, digest in file_digests(root))',
                         '    joined = "\\n".join(d for _, d in sorted(file_digests(root), key=lambda kv: kv[1]))  # MUTANT'),
     "test_the_digest_covers_paths_and_not_only_contents"),
    ("the surface globbed, so a new neighbour widens the core", IDENTITY,
     lambda s: s.replace("    for relative in sorted(CORE_SURFACE):",
                         "    for relative in sorted(p.relative_to(root).as_posix() for p in (root / 'core').rglob('*.py') if '__pycache__' not in p.parts):  # MUTANT"),
     "test_the_surface_is_declared_and_a_new_neighbour_does_not_widen_it"),
    ("the registry pulled into the surface", IDENTITY,
     lambda s: s.replace('    "core/projection/project.py",\n)',
                         '    "core/projection/project.py",\n    "architecture/invariants.yaml",  # MUTANT\n)'),
     "test_a_change_outside_the_surface_does_not_move_the_digest"),
    ("the content ignored, so a changed core hashes the same", IDENTITY,
     lambda s: s.replace("        digests.append((relative, _sha256(candidate.read_bytes())))",
                         "        digests.append((relative, _sha256(relative.encode())))  # MUTANT"),
     "test_a_change_to_the_core_surface_moves_the_digest"),

    # -- it must refuse ----------------------------------------------------
    ("a missing surface file hashed around instead of refused", IDENTITY,
     lambda s: s.replace("    if missing:\n        raise CoreIdentityError(",
                         "    if False:  # MUTANT\n        raise CoreIdentityError("),
     "test_a_missing_surface_file_refuses_rather_than_hashing_what_is_left"),

    # -- a party must be able to act on it ---------------------------------
    ("verify returns a bare verdict with no address", IDENTITY,
     lambda s: s.replace('        "files": [{"path": path, "sha256": digest}\n'
                         "                  for path, digest in file_digests(root)],",
                         '        "files": [],  # MUTANT'),
     "test_verify_names_the_file_that_moved_rather_than_saying_no"),
    ("compare misses a path present on only one side", IDENTITY,
     lambda s: s.replace("    differing = [path for path in sorted(set(mine) | set(theirs))",
                         "    differing = [path for path in sorted(set(mine) & set(theirs))  # MUTANT"),
     "test_compare_reports_a_surface_that_gained_or_lost_a_file"),
    ("verify reports a match it did not check", IDENTITY,
     lambda s: s.replace('        "matches": actual == expected,',
                         '        "matches": True,  # MUTANT'),
     "test_verify_names_the_file_that_moved_rather_than_saying_no"),

    # -- the artifact -------------------------------------------------------
    ("version and digest collapsed into one thing", ARTIFACT,
     lambda s: s.replace("the IDENTITY -- which core that statement was made about",
                         "the version"),
     "test_the_artifact_keeps_version_and_digest_as_different_things"),
    ("a reason that is not a reason", ARTIFACT,
     lambda s: re.sub(r'"architecture/invariants.yaml": "[^"]*"',
                      '"architecture/invariants.yaml": "no"', s),
     "test_the_artifact_says_what_is_outside_the_surface_and_why"),
    ("the finding's origin quietly dropped", ARTIFACT,
     lambda s: s.replace("could not act on it", "was not worth acting on"),
     "test_the_artifact_credits_the_party_that_found_the_gap"),
]


def _compiles(path, source):
    if path.suffix in (".yaml", ".yml"):
        import yaml
        try:
            yaml.safe_load(source)
        except yaml.YAMLError as error:
            return str(error)[:120]
        return ""
    try:
        compile(source, str(path), "exec")
    except SyntaxError as error:
        return f"{error.msg} (line {error.lineno})"
    return ""


def _purge_cache(path):
    cache = path.parent / "__pycache__"
    if cache.is_dir():
        for stale in cache.glob(f"{path.stem}.*.pyc"):
            stale.unlink()


def run_one(target, path):
    _purge_cache(path)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-x", f"{SUITE}::{target}"],
        cwd=REPO, capture_output=True, text=True,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return result.returncode != 0


def main():
    print("=== MUTATION VERIFICATION: the core identity's refusals ===")
    verdicts = []
    for label, path, mutate, target in MUTATIONS:
        original = path.read_text()
        mutated = mutate(original)
        if mutated == original:
            print(f"  MALFORMED  {label:60} (diff reached nothing)")
            verdicts.append(("MALFORMED", label)); continue
        broken = _compiles(path, mutated)
        if broken:
            print(f"  MALFORMED  {label:60} (does not parse: {broken})")
            verdicts.append(("MALFORMED", label)); continue
        path.write_text(mutated)
        try:
            caught = run_one(target, path)
        finally:
            path.write_text(original)
        status = "KILLED" if caught else "SURVIVED"
        print(f"  {status:10} {label:60} -> {target}")
        verdicts.append((status, label))
    bad = [v for v in verdicts if v[0] != "KILLED"]
    print(f"\n{len(verdicts)-len(bad)}/{len(verdicts)} mutants killed by their named test")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
