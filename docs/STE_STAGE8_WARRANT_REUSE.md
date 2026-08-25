# STE Stage 8 — Warrant Reuse / Proof Artifact Cache

Stage 7 measured its own next bottleneck: routine Nexus proving was
301.8 s of the campaign's 366.8 s total proving time, and 5 of its 15
routine proofs re-proved a statement **identical** to one already
proven. A proof is a portable artifact; an identical statement can
reuse it. Stage 8 builds that reuse — under one non-negotiable rule:

> **A cached proof is NOT trusted because it is cached.**
> cache hit → retrieve bytes → backend verifier → `VerifiedExecution`.
> The cache contains **bytes, not trust**.

## What was built (the smallest superset)

| Piece | Where | Responsibility |
|---|---|---|
| `statement_key` | `campaign/warrant_cache.py` | identity of the *statement* a proof answers |
| `WarrantCache` | `campaign/warrant_cache.py` | store / lookup / explicit invalidate of proof **bytes** |
| `verify_existing_proof` | `execution/proving.py` | the verify-only gate every hit must pass — no proving anywhere in this path |
| cache-aware dispatch | `campaign/policy.py::policy_runner` | hit → mandatory re-verify; miss → prove + store; hit-invalid → recorded failure, regeneration only as an explicit decision |

Nothing else changed. `EvidencePool`, `Observation`/`ExperimentalResult`
identity, `ExecutionSpecification`, `OperationTrace`, the `ProofBackend`
contract, and `VerifiedExecution` semantics are untouched; the `crates/`
workspace gained no dependency.

## The statement key

```
commit( scout.campaign.warrant-statement.v1,
        [ backend name, sha256(guest artifact), specification identity ] )
```

- **Specification identity** covers program descriptor, configuration,
  and input — change any of them and the key changes (identity-based
  invalidation; there is no other kind except the one explicit
  `invalidate`).
- **Guest artifact hash** ties the warrant to the Stage 5 reproducible
  build actually verified — a rebuilt or different ELF is a different
  statement.
- **Backend name** isolates proof systems structurally: a Nexus proof
  can never be *retrieved* for a RISC Zero request; even if bytes were
  swapped on disk, the RISC Zero verifier would reject them. The key is
  the structural guarantee, the verifier the cryptographic one.

Deliberately **not** in the key: output and exit code (the statement is
rebuilt from the *fresh* native execution on every hit, so a cached
proof committed to a different output fails verification — it cannot
silently pass), and never occurrence numbers, timestamps, filenames,
hostnames, or PIDs. The cache deduplicates **proofs**, not
**operations** — three runs of one spec remain three trace occurrences
and one observation, now backed by one reusable warrant. This is the
Phase 121–123 two-ledger distinction applied to warrants.

Storage is deliberately minimal per the overbuild ban: one immutable
local directory per key holding `proof.bin` + `meta`; the artifact
identity is sha256 of the bytes. No TTLs, no LRU, no eviction policy,
no database, no remote store.

## Separation of concerns (unchanged from Stage 7, extended)

- the **policy** decides WHICH warrant is wanted,
- the **cache** answers WHETHER a proof artifact already exists,
- the **backend verifier** decides WHETHER that artifact verifies,
- the **evidence pool** decides WHAT counts as scientific evidence,
- the **operation trace** records WHAT actually happened, every time.

`WarrantRecord` gained one campaign-metadata field, `cache`, with
values `miss+stored` / `hit` / `hit-invalid` / `invalidated` /
`regenerated+stored` — never part of any evidence identity.

## Failure semantics

A **miss** ("no warrant") and a **hit that fails verification**
("invalid warrant") are different results and are recorded differently.
A hit-invalid is a *failed lane*: it feeds the existing deterministic
escalation and is never silently regenerated. Only
`regenerate_invalid=True` lets the policy discard the bad artifact —
via an explicit `invalidate` that itself lands on the warrant record —
and prove afresh. Corruption is an *event with a record*, never an
automatic repair that hides it.

## Empirical results (tests: `tests/test_execution_stage8_warrant_cache.py`)

All with real Nexus proofs and an **instrumented host** (a logging shim
in front of the real host binary), so "proving was skipped" is an
observed fact about which subcommands ran, not an inference:

1. **Key discrimination** — same (backend, artifact, spec) → same key;
   different backend / ELF / input / configuration / descriptor → all
   different keys.
2. **Reuse skips proving, never verification** — three identical
   campaign points: 3 occurrences, 1 observation, 1 stored artifact;
   shim log shows `prove` × 1, `verify` × 3; warrant records
   `miss+stored, hit, hit`; observation ids identical with and without
   the cache.
3. **Corruption (mandatory experiment)** — one byte flipped in the
   stored artifact: the hit still goes to the verifier, fails
   (`Malformed`), the dispatch **fails**, no `VerifiedExecution`, no
   automatic regeneration, the corrupted entry left in place, `prove`
   count unchanged. With `regenerate_invalid=True`: records
   `hit-invalid → invalidated → regenerated+stored`, and the
   replacement serves clean hits.
4. **Cross-process reuse** — a producer *process* proves and stores; a
   separate consumer *process* sharing only the cache directory hits,
   re-verifies (shim log: `verify` × 1, `prove` × 0), and gets the same
   proof identity.
5. **Backend isolation** — a warrant stored under the Nexus key is
   invisible to a RISC Zero lookup of the same spec and ELF.

## Measured campaign (`scripts/stage8_warrant_campaign.py`)

The identical campaign the Stage 7 experiment ran (9-cell sweep, 3
repeats, near-identical variant, genuine escalation, failure, retry,
rejection — 17 points), same policy identity, three arms:

<!-- STAGE8_RESULTS -->

Evidence was asserted identical across all three arms (same observation
ids on the common points; arm C's one *new* spec was a cache **miss**
that proved fresh — a changed statement is a different key).

## What this did NOT change

- Verification never became optional: every `verified` outcome in every
  arm passed a real backend verifier in that arm.
- The proof ladder's meaning is untouched — the cache changes *when a
  proof is generated*, never *what a proof means*.
- COMPUTATION ≠ MEASUREMENT stands: a reused warrant certifies the same
  computation-correctness claim the original proof did, nothing more.
