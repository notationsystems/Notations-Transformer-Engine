# The Derived Invariant Register

Core: **core@1.0.0**, now *declared* in `architecture/core.yaml`.
Register derived from three bound repositories at named commits — and,
as of this phase, at commits verified against their **remotes**.

## Order of work

The three stale rows were not patched individually. They fell out of
three structural corrections, done in this order: declare the core
version, compare the two probes, derive with three parties one of which
has no source.

---

## 1. The core version is a declaration, not an inference

The previous fix set STE's core version by reading `pyproject.toml` and
added a test asserting the two agreed. The number (1.0.0) was right and
the reasoning was wrong.

**A package version moves on any release; a core-schema version moves
only under `bend_protocol`.** Coupling them means a routine release
renumbers the core with no invariant changing meaning — and every
`Bent: zero` this repository has claimed is then asserted against a
referent that can move without anyone bending anything.

`architecture/core.yaml` now declares it, with the coupling explicitly
denied (`derived_from_packaging: false`, `moves_only_under:
bend_protocol`, `moves_on_release: false`). `conformance.core_version()`
reads the declaration and **refuses** one that admits to being derived
from packaging. `invariants.yaml` no longer restates the version; it
points at the declaration. One referent, one place.

### What decoupling cost, and where it is paid

Found by mutation: setting the declaration to `0.1` left the
declaration test **green**. That test compares the declaration against
itself, and a self-consistent declaration is unfalsifiable on its own.
Nothing external pins the value any more — that is the *point*, and it
is also a real loss that has to be paid somewhere rather than pretended
away.

It is paid by the **closure**. Six architecture artifacts bind
`extends: core@<v>`; the gate requires every one to match. A version
that moves stops the whole repository conforming at once. That is
`bend_protocol`'s teeth: the version cannot move quietly, because moving
it invalidates every declared vertical and probe *by construction*
rather than by anyone remembering to re-run them. Locked by
`test_moving_the_declared_core_version_breaks_every_artifact_that_binds_it`.

---

## 2. Two probes, 51 and 73 lines — and what it says about `Bent: zero`

| key | STE | DAQ |
|---|---|---|
| `observation_properties` | 4 entries | **identical** 4 entries |
| `computation_properties` | **key absent** | `[recursive_computation]` |

The two probes agreed exactly on what an *observation* can be, and
differed on whether a **computation** property was in scope at all.

Every property in STE's probe was a property of an observation. The
probe therefore could not falsify anything about computation — and
DAQ's probe, which has the key, found exactly such a case and returned
its first FAIL.

**The consequence for this repository's own record, stated plainly:**
every `Bent: zero` STE has claimed was measured against a probe
structurally unable to find the case DAQ closed. That does not make the
claim false — the evaluation now added returns no bend — but its
**evidence was narrower than the claim implied**, which is the same
shape as trusting an anchor for the property that made it blind.

STE's probe now carries the key, as a **separate key** rather than a
fifth entry in the observation list: a computation property is not one
any source's observations can have, and appending it would be the
category error DAQ's probe deliberately avoided.

**Verdict: `bend: none`, on structural grounds.** An N-iteration
estimator runs to completion *inside one* `ExecutionSpecification`, so
it is one computation identity and one trace occurrence here; the
iteration count is not visible to any identity STE mints and cannot
inflate one. Recorded beside it, because it qualifies the verdict rather
than supporting it: STE **cannot** evaluate the evidence-lineage half —
whether a chain of derivations is bounded and its depth recorded. That
is `generation_depth_bounded`, owned by DAQ. A repository that owns
execution identity cannot falsify a lineage-depth invariant by
inspecting its own ledgers, because lineage depth is not a quantity its
ledgers carry.

---

## 3. Three parties, one with no invariant source

| party | binding mode | invariants | binds via | commit |
|---|---|---|---|---|
| STE | `invariant_registry` | 26 | 6 artifacts | local |
| DAQ | `invariant_registry` | 43 | 30 artifacts | `708f6d6` |
| SCL | **`extends_only`** | **0** | 5 artifacts | `966b31f` |

SCL holding neither `invariants.yaml` nor a probe is a **binding mode**,
not an absence to route around. A party can bind the core by declaring
`extends: core@<v>` in its own artifacts while declaring no invariants
of its own.

The distinction this pins: *a party contributing zero records* and *a
party the derivation failed to read* produce the same number. Only one
of them is a fact. So `extends_only` is recorded explicitly, with the
binding files **named** — the register can be read to see that SCL
declares none, rather than leaving a reader to infer it from a count.

And the case it must not absorb: a repository with **neither**
invariants nor `extends` is not "bound with no source" — nothing
establishes it is bound at all, and counting it as a contributor of zero
would be the register asserting a binding on the party's behalf. That
**fails**.

---

