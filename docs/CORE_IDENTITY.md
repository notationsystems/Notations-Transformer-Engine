# The core, identified by its bytes rather than by its label

## The gap, found by another party

`architecture/core.yaml` declares `version: 1.0.0`, and that version
moves **only under `bend_protocol`** — correctly, because a routine
release must not renumber the core. The consequence had never been said
out loud: **many different core commits legitimately carry the same
label**, so a sibling that pins `core@1.0.0` cannot tell which of them it
bound.

That is not hypothetical. The acquisition channel's independently
recorded census observed it directly:

> two checkouts of this repository, different commits, three days apart,
> both reporting the version string 1.0.0 — with the ancestry between
> them **undeterminable** from that machine

and then said plainly what it could not do about it:

> What Phase 39 did not do, and could not, is say anything about the
> **other parties**. Two core commits wearing one label is now an
> observed fact rather than an unexamined possibility.

Naming which core a label refers to is **this repository's act**, because
this repository declares the label. That makes this the third gap in a
row that a sibling identified precisely and correctly declined to reach
across a boundary to close.

## What was built

The label gains a digest. They are different things and the artifact
keeps them apart:

| | |
|---|---|
| `core@1.0.0` | the **compatibility** statement — what a party may rely on |
| `sha256:8a8c73f4…` | the **identity** — which core that statement was made about |

A binding party runs `covers_what_is_bound(path, surface)` **first** — to
establish the digest is about code it actually imports — then
`core_identity.verify(digest, root, surface)` over its own copy. Both
arguments matter: `verify` without a surface name checks the twin track,
which is not what any measured party binds. Checking a digest
without checking its referent is what produced the defect described
below. **Bytes, not trust** — applied to the version string, which was
the one place this project had been trusting a name.

A mismatch returns the per-file digests, so the answer is *which file
moved*, not a bare no. A difference with no address leaves the reader
exactly where the label left them.

## The correction: the digest had the wrong referent

The first version of this module published **one** digest, over
`core/canonical` and `core/projection`, and described it as the thing a
binding party checks. That description was false, and the measurement is
exact.

The acquisition channel imports from this repository **291 times** —
`evidence` 125, `materials` 105, `scout` 46, `retrieval` 11, `structures`
4. It imports from `core` **zero times**. The compute layer imports 41
and zero. So the digest published as *the core they bind* covered exactly
the packages no binding party touches, and a change to `evidence/types.py`
— imported 125 times — would not have moved it at all.

**This is the original core-version defect recurring.** That one set the
version from this repository's packaging rather than from what it
declares: the wrong referent, in a way that quietly weakened every claim
made against it. This is the same error one level down — the right *kind*
of identity over the wrong *body* of code.

### Why one digest could never have been right

This repository holds **two disjoint tracks**. The acquisition channel's
own reconnaissance says so, and import analysis confirms it here: zero
imports in either direction between `{core, morpho, backends, runtime,
adapters, renderer}` and `{evidence, scout, retrieval, materials,
experiment, workbench}`. Two unrelated projects sharing one repository.

| surface | what it covers | who binds it |
|---|---|---|
| `twin_compiler` | canonical state, schema, versioning, deltas, validation, projection | nobody measured |
| `evidence_platform` | `evidence/` types, identity, classes, admission, pool | DAQ (291), SCL (41) |

Each is named, each is digested, and the register records **which one a
party binds — measured from what it imports, not assumed**.

### The measurement, not a declaration

`imported_tracks(consumer)` walks a consumer's AST and counts, per track.
`binding_track(consumer)` returns the track it imports more of, and
**None on a tie or on zero** — a consumer split evenly across two
disjoint tracks is not bound to either in any sense this can name, and
guessing would put a digest against a binding nobody made.

`covers_what_is_bound(consumer, surface_name)` is the refusal this module
now exists for. It answers *false, with the counts*, when a digest is
about code the party does not use. The counts are what make the refusal a
measurement rather than an opinion.

A consumer's **vendored copy** of this repository is skipped. A mirror
counted as a source is the same error in another dress.

### The checking function had to move too

`verify(expected, root)` computed `core_digest(root)` — the twin surface.
So the correction above would have been cosmetic: a party could be told
*which* surface it binds and then have no way to check it, because the
only checking function spoke about the track nobody imports.

`verify` now takes the **surface by name**, reports it in the result, and
**refuses a name it does not publish** rather than falling back to a
default — a fallback here would report a match about other code, which is
the exact failure this module exists to refuse. `compare` takes a surface
too.

The locks drive both surfaces and cross-check: a `verify` that matched
either digest against either surface would be reporting agreement it
never tested.

## What is hashed, and why it is not everything

Only what a bend changes. For `twin_compiler`, the **core schema
surface** — canonical state, its schema, versioning, deltas, validation,
and the projection contract. Nine files, three of them empty package
markers.

For `evidence_platform`, the **identity-bearing modules only** — five
files, not every file in six packages. A digest that moved on any change
to any of those packages would move on nearly every commit and
distinguish nothing.

Two properties matter and they are opposite. Both are pinned:

