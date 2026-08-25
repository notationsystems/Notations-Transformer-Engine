"""Conformance gates: the executable checks between canonical
architecture and everything that claims to follow it.

Four gates, all fail-closed:

  check_vertical_contract   a vertical.yaml carries the full contract
                            and pins the current core version -- an
                            unconformant vertical must not be wired
  check_core_closure        no architecture artifact silently extends a
                            different core version than the registry's
  lint_doctrine_vendor_free vendor identities never appear in doctrine
                            (generated or otherwise)
  check_doctrine_current    regenerating doctrine from canonical
                            sources reproduces the committed output
                            byte-for-byte; a non-zero diff fails

There is no CI workflow infrastructure in this repository (inspected
2026-08-25: no .github/); the test suite is the gate, and these
functions are what the tests -- and any future CI -- call.
"""

from __future__ import annotations

import pathlib
from typing import List

import yaml

ROOT = pathlib.Path(__file__).resolve().parent

REQUIRED_CONTRACT_KEYS = (
    "extends", "vertical", "extensions", "observation_types",
    "admissibility_class", "instrument_adapters", "retraction_policy",
)

#: Vendor tokens that must never appear in doctrine. Bindings and
#: adapters are where these live; doctrine expresses constraints only.
VENDOR_TOKENS = ("anthropic", "openai", "mistral", "claude", "gpt-", "sonnet", "opus")


class ConformanceError(ValueError):
    """A gate failure: the artifact must not be wired/accepted."""


def core_version() -> str:
    registry = yaml.safe_load((ROOT / "invariants.yaml").read_text())
    return f"{registry['core']['name']}@{registry['core']['version']}"


def check_vertical_contract(path: pathlib.Path) -> dict:
    """The vertical_contract gate. Returns the parsed contract, or
    refuses."""
    contract = yaml.safe_load(path.read_text())
    missing = [key for key in REQUIRED_CONTRACT_KEYS if key not in contract]
    if missing:
        raise ConformanceError(
            f"{path.name}: vertical contract is missing {missing}; an "
            f"unconformant vertical must not be wired"
        )
    expected = core_version()
    if contract["extends"] != expected:
        raise ConformanceError(
            f"{path.name}: extends {contract['extends']!r} but the core is "
            f"{expected!r}; re-run the vertical against the current core"
        )
    return contract


def check_core_closure() -> List[pathlib.Path]:
    """Every architecture artifact that declares `extends` pins the
    current core version -- a mismatch anywhere fails closed."""
    expected = core_version()
    checked = []
    for path in sorted(ROOT.rglob("*.yaml")):
        if path.name == "invariants.yaml":
            continue
        data = yaml.safe_load(path.read_text())
        declared = data.get("extends") if isinstance(data, dict) else None
        if declared is None:
            raise ConformanceError(f"{path} declares no `extends: core@<version>`")
        if declared != expected:
            raise ConformanceError(
                f"{path} extends {declared!r}; the core is {expected!r} -- a "
                f"core change requires re-running every declared vertical and probe"
            )
        checked.append(path)
    return checked


def lint_doctrine_vendor_free(text: str, where: str = "doctrine") -> None:
    """no_vendor_in_doctrine, mechanically."""
    lowered = text.lower()
    for token in VENDOR_TOKENS:
        if token in lowered:
            raise ConformanceError(
                f"{where}: vendor token {token!r} found -- vendor identities "
                f"belong in model_binding.yaml and adapters, never in doctrine"
            )


def check_doctrine_current() -> None:
    """generated_doctrine_matches_source: regenerate from canonical
    sources and require a byte-identical match with the committed
    projection. Manual edits to generated doctrine fail here."""
    from architecture.doctrine_generator import generate_doctrine

    generated = generate_doctrine()
    for name, content in generated.items():
        committed = ROOT / "generated" / "doctrine" / name
        if not committed.exists():
            raise ConformanceError(
                f"generated doctrine {name} is not committed; run the generator"
            )
        if committed.read_text() != content:
            raise ConformanceError(
                f"generated doctrine {name} differs from regeneration -- either "
                f"canonical sources changed without regenerating, or the "
                f"projection was edited by hand; both fail closed"
            )
    extras = {p.name for p in (ROOT / "generated" / "doctrine").glob("*.md")} - set(generated)
    if extras:
        raise ConformanceError(
            f"committed doctrine files with no canonical source: {sorted(extras)}"
        )
