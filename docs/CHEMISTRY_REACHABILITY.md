# Chemistry gate reachability — per code, and what the number means

**20 refusal codes. 20 LIVE. 0 REACHABLE. No rejection rate is
reportable.**

## Why per-code

A probe reporting "clean" across a gate set is a handful of measurements
and a larger number of **silences**, presented as one number. The
acquisition layer measured 2 of 15 admission codes REACHABLE — the other
13 are not clean, they are unmeasured, and a zero rate says nothing
about any of them.

The earlier probe here reported "0/3 gates reached" over three gates
picked by hand. This one enumerates every refusal in the vertical.

## Two questions, kept apart

The earlier probe ran one and reported it as though it were the other.

| | asks | why it comes first |
|---|---|---|
| **LIVE** | call the gate directly with a violating payload — does it refuse? | reachability analysis over a gate that does not refuse is analysis of nothing |
| **REACHABLE** | plant the same violation at an **entry path** — does it arrive? | this is the question a rejection rate depends on |

A gate can be LIVE and UNREACHABLE. That is not a contradiction and not
a defect — it is the honest state of a vertical whose gates have no
callers yet. What *would* be a defect is reporting the rate anyway.

## Result

| | |
|---|---|
| refusal codes enumerated | **20** |
| LIVE (gate refuses a violating payload) | **20** |
| DEAD | 0 |
| REACHABLE from acquisition | **0** |
| REACHABLE from execution | **0** |
| exercised by real acquisition | **0** |

Verdict vocabulary is adopted from the acquisition layer's
`admission_reachability.yaml` rather than reinvented, so the two
registers read side by side instead of in two private vocabularies.

## An UNREACHABLE verdict needs a path that terminates

Not an absence of anyone finding one. The acquisition layer's **Phase 27
correction** is the case: a stage claimed unreachable turned out
REACHABLE via two real bindings on a zero-length response body — and the
error ran *in the direction that made the metric look meaningful*.

So the verdict here rests on two things, not one:

1. **The traced stop.** No module under `scout/` imports `structures/`
   at all, so no document `run_scout` admits can reach these gates. The
   path terminates at the import graph, and the graph is **re-measured
   on every run** rather than remembered from the phase that checked it.
   (Only `transformer/` imports `structures/` — not an acquisition path.)
2. **The stop, executed.** An import edge is an *inference*. So a
   document carrying a bare scalar — no unit, method, conditions or
   uncertainty posture — and a polymer identified by a structure string
   goes through `run_scout`, entering at the **adapter**, the door a live
   document uses. Result: **1 observation admitted, 0 chemistry
   refusals.** The gates were not consulted. That is the termination
   measured rather than argued.

## Two corrections, both found by running

**A malformed plant.** The `DISTRIBUTION_FIELDS_MISSING` plant passed an
empty field mapping and tripped a *different* refusal one line earlier —
so it measured the plant, not the gate. The guard has two refusals and
the enumeration had one. `STRUCTURE_STRING_ONLY` was **added**, not the
plant quietly re-aimed: a malformed plant is a finding about the
enumeration.

**A vacuous confirmation.** The executed plant first used `key: value`
lines, which the shipped extractor does not read. It produced **zero
findings, zero refusals**, and the probe reported *"termination
confirmed"* — nothing had traversed the path. That is the same shape as
the Phase 27 error the confirmation exists to avoid. The probe now
refuses to call zero findings a termination.

## The mutation round that mattered

Three of seven mutants survived the first battery, all the same class:
**a check whose inputs are coincidentally uniform tests nothing about
the selection.**

- Every one of the 20 gates is LIVE, so the classifier's `DEAD` arm never
  executes against production inputs — deleting it changed nothing
  observable.
- No plant is malformed, so the `MALFORMED` arms never execute either.
- And the vacuous-pass test **recomputed the rule inside itself** instead
  of calling it, so it passed whatever the code did. A test that
  reimplements its subject tests only its own copy.

Fixed by extracting `classify_liveness` and `termination_verdict` as
pure functions and driving them over *constructed* inputs covering every
branch — the same move as planting two siblings in different currency
states. **9/9 mutants killed by their named test.**

## What this does not claim

That the gates are wrong, or that the vertical is unfinished in some way
it does not admit. The gates are live and correct; they have no caller on
any entry path yet.

The claim is narrower and harder: **no rejection rate measured today is
evidence about anything**, and a probe that reported one would be
manufacturing a measurement out of an absence.

## What would change it — and what it would *not*

Wiring the chemistry gates onto the acquisition path — an extractor that
emits property observations through `assert_property_context` — and then
re-running this probe. Codes that go REACHABLE become measurable; the
rest stay silent and stay labelled. The register is regenerated, never
edited.

**A sibling has measured that this is not the polymer constraint.** The
acquisition layer asked, before acquiring GPC data, whether "no content
gate runs at ingest" was the state that data should arrive into, and
measured the answer in its own substrate: not the question that decides
anything. Its result is **pointed at, not transcribed** — read it at the
source, which the derived register names and pins to a commit.

It does not change the verdict above, and the reason is the same
boundary that runs through this project: the sibling measured *its*
gates and *its* comparison machinery. `0 of 20 REACHABLE` is a statement
about this repository, established here, and a sibling's finding about
its own path is not evidence about paths this repository has.

What it does change is the sentence a reader would otherwise infer from
this section. Wiring the gates makes the **rate measurable here**. It is
not the thing that unblocks polymer science, and the sibling has
measured what is. Recording that distinction matters because this
document could otherwise be cited as "the gates are the blocker" — which
would be this repository's local scope quietly promoted into a claim
about the project.
