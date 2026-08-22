# Phase 13 — Structured State Architecture Investigation

Status: **research only**. No implementation file was modified to produce
this document. Every claim about current behavior below was verified
against the actual source in this repository (grep/read evidence noted
inline), not recalled from memory of having written it.

---

## A. Current architecture map

```
external input (JSON / CSV / manual)
      |
      v
adapter (adapters/json_adapter.py, csv_adapter.py -- Protocol: normalize())
      |
      v
CandidateDelta { version_from, transaction_id, timestamp,
                 changes: Tuple[CandidateChange, ...] }
      |
      v
validate_candidate(schema, base, candidate)          core/canonical/validation.py
      |  schema-stage -> constraint-stage -> apply_changes -> make_version
      v
Version { id (content-addressed hash), parent, state, schema_version,
          provenance, timestamp }                     core/canonical/version.py
      |
      v
CanonicalState { schema_version, fields: Mapping[str, Field],
                 edges: Tuple[EdgeRecord, ...] }        core/canonical/state.py
      |
      v
project_state(version) -> ProjectedState (pure copy)    core/projection/project.py
      |
      v
compile_morpho(projected, config) -> MorphoDocument      morpho/compiler.py
      |   { entities: Tuple[Entity,...], relations: Tuple[MorphoRelation,...],
      |     frames, groups, constraints }                morpho/ir.py
      v
backends (all pure functions of ONE MorphoDocument)
      |-- compile_threejs -> ThreeJSSceneDescriptor
      |-- compile_svg     -> SVG string
      \-- analyze         -> GraphAnalysisReport
```

### Where each concept currently lives

