#!/usr/bin/env python3
"""Probe the ecosystem register's refusals.

Same two guards as the sibling batteries, carried rather than
rediscovered: a mutant that does not PARSE can only be killed by an
import error, and a mutant is not identified by `(mtime, size)`.
"""

import os
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
ECO = REPO / "architecture" / "ecosystem.py"
ARTIFACT = REPO / "architecture" / "exchange" / "ecosystem_register.yaml"
DECLARATION = REPO / "architecture" / "apparatus.yaml"
SUITE = "tests/test_ecosystem_register.py"

MUTATIONS = [
    # -- org ownership is not authorship ---------------------------------
    ("the org prefix admitted as evidence of authorship", ECO,
     lambda s: s.replace(
         "    if facts.declares_core and AUTHORED_BY in facts.authors:",
         "    if facts.under_our_org or (facts.declares_core and AUTHORED_BY in facts.authors):  # MUTANT"),
     "test_our_org_alone_never_makes_something_an_apparatus"),
    ("a core declaration alone adopts a vendored repository", ECO,
     lambda s: s.replace(
         "    if facts.declares_core and AUTHORED_BY in facts.authors:",
         "    if facts.declares_core:  # MUTANT"),
     "test_a_core_declaration_without_our_authorship_is_not_an_apparatus"),
    ("the mirrored-under-our-org flag never set", ECO,
     lambda s: s.replace(
         "            mirrored_under_our_org=facts.under_our_org,\n"
         "            upstream_authors=upstream)",
         "            mirrored_under_our_org=False,  # MUTANT\n"
         "            upstream_authors=upstream)"),
     "test_our_org_alone_never_makes_something_an_apparatus"),
    ("the third verdict removed, forcing a guess", ECO,
     lambda s: s.replace(
         "    return Classification(\n        facts=facts, verdict=UNRESOLVED,",
         "    return Classification(\n        facts=facts, verdict=VENDORED_INPUT,  # MUTANT"),
     "test_a_repository_with_no_discriminating_evidence_is_unresolved"),

    # -- strong evidence only ---------------------------------------------
    ("licence boilerplate read as a copyright grant", ECO,
     lambda s: s.replace('            if not re.search(r"(19|20)\\d\\d", holder):\n                continue',
                         "            if False:  # MUTANT\n                continue"),
     "test_licence_boilerplate_is_not_read_as_a_copyright_grant"),
    ("the boilerplate phrase filter removed", ECO,
     lambda s: s.replace("            if any(phrase in holder.lower() for phrase in _BOILERPLATE):",
                         "            if False:  # MUTANT"),
     "test_licence_boilerplate_is_not_read_as_a_copyright_grant"),
    ("a squashed commit author disowns a repository again", ECO,
     lambda s: s.replace("    if strong:", "    if strong or upstream:  # MUTANT"),
     "test_a_squashed_commit_author_alone_does_not_disown_a_repository"),
    ("an unsettled repository flagged as a mirror anyway", ECO,
     lambda s: s.replace("        mirrored_under_our_org=False, upstream_authors=upstream)",
                         "        mirrored_under_our_org=facts.under_our_org, upstream_authors=upstream)  # MUTANT"),
     "test_a_squashed_commit_author_alone_does_not_disown_a_repository"),
    ("a self-declared upstream ignored", ECO,
     lambda s: s.replace("    if facts.declared_upstream:\n        strong.append(",
                         "    if False:  # MUTANT\n        strong.append("),
     "test_each_strong_signal_settles_it_on_its_own"),
    ("our own org read as an upstream", ECO,
     lambda s: s.replace('            if owner and owner.lower() != ORG:',
                         "            if owner:  # MUTANT"),
     "test_a_self_declared_upstream_inside_our_org_is_definitive"),

    # -- reconciled against an independent census -------------------------
    ("the narrower meaning of APPARATUS quietly dropped", ARTIFACT,
     lambda s: s.replace("BOUND TO THE CORE, which is narrower",
                         "ours, which is exactly what it sounds like"),
     "test_the_register_records_that_its_verdict_is_narrower_than_ownership"),
    ("the structural blind spot presented as closed", ARTIFACT,
     lambda s: s.replace("limitation rather than closed", "limitation now closed"),
     "test_the_register_records_what_it_structurally_cannot_see"),
    ("the sibling's census transcribed instead of pointed at", ARTIFACT,
     lambda s: s.replace('"not_transcribed":',
                         '"census_rows": "data_acquisition_fabric, notation_physical_commerce, network_scout_signal_miner"\n  "not_transcribed":'),
     "test_the_siblings_census_is_pointed_at_and_not_transcribed"),

    # -- the instrument is not its own evidence ---------------------------
    ("the instrument counts its own prose as a dependency", ECO,
     lambda s: s.replace("MEASURING_APPARATUS: Tuple[str, ...] = (\n"
                         '    "architecture/ecosystem.py",',
                         "MEASURING_APPARATUS: Tuple[str, ...] = (  # MUTANT"),
     "test_the_names_cited_in_the_instrument_are_reported_unreferenced"),
    ("the exclusion widened to hide a real dependency", ECO,
     lambda s: s.replace('    "docs/ECOSYSTEM_REGISTER.md",',
                         '    "docs/ECOSYSTEM_REGISTER.md",\n    "README.md",  # MUTANT'),
     "test_nothing_outside_the_instrument_is_excluded"),
    ("an excluded path that does not exist", ECO,
     lambda s: s.replace('    "docs/ECOSYSTEM_REGISTER.md",',
                         '    "docs/ECOSYSTEM_REGISTER.md",\n    "architecture/ecosystem_absent.py",  # MUTANT'),
     "test_every_excluded_path_exists"),

    # -- presence is not participation ------------------------------------
    ("prose counted as integration", ECO,
     lambda s: s.replace("        if is_load_bearing:\n            load_bearing += 1",
                         "        if True:  # MUTANT\n            load_bearing += 1"),
     "test_prose_alone_is_mentioned_not_integrated"),
    ("unreferenced inputs dropped from the artifact", ECO,
     lambda s: s.replace(
         '            for c in sorted(vendored, key=lambda c: (c.integration, c.facts.name))',
         '            for c in sorted(vendored, key=lambda c: (c.integration, c.facts.name))\n'
         '            if c.integration != UNREFERENCED  # MUTANT'),
     "test_an_unreferenced_input_is_recorded_not_omitted"),

    # -- roles are self-declared ------------------------------------------
    ("a role invented for an apparatus that declares none", ECO,
     lambda s: s.replace('        return NOT_DECLARED, ""',
                         '        return "an apparatus of the ecosystem", ""  # MUTANT'),
     "test_an_undeclared_role_is_reported_and_never_filled_in"),
    ("this apparatus stops declaring its own role", DECLARATION,
     lambda s: s.replace("role: >-", "role_disabled: >-  # MUTANT"),
     "test_this_apparatus_declares_its_own_role"),

    # -- it has to be able to run -----------------------------------------
    ("generated trees read again, and the scan stops being runnable", ECO,
     lambda s: s.replace('    "target", "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache",',
                         '    ".mypy_cache", ".pytest_cache", ".ruff_cache",  # MUTANT'),
     "test_generated_trees_are_not_read"),
    ("the file-size cap removed", ECO,
     lambda s: s.replace("                if entry.stat().st_size > MAX_FILE_BYTES:",
                         "                if False:  # MUTANT"),
     "test_a_file_larger_than_the_cap_is_not_read"),
    ("the streaming tally drifts from the corpus one", ECO,
     lambda s: s.replace("                    if is_load_bearing:\n                        load_bearing[name] += 1",
                         "                    load_bearing[name] += 1  # MUTANT"),
     "test_the_streaming_tally_keeps_prose_and_code_apart"),

    # -- the refusal ------------------------------------------------------
    ("a map emitted with no apparatus in it at all", ECO,
     lambda s: s.replace("    if not apparatuses:\n        raise EcosystemError(",
                         "    if False:  # MUTANT\n        raise EcosystemError("),
     "test_the_register_refuses_when_there_is_no_apparatus_at_all"),

    # -- the artifact -----------------------------------------------------
    ("the org finding stripped of its count", ARTIFACT,
     lambda s: re.sub(r'("org_ownership_is_not_authorship": ")\d+ of \d+',
                      r"\1some of the", s),
     "test_the_artifact_records_the_org_finding_with_its_count"),
    ("the totals stop adding up", ARTIFACT,
     lambda s: re.sub(r'("vendored_inputs": )(\d+)',
                      lambda m: m.group(1) + str(int(m.group(2)) - 2), s, count=1),
     "test_nothing_is_lost_between_the_three_verdicts"),
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
    print("=== MUTATION VERIFICATION: the ecosystem register's refusals ===")
    verdicts = []
    for label, path, mutate, target in MUTATIONS:
        original = path.read_text()
        mutated = mutate(original)
        if mutated == original:
            print(f"  MALFORMED  {label:56} (diff reached nothing)")
            verdicts.append(("MALFORMED", label)); continue
        broken = _compiles(path, mutated)
        if broken:
            print(f"  MALFORMED  {label:56} (does not parse: {broken})")
            verdicts.append(("MALFORMED", label)); continue
        path.write_text(mutated)
        try:
            caught = run_one(target, path)
        finally:
            path.write_text(original)
        status = "KILLED" if caught else "SURVIVED"
        print(f"  {status:10} {label:56} -> {target}")
        verdicts.append((status, label))
    bad = [v for v in verdicts if v[0] != "KILLED"]
    print(f"\n{len(verdicts)-len(bad)}/{len(verdicts)} mutants killed by their named test")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
