# Retrieval Architecture — Phase 15

This document is Phase 15's required deliverable: the retrieval/context
boundary between SCOUT's evidence pool (`docs/SCOUT_ARCHITECTURE.md`)
and a future computational layer (`InquiryState`, still unimplemented).
It documents `retrieval/` — a new, deterministic, read-only package —
and nothing else changed: `core/`, `morpho/`, `adapters/`, `backends/`,
`runtime/`, and `evidence/`'s existing behavior are all untouched (the
one addition to `evidence/` is a new, pure `EvidencePool.fingerprint()`
method — see §Evidence versioning below).

## 0. The pipeline this phase completes

```
Evidence (evidence/, Phase "SCOUT")
     |
Trust Graph (evidence.trust_graph -- derived view, unchanged)
     |
RetrievalQuery (retrieval/query.py)              <-- NEW
     |
RetrievalEngine (retrieval/engine.py)             <-- NEW
     |
RetrievalResult (retrieval/result.py)              <-- NEW
     |
ContextPackage (retrieval/context.py)               <-- NEW
     |
InquirySeam (retrieval/seam.py)                       <-- NEW, deliberately minimal
     |
[future InquiryState -- NOT implemented this phase]
```

This is the layer `docs/PHASE_14_DATA_POOL_ARCHITECTURE.md` and
`docs/COMPUTATIONAL_COMMONS.md` both discussed only conceptually
("retrieval," "reusable context," "InquiryState") — Phase 15 is its
first real implementation, for the deterministic case only. No model,
no vector search, no external database, per this phase's explicit
constraints (§13 below).

## 1. What retrieval consumes — the exact existing objects

Investigated first, per this phase's own instruction not to invent a
parallel evidence model. Retrieval consumes exactly:

- `evidence.pool.EvidencePool` — read-only; every lookup already
  exposed (`get_referent`, `get_observation`, `get_record`,
  `get_document`, `get_source`, `all_referents`,
  `all_claimed_relationships`, `all_observations`,
  `relationships_touching`) is used as-is. The only new pool method,
  `fingerprint()`, is additive and itself read-only (§Evidence
  versioning).
- `evidence.trust_graph.build_trust_graph(pool)` — the existing derived
  graph view, used unmodified as the traversal substrate.
- `evidence.types.{Source, Document, Record, Observation, Referent,
  ClaimedRelationship}` — read, never constructed or mutated by
  `retrieval/`.

Nothing in `retrieval/` defines a competing `Entity`/`Relationship`/
`Observation` type. `docs/PHASE_14_DATA_POOL_ARCHITECTURE.md`'s own
naming-collision warning (avoid a second `Entity`, avoid a second
`Relationship`) is honored a second time here by simply not introducing
new object types for the same concepts at all.

## 2. Authoritative vs. derived vs. temporary objects

| Object | Kind | Mutable? | Authority |
|---|---|---|---|
| `CanonicalState`/`Version` | Authoritative | No (immutable, versioned) | Sole source of truth (unchanged, untouched by this phase) |
| `evidence.pool.EvidencePool` contents (`Source`/`Document`/.../`ClaimedRelationship`) | Authoritative (for evidence, not truth) | No (append-only) | The evidence record — uncertain, conflicting, never authoritative over `CanonicalState` |
| `evidence.trust_graph.TrustGraph` | Derived | N/A (recomputed, never stored) | A view, not a store — `docs/SCOUT_ARCHITECTURE.md` §4 |
| `retrieval.query.RetrievalQuery` | Derived (content-addressed from its own fields) | No | Not authoritative over anything — a request |
| `retrieval.result.RetrievalResult` | Derived (references into the pool only) | No | Not authoritative — a reproducible answer to one query, against one evidence snapshot |
| `retrieval.context.ContextPackage` | Derived (composed from one or more results) | No | Not authoritative — a reproducible *selection*, never a copy |
| `retrieval.seam.InquirySeam` | Temporary marker | No (itself immutable — but represents the *opening* of a temporary computation) | Not authoritative — a seam, not a store |
| future `InquiryState` | Temporary, disposable | Yes (explicitly, per design) | Never authoritative — the eventual, still-unimplemented computational workspace |

The one property every "derived"/"temporary" row shares: none of them
can ever become authoritative by construction, because none of them
hold anything but ids referencing the authoritative rows above them.
There is no code path anywhere in `retrieval/` that writes a
`RetrievalResult`'s or `ContextPackage`'s referenced ids back into
`evidence/` or `core.canonical` — checked by
`tests/test_retrieval_boundaries.py`.

## 3. The authority boundary, explicitly

