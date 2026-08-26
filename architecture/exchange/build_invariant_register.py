#!/usr/bin/env python3
"""Emit the derived invariant register, canonicalized and digested.

The register is a PROJECTION of every bound repository's canonical
sources. It is emitted, never hand-authored -- hand-authored YAML has
nothing but agreement between it and a digest the two readers disagree
on, and this artifact's whole purpose is to be quotable outside the
project.

Usage:  python3 build_invariant_register.py [--check]
  (no flag) writes invariant_register.yaml and .sha256
  --check   re-derives and fails if the committed artifact is stale
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from architecture.derive_register import derive, register_document  # noqa: E402
from architecture.exchange.canonical_yaml import (  # noqa: E402
    canonical_bytes,
    canonical_sha256,
)

ARTIFACT = HERE / "invariant_register.yaml"
DIGEST = HERE / "invariant_register.sha256"


def build() -> tuple[bytes, str]:
    document = register_document(derive())
    return canonical_bytes(document), canonical_sha256(document)


def main(argv) -> int:
    payload, digest = build()
    if "--check" in argv:
        if not ARTIFACT.exists() or not DIGEST.exists():
            print("register artifact is not committed", file=sys.stderr)
            return 1
        if ARTIFACT.read_bytes() != payload:
            print(
                "STALE REGISTER: re-derivation differs from the committed "
                "artifact. A derivation against a stale commit is a FAILED "
                "derivation, not a successful one carrying old data.",
                file=sys.stderr,
            )
            return 1
        if DIGEST.read_text().strip() != digest:
            print("register digest does not match its content", file=sys.stderr)
            return 1
        print(f"register current: {digest}")
        return 0
    ARTIFACT.write_bytes(payload)
    DIGEST.write_text(digest + "\n")
    print(f"wrote {ARTIFACT.name} ({len(payload)} bytes)\n{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
