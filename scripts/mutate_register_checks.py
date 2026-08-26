"""Probe each register lock against the defect it claims to catch.

A check that has never failed is an untested assertion. Each mutation
below reaches executable semantics; a mutation whose diff does not is
MALFORMED, not SURVIVED, and is reported as such. Attribution is
per-test: "caught by something" is not evidence.
"""

import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
DERIVE = REPO / "architecture" / "derive_register.py"
INVARIANTS = REPO / "architecture" / "invariants.yaml"
REGISTER = REPO / "architecture" / "exchange" / "invariant_register.yaml"

MUTATIONS = [
    ("unreachable repo tolerated", DERIVE,
     lambda s: s.replace(
         'raise DerivationError(\n            f"bound repository {name} is unreachable',
         'return [], "0"*40  # MUTANT\n        raise DerivationError(\n            f"bound repository {name} is unreachable'),
     "test_unreachable_bound_repository_fails_the_derivation"),
    ("citation check always passes", DERIVE,
     lambda s: s.replace(
         "    if not evidence:\n        return False",
         "    return True  # MUTANT\n    if not evidence:\n        return False"),
     "test_enforced_claims_must_cite_their_own_id"),
    ("commit not recorded per claim", DERIVE,
     lambda s: s.replace("source_commit=commit,", 'source_commit="0"*40,  # MUTANT'),
     "test_every_derived_record_carries_the_commit_it_was_read_at"),
    ("contest detection disabled", DERIVE,
     lambda s: s.replace(
         "        return {\n            key: rs for key, rs in self.records.items()",
         "        return {}  # MUTANT\n        return {\n            key: rs for key, rs in self.records.items()"),
     "test_contested_invariants_are_surfaced_not_averaged"),
    ("core version mislabelled again", INVARIANTS,
     lambda s: s.replace('version: "1.0.0"', 'version: "0.1"', 1),
     "test_declared_core_version_matches_this_repository_s_own_pyproject"),
    ("committed register goes stale", REGISTER,
     lambda s: s.replace('"contested_count": 9', '"contested_count": 0', 1)
               if '"contested_count": 9' in s else s.replace("contested_count: 9", "contested_count: 0", 1),
     "test_register_is_current_against_every_bound_repository"),
]


def run_one(target_test):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-x",
         f"tests/test_invariant_register.py::{target_test}"],
        cwd=REPO, capture_output=True, text=True)
    return result.returncode != 0


def main():
    print("=== MUTATION VERIFICATION (per-test attribution) ===")
    verdicts = []
    for label, path, mutate, target in MUTATIONS:
        original = path.read_text()
        mutated = mutate(original)
        if mutated == original:
            print(f"  MALFORMED  {label:34} (diff reached nothing)")
            verdicts.append(("MALFORMED", label)); continue
        path.write_text(mutated)
        try:
            caught = run_one(target)
        finally:
            path.write_text(original)
        status = "KILLED" if caught else "SURVIVED"
        print(f"  {status:10} {label:34} -> {target}")
        verdicts.append((status, label))
    bad = [v for v in verdicts if v[0] != "KILLED"]
    print(f"\n{len(verdicts)-len(bad)}/{len(verdicts)} mutants killed by their named test")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