```
retrieval/  ---->  evidence/  (read-only: get_*, all_*, fingerprint())
retrieval/  ---->  core.canonical.*  NEVER (no import at all)
```

Enforced by `tests/test_retrieval_boundaries.py`:
- no import of `backends/`, `renderer/`, or `runtime/`;
- no import of `core.canonical.validation`, and no import of
  `validate_candidate`/`make_version`/`create_genesis_version` by name;
- no AST `Call` node anywhere in `retrieval/` whose called name is
  `validate_candidate`;
- no AST `Call` node anywhere in `retrieval/` whose method name is any
  of the pool's `put_*` mutators — retrieval cannot write to the
  evidence pool either, not just to `core.canonical`;
- no import of `Version`/`CanonicalState` by name;
- and, symmetrically, `core/` never imports `retrieval/`.

## 4. RetrievalQuery — minimum representation

```python
RetrievalQuery(
    id,                      # content_hash of everything below
    entity_natural_keys,      # exact entity lookup / traversal seeds
    relationship_types,        # restrict traversed/returned edges; () = no restriction
    source_kinds,                # restrict returned Observations by Source.kind
    epistemic_statuses,            # restrict by retrieval.epistemic classification
    text_terms,                      # substring match over Observation.content values
    traversal_depth,                   # bounded BFS depth from the seeds
    limit,                                # cap on returned Referent count (None = unbounded)
)
```

Every field considered by the prompt's own sketch (`query_id`, entities,
relationship types, source filters, epistemic-status filters, metadata
filters, traversal depth, text terms, result limit) is present except a
generic "metadata filters" catch-all — investigated and rejected as
premature: nothing in `evidence.types` currently exposes free-form
metadata beyond what `source_kinds`/`epistemic_statuses`/`text_terms`
already cover, and adding an open-ended filter with no concrete
consumer would be exactly the "speculative infrastructure" this phase
was told not to introduce. `id` is always derived
(`retrieval.query.make_retrieval_query`), never caller-supplied — same
discipline as `make_version`/every `evidence.types.make_*` factory —
and every list field is deduplicated and sorted before hashing, so two
queries expressing the same request in a different order or with
accidental repeats get the identical `id`
(`tests/test_retrieval_query.py::test_query_identity_ignores_input_order_and_duplicates`).

## 5. RetrievalResult — what it answers

| Question | Answered by |
|---|---|
| What was queried? | `query_id` (dereference the `RetrievalQuery` if the caller still has it) |
| What was returned? | `referent_ids`/`relationship_ids`/`observation_ids`/`source_ids` |
| Why was it returned? | `filters_applied` (human-readable) + `traversal_depth` |
| Which source versions were used? | `evidence_version_id` (`EvidencePool.fingerprint()` at query time) |
| Which graph entities were involved? | `referent_ids` |
| Which relationships were traversed? | `relationship_ids` |
| What retrieval configuration was used? | `retrieval_method` + `filters_applied` + `traversal_depth` |
| Can the result be reproduced? | Yes — `result.id` is a content hash of every field above; recomputing the identical query against the identical evidence snapshot always yields the identical `id` |

`RetrievalResult` stores only sorted tuples of ids — never a copied
`Referent`/`Observation`. "Ordering is not ranking": `ordering` is
always `"sorted_by_id"` in this phase's implementation, stated
explicitly rather than left implicit, because id-sort is an arbitrary,
stable tiebreaker, not a relevance/quality signal — no ranking model
exists in this codebase (consistent with `evidence.fep_interface`'s own
refusal to fabricate a `priority` without real inputs).

### Evidence versioning