## 4. Recording the commits — and the failure that found

The instruction was to record the commits derived from, so a later
derivation can tell current from stale. Doing it exposed that the
previous derivation had recorded the wrong side of the question.

**Measured: both sibling clones were behind their remotes** at the
moment the previous phase recorded their local HEADs as the commits it
had derived from, and reported them current. DAQ `854780d` → remote
`aa1f7eb`; SCL `482c336` → remote `3d73080`. One of them (DAQ) moved
*again* between a fetch and the next derivation minutes later.

A local commit proves authorship. Only the remote head proves the clone
is current. The derivation now asks the remote — the same posture as
DAQ's `verify_pair_landed.py`, for the same reason — and the question is
treated as **directional**, because collapsing it to equality gets one
direction wrong:

- clone does **not contain** the remote head → **stale → derivation fails**
- clone **ahead** of remote → `local_ahead_of_remote`, recorded (the
  normal case for the deriving repository, which emits the register from
  its working tree and commits it alongside the state it describes)

`check_remotes=False` is permitted and is **recorded** in the artifact
(`currency_established_against_remotes: false`). What must not exist is
a register that reads the same whether or not the question was asked.

### Faithfulness and currency are different properties

Enforcing currency *inside the test suite* was a design error of mine,
and the siblings made it visible: DAQ pushed **four times** during this
phase, and each push turned STE's suite red for something nobody here
did wrong. Worse than the noise is the direction of the pressure — the
cheapest way back to green becomes weakening the staleness gate.

So the two are split:

| property | whose | when checked | on failure |
|---|---|---|---|
| **faithfulness** — the register is what derivation produces from the commits it *names* | STE's | offline, deterministic, in the suite | hard failure |
| **currency** — those commits are still the remote heads | the world's | at emission, and on demand (`--currency`) | refuse to emit / report, exit 2 |

The digest still covers the **whole** artifact, currency fields
included; only the *comparison* is narrowed, to exactly two fields
(`currency`, `remote_commit`) named in a module constant rather than
filtered ad hoc at each call site — widening that set would let real
drift hide in the gap. The currency gate's own behaviour is locked
hermetically against a local origin nobody else can push to.

### What the register actually guarantees

**Not "never stale" — "stale is detected".** The
committed register is current as of the commits it names and will read
stale the moment a sibling pushes again. That is the correct shape and
worth stating rather than leaving a reader to assume the stronger claim:
a derived register cannot make a moving sibling hold still, it can only
make the divergence *loud* instead of silent. The previous,
hand-maintained projection had the opposite property — it never failed,
and it was wrong.

---

## 5. Nine contested → zero, and why that is a result rather than a silence

The nine disagreeing rows were three different things in one bucket:

**(a) Four rows STE reported for an invariant DAQ owns**
(`generation_depth_bounded`, `no_circular_training`,
`training_admissibility_declared`, `prediction_carries_uncertainty`).
These were the defect.

The fix is **not a corrected copy** — a corrected copy is the same
artifact one correction later, and in the sibling pair this exact
artifact went *two* corrections stale with every suite green. STE now
records `owner_elsewhere: DAQ` and **no status for the owner at any
version**; the register resolves the owner's live value on every
derivation (`owner_status_resolved`). A pointer that resolves cannot go
stale; a copy always can.

The cost is real and is the property working: **STE can no longer be
derived alone.** Four of its rows have no status here, so a single-party
derivation *fails* rather than quietly producing unresolvable pointers.
That is what the copied status bought, and what giving it up costs.

**(b) Five development-process rows** whose state is genuinely
per-repository — each repository has its own authorship lineage,
doctrine and review history, so two parties holding different statuses
are *both* telling the truth. Declared `scope: this_repository`. Scope
defaults to `project`, so silence never buys the exemption.

**(c) One row where STE was stale about *itself*.**
`no_vendor_in_doctrine` read `status: process` with the note *"no
doctrine files exist in this repository"*. Five generated doctrine files
and a mechanical vendor lint have existed here since the
architecture-sync phase. The register was built to catch a claim about
someone else's state going stale, and the first thing it caught in this
file was a claim about our own. A note is not re-checked when the thing
it describes changes, and nothing was watching it. Corrected to
`enforced` with the real validator.

### The reachability proof zero demands

Zero contested is also exactly what a broken detector reports. So a
genuine same-scope disagreement is **planted** and the derivation is
required to find it, then required to stop finding it once the scope is
declared — showing the exemption is the scope declaration doing work,
not the detector having failed.

That test earned its place immediately: the first `contested`
implementation grouped *by* scope and flagged any group that disagreed,
which is a different rule wearing the same words — two claims both
scoped `this_repository` still contested. The plant found it.

The register also emits `rows_with_a_local_scope_claim`, so a reader can
see how much of the zero was reached by agreement and how much by
scoping, instead of taking the count on faith.

