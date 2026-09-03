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

A binding party runs `core_identity.verify(digest, root)` over its own
copy. **Bytes, not trust** — applied to the version string, which was the
one place this project had been trusting a name.

A mismatch returns the per-file digests, so the answer is *which file
moved*, not a bare no. A difference with no address leaves the reader
exactly where the label left them.

## What is hashed, and why it is not everything

Only what a bend changes: the **core schema surface** — canonical state,
its schema, versioning, deltas, validation, and the projection contract.
Nine files, three of them empty package markers.

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
