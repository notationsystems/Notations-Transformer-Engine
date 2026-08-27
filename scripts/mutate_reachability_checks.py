"""Probe the reachability probe.

A probe whose job is to refuse to manufacture a measurement has to be
shown refusing. Each mutation makes it manufacture one; the named test
must catch it.
"""

import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
PROBE = REPO / "scripts" / "chemistry_reachability.py"
ARTIFACT = REPO / "architecture" / "chemistry_reachability.yaml"

MUTATIONS = [
    ("a dead gate passes as live", PROBE,
     lambda s: s.replace(
         '    return "DEAD", "the violating payload was ACCEPTED"',
         '    return "LIVE", "the violating payload was ACCEPTED"  # MUTANT'),
     "test_the_liveness_classifier_reports_a_dead_gate_as_dead"),
    ("a misaimed plant counts as a measurement", PROBE,
     lambda s: s.replace(
         '        return "MALFORMED_PLANT", f"right type, wrong refusal: {str(error)[:100]}"',
         '        return "LIVE", ""  # MUTANT'),
     "test_the_liveness_classifier_reports_a_misaimed_plant_as_malformed"),
    ("a wrong-TYPE plant counts as a measurement", PROBE,
     lambda s: s.replace(
         '        return "MALFORMED_PLANT", f"{type(error).__name__}: {str(error)[:100]}"',
         '        return "LIVE", ""  # MUTANT'),
     "test_the_liveness_classifier_reports_a_misaimed_plant_as_malformed"),
    ("the second refusal of the two-refusal guard is dropped", PROBE,
     lambda s: s.replace(
         '    Code("STRUCTURE_STRING_ONLY", "structures.substance.assert_distribution_identity",',
         '    Code("DROPPED_BY_MUTANT", "structures.substance.assert_distribution_identity",'),
     "test_both_refusals_of_the_two_refusal_guard_are_enumerated"),
    ("an unreachable verdict with no traced termination", PROBE,
     lambda s: s.replace(
         '            code.blocked_by["acquisition"] = (\n'
         '                "no module under scout/ imports structures/ at all,',
         '            code.blocked_by["acquisition"] = ""  # MUTANT\n'
         '            _unused = (\n'
         '                "no module under scout/ imports structures/ at all,'),
     "test_an_unreachable_verdict_carries_a_traced_termination"),
    ("a vacuous plant reported as a termination", PROBE,
     lambda s: s.replace(
         '        "terminated": admitted > 0 and chemistry_refusals == 0,',
         '        "terminated": chemistry_refusals == 0,  # MUTANT'),
     "test_a_plant_that_lands_nothing_is_not_counted_as_terminated"),
    ("a refused path reported as a termination", PROBE,
     lambda s: s.replace(
         '        "terminated": admitted > 0 and chemistry_refusals == 0,',
         '        "terminated": admitted > 0,  # MUTANT'),
     "test_a_plant_that_lands_nothing_is_not_counted_as_terminated"),
    ("silences reported as a clean set", ARTIFACT,
     lambda s: s.replace('"reachable_from_any_entry": 0',
                         '"reachable_from_any_entry": 20'),
     "test_the_artifact_reports_silences_as_silences_not_as_clean"),
    ("the corrections quietly dropped", ARTIFACT,
     lambda s: s.replace('"found": "a VACUOUS confirmation, on the second run"',
                         '"found": "nothing worth recording"'),
     "test_the_artifact_records_its_own_two_corrections"),
]


def run_one(target):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-x",
         f"tests/test_chemistry_reachability.py::{target}"],
        cwd=REPO, capture_output=True, text=True)
    return result.returncode != 0


def main():
    print("=== MUTATION VERIFICATION: the probe's own refusals ===")
    verdicts = []
    for label, path, mutate, target in MUTATIONS:
        original = path.read_text()
        mutated = mutate(original)
        if mutated == original:
            print(f"  MALFORMED  {label:48} (diff reached nothing)")
            verdicts.append(("MALFORMED", label)); continue
        path.write_text(mutated)
        try:
            caught = run_one(target)
        finally:
            path.write_text(original)
        status = "KILLED" if caught else "SURVIVED"
        print(f"  {status:10} {label:48} -> {target}")
        verdicts.append((status, label))
    bad = [v for v in verdicts if v[0] != "KILLED"]
    print(f"\n{len(verdicts)-len(bad)}/{len(verdicts)} mutants killed by their named test")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