---

## 6. One party, two names — arriving inside this derivation

DAQ and SCL found that DAQ calls itself `daf` in all six of its own
artifacts while SCL addresses all eight requirement rows to `daq` — both
internally consistent, invisible to every check inside either
repository, and visible the first time anything **joined on the token**.

This derivation joins on a **third** name (`STE`/`DAQ`/`SCL`, labels
chosen here). So it records each party's self-declaration beside the
local label and marks the label as a local handle
(`label_is_a_local_handle_not_the_party_s_name`), rather than asserting
the label is the name.

**Found by running:** the first implementation reported DAQ's
`also_known_as` as *SCL's* name. SCL holds a byte-identical **mirror**
of DAQ's requirement response, which carries DAQ's self-declaration —
one party's name attributed to another, by a derivation whose entire
subject is not trusting one repository's account of another.

Mirrors are byte-identical to their origins by design, so content cannot
separate them. The **generator** can: an emitted artifact names the
script that built it, and only the origin repository holds that script.
An artifact naming no generator is hand-authored in place and counts as
origin — absent is not false.

---

## 7. Carried forward, unresolved

- **DAQ's `no_vendor_in_doctrine`** claims enforced, but the cited test
  does not cite the id — the implementation does. Enforcement is real;
  the machine-checkable link from the *named test* is absent. DAQ's to
  close, reported not patched.
- **Ingest probe: 0/3 gates proven reached** (unchanged this phase).
  `no_context_free_property` and `quantity_is_typed` UNREACHED;
  `class_assigned_at_ingest` **MALFORMED plant**, reported rather than
  counted as a hole, because no document payload *can* produce an
  undeclared extraction method — the extractor declares its own as a
  class constant. The probe is not a baseline; it is a gate that must
  pass first, and it correctly fails.
- **`cohort_identity` / `uncontrolled_conditions`** remain `unknown` in
  STE's probe — recorded, not guessed. DAQ ran the cohort probe in *its*
  substrate mid-phase and reports a representation gap; that result is
  **pointed at, not transcribed**, and STE's verdict is unchanged
  because the sibling measured gates STE does not have. Same boundary as
  §2, from the other side.
- **Tombstone / defeasance semantics** — the one recorded candidate
  bend (`evidence_append_only`), a core increment when addressed.

---

## Verified

Register locks **19/19**, all mutation-verified with per-test
attribution: **14/14 mutants killed by their named test** — tolerated
unreachable repo, citation check always passing, commit not recorded per
claim, contest detection disabled, core version moving without breaking
the closure, core version inferred from packaging, sourceless party
silently dropped, unbound party accepted as sourceless, currency asked
of the local clone only, offline derivation claiming currency, mirror
read as the holder's own name, deferral to a silent party tolerated,
owner status transcribed instead of resolved, committed register gone
stale.

Two mutants **survived** before being retargeted, and the reason is
worth keeping: both mutated `core.yaml`, and both target tests
manipulate that file themselves and restore what they found — so the
test's own save/restore silently reverted the mutant. **A mutation of a
file the test rewrites measures the test's bookkeeping, not its
assertion.** Both now mutate the enforcing code.

`invariant_register.yaml`: 3 parties, 51 invariants, **0 contested**, 4
deferred, emitted through the byte-identical shared serializer adopted
from DAQ. `crates`: `fmt` and `clippy` clean.

### Suite: 2050 passed, and 5 failures that are NOT this phase's

Reported rather than absorbed into a green claim.

- `test_execution_stage5_build.py` ×3 — **verified pre-existing.**
  Stashed every change in this phase and ran them at `cbe1185`: the same
  three fail identically with none of this work applied.
- `test_execution_proving{,_nexus}.py::test_a_wrong_program_specification_is_refused_before_proving`
  ×2 — the refusal fires correctly; the test's `pytest.raises(match=...)`
  regex (`"not registered"`) no longer matches the message wording
  (`"no built guest is registered for..."`). A stale assertion, in a
  message this phase does not touch.

**Not fixed here.** They are in the execution vertical, outside this
phase's scope, and quietly repairing unrelated tests in a commit about
cross-repository derivation would make the diff lie about what it did.

**An earlier, larger failure set was mine and was environmental.** A run
showed `host exited -9` (SIGKILL) across the proving and two-backend
suites — the OOM killer, because I had several pytest runs racing for
the ~8.5 GB prover on a 15 GB box. Re-run serially they pass. Worth
recording because the first read of that output was "eleven failures"
and the true count was five: *a measurement taken under contention I
created was not a measurement of the code.*

**Bent: zero** — and, for the first time, measured against a probe that
carries a computation property. The evidence for that claim is wider
than it was; §2 records exactly how narrow it had been.