`EvidencePool.fingerprint()` (the one new method added to `evidence/`
this phase) is a content hash of the sorted id sets of every object
category the pool holds. Two pools with identical contents fingerprint
identically regardless of insertion order; any change to the pool —
even one unrelated to a given query's visible result — changes the
fingerprint. This is deliberately coarse: a `RetrievalResult`'s `id`
therefore changes whenever the *pool* changes, even if the specific
referents/relationships/observations that satisfy one narrow query
happen to be identical before and after
(`tests/test_retrieval_engine.py::test_source_version_sensitivity`).
This was a specific, literal requirement (§7 of the phase prompt: "the
system must be able to distinguish the new retrieval from the old one")
and is met by including the whole-pool fingerprint in the result's
identity hash, not just the returned id sets.

## 6. ContextPackage

```python
ContextPackage(
    id,                       # content_hash of everything below
    retrieval_result_ids,      # which RetrievalResults contributed
    referent_ids,                # union, deduplicated, sorted
    relationship_ids,
    observation_ids,
    source_ids,
    evidence_version_ids,          # every DISTINCT evidence_version_id among contributors
)
```

`ContextPackage` is not `CanonicalState` and not a new authoritative
store — `retrieval.context.build_context_package` never copies a
`Referent`/`Observation`/etc., it only unions and sorts id sets from one
or more `RetrievalResult`s. Dereferencing (`retrieval.context.referents`/
`.relationships`/`.observations`/`.sources`) always returns the exact
same object instances already stored in `evidence/`
(`tests/test_context_package.py::test_context_package_holds_references_not_copies`
asserts `is`, not just `==`).

**Composition across different evidence versions is recorded, not
hidden.** If the contributing `RetrievalResult`s were queried against
different pool states, `evidence_version_ids` has more than one entry
— the caller can see that directly, rather than the `ContextPackage`
silently presenting a blend of two snapshots as if it were one coherent
moment (`tests/test_context_package.py::test_composition_across_different_evidence_versions_is_recorded_not_hidden`).

## 7. Reproducibility, precisely

Both required equalities are tested directly, not just asserted in
prose:

```
same evidence version + same RetrievalQuery + same retrieval configuration
    => same RetrievalResult.id
    (tests/test_retrieval_engine.py::test_retrieval_result_is_deterministic_across_calls)

same RetrievalResult(s)
    => same ContextPackage.id
    (tests/test_context_package.py::test_context_package_reproducible_from_same_result)
```

Both are additionally checked across three different `PYTHONHASHSEED`
values in separate subprocesses
(`tests/test_retrieval_engine.py::test_retrieval_result_deterministic_across_hash_seeds`),
the same discipline `tests/test_versioning.py` and
`tests/test_trust_graph.py` already established — an in-process test
cannot exercise `PYTHONHASHSEED` at all, since Python only applies it at
interpreter startup.

## 8. Minimum retrieval capabilities — what is and isn't implemented

| Capability | Implemented? | How |
|---|---|---|
| Exact entity lookup | Yes | `entity_natural_keys` matched against `Referent.natural_key` |
| Exact relationship lookup | Yes | via `relationship_types` filter + traversal at `depth=0`/`1` |
| Source/document lookup | Yes | `source_kinds` filter; `source_ids` in every result |
| Field/property lookup | Yes | `text_terms` substring match over `Observation.content` values |
| Provenance filtering | Yes | `evidence_version_id` per result; full trace via dereferencing (§Provenance below) |
| Epistemic-status filtering | Yes | `epistemic_statuses`, via `retrieval.epistemic.classify_epistemic_status` — reuses `docs/COMPUTATIONAL_COMMONS.md` §K's taxonomy, does not invent a second one |
| Simple metadata filtering | Yes, narrowly | `source_kinds` is the one metadata filter implemented; see §4 on why a generic filter was not added |
| Graph-neighborhood traversal | Yes | bounded BFS over the Trust Graph, `retrieval.engine._bounded_neighborhood` |
| Bounded traversal depth | Yes | `traversal_depth`, enforced (0 = seeds only) |
| Simple text/token matching | Yes | `text_terms`, case-insensitive substring |
| Embeddings | **No** | explicitly out of scope this phase |
| Vector search | **No** | explicitly out of scope this phase |
| Semantic/LLM retrieval | **No** | explicitly out of scope this phase — see §Future seam |

## 9. Provenance preservation

Traced end-to-end and tested
(`tests/test_context_package.py::test_provenance_trace_from_context_to_source`):

```
ContextPackage
     |
Referent (retrieval.context.referents)
     |
ClaimedRelationship (retrieval.context.relationships, touching that Referent)
     |
Observation (relationship.observation_id -> retrieval.context.observations)
     |
Record (observation.record_ids[0] -> pool.get_record)
     |
Document (record.document_id -> pool.get_document)
     |
Source (document.source_id -> pool.get_source)
```

Every hop is a plain id dereference against the same, unmodified
`evidence/` accessors SCOUT already used — `retrieval/` adds no new
provenance mechanism, it exercises the one that already existed.

## 10. Retrieval ≠ reasoning — the hard boundary, as implemented

`retrieval.engine.DeterministicRetrievalEngine.retrieve` performs
exactly: seed lookup, bounded BFS, set intersection/union for filters,
sort. There is no branch anywhere in it that constructs a new
`Observation`, a new `ClaimedRelationship`, or any object not already
present in the pool it was given. It cannot infer a new claim, because
it has no code path that calls any `evidence.types.make_*` factory or
any `evidence.admission.admit_*` function at all — confirmed by
`tests/test_retrieval_boundaries.py::test_retrieval_never_writes_to_the_evidence_pool`
and, structurally, by `retrieval/engine.py` never importing
`evidence.admission` or `evidence.types.make_*` in the first place.

## 11. The InquiryState seam — deliberately not InquiryState

`retrieval.seam.InquirySeam` holds exactly two fields: `context_id` and
`opened_at`. It has no mutable slots, no hypothesis storage, no
computation. It exists only to prove the boundary between
`ContextPackage` (selected persistent reality) and a future
`InquiryState` (a temporary computational world built from that
reality) is already representable in code, without committing to
InquiryState's eventual shape — exactly what §12 of the phase prompt
asked for and no more. What remains **intentionally deferred**:

- Any mutable inquiry workspace (hypotheses, derived quantities,
  constraints, candidate regions, annotations — all of §5's worked
  example in `docs/COMPUTATIONAL_COMMONS.md`).
- Any promotion path from an inquiry's output back toward
  `evidence.types.Referent`/`ClaimedRelationship` or, further
  upstream, a `CandidateDelta`.
- Any persistence for `InquirySeam`/`InquiryState` beyond one Python
  object's lifetime — no store, no versioning, no reproducibility
  guarantee for whatever happens *after* the seam is opened (only the
  `ContextPackage` it was opened from is reproducible).

## 12. Compute amortization — measured, not claimed

`tests/test_retrieval_amortization.py::test_extraction_runs_once_regardless_of_later_retrieval_count`
wraps `scout.extraction.DeterministicExtractor` in a call-counting
subclass, runs SCOUT once (one `extract()` call per `Record`), then
issues five independent `RetrievalQuery`s and composes their results
into one `ContextPackage` — and asserts the extractor's call count is
unchanged afterward. This is the one thing actually measured in this
phase: **extraction is not re-invoked by retrieval, at all, regardless
of how many queries run against the same pool.** No throughput, latency,
or cost number is claimed anywhere in this document or its tests — per
this phase's explicit instruction not to fabricate performance claims,
only what is actually measurable (a call count) is reported.

The architectural claim this supports: expensive work (source
acquisition, extraction) happens once per `Record`, at SCOUT time;
retrieval and context construction thereafter are pure functions over
already-computed, already-stored data — repeatable at whatever
frequency a future computation layer needs, without paying extraction's
cost again.

## 13. No database yet

Confirmed by inspection, not just by instruction: `retrieval/` imports
nothing beyond `evidence/` and the Python standard library. No
Neo4j/PostgreSQL/DuckDB/Elasticsearch/Qdrant/Milvus/Weaviate/Pinecone/
RDF-store/warehouse dependency exists anywhere in this repository.
Traversal is a linear BFS over `EvidencePool.all_referents()`/
`all_claimed_relationships()` — adequate at fixture scale, explicitly
not a real index, exactly matching
`docs/PHASE_14_DATA_POOL_ARCHITECTURE.md` §R step 6's own sequencing
("indexes are derived and can be rebuilt; getting the underlying record
shapes right first avoids re-deriving a wrong index twice").

## 14. Future semantic/vector retrieval seam

```python
class RetrievalEngine(Protocol):
    def retrieve(self, pool: EvidencePool, query: RetrievalQuery) -> RetrievalResult: ...
```

The entire seam is this one Protocol (`retrieval/engine.py`). A future
`SemanticRetrieval`, `VectorRetrieval`, `GraphRetrieval`, or
`HybridRetrieval` engine implements it and must return the same
`RetrievalResult` shape — proven, not just asserted, by
`tests/test_retrieval_engine.py::test_second_engine_implementation_can_satisfy_the_same_protocol`,
which implements a second, trivial engine (`method_name =
"stub:always_empty_v1"`) and shows it produces a structurally valid
result. No stub classes for the unimplemented engine kinds were added —
per this phase's "do not introduce speculative infrastructure" rule,
the Protocol itself is the extension boundary; five empty subclasses
would add names without adding a capability. A future Mistral or
embedding-based engine improves *which* referents/observations a query
returns; it does not get to redefine what a `RetrievalResult` or
`ContextPackage` means — that contract is fixed by this phase.

## 15. Verification

`python3 -m pytest -q` — 213 passed (174 pre-existing + 39 new: 6 query,
16 engine, 9 context package, 2 amortization, 6 boundary). No file
under `core/`, `morpho/`, `adapters/`, `backends/`, `runtime/`, or any
existing `evidence/`/`scout/` behavior was modified — the only change to
`evidence/` is the additive, read-only `EvidencePool.fingerprint()`
method. `git status --short` (checked before commit) shows only new
files plus the two documentation pointer updates in `README.md`/
`docs/ARCHITECTURE.md` and the one line added to `evidence/pool.py`.