- a change to the surface **must** move the digest
- a change that is **not** a bend must **not** move it

Adding an invariant row, writing a phase report, landing a vertical —
none of these is a bend. A digest that moved on them would move on almost
every commit and stop distinguishing anything, which is how a fingerprint
that covers too much becomes useless. A digest that moved on none would
be equally useless.

**The surface is declared, not globbed.** A glob would silently widen the
core the first time somebody added a file beside these, and widening the
core without a bend is precisely what `bend_protocol` forbids by name.
Adding a path to the surface is therefore itself a core change, and shows
up as a moved digest.

The digest covers **paths and contents**, not contents alone: two files
whose bodies were swapped are a different core, and a digest that could
not tell them apart would be hashing a multiset rather than a schema.

What is left out is listed **with a reason for each**, so a later reader
can tell *left out deliberately* from *forgotten*.

## Refusals

A **missing** surface file refuses rather than hashing what remains. A
digest over a surface that has moved is a digest of something else, and
computing one anyway would be worse than failing.

A **failure to take the digest** is reported, not omitted — the ecosystem
register publishes `NOT_TAKEN: <error>` rather than dropping the field,
because a register that silently dropped it would look like a register
that never had one. That path fired for real on an unresolvable import
during development and said so, which is how it was found.

## What this does not claim

That a matching digest means two parties agree about anything beyond
these bytes. It is an **identity, not a warrant**: it says which core, and
says nothing about whether that core is right.

And it does not know what any party has *checked out*. This register
reads sibling clones on one machine; it cannot see another party's
working tree and does not pretend to.

## One invariant is written and held, and this says why

The rule this correction establishes —

> a published content identity names the surface it covers, and a
> party's binding to that surface is **measured** from what it imports
> rather than assumed; a digest whose surface the binding party does not
> import is refused with the counts

— is **enforced in code and locked in tests** (`covers_what_is_bound`,
driven over both tracks in both directions). It is **not yet a row in
`architecture/invariants.yaml`**, and the reason is the register's own
rule rather than an oversight.

The invariant register is a projection over three parties. Emitting it
requires every sibling clone to be current against its remote. At the
time of writing both are behind — DAQ at `9927d1b` against `ea3a008`,
SCL at `8b39ec3` against `e31ba0e` — and this session cannot advance
another session's working tree.

The deriver offers `check_remotes=False`, which emits from the local
clones and records that it did. **That is not the right escape here.**
That flag exists for a remote that cannot be *reached*; the marker it
writes means *I did not ask*. These remotes were asked and answered: the
clones are stale. Emitting under that flag would make the artifact say
something false about what this party knew — a force path wearing a
disclosure's clothes.

So the row waits for the clones. Faithfulness stays intact
(`build_invariant_register.py --check` passes), the enforcement is
already real, and the gap is recorded here rather than closed by
weakening the gate that found it. **A suite goes green by fixing the
condition, not by loosening the check that reports it.**

### The row, ready to land

Verbatim, so it goes in unchanged the moment the clones are current:

```yaml
  - id: identity_covers_what_is_bound
    scope: this_repository
    decided: >-
      2026-09-03, AFTER THE DEFECT SHIPPED TWICE. A content digest is
      published for one purpose -- so a binding party can check the
      code it bound. A digest over a body of code that party does not
      import serves that purpose not partially but not at all: it
      verifies something unused while a change to what IS used moves
      nothing.
    found_by: >-
      measurement, not review. The acquisition channel imports from this
      repository 291 times (evidence 125, materials 105, scout 46,
      retrieval 11, structures 4) and from the digested track ZERO. The
      compute layer imports 41 and zero. No reading of the code would
      have shown that; counting the imports did.
    why_it_recurred: >-
      it is the ORIGINAL CORE-VERSION DEFECT one level down. That one
      set the version from this repository's packaging rather than from
      what this repository declares. This one set the digest's surface
      from what looked like a core rather than from what a binding party
      reaches for. Both are the right KIND of identity over the wrong
      REFERENT, and the second was written by a party that had already
      fixed the first -- which is the part worth recording.
    rule: a published content identity names the surface it covers, and
          a party's binding to that surface is MEASURED from what it
          imports rather than assumed; a digest whose surface the
          binding party does not import is refused with the counts
    status: enforced
    enforcement:
      validator: architecture/core_identity.py covers_what_is_bound --
                 returns (False, reason-with-counts) when the bound
                 track differs from the surface named, and (False,
                 no-binding) when a party imports neither
      locks: tests/test_core_identity.py,
             tests/test_ecosystem_register.py
      failure_mode: fail_closed
    driven_both_ways: >-
      the locks assert TRUE and FALSE for each track over constructed
      consumers. A check whose inputs cannot span its branches tests
      nothing about the branch, which is the failure mode this project
      has now met five times.
    residual: >-
      the binding is measured by import COUNT, and ties return None
      rather than a guess. A consumer that imports one track heavily
      and depends on the other for one load-bearing type is reported as
      binding the first. Counting weights nothing, and a weighted count
      would be a judgement wearing a measurement's clothes.
```
