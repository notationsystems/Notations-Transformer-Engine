# The generator: measured, and not built

**Metric before optimization. The metric came back 2, and the class that
actually drifts is not the class a generator addresses.**

This records a decision *not* to build, with the measurement that
settled it, so the question is not re-raised from memory next time.

## The case for it, before measuring

The generator was the oldest open item — raised in the first exchange
and never built. The argument was strong: it is the only option that
reduces the *rate* at which drift findings appear rather than catching
them one at a time, and this session alone produced a stale register, a
class with two homes, and prose carrying a wrong measurement across
repositories.

I recommended it. Then I measured the population it would serve.

## Three contaminated measurements, in a row

| attempt | facts searched | result | why it was worthless |
|---|---|---|---|
| 1 | `bound_parties` = **3**, `contested_count` = **0** | 33 of 33 docs | single digits match every document trivially |
| 2 | `invariant_count` = **58**, `codes_total` = **20** | 9 docs | still bare numbers |
| 3 | inspected each hit | **0 real** | `20` was a sample size, a speedup factor, a section reference, a document count; `58` was a line number |

**A derived fact cannot be located in prose by its value.** Three
attempts, three contaminated results, each of which looked like evidence
until it was inspected. That is not a measurement problem to solve
harder — it is a property of the thing.

## The fair test

Facts that are *strings* are distinctive by construction. Searching for
the declared core version, and for an invariant id appearing near a
status word:

**2 documents.** `ARCHITECTURE_SYNC.md` (the core version) and
`DERIVED_INVARIANT_REGISTER.md` (the core version, and one status). Both
are phase records maintained deliberately as narrative.

That is the population. Not "every document" — two, both intentional.

## Why the metric being small is not the whole reason

The generator would not have caught what actually went stale this
session:

| what drifted | shape |
|---|---|
| "Not fixed here", with a suite count of 2065 | a **status assertion** plus a runtime measurement |
| "no doctrine files exist in this repository" | a **status assertion** |
| "there is no counterparty response" | a **status assertion** |
| a transcribed invariant status, two corrections behind | a **transcribed claim** — already fixed by deferral |

None is a restatement of a derived field. They are *judgements about
current state*, written in prose, and **no generator emits a judgement**.
A generator that tried would be a template, and a template lies
differently — it produces confident text about a state nobody checked.

So the target is small *and* aimed at the wrong class.

## What handles the measured class, and already exists

The class is prose claims about current state. Two mechanisms work on it,
both built this session:

- **Date it.** A dated measurement does not go stale — it stays true of
  its date. "0/3 gates reached, 2026-08-26" is permanently correct; "0/3
  gates reached" is a claim that expires silently.
- **Trigger it.** A claim that is safe under a condition names the
  condition and a check that fires when it stops holding — the tombstone
  and merge-policy deferrals.

Neither is a generator, and neither scales by being automated further:
they apply when a claim is written, by the person writing it.

## The honest residual

The class is real and is **not mechanically enumerable**. Prose
judgements cannot be found by scanning, which is the same finding as the
three contaminated attempts above, arriving from the other direction. So
it cannot be optimized against a metric — only handled case by case as
claims are written.

`metric_before_optimization` therefore returns: **no optimization
target.** That is the invariant doing its job, and it is the answer even
though the underlying worry was legitimate.

## The one candidate that survives, at n=1

The published systems report is a genuine hand-maintained projection of
derived state, and it churned repeatedly this session — its suite count
was corrected three times. It is one artifact, it lives outside the
repository, and generating its fact-bearing sections from the register
is a real and bounded piece of work.

**Recorded as a candidate, not started.** n=1 does not meet the bar this
document just applied to n=2, and applying a bar to someone else's
proposal and not to one's own is how a rule acquires its first
exception.
