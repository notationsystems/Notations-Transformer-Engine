# The Derived Invariant Register

Core: **core@1.0.0** (corrected this phase). Register derived from three
bound repositories at named commits, never from a local copy.

## Divergence found (§1 INSPECT — this precedes the derivation)

The three repositories do **not** hold one `invariants.yaml`.

| repo | commit | invariants.yaml | generality probe | binds |
|---|---|---|---|---|
| STE | `d4d0c19` | 193 lines, own copy | 51 lines, own copy | ~~core@0.1~~ → core@1.0.0 |
| DAQ | `854780d` | 419 lines, **divergent** | 73 lines, **divergent** | core@1.0.0 |
| SCL | `482c336` | **absent** | **absent** | core@1.0.0 |

**The core version itself was wrong, and STE was wrong about itself.**
STE's `pyproject.toml` reads `version = "1.0.0"` / "Frozen Specification
v1.0.0". DAQ inspected that file and bound `core@1.0.0`; SCL binds
`core@1.0.0`. STE alone asserted `core@0.1` — a number invented during
the architecture-sync phase and never checked against STE's own
manifest, then enforced self-consistently by STE's own core-closure
lint. Corrected to 1.0.0. This is a **truthfulness repair to a
mislabel, not a version increment**: no invariant changed meaning, so
no bend protocol is triggered.

**Nine of eighteen shared ids disagreed on status**, not one:
`generation_depth_bounded`, `no_circular_training`,
`training_admissibility_declared`, `prediction_carries_uncertainty`,
`no_vendor_in_doctrine`, `no_self_validation`, `cross_vendor_validation`,
`agent_concurrence_is_not_corroboration`, `builder_check_lineage_recorded`.

## The three stale rows, verified at source

1. **`generation_depth_bounded` — CONFIRMED enforced in DAQ.**
   `science/lineage_depth.py`, `tests/test_lineage_depth.py`, and
   `tests/test_recursive_lineage_depth.py` (cites the id 11×), with a
   declared bound (`MAX_LINEAGE_DEPTH = 3`), a composition guard making
   depth a maximum over *both* initialization prior and every input
   stream, and the initialization-only hole planted in the suite. Meets
   the meta-test bar. Owner: DAQ. Not re-implemented here.

2. **Generality probe — CONFIRMED, divergent copy.** `recursive_computation`
   exists in DAQ's probe under a separate `computation_properties:` key,
   deliberately *not* appended to `observation_properties:` because a
   computation property is not one any source's observations can have.
   The case is closed (verdict FAIL recorded, then enforced). STE's probe
   lacks the key entirely. *Recorded honestly: my first read printed only
   `observation_properties` and reported the key absent — a truncation
   presented as a finding, which is the exact error class this phase is
   about. Caught by reading the whole file.*

3. **`SCL / CUDA — absent` — CONFIRMED wrong on the first half.** SCL has
   `python/scl/{fourier,least_squares,kalman,method_block,ste_adapter,client}.py`,
   a `native/` tree and tests. CUDA is linked (`CUDA::cufft` in
   `native/CMakeLists.txt`) but described throughout as *would use* —
   never GPU-executed. The row is split: **numerical computation
   capability exists; numerical acceleration does not.**

## What was built

`architecture/derive_register.py` + `architecture/exchange/build_invariant_register.py`
emit `invariant_register.yaml` (+ `.sha256`) through the **byte-identical
shared serializer** adopted from DAQ (`canonical_yaml.py`, digest
verified against its recorded value) — STE joins the encoding agreement
rather than writing a second emitter.

Per invariant: `owning_repository`, `contested`, and every claim's
`asserted_by` / `status` / `source_file` / `source_commit` /
`evidence` / `evidence_cites_id`. Rules enforced: an unreachable bound
repository **fails** the derivation rather than reporting a partial
count as a total; a claim of enforcement must name a file citing the id;
every claim records the commit it was read at.

**Derivation produced a finding I was not told about:** DAQ claims
`no_vendor_in_doctrine` enforced, but the cited test
(`tests/test_doctrine_generation.py`) does not cite the id — the
implementation (`epistemics/doctrine.py`) does. Enforcement is real; the
machine-checkable link from the *named test* is absent. DAQ's to close.

## Defect found by running: a projection re-read as a source

The emitted register lives under `architecture/` and carries its own
`invariants:` key, so it was ingested by **two** scans: its own
derivation (count 51 → would double; every real status reported
`unstated`) and the core-closure lint (which demanded an `extends:` a
projection cannot honestly carry — the register spans repositories that
may bind different cores). Both now exclude the `exchange/` surface, and
the defect *class* is locked by test so a third surface cannot reacquire
it. Note the timing: the first build was clean because the artifact did
not yet exist — the contamination would have struck on the **next** run.

## Ingest probe: reachability first, and it failed

Run before any rate was interpreted (`scripts/ingest_reachability_probe.py`),
planting one violation per gate through the **adapter** — the same door
a live document uses:

| gate | result |
|---|---|
| `no_context_free_property` | **UNREACHED** — planted violation admitted |
| `quantity_is_typed` | **UNREACHED** — planted violation admitted |
| `class_assigned_at_ingest` | **MALFORMED plant** — reported, never counted as a hole |

**0/3 gates proven reached.** STE's chemistry gates have zero callers
outside their own module, and STE has two fixture documents, no live
corpus. A rejection rate measured now would read 0% because the probe
reaches nothing — precisely the ambiguity §4.1 forbids interpreting. The
third plant is classified MALFORMED rather than UNREACHED because no
document payload *can* produce an undeclared extraction method: the
extractor declares its own as a class constant. Claiming a hole there
would be as wrong as claiming cleanliness.

**The probe is therefore not a baseline. It is a gate that must pass
first**, and it currently fails, correctly.

## Verified

Register locks 8/8, all **mutation-verified with per-test attribution**
(6/6 mutants killed by their named test: tolerated unreachable repo,
citation check always passing, commit not recorded, contest detection
disabled, core mislabelled again, committed register gone stale). Fast
suite **1988**; chemistry vertical 12/12 with a real Nexus proof and a
real GROMACS run; crates 19 suites, `fmt` + `clippy` clean.

**Bent: zero.** Core semantics unchanged; the version correction is a
mislabel repair.
