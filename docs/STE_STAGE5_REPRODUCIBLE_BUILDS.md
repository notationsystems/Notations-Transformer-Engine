# STE Stage 5 -- Reproducible Builds: the Declaration Becomes Checkable

The question: can "I declare this ELF means X" become "X
deterministically produces this ELF, independently checkable"?
Answer, built and measured: **yes**, with the residue named precisely.

## What was actually built

`execution/build.py`: `GuestBuildRecipe` (content-addressed:
descriptor + full source manifest + toolchain identity + target + flags
+ profile + fork commit -- no timestamps, hostnames, PIDs or
occurrences), `BuildArtifact`, `make_recipe`, `build_from_recipe`
(manifest-verified staging at a canonical path, then a locked, pinned,
flag-controlled cargo build), `verify_build` (the independent-rebuild
root-of-trust operation), recipe persistence whose stored format IS the
canonical bytes, and `rebuild_all_and_write_registry` -> the generated
`execution/guest_registry.py` index plus `zk/recipes/*.recipe` (four
committed recipes) and `zk/artifacts/*.elf` (derived, gitignored).
The proving driver now refuses any ELF whose hash is not the registered
reproducible artifact for the specification's program -- and the
registration is re-derivable by rebuild, so a false one is CATCHABLE.

## Reproducibility: measured, not assumed

Guest builds were NOT naturally reproducible. Found empirically, in
order:

1. **Temporal determinism held** (same tree, fresh target dirs:
   identical ELFs).
2. **Relocation broke it**: absolute source paths embedded as
   panic-location strings (execution-kernel + sp1-zkvm entrypoint
   files). Control: `--remap-path-prefix <root>=/src`,
   `<cargo-home>=/cargo`.
3. **Still broken on the SP1 target at the symbol level and on the
   Nexus target in `.text` itself**: cargo's `-C metadata` fingerprint
   bakes path-dependency package ids (absolute paths) into symbol
   disambiguators; on riscv32 this reordered the code layout.
   Controls: `-C strip=symbols` (the zkVMs load segments, never symbol
   tables) and -- structurally -- **building from a canonical staging
   path** (`/tmp/ste-stage/<backend>-<recipe-id16>`), so the path cargo
   sees is a pure function of the recipe. Staging also makes the
   manifest real: only declared files are staged, so an undeclared
   stray source cannot influence the artifact.

After controls: byte-identical ELFs across relocated source trees on
both targets. Toolchains: succinct (rustc 1.94.0-dev) for
riscv64im-succinct-zkvm-elf; nightly-2025-05-09 for
riscv32im-unknown-none-elf; identities recorded per-recipe from
`rustc -vV` (release/commit-hash/host).

Scope honestly stated: verified across source relocations ON THIS
MACHINE. Cross-machine reproduction (different cargo registry state,
different fork checkout paths) is the designed-for case but was not
demonstrable with one machine; the staging convention and remap flags
exist for it.

## The chain that actually ran

```text
heat ExecutionSpecification
  -> BuildRecipe (nexus-heat: 2245aec9..., sp1-heat: 134673ac...)
  -> reproducible build (staged, locked, pinned)
  -> ELF identity (sp1: a14e3750..., nexus: 6b11f85e...)
  -> registry-gated driver
  -> real execution + SP1 core proof   347 s, vkey 0x003c11f7... derived
                                       from the reproducible ELF
  -> real execution + Nexus stwo proof  17 s
  -> independent verification, both
  -> ONE computation identity ae4198eb... , TWO proof identities
```

Identity sensitivity, all exercised with real rebuilds: modified kernel
source -> different recipe AND different ELF, old identity not
attributable (BuildMismatch); stored recipe vs tampered tree -> refused
at staging, before any build; false artifact claim -> caught by
rebuild; recipe identity separates descriptor / toolchain / flags /
fork commit / per-file source hashes.

## What is now independently verifiable vs still declared

A verifier holding the recipe, the sources, the claimed ELF identity
and a proof -- who does NOT trust our registration -- can now
establish: the sources match the recipe's manifests; the rebuild
converges on the claimed ELF identity; the verification key derived
from THEIR rebuilt ELF verifies the proof; hence the proof is about the
executable those sources deterministically produce.

Still declared, exactly: (1) that the pinned source SEMANTICALLY
implements the descriptor's mathematics -- now pinned to exact
reviewable source instead of an arbitrary binary, but reviewed, not
proven; (2) the verifier's own toolchain binaries match the recorded
toolchain identity (their provisioning problem); (3) the fork's source
integrity, referenced by git commit -- a content hash, independently
checkable against the upstream, not re-hashed file-by-file here.

## Impact

- **SP1 / Nexus**: `ProofBackend` unchanged -- no contract deficiency
  surfaced. Both consume registry-gated reproducible artifacts; the
  vkey / the wholesale ELF are now derived from checkable builds.
- **Morpho HDL**: the lowering target is now sharper -- Morpho lowering
  should emit a BuildRecipe (or an input encoding against a registered
  recipe), inheriting reproducibility instead of re-solving it.
- **Evidence / operations**: untouched; build identities live beside,
  never inside, evidence and operation identities.

## Remaining trust boundary and recommended Stage 6

The semantic link source->descriptor is the last declaration in the
computational chain (physical measurement remains forever outside it).
Recommended Stage 6: put the substrate to scientific WORK -- drive a
real multi-step experiment campaign (the closed loop over one of the
stage-4 workloads with proved dispatches throughout), which will
pressure-test the one seam no stage has yet exercised at scale: many
occurrences, many proofs, one evidence ledger.