| Concept | Lives in | Notes |
|---|---|---|
| Identity | `Field.id` == its own dict key (I5) → `Entity.id` unchanged → `geometry_id`/`visual_id`/`node_id`/`cell_id` (all identity functions on the same string, `morpho/identity.py`) | Deliberate, documented, not a duplication — a seam for future divergence, unused today. |
| Value | `Field.value` (`FieldValue = int\|float\|str\|bool\|Tuple[float,...]`) → `Entity.attributes["value"]` | Copied verbatim, untyped once inside `attributes: Dict[str, Any]`. |
| Type | `FieldSchema.type` / `Field.type` (`FieldType` Literal) → `Entity.attributes["type"]` | See "conceptual duplication" below — Morpho has no real type slot. |
| Structure | **Nowhere in CanonicalState** except flat `edges`. Nesting is purely an adapter-side string convention (`__`-joined ids), never read back as structure by anything downstream. | This is the bottleneck the prompt names. |
| Relationship | `CanonicalState.edges` / `EdgeRecord` (explicit only, I4) → `MorphoRelation` (adds `is_canonical`/`inference_status`) | Solid, already proven (Phase 12's `"precedes"`/`"relationships"` use). |
| Provenance | `ProvenanceInfo` (per `CandidateChange`, and — **only the first change's** — on `Version`) → `ProvenanceRecord` (per Morpho construct) | **Real gap found this phase**, see below. |
| Units | `Field.unit` / `FieldSchema.unit` (flat `Optional[str]`) → `Entity.attributes["unit"]` | No unit algebra; a plain label. |
| Timestamp | Four places: `Version.timestamp` (accepted-at), `CandidateDelta.timestamp` (submitted-at), `ProvenanceInfo.timestamp` (measured-at, Phase 12), `ProvenanceRecord.timestamp` (Morpho, always `None` in the canonical path — see below) | Overlapping meanings; one of the four is dropped in transit. |
| Version | `Version` / `VersionStore` — content-addressed, immutable, append-only | Solid, unchanged by this investigation. |
| Validation | `StateSchema`/`FieldSchema`/`FieldConstraints`/`EdgeSchema` → `validate_candidate` (schema-stage then constraint-stage, atomic) | Solid. |
| Mutation | Does not exist — every "update" is "produce a new immutable `Version`" | Solid, unchanged. |
| Representation | `backends/threejs`, `backends/diagram`, `backends/graph` — pure functions of one `MorphoDocument` | Solid, proven in Phase 9/12. |
| Geometry | Only `backends/threejs/compiler.py` (`kind`, `size`, `position`) | Correctly isolated; never touches `CanonicalState` or Morpho. |

### Conceptual duplication found (verified against source, not assumed)

1. **Per-field provenance does not survive acceptance.** `validate_candidate`
   (`core/canonical/validation.py:191-195`) builds the whole `Version`'s
   `.provenance` from `candidate.changes[0].provenance` — literally the
   first change in the batch. Every other change's provenance in the same
   accepted transaction is discarded the moment `make_version` returns.
   Confirmed: `grep -n "changes\[0\]" core/canonical/validation.py` — one
   hit, no compensating retention anywhere else.
2. **`StateDelta` (§5) is a defined type that production code never
   constructs.** Confirmed: `grep -rn "StateDelta(" --include="*.py"`
   outside `tests/` returns nothing. `diff()` builds `Change` tuples for
   *ad hoc* comparison (used by tests and by nothing in the accept path);
   `validate_candidate` never wraps an accepted transaction's changes into
   a `StateDelta` and nothing stores one. This means: after a `Version` is
   accepted, there is no way to answer "what exactly changed, with what
   per-field provenance, to produce this version" without externally
   recomputing `diff(parent.state, this.state, ...)` — which synthesizes
   *new* provenance from whatever the caller passes it, not the original.
3. **Per-fact timestamp is captured at ingestion and then dropped before
   Morpho.** `morpho/compiler.py::compile_morpho` calls
   `canonical_provenance(origin_version=..., compiler_version=...)` with no
   `timestamp=` argument (confirmed: `grep -n timestamp morpho/compiler.py`
   shows no hits in that file), so a JSON adapter's explicit per-field
   `timestamp` (Phase 12, `ProvenanceInfo.timestamp`) never reaches the
   Morpho `Entity.provenance.timestamp` — it is stranded on the discarded
   `CandidateChange` from finding 1, and even if it weren't discarded,
   nothing forwards it.
4. **`Field` itself carries no provenance at all** (confirmed:
   `core/canonical/state.py`'s `Field` = `{id, type, value, unit}`,
   nothing else). All provenance is transaction-level, not field-level,
   inside `CanonicalState`.
5. **Morpho's `type`/`value`/`unit` are untyped dict entries**, not real
   dataclass fields on `Entity` — `Entity.attributes: Dict[str,
   AttributeValue]` is a generic bag. This is a minor duplication of the
   *concept* of type without a matching structural guarantee at the
   Morpho layer.

Findings 1-3 are more consequential than the flat-namespace problem the
prompt opens with: **any structured-state proposal that doesn't also fix
per-field provenance retention will make the existing gap worse**, not
better, because richer structures mean more fields land in one batched
candidate, and today only the first one's provenance survives. This
investigation treats fixing that as a co-requirement, not an optional
extra — see §I and §Q.

---

## B. Current conceptual bottleneck

Two, not one:

1. **Structural (the one named in the prompt):** `CanonicalState.fields`
   is `Mapping[str, Field]` — flat, one level, no nesting, no first-class
   sequence/array/tensor. Phase 12 worked around this entirely at the
   adapter boundary (`__`-joined flattened ids), which is honest and
   functions correctly, but means nothing downstream — not `Morpho`, not
   any backend — ever sees "this is a nested record" or "this is an
   ordered sequence" as a fact. It only ever sees a flat bag of
   independently-named scalars, some of which happen to share a naming
   convention that nothing enforces or interprets.
2. **Provenance retention (found during this investigation, not
   previously documented):** per-field provenance is discarded down to a
   single transaction-level summary the moment a candidate is accepted.
   This is orthogonal to the structural bottleneck but interacts with it
   directly: the more structure a single ingested record has, the more
   fields land in one batch, the more provenance gets silently dropped.

---

## C. Three candidate architectures

### A — Structured Canonical State

`CanonicalState` itself grows nested entities, structured values,
sequences, arrays. Concretely this means `Field.value`'s type union
widens to include recursive structures (nested maps, ordered lists of
`Field`), or `CanonicalState.fields` becomes `Mapping[str, Node]` where
`Node` can itself contain child `Node`s.

**What this actually requires touching**, traced against the real code:

- `core/canonical/delta.py::parse_path` already tokenizes dot/bracket
  paths generically, so path *syntax* survives — but `apply_changes` /
  `_apply_field_change` / `_apply_edge_change` are hand-written for
  exactly two shapes (`fields.<id>`, `fields.<id>.<attr>`, `edges[i]`,
  `edges[i].<attr>`) and would need a genuinely recursive
  tree-diff/tree-apply algorithm to handle arbitrary depth — a real
  rewrite of the core delta engine, not an extension of it.
- `core/canonical/version.py::canonical_content`'s hash input (currently
  a flat, trivially-sorted dict-of-dicts) would need a canonical
  recursive serialization — solvable, but it changes what "the hash
  input" *is*, which is exactly the kind of core semantic change this
  phase was told not to make.
- `core/canonical/schema.py::StateSchema` (flat `Mapping[str,
  FieldSchema]`) would need recursive schema definitions — this is where
  Option A tips into reinventing JSON Schema, i.e. exactly the "universal
  ontology engine" anti-pattern named later in this document.
- The identity model (§9, "field_name == node_id == ...") was designed
  for flat ids; nested nodes need their *own* identity scheme (path-based
  or synthetic), which is a new invariant, not an extension of I5.

**Verdict:** maximizes expressive power, but at the cost of rewriting the
exact mechanisms (delta application, hashing, schema) that 109 passing
tests currently prove are simple and correct. This is "redesign
`CanonicalState`," explicitly out of scope this phase, and — independent
of that instruction — a real architectural risk: it moves organizational
concerns (how backends want to consume "a sequence") into the one layer
whose entire value proposition is being a minimal, flat, trivially-hashed
source of truth.

### B — Canonical State + Structural Morpho

`CanonicalState` stays exactly as it is, forever. All structural
richness lives only in Morpho, which is asked to *infer* structure —
e.g. recognize `"material__polymer__molecular_weight"`-style id
conventions and reconstruct a tree from the string.

**Verdict:** preserves 100% of `CanonicalState`'s proven simplicity —
literally zero core changes. But taken literally ("Morpho guesses
structure from id strings"), this reintroduces a problem this project
already recognized and avoided once: in Phase 12, compiling
`compile_morpho` was deliberately **not** given naming-convention-based
grouping logic, specifically because inferring structure from a string
pattern is fragile, implicit, and exactly the "representation-driven /
hidden semantics" anti-pattern this architecture has avoided everywhere
else (renderer never infers meaning, backends never guess). Pure Option
B, taken literally, would walk that back. It also doesn't actually solve
the semantic problem — it relocates the flattening problem one layer
downstream and adds guessing on top.

### C — Hybrid

`CanonicalState` keeps authoritative typed values, stable identities, and
gains a **small, explicit, finite vocabulary of structurally-meaningful
relationship types** riding on the *already-existing* `edges` mechanism
(no new field, no new type — a documented naming convention for edge
`type` strings). Morpho reads those explicit, asserted edges (never
guesses from id strings) and reifies them into richer organizational IR
constructs.

**Verdict — recommended, with one refinement below.** This is not "add a
third, different mechanism" — it is the *same* mechanism Phase 12 already
proved end-to-end for `"precedes"` (the time-series fixture) and
arbitrary `"relationships"` (the JSON adapter), generalized on purpose
rather than by accident. The key discipline that keeps this from becoming
Option A in disguise: **CanonicalState's shape does not change at all** —
not even an additive dataclass field, which is a *stronger*
backward-compatibility position than Phase 12's own
`ProvenanceInfo.timestamp` addition. Only two things are new: (1) two
reserved, documented `EdgeRecord.type` strings (`"contains"`,
`"precedes"`) that Morpho treats specially, and (2) new Morpho IR
construct *kinds* built from them. See §F for the exact primitives.

---

## D. Detailed comparison

| | A: Structured Canonical | B: Pure inference-in-Morpho | C: Hybrid (recommended) |
|---|---|---|---|
| CanonicalState shape change | Major (nested `Field`/`Mapping`) | None | **None** |
| Delta engine change | Major (recursive apply/diff) | None | None |
| Hashing change | Major (recursive serialization) | None | None |
| Schema change | Major (recursive `FieldSchema`) | None | None (2 reserved *string values*, not new fields) |
| Structure is explicit or guessed | Explicit (as new fields) | **Guessed** (id string patterns) | Explicit (asserted edges) |
| New Morpho constructs needed | Fewer (canonical carries structure) | More, and unreliable | Two (`Sequence`, `Composite`) |
| Risk of "hidden semantics" anti-pattern | Low | **High** | Low |
| Migration difficulty | High | Low | Low |
| Preserves 109 existing tests unmodified | At risk (core types change) | Yes | Yes |

## E. Recommended architecture

**Option C, refined as above:** zero changes to `CanonicalState`, `Field`,
`EdgeRecord`, or `StateSchema`. Two reserved `EdgeRecord.type` values
(`"contains"` for nesting, `"precedes"` for ordering — already the exact
string Phase 12 used). Two new, purely additive Morpho IR construct
kinds (`Sequence`, `Composite`) built by `compile_morpho` recognizing
those edge types. Plus the provenance-retention fix from §B, which this
investigation treats as a required companion, not an optional add-on.

---

## F. Exact proposed primitives

Two Morpho-level dataclasses, both new, both purely additive to
`MorphoDocument` (same pattern already used for `frames`/`groups`/
`constraints` — a new defaulted-empty tuple field, nothing existing
changes shape):

```python
# morpho/ir.py (proposed additions)

@dataclass(frozen=True)
class Sequence:
    id: str                          # = the id of the chain's root entity
    member_ids: Tuple[str, ...]       # ordered root -> tail
    provenance: ProvenanceRecord

@dataclass(frozen=True)
class Composite:
    id: str                            # = the id of the entity that is a
                                         # "contains" source but never a target
    member_ids: Tuple[str, ...]         # direct children ONLY, one level
    provenance: ProvenanceRecord

@dataclass(frozen=True)
class MorphoDocument:
    entities: Tuple[Entity, ...] = ()
    relations: Tuple[MorphoRelation, ...] = ()
    frames: Tuple[CoordinateFrame, ...] = ()
    groups: Tuple[Group, ...] = ()
    constraints: Tuple[Constraint, ...] = ()
    sequences: Tuple[Sequence, ...] = ()      # NEW
    composites: Tuple[Composite, ...] = ()    # NEW
```

**Recognition algorithm** (deterministic, order-independent, runs inside
`compile_morpho` alongside the existing entity/relation loop — not a
separate pass with its own nondeterminism risk):

- For every canonical edge with `type == "precedes"`: build a directed
  graph over entity ids. Each maximal chain where every node has
  in-degree ≤ 1 and out-degree ≤ 1 becomes one `Sequence`, ordered by
  walking from the unique in-degree-0 node. A node with out-degree > 1 on
  `"precedes"` edges is a malformed sequence — raise `SemanticError`
  (the same class `morpho/ir.py` already raises for cyclic frame
  parents), never silently pick one branch.
- For every canonical edge with `type == "contains"`: group by source id.
  Each source becomes one `Composite` with `member_ids` = its direct
  targets. A node that is both a target of one `"contains"` edge and the
  source of another is simply a member of one `Composite` and the root of
  a different one — nesting falls out of *traversal*, not recursion in
  the data shape, which keeps both new dataclasses flat and trivial to
  hash/compare (consistent with how `CanonicalState` itself stays flat).
- **Matrix/tensor is not a third construct.** A 3×3 tensor is a
  `Sequence` of 3 row-`Sequence`s (or, more simply, 9 scalar `Field`s
  linked by one `"contains"` edge from a `tensor` field to each row-group
  and `"precedes"` edges within each row) — reusing the two primitives
  above rather than inventing `Matrix`/`Tensor` kinds. See §P.

**Why exactly two reserved types and not more:** every data-model
requirement in the prompt's list of 14 reduces to "ordering" and/or
"nesting" once value/type/unit are already handled by existing `Field`
machinery:

| Requirement | Reduces to |
|---|---|
| Vector, tensor, matrix | nesting + ordering (see §P) |
| Nested record | nesting (`Composite`) |
| Sequence, time series | ordering (`Sequence`) |
| Table (samples × properties) | nesting (`Composite` per sample) — this is exactly Phase 12's CSV multi-row prefixing, now expressible as edges instead of id-prefixing (see §H) |
| Graph, temporal graph | already solved — plain `edges`, unchanged |
| Material/process state | nesting (`Composite` of `Composite`s) |
| Candidate state | already solved — `CandidateDelta`, unchanged |
| Simulation result | nesting + ordering, same as any other structured record |

No third primitive was found necessary. This is the answer to "determine
the minimum primitives required": **two — one for containment, one for
order — both expressed as reserved edge-type strings, not new types.**

---

## G. CanonicalState vs. Morpho responsibility boundary

- **CanonicalState owns:** atomic field identity, atomic typed value,
  atomic unit, and *explicit, flat* relationships — including the now-
  reserved structural edge types, which are still, at the canonical
  layer, just edges with a type string. CanonicalState has no concept of
  "this is a sequence" or "this is nested" — it only ever asserts
  individual facts and individual pairwise relationships.
- **Morpho owns:** interpreting *which* relationships are structural (by
  reserved type, never by guessing) and reifying them into organizational
  constructs consumable by backends. Structure, in this architecture, is
  a **compiled fact**, not a **stored fact** — it exists because Morpho
  built it deterministically from canonical edges, not because
  `CanonicalState` remembers it as a tree.

This is the direct answer to "`CanonicalState → Morpho` vs. `CanonicalState
== Morpho`": **keep them distinct.** Merging them would mean every
backend-facing organizational concern (grouping, ordering, eventually
layout-adjacent concepts) has to be re-litigated as a canonical-state
change, reintroducing exactly the risk Option A carries, for no benefit —
Morpho already exists as the layer designed to carry compiled,
backend-neutral structure (§1 of the frozen spec), and Phase 9 already
proved backends can consume a shared Morpho object without touching
canonical state. Distinctness is not incidental; it is what makes "swap a
backend without touching canonical state" (already proven, Phase 9) keep
holding as structure grows.

---

## H. Identity model

Because `CanonicalState` gains **no** nesting primitive of its own —
nesting is represented purely as edges between independently-identified
flat fields — every identity question below has a direct, mechanical
answer, not a new rule:

Worked example: `Material M1 → Polymer P1 → MolecularWeight F1`
(`"contains"` edges: `M1→P1`, `P1→F1`).

| Question | Answer | Why |
|---|---|---|
| Does M1 identity remain stable when F1's value changes? | **Yes** | M1, P1, F1 are three independent `Field`s. Changing `F1.value` is a `fields.F1.value` replace — it does not touch `fields.M1` or `fields.P1` at all. Identical to how any two unrelated fields behave today; nesting via edges introduces no new coupling. |
| Does P1 identity remain stable? | **Yes** | Same reasoning. |
| Does F1 identity remain stable? | **Yes** | I5 already guarantees this — identity is the field name, never the value. |
| Does the state Version change? | **Yes, always** | `Version.id` is content-addressed over ALL fields+edges (§4) — any field value change anywhere produces a new `Version.id`, exactly as today. |
| Does the Composite's (M1's) *structural* identity change? | **No** | A `Composite`'s id and `member_ids` are a function of its `"contains"` edges, not of its members' current values. As long as the edge set `M1→P1` is unchanged, the `Composite` is identical across the value change. |
| Does the backend representation identity change? | **No** | `geometry_id`/`visual_id` are still the identity function of `entity.id` (§9, unchanged) — a `Composite` gets its own stable `geometry_id`/`visual_id` the same way any entity does. |

**A genuinely useful side effect of the edge-based model, worth naming
explicitly:** Phase 12's JSON adapter flattened nested keys into ugly
compound ids (`material__polymer__molecular_weight`) *because* that was
the only way to disambiguate structure inside a flat namespace. With
`"contains"` edges carrying that disambiguation instead, a *future*
adapter revision could emit natural ids (`molecular_weight`, `polymer`,
`material`) plus explicit edges — more readable, and it only affects
*adapter output shape*, not `CanonicalState`, `Morpho`, or any invariant.
This is not required by this phase (see §T), but it falls out of the
recommendation for free and is worth recording.

The Phase 12 multi-row CSV convention (`P001__temperature_C`) still needs
*some* disambiguation mechanism for the case of *multiple independent
records sharing one schema* (that's not nesting — P001 and P002 are
siblings, not parent/child) — id-prefixing remains the right tool there,
unchanged by this proposal.

### Structural edit operations

| Operation | How it's expressed | New mechanism needed? |
|---|---|---|
| Add a child | field `add` + `"contains"` edge `add`, one candidate | No — both already exist, already proven (Phase 11's field-add test, Phase 12's edge-add test) |
| Remove a child | field `remove` + `"contains"` edge `remove` | No |
| Rename a field | **Not supported**, unchanged by this proposal | Renaming was already out of scope by the frozen spec's own design (`Operation` reserves `"rename"`, `diff()` never emits it, §5/§23). This investigation does not reopen that — a rename is, and remains, "remove old identity, add new identity." |
| Change a value | `fields.<id>.value` replace | No |
| Change a relationship (move F1 from P1 to P2) | remove `P1→F1` edge, add `P2→F1` edge, one candidate | No — F1's own identity is untouched; only Composite membership changes |
| Reorder a sequence | Remove and re-add `"precedes"` edges in the new order | **Correctness: no new operation needed.** Efficiency: reordering one element in an N-long sequence costs O(N) edge changes today. A dedicated `REORDER`/`MOVE` operation would fix that but is not required for correctness — recommended **not** to add it now (see §T); nothing in the current data model requirements forces it. |

---

## I. Provenance model

Two separate questions: how provenance traces through nested structures
(straightforward, given H above), and the retention gap found in §A
(the harder, more important one).

**Tracing (straightforward):** `rheometer.csv row 17 → viscosity` already
works exactly as far as the *Morpho* layer, end to end, proven by Phase
12's `test_csv_source_reaches_canonical_field_with_traceable_provenance`
and `test_canonical_field_reaches_morpho_entity_and_every_backend_representation`.
Nesting doesn't change this trace at all: a nested field's `Entity` in
Morpho still carries `provenance.origin_version == the Version.id it was
compiled from`, regardless of how many `"contains"`/`"precedes"` edges
point at it.

**Retention (the real gap, §A findings 1-3): minimum required fix,
fully specified:**

1. `validate_candidate`, on the accept path, additionally constructs the
   `StateDelta` that already exists as a type but is never built today:
   `StateDelta(version_from=candidate.version_from, version_to=new_version.id,
   transaction_id=candidate.transaction_id, timestamp=candidate.timestamp,
   changes=<Change tuple, one per CandidateChange, each keeping that
   change's own ProvenanceInfo verbatim>)`.
2. `VersionStore` gains one new method, `get_delta(version_id) ->
   Optional[StateDelta]` (`None` for the genesis version, which has no
   triggering delta). The in-memory implementation stores the
   `StateDelta` in a second dict keyed by `version_to`, populated
   wherever `put()` already runs today.
3. `Version.provenance` (the existing single-summary field) is
   **unchanged in shape** — every one of the 109 existing tests that
   reads `.provenance.source` etc. keeps working untouched. It is
   redefined *in documentation only* as "a convenience summary of the
   triggering change," with the retained `StateDelta` as the new
   authoritative per-field record.
4. `compile_morpho` is extended to pass `timestamp=` through to
   `canonical_provenance()`/`derived_provenance()` when a per-field
   timestamp is available from the originating `StateDelta` (looked up
   via `VersionStore.get_delta`) — closing finding 3 from §A.

This is additive only: one new store method, one new stored object per
accepted version, one new constructor argument threaded through an
existing call. No existing dataclass shape changes. No existing test's
assertions are contradicted (verified by inspection of what each
existing provenance-related test actually asserts — all check `.source`,
`.origin_version`, `.confidence`, `.compiler_version`, none assert
anything about `StateDelta` not existing).

---

## J. Version / hash model

**Must the hash depend on:**

| Input | In the hash today | Should it be, going forward | Why |
|---|---|---|---|
| Entity/field identities | Yes (they're the dict keys) | Yes, unchanged | Identity is semantic — the same value under a different name is a different fact. |
| Field values | Yes | Yes, unchanged | The core of what "content-addressed" means. |
| Structure (edges, including the new reserved types) | Yes (`edges` is already in the hash input) | Yes, unchanged | A `"contains"`/`"precedes"` edge is still just an edge — no special-casing needed in the hash function itself. |
| Relationships (non-structural edges) | Yes | Yes, unchanged | Same reasoning. |
| Units | Yes (part of the serialized `Field`) | Yes, unchanged | A value with a different unit is a different fact (`4.2` vs `4.2 MPa` are not interchangeable). |
| Provenance (source, author, transaction_id) | **No** (§4 already excludes all of `ProvenanceInfo`/`Version.provenance` from the hash) | **No, must stay excluded** | This is the correct existing behavior and the reason the cross-process determinism test (`tests/test_versioning.py`) passes: the same fact asserted by two different sources must hash identically, or "convergence" (Phase 12 §7, already proven) breaks. |
| Timestamps | No | **No** | Same reasoning — a timestamp is *when* a fact was recorded, not part of the fact. |
| Source metadata | No | **No** | Same reasoning. |
| Representation metadata (backend config, layout) | No, and never has been (`ThreeJSRenderConfig`/`DiagramLayoutConfig` are not part of `CanonicalState` at all) | **No** | This is I8/§12's extrinsic-vs-intrinsic boundary, already correctly enforced. |

**Semantic identity vs. provenance metadata vs. representation
metadata — the existing three-way split is already correct and this
investigation does not change it.** The only change is what §I proposes:
provenance metadata becomes *retained* (via the new `StateDelta` store
lookup) without becoming *hashed*. Retention and hashing are independent
axes; conflating them was never proposed and would be wrong — a fact's
identity must not depend on who reported it or when, but the system
should still remember who reported it and when.

**Migration:** none required for `Version.id` itself — the hash function,
its inputs, and its exclusions are untouched by this whole investigation.
Every existing `Version.id` computed under the current scheme remains
valid and unchanged if `Sequence`/`Composite` recognition and `StateDelta`
retention are added later, because neither touches `canonical_content()`
or its inputs.

---

## K. StateDelta model

**Operations actually necessary**, evaluated against the prompt's list of
nine candidates:

| Proposed op | Necessary now? | Reasoning |
|---|---|---|
| `SET_VALUE` (already `replace`) | Yes — exists | Already implemented, proven. |
| `ADD_ENTITY` (already field `add`) | Yes — exists | Already implemented, proven. |
| `REMOVE_ENTITY` (already field `remove`) | Yes — exists | Already implemented, proven. |
| `ADD_RELATION` (already edge `add`) | Yes — exists | Already implemented, proven (Phase 12). |
| `REMOVE_RELATION` (already edge `remove`) | Yes — exists | Already implemented, proven. |
| `INSERT_SEQUENCE` / `REMOVE_SEQUENCE` | **No, not as new opcodes** | A sequence is just `"precedes"` edges over ordinary fields; inserting/removing a sample is field add/remove + edge add/remove, already covered. |
| `REPLACE_ARRAY` | **No** | An "array" here is a `Composite`/`Sequence` of fields; replacing it is N field replaces, already covered — no evidence a bulk-replace opcode is needed yet. |
| `PATCH_ARRAY` | **No, not yet** | Same reasoning as `REORDER` in §H: real but unproven need, efficiency not correctness, not required by any of the 14 data-model requirements as stated. |
| `SET_METADATA` | **No** | Provenance/unit/timestamp are already per-field or per-change; no evidence of a distinct "metadata-only, no value change" use case in any Phase 12 example. |

**Conclusion: zero new delta operations are required.** `add`/`remove`/
`replace` on fields and edges (already implemented, already proven
across 109 tests) are sufficient to express every structural edit in
§H's table. This is a direct, evidence-based rebuttal of the assumption
that richer structure requires a richer delta vocabulary — it doesn't;
it requires richer *interpretation* of the same flat delta vocabulary,
one layer up, in Morpho.

**Preserving `State_t + Delta_t = State_t+1` with deterministic replay:**
already holds today (`tests/test_replay.py`,
`tests/test_live_state_bridge.py::test_deterministic_replay_of_the_whole_chain`)
and is unaffected by anything in this proposal, because nothing about
delta *application* changes — only what gets *retained* after
application (§I) and how the *result* gets *compiled* (§F/§G) change.
Ordering, conflict detection, and immutability are all governed by the
existing single-writer `VersionStore` model (§20 of the frozen spec
already names multi-writer conflict resolution as explicitly out of
scope) — nothing here reopens that.

---

## L. Units / type model

Evaluated against `185 °C` / `4.2 MPa` / `1250 Pa·s` / `85000 g/mol`
vs. bare `185`/`4.2`/`1250`/`85000`:

| Option | Verdict |
|---|---|
| A. Unit is part of the semantic value (e.g. encode into the number) | **Rejected.** Would make `Field.value`'s type depend on `Field.type` in a new way and break the existing flat `FieldValue` union; also makes unit-blind comparisons (e.g. Phase 12's convergence test) harder, not easier. |
| B. Unit is metadata attached to the value | **Already the current model, and correct.** `Field.unit: Optional[str]` sits beside `Field.value`, already proven sufficient for every Phase 12 example (`"C"`, `"MPa"`, `"Pa_s"`, `"g/mol"` all round-tripped correctly through the JSON adapter's envelope mechanism). |
| C. A typed value object (e.g. `Quantity(value, unit)` with unit-aware arithmetic) | **Not needed yet.** No requirement in this phase's 14-item list needs unit *conversion* or *arithmetic* — only unit *labeling and preservation*, which (B) already does. Building (C) now would be exactly the "unit library" the prompt says not to introduce. |
| D. External ontology reference (e.g. QUDT/UCUM URIs) | **Not needed yet, and would be the ontology-engine anti-pattern.** Nothing in the current data ever needs to resolve "is MPa compatible with Pa" — that's a real future need (once simulation/ML consumers exist) but not one this phase's evidence justifies solving now. |

**Recommendation: keep (B), unchanged.** `Field.unit` as a plain optional
string is sufficient for everything demonstrated so far and does not
need to change as part of the structural-state work — units are already
correctly modeled as metadata on an atomic value, and atomic values don't
change shape under this proposal.

---

## M. Representation model

Unchanged in principle from what Phase 9 already established: backends
consume a `MorphoDocument` and produce declarative, backend-specific
output; none may mutate canonical state; none becomes a second source of
truth. The only change under this proposal is that `MorphoDocument` now
optionally carries `sequences`/`composites`, which existing backends may
ignore entirely (they remain correct, if incomplete, without any change)
or optionally consume:

- `backends/graph/analysis.py`: no change required for correctness
  (sequence/composite structure is already visible through ordinary
  edge adjacency, since both are built *from* edges); could optionally
  add `sequence_count`/`composite_count` to `GraphAnalysisReport` later.
- `backends/diagram/compiler.py`: no change required; existing per-edge
  line rendering already draws `"contains"`/`"precedes"` edges. A
  bounding-box-per-Composite visual grouping is a plausible future
  enhancement, not required now.
- `backends/threejs/compiler.py`: no change required; a `Composite`'s
  parent/child relationship could reuse the *already-existing*
  `hierarchy` descriptor field (today populated only from
  `CoordinateFrame` parent/child) as a natural, additive fit — proposed
  as a follow-up, not required now.

This confirms §G's boundary claim with a concrete test: **a backend can
be upgraded to understand `Sequence`/`Composite`, or not, independently
of every other backend and independently of `CanonicalState`** — exactly
the "backend replacement doesn't require canonical-state changes"
invariant this whole project has maintained since Phase 9.

---

## N. Worked example — polymer process

```
Material (M)          Process (Pr)            Measurement (Ms)
  polymer = "FEP"        temperature = 185       viscosity = 1250
  molecular_weight       pressure = 4.2           tensile_strength = 42.7
    = 85000               screw_speed = 60
  crystallinity = 0.38

M --contains--> polymer, molecular_weight, crystallinity   (3 fields, natural ids)
Pr --contains--> temperature, pressure, screw_speed
Ms --contains--> viscosity, tensile_strength
M --process_input_to--> Pr        (ordinary, non-structural relation, unchanged)
Pr --produces--> Ms                (ordinary, non-structural relation, unchanged)
```

7 canonical `Field`s (all flat, all independently identified — no
`__`-joins needed under this proposal, contrast with Phase 12's actual
`material__polymer__molecular_weight`), 5 `"contains"` edges (3+3+2... —
concretely: `M→polymer`, `M→molecular_weight`, `M→crystallinity`,
`Pr→temperature`, `Pr→pressure`, `Pr→screw_speed`, `Ms→viscosity`,
`Ms→tensile_strength` = 8 `"contains"` edges), 2 ordinary relation edges.
Compiles to 3 `Composite`s (`M`, `Pr`, `Ms`) plus the 2 ordinary
`MorphoRelation`s, entirely from existing mechanisms plus the two
reserved edge types.

## O. Worked example — time series

```
Experiment (E)
  E --contains--> t0, t1, t2, t3        (4 sample Composites, or...)
```

Two valid modelings, both expressible without new primitives:

- **Per-sample Composite:** each `t_i` is itself a `Composite`
  (`t0 --contains--> timestamp_0, temperature_0, pressure_0, torque_0,
  viscosity_0`, etc.), and `t0 --precedes--> t1 --precedes--> t2
  --precedes--> t3` orders the samples. This is a direct improvement on
  Phase 12's actual time-series fixture, which used per-*channel*
  `"precedes"` chains (`temperature_t0 → temperature_t1 → ...`) rather
  than per-*sample* composites — both are valid under this model; which
  one an adapter chooses is a modeling decision, not an architectural one.
- Either way: zero new primitives, zero `CanonicalState` changes,
  consistent with Phase 12's already-proven fixture.

## P. Worked example — matrix/tensor

```
stress_tensor (T): 3x3 matrix
  T --contains--> row0, row1, row2         (3 row Composites)
  row0 --contains--> T_00, T_01, T_02        (3 scalar Fields each)
  row1 --contains--> T_10, T_11, T_12
  row2 --contains--> T_20, T_21, T_22
  row0 --precedes--> row1 --precedes--> row2   (row order)
  T_00 --precedes--> T_01 --precedes--> T_02   (column order, per row)
```

9 scalar `Field`s, 3 row-`Composite`s, 1 tensor-`Composite`, ordering
edges for both axes. No `Matrix`/`Tensor` Morpho construct was needed —
confirms §F's claim that `Sequence`+`Composite` are jointly sufficient
for the full data-model requirement list.

---

## Q. Migration strategy

No migration of existing data is required — nothing about `Version.id`,
`CanonicalState`, or `StateSchema` changes shape (§J). The rollout is
purely additive, in this order:

1. Implement §I's `StateDelta` retention (`validate_candidate` +
   `VersionStore.get_delta`) — independently useful, fixes a real gap,
   zero dependency on §F.
2. Implement §F's `Sequence`/`Composite` dataclasses and recognition
   logic in `compile_morpho`.
3. Optionally extend one backend (recommend `backends/threejs`'s
   `hierarchy` field, per §M) to consume `Composite` parent/child.
4. Update `adapters/json_adapter.py` to optionally emit natural
   (non-`__`-joined) ids plus `"contains"` edges for nested objects, as
   an alternative to the current flattening — **not a breaking change**,
   since both representations remain valid; this could even be an
   adapter *parameter*, not a hard cutover.

Each step is independently shippable and independently testable; none
requires the next to already exist.

## R. Backward compatibility strategy

Every one of the 10 invariants re-verified in Phase 12 remains intact by
construction, because nothing in this proposal touches the mechanisms
that provide them:

| Invariant | Still holds because |
|---|---|
| Immutable versions | `Version`/`CanonicalState` shapes unchanged |
| Validation gate | `validate_candidate`'s schema/constraint stages unchanged; `StateDelta` retention is a pure addition after acceptance |
| Canonical authority | Structure is *compiled*, never *stored as a second source of truth* (§G) |
| Provenance | Strictly improved (§I), not weakened |
| Deterministic serialization | `canonical_content()` untouched (§J) |
| Deterministic compilation | `compile_morpho`'s new recognition step is a pure function of already-hashed edge data |
| Backend isolation | New IR fields are optional/ignorable per backend (§M) |
| State-delta replay | Delta application mechanism untouched (§K) |
| Representation equivalence | Unaffected — still one shared `MorphoDocument` per compile |
| Source identity | Strictly improved (§I) |
| Rejection of invalid candidates | `validate_candidate`'s reject path untouched |

### Test classification (109 existing tests)

- **Unchanged (all 109):** nothing in this proposal changes the
  *behavior* any existing test observes. `Version.id` values, validation
  outcomes, delta application results, and every backend's output for
  existing inputs are bit-for-bit identical, since `Sequence`/`Composite`
  only appear when the two new reserved edge types are present, and no
  existing fixture uses them for anything but their already-tested
  literal purpose (Phase 12's own `"precedes"` fixture would newly
  produce `Sequence` objects in its `MorphoDocument` — additive, not
  contradictory, since nothing currently asserts `ir_doc.sequences == ()`
  anywhere).
- **Adapted:** none required. (If `MorphoDocument`'s default-empty
  `sequences`/`composites` fields are added, `MorphoDocument() ==
  MorphoDocument()` equality checks already used throughout the test
  suite keep working unchanged, since dataclass equality includes the
  new fields on both sides symmetrically.)
- **Replaced:** none.
- **Newly required (before implementation, see §S):** tests for the
  `Sequence`/`Composite` recognition algorithm itself, the malformed-
  sequence `SemanticError` path, `StateDelta` retention, and the
  `compile_morpho` timestamp-forwarding fix — none of which exist today
  because none of this exists today.

---

## S. Required tests BEFORE implementation

In implementation order, mirroring §Q's rollout:

1. `StateDelta` is now constructed by `validate_candidate` and retrievable
   via `VersionStore.get_delta(version_id)`; genesis version's delta is
   `None`.
2. A `StateDelta`'s `changes` retain each `CandidateChange`'s original
   `ProvenanceInfo` (including `.timestamp`) unmodified.
3. `Version.provenance` is unchanged in shape and value for every
   existing acceptance scenario (regression guard against §I
   accidentally changing the summary field's semantics).
4. `compile_morpho` forwards a field's originating `ProvenanceInfo.timestamp`
   (via `VersionStore.get_delta`) into that `Entity`'s
   `ProvenanceRecord.timestamp`, when available.
5. A chain of `"precedes"` edges compiles to exactly one `Sequence` with
   correctly root-to-tail-ordered `member_ids`.
6. A `"precedes"` chain with a branch (out-degree > 1 on one node) raises
   `SemanticError`, does not silently pick one branch.
7. A `"contains"` edge set compiles to one `Composite` per source node,
   with correct direct-children `member_ids`.
8. Two-level nesting (`M contains P`, `P contains F`) produces two
   `Composite`s (`M` and `P`), each with the correct one-level
   `member_ids` — confirms recursion-by-traversal, not recursion-in-data.
9. `Sequence`/`Composite` recognition is deterministic across
   `PYTHONHASHSEED` values (same discipline as the existing
   `tests/test_versioning.py` cross-process check) — edge iteration order
   must never leak into `member_ids` ordering except via the edges'
   actual `"precedes"` semantics.
10. An entity that changes value, but whose structural edges are
    unchanged, produces a `Composite`/`Sequence` with the same id and
    `member_ids` across both versions (§H's identity table, made
    executable).
11. Existing backends (`compile_threejs`, `compile_svg`, `analyze`)
    produce unchanged output for `MorphoDocument`s with non-empty
    `sequences`/`composites` that they don't yet interpret — i.e.
    additive fields are provably ignorable, not merely assumed to be.
12. Full existing 109-test suite still passes unmodified, run as a
    regression gate, not rewritten to accommodate the change.

---

## T. Explicit list of things that should NOT be implemented yet

- `Matrix`/`Tensor` as distinct Morpho construct kinds (§F/§P show
  `Sequence`+`Composite` already suffice).
- A `REORDER`/`MOVE`/`PATCH_ARRAY` delta operation (§H/§K — correctness
  doesn't need it; no proven efficiency requirement yet either).
- A typed `Quantity`/unit-arithmetic object, or any external unit
  ontology reference (§L).
- Any change to `CanonicalState`, `Field`, `EdgeRecord`, `StateSchema`,
  or `Version.id`'s hash inputs (this entire investigation is designed
  to need none).
- Backend consumption of `Sequence`/`Composite` beyond what §M names as
  optional follow-ups (bounding boxes, hierarchy reuse) — ship the IR
  first, prove it, then decide per-backend.
- Rewriting `adapters/json_adapter.py`'s existing `__`-flattening
  behavior — the natural-id-plus-edges alternative (§H) is additive, not
  a replacement, and should not force a breaking change to Phase 12's
  already-tested adapter output.
- Anything from the frozen spec's own §23 list (still fully in force:
  no Kalman filters, no neural models, no physics simulation, no
  databases, no CRDTs, no ontology reasoning engine).
- Multi-writer `VersionStore` concurrency (§20 of the frozen spec,
  unaffected and unreopened by this investigation).

---

## U. Exact next implementation phase

**Phase 14 (proposed name): Provenance Retention + Structural Morpho
Primitives.** Concretely, in the order given in §Q, gated by the tests
in §S being written and passing before each corresponding piece of
implementation lands — matching how every prior phase in this project
was actually executed (tests as the gate, not as an afterthought).

---

## Architectural scorecard

Scored 1-5 (5 = best) across the requested criteria. Justification is
terse by design — the detailed reasoning is in §C-§M above; this table
is a summary index into it, not a replacement for it.

| Criterion | A: Structured | B: Pure inference | C: Hybrid (recommended) |
|---|---|---|---|
| Conceptual simplicity | 2 — new recursive concepts throughout core | 4 — nothing new, but the guessing is conceptually murky | **5** — two reserved strings, two flat dataclasses |
| Semantic clarity | 3 — structure is explicit but duplicated across layers | 2 — structure is inferred, not asserted | **5** — structure is exactly as explicit as any other edge |
| Identity stability | 3 — needs a new nested-identity scheme | 5 — nothing changes | **5** — falls out of existing I5, shown in §H |
| Provenance | 3 — more surface area, same underlying gap (§A) unless separately fixed | 3 — same gap, unaddressed | **5** — this proposal fixes the gap as a co-requirement |
| Deterministic serialization | 2 — recursive hash function is new, unproven | 5 — untouched | **5** — untouched (§J) |
| State-delta compatibility | 2 — needs new recursive delta ops | 5 — untouched | **5** — zero new ops needed (§K) |
| Validation | 2 — recursive schema needed | 5 — untouched | **5** — untouched |
| Queryability | 4 — structure queryable directly | 2 — must be re-inferred every time | **4** — queryable via Morpho, recompiled deterministically (cheap, since compile_morpho is already proven fast and pure) |
| Time-series support | 4 | 3 — inferred, fragile | **4** — explicit, proven pattern (§O) |
| Array/tensor support | 4 | 2 | **4** — proven sufficient without new constructs (§P) |
| Graph support | 4 | 5 — already this project's strongest area | **5** — unchanged, still strongest area |
| Backend independence | 3 — backends may need to understand new canonical shapes directly | 5 | **5** — new IR fields are optional per backend (§M) |
| Morpho compatibility | 2 — Morpho's role shrinks/duplicates canonical | 3 — Morpho does too much guessing | **5** — exactly the role Morpho was designed for (§G) |
| Simulation compatibility | 3 | 3 | **4** — `CandidateNextState` shape unaffected, structural facts available to a future simulation the same way any other canonical fact is |
| ML compatibility | 3 | 3 | **4** — same reasoning |
| Industrial applicability | 3 — powerful but risky to ship | 3 — works for the cases already proven, brittle beyond them | **4** — proven pattern extended, not a new one |
| Migration difficulty | 1 — touches core hashing/delta/schema | 5 — nothing to migrate | **5** — nothing to migrate (§Q) |
| Implementation complexity | 1 — large, core-invasive | 4 — small but the "guessing" logic itself is subtly complex to get right and keep deterministic | **4** — small, fully specified in §F |
| **Total (/90)** | **48** | **64** | **83** |

---

## Anti-pattern check

| # | Anti-pattern | Does the recommendation create it? | Why not |
|---|---|---|---|
| 1 | Universal ontology engine | No | Exactly two reserved relationship types, not an open vocabulary; no reasoning, no external ontology (§L rejects that explicitly) |
| 2 | Backend-specific semantic model | No | `Sequence`/`Composite` live in Morpho, consumed identically (or ignored) by every backend (§M) |
| 3 | Multiple sources of truth | No | Structure is compiled from canonical edges every time, never stored redundantly (§G) |
| 4 | Mutable canonical state | No | Nothing about `CanonicalState`'s immutability changes anywhere in this proposal |
| 5 | Representation-driven semantics | No | The reserved edge types are asserted at ingestion (a semantic act), not inferred from how something will be displayed |
| 6 | Unstable identities | No | §H shows every identity question resolves via existing I5, unchanged |
| 7 | Non-deterministic serialization | No | `canonical_content()` untouched; §S item 9 explicitly tests cross-seed determinism of the new recognition logic too |
| 8 | Provenance loss | No — the opposite: this proposal *fixes* an existing, real provenance-loss bug (§A findings 1-3, §I) |
| 9 | Hidden renderer dependencies | No | Structure recognition lives in `compile_morpho`, never in a backend, never in `renderer/index.html` |
| 10 | Agent-controlled canonical mutation | No | See Agent/AI boundary section below — unaffected, still enforced entirely by `validate_candidate` |
| 11 | Excessive abstraction | No | Two dataclasses, two reserved strings, zero new opcodes (§K) — the scorecard's complexity numbers reflect this directly |
| 12 | Premature distributed architecture | No | Single-writer `VersionStore` model untouched; §20's existing "out of scope" stance is not reopened |

---

## Agent / AI boundary

```
external producer (AI agent, optimizer, simulator, experiment, sensor,
                    database, knowledge graph)
      |
      v
candidate state  (CandidateDelta -- same shape regardless of producer)
      |
      v
validation gate  (validate_candidate -- unchanged, sole entry point)
      |
      v
canonical state  (Version -- immutable, content-addressed)
```

This proposal does not touch this boundary at all — it operates entirely
*downstream* of `validate_candidate` (in `compile_morpho`) and
*alongside* it (in `StateDelta` retention, which happens *after*
acceptance, not as part of the accept/reject decision). An AI agent
producing a candidate with `"contains"`/`"precedes"` edges is
indistinguishable, from `validate_candidate`'s point of view, from any
other candidate producer — it still must satisfy `StateSchema` and
`FieldConstraints` exactly as strictly as a manual edit (proven pattern,
Phase 12 §`test_ingested_data_violating_an_authored_constraint_is_still_rejected`).
**Agents remain unable to become authoritative state managers** under
this proposal, for the same reason they already are under the current
one: there is exactly one function capable of minting an accepted
`Version`, and this investigation does not add a second one.

---

## Final verdict

Every primitive in §F is fully specified (exact dataclass shapes, exact
recognition algorithm, exact error behavior for the malformed case).
Every required core-adjacent change in §I is fully specified (exact new
method signature, exact retention shape, exact backward-compatible
handling of the existing summary field). The migration order (§Q), test
list (§S), and explicit non-goals (§T) are concrete enough that another
engineer could implement Phase 14 from this document without making a
single open architectural judgment call — the judgment calls (A vs. B
vs. C, how many reserved edge types, whether to add new delta opcodes,
whether units need a typed object) were the actual subject of this
investigation and have been made, with reasoning, above.

**IMPLEMENTATION READY**
