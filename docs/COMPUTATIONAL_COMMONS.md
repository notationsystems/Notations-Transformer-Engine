# Computational Commons / Information Substrate

Status: **research only**. No implementation file was modified to
produce this document. This investigation extends, and repeatedly
cross-references rather than re-derives, two prior research documents
already in this repository:

- `docs/PHASE_13_ARCHITECTURE_INVESTIGATION.md` — the structured-state
  primitives (`Sequence`, `Composite`, reserved edge types) that would
  eventually let `CanonicalState`/Morpho represent richer structure.
- `docs/PHASE_14_DATA_POOL_ARCHITECTURE.md` — the evidence/warehouse
  layer (`Document`, `Record`, `Observation`, `Referent`,
  `ClaimedRelationship`, `Derived value`) that sits upstream of the
  existing adapter boundary.

This document does not repeat those two documents' reasoning; it builds
one more layer on top and answers the one question they didn't:
**what sits between "validated evidence" and "an inquiry actively
reasoning about it," and how does that avoid becoming an agent swarm.**

---

## A. Architectural model

```
EXTERNAL WORLD
      |
DATA ACQUISITION                              (docs/PHASE_14, S1-S2)
      |
EVIDENCE / DATA WAREHOUSE                     (docs/PHASE_14 in full --
      |                                        Document/Record/Observation/
      |                                        Referent/ClaimedRelationship/
      |                                        Derived value, conflicts coexist)
      | extraction / normalization / promotion gate (NEW, this document)
      v
IMMUTABLE KNOWLEDGE GRAPH                     (NEW: the PROMOTED, identity-
      |                                        resolved, versioned subset of
      |                                        the same Phase-14 object types
      |                                        -- not a new type system)
      | retrieval (read-only, by reference)
      v
INQUIRY STATE                                 (NEW, conceptual only --
      |                                        ephemeral, mutable, disposable,
      |                                        non-authoritative workspace)
      | operators (retrieval / extraction / entity-resolution / classification /
      |            math / simulation / hypothesis-generation / validation-support)
      | -- read Commons + InquiryState, write ONLY to InquiryState --
      v
derived results / hypotheses / candidates / annotations
      |
      | explicit promotion (reuses the EXISTING, UNCHANGED
      |                      Derived-value -> CandidateDelta -> validate_candidate
      |                      path from docs/PHASE_14 S:O)
      v
VALIDATION GATE                               (existing, unchanged: validate_candidate)
      |
      v
CANONICAL STATE                               (existing, unchanged: Version/CanonicalState,
      |                                        schema-scoped, narrow, one domain problem)
      v
MORPHO IR -> Three.js / SVG / Graph            (existing, unchanged)
```

**The one new architectural claim this document makes, precisely:** the
"Immutable Knowledge Graph" is not a seventh new type system bolted onto
Phase 14's six. It is a **promotion state plus an immutability
guarantee** applied to the *same* `Referent` / `ClaimedRelationship` /
`Observation` / `Derived value` objects Phase 14 already defines. An
object in the Warehouse can be duplicated, conflicting, or unresolved; the
identical object, once it crosses a *separate, evidentiary* promotion
gate (not `validate_candidate` — see §E), becomes immutable, gets a
stable citable identity, and is what an `InquiryState` is allowed to
retrieve *by reference* without re-verifying it every time. This is the
answer to "do not collapse Warehouse and Knowledge Graph" that avoids
also creating a second, parallel object model to maintain.

---

## B. Layer definitions

| Layer | What it is | Authoritative? | Mutable? | Bound to a schema? |
|---|---|---|---|---|
| Evidence / Warehouse | Everything Phase 14 already defines: raw and extracted evidence, duplicated, conflicting, unresolved | No | Append-only (new objects supersede, nothing is edited in place — Phase 14 discipline, unchanged) | No |
| Immutable Knowledge Graph | The promoted, identity-resolved, provenance-complete subset of Warehouse objects | For *evidentiary* facts, yes — but not the same authority as CanonicalState (§N) | No — immutable once promoted; a correction is a new object that supersedes, never an edit | No — general-purpose, spans arbitrarily many domains/materials/inquiries |
| InquiryState | A temporary workspace for one inquiry | **No, never** | Yes, freely | No — may contain notation, hypotheses, half-finished calculations |
| CandidateDelta | Existing, unchanged | No — a proposal | N/A (constructed fresh each time) | Yes — targets one specific `StateSchema` |
| CanonicalState / Version | Existing, unchanged | **Yes, the sole authority for its schema's domain** | No — immutable, versioned | Yes — exactly one `StateSchema` |
| Morpho IR | Existing, unchanged | No — compiled, not stored | No | N/A |

---

## C. Data-flow diagram

See §A — the diagram there *is* the data-flow diagram, annotated with
which parts are existing/unchanged vs. new-this-document vs. new-from-
Phase-14. Repeated here only as a one-line summary of direction:
information flows strictly downward (Warehouse → Graph → InquiryState →
Candidate → Canonical); nothing flows back upward except by the single,
explicit, gated act named "promotion," which appears exactly twice
(Warehouse→Graph, and InquiryState-derivation→Candidate) and is never
implicit.

---

## D. Evidence → Warehouse → Graph → InquiryState → Validation lifecycle

Worked as a single trace, in the language already established:

```
1. A Document is acquired (docs/PHASE_14 S:C) -> Records -> Observations
   -> NormalizedRecords, all Warehouse-resident, all conflict-tolerant.

2. A promotion gate (NEW, S:E) evaluates a Referent/Observation/
   ClaimedRelationship for: identity-resolution confidence, provenance
   completeness, non-duplication. If it passes, the SAME object (not a
   copy) is marked promoted and becomes part of the Immutable Knowledge
   Graph -- citable, stable, no longer editable in place.

3. An inquiry begins. An InquiryState is created (S:L). It RETRIEVES
   (read-only, by reference -- never copies the underlying data)
   relevant Graph nodes/edges, and optionally also live Warehouse
   evidence not yet promoted (clearly tagged as such, never silently
   treated as equivalent to promoted evidence).

4. Operators (S:H) run against the InquiryState: they read Commons data
   and the InquiryState's current contents, and write ONLY new entries
   into the InquiryState (working Observations, working
   ClaimedRelationships, Derived-value-in-progress, notes, hypotheses).
   Nothing here is authoritative; contradictory hypotheses may coexist.

5. When a Derived value inside the InquiryState is judged ready, it is
   handed to the EXISTING, UNCHANGED promotion path already specified in
   docs/PHASE_14 S:O: Derived value -> (existing) adapter ->
   CandidateDelta -> (existing) validate_candidate.

6. validate_candidate accepts or rejects exactly as it does today for
   any other candidate source (Phase 12's JSON/CSV adapters, Phase 9's
   simulation/neural interfaces). On acceptance, a new Version exists.
   The InquiryState that produced the winning Derived value may now be
   closed/archived (S:F) -- it was never authoritative and does not need
   to persist for the CanonicalState update to be valid.
```

---

## E. Responsibility matrix

| Responsibility | Owner |
|---|---|
| Store raw evidence, tolerate duplication/conflict | Warehouse |
| Resolve identity, guarantee immutability, assign stable citable ids | Knowledge Graph promotion gate |
| Answer "what do we already know" cheaply | Knowledge Graph + its indexes |
| Hold exploratory, possibly-wrong, possibly-contradictory working material | InquiryState |
| Run retrieval/extraction/math/simulation/hypothesis-generation | Operators (read Commons + InquiryState, write only InquiryState) |
| Decide a Derived value is ready to propose | Whatever process closes the InquiryState (human, or later a reviewed policy — not a bare model call) |
| Enforce schema/constraint correctness for one domain | `validate_candidate` — **unchanged, still the only place a `Version` is minted** |
| Hold the one narrow, authoritative "current state" for a bounded domain problem | `CanonicalState` — **unchanged** |
| Compile validated state into backend-consumable structure | Morpho — **unchanged, still scoped to `CanonicalState` only (§I)** |

---

## F. Persistence vs. ephemeral-state matrix

| Object | Persistence | Versioned? | Deletable? |
|---|---|---|---|
| Document, Record | Persistent, append-only | No (immutable by construction, per Phase 14) | Never — archived only |
| Warehouse Observation/ClaimedRelationship (unpromoted) | Persistent | No | Superseded, not deleted |
| Knowledge Graph (promoted) object | Persistent, **immutable** | Implicitly — a correction is a new object that supersedes | Never |
| InquiryState | **Ephemeral by default** — not required to persist at all for the architecture to be correct | No | Yes, freely — disposal is the expected end state for most InquiryStates |
| InquiryState trace/log (optional) | May optionally be archived for audit/reproducibility (see nuance below) | N/A | Yes |
| CandidateDelta | Transient — exists only for the duration of one `validate_candidate` call | N/A | N/A (never stored as itself) |
| StateDelta (per docs/PHASE_13 S:I fix) | Persistent, retained per accepted Version | Implicitly, one per Version | No |
| Version / CanonicalState | Persistent, immutable, versioned | Yes — the whole point | Never |

**Nuance on "ephemeral":** an InquiryState not persisting *as an
authoritative object* does not mean its trace is worthless. Optionally
logging "what was retrieved, which operators ran, what was concluded"
supports later reproducibility and audit ("why did we promote this
Derived value") without making the InquiryState itself authoritative —
these are independent properties. This document does not require such
logging; it only notes that adding it later would not contradict
anything above.

---

## G. Compute / energy analysis

Classifying real operations against the categories requested:

| Operation | Amortizable / one-time | Incremental | Query-time | Cacheable | Typical cost |
|---|---|---|---|---|---|
| Document acquisition | Yes — per document | — | — | Yes (content-addressed, Phase 14) | Moderate (network + storage) |
| Extraction (parse a table, NER, OCR) | **Yes — per document, paid once, reused by every future inquiry** | — | — | Yes | Moderate-to-high, especially if model-assisted |
| Normalization | Yes — per Observation | — | — | Yes | Low-to-moderate |
| Identity resolution / promotion | Mostly one-time; re-evaluated only when new conflicting evidence arrives | Incremental as evidence accumulates | — | Yes (the promoted result) | Moderate (unresolved methodology, docs/PHASE_14 S) |
| Index maintenance (warehouse + graph, docs/PHASE_14 S:G/H) | — | **Incremental**, updated per new record | — | The index itself is the cache | Low per update |
| Retrieval into an InquiryState | — | — | **Query-time** | The underlying Graph data is reused; the specific retrieval isn't, but is cheap by construction (index lookup) | **Cheap** |
| InquiryState reasoning (model calls, calculations, hypothesis generation) | — | — | Query-time, inquiry-specific | Only the *artifacts it produces* (a Derived value), not the reasoning process itself, unless the exact same sub-question recurs | **Expensive** |
| Simulation runs | Often one-time per configuration | — | — | Yes, once promoted | High |
| `validate_candidate` | — | — | Query-time | N/A — deterministic and already fast (109 tests run in well under a second) | **Cheap** |

**Architecture A vs. B, made concrete, not merely asserted:**
Architecture A pays extraction + retrieval-equivalent-effort + reasoning
cost on **every** inquiry — cost scales roughly with
`inquiries × sources_touched`. Architecture B pays extraction cost
**once per source** (amortized — cost scales with `sources`, not
`inquiries × sources`), pays retrieval cost cheaply per inquiry (index
lookup, not re-extraction), and pays full reasoning cost only for the
**novel** part of each inquiry — and even that shrinks over time, because
a Derived value, once promoted, becomes cheap retrieval for the *next*
inquiry that needs the same fact instead of a second expensive
recomputation. This is the literal mechanism behind "build information
once, reuse it many times" — not a slogan, a consequence of where each
operation in the table above sits.

**Honest caveat (see also §P):** this asymptotic argument only pays off
under **reuse**. A genuinely one-off inquiry that will never recur gets
none of the amortization benefit and pays the *same* extraction/retrieval/
reasoning cost as Architecture A, plus the (small, but nonzero) overhead
of writing through the promotion machinery. The architecture should not
force every inquiry through full Warehouse/Graph promotion regardless of
expected reuse value — see §P.

---

## H. Agent / model role analysis

**Operators, not agents-with-memory.** Each operator is modeled as a
function: `Operator(inputs: Commons references + current InquiryState) ->
InquiryState delta`. It reads the Commons (Warehouse/Graph, read-only)
and the current InquiryState; it writes **only** to the InquiryState —
never directly to Warehouse, Graph, or CanonicalState. This single rule
is what makes "no continuous agent-to-agent messaging required" true by
construction rather than by convention: two operators never need to talk
to each other, because they coordinate entirely through the shared
InquiryState (and, further upstream, the shared Commons) — the same
"shared information → local working state → independent computation"
shape the prompt asks for, not `Agent A ↔ Agent B ↔ Agent C`.

| Operator | Reads | Writes |
|---|---|---|
| Retrieval | Knowledge Graph, indexes | InquiryState (retrieved refs) |
| Extraction | Warehouse Documents/Records | Warehouse Observations (this one operator *does* write to the Warehouse, not the InquiryState — extraction is a Warehouse-layer act per §D step 1, not an inquiry-layer act; listed here because the prompt names it as an operator, but its target differs from the rest) |
| Entity-resolution | Warehouse/Graph Referents | Proposed `same_as` `ClaimedRelationship`s (Warehouse, pending promotion — docs/PHASE_14 S) |
| Classification | InquiryState contents, or Warehouse Documents | InquiryState (labels/annotations) |
| Mathematical analysis | InquiryState (retrieved values) | InquiryState (derived quantities) |
| Simulation | InquiryState (configuration) | InquiryState (results — these ARE evidence, just inquiry-scoped until promoted) |
| Hypothesis-generation | InquiryState | InquiryState (hypotheses, explicitly tagged `epistemic_status="hypothesized"`, §K) |
| Validation-support | InquiryState, Commons | InquiryState (an argument/checklist for or against promoting a Derived value — **not** the promotion decision itself, and never a bypass of `validate_candidate`) |

**Multiple models operating independently over the same substrate:**
yes, without continuous messaging, provided each operates over its own
InquiryState (or a well-defined, explicitly shared one) and reads the
same immutable Knowledge Graph — because the Graph is immutable once
promoted, two independent readers can never observe it changing
mid-computation, which is exactly the property that makes concurrent,
uncoordinated reads safe without a coordination protocol. This is the
same content-addressed-immutability discipline `Version` already relies
on, one layer up.

---

## I. Storage architecture analysis

Extends `docs/PHASE_14_DATA_POOL_ARCHITECTURE.md` §I/§L rather than
re-deriving it; answers the design questions this new document adds:

| Data kind | Where it lives | Why |
|---|---|---|
| Documents, raw large numerical arrays (trajectories, sensor dumps) | Content-addressed blob store (unchanged from Phase 14) | Large, mostly-opaque, immutable once acquired — pulling a trajectory apart into millions of individual Observations would be exactly the "everything forced into a graph" anti-pattern design question 18 warns against. The array is *itself* the evidence object; a `Derived value` later extracts specific scalar summaries from it on demand. |
| Records, Observations, NormalizedRecords, Referents, ClaimedRelationships, Derived values | Structured record store (unchanged from Phase 14 — files/SQLite at small scale, a real store later) | — |
| Graph traversal (relationship/provenance navigation) | A derived index over the structured store's own reference fields (unchanged from Phase 14 §G) — **not** forced into a relational join model | Answers design question 19 directly: graph reasoning does not require a relational database, because the graph is a *view*, not primary storage. |
| Numeric/analytical queries (ranges, aggregation) | A derived warehouse-style/columnar index (unchanged from Phase 14 §H) | — |
| Embeddings / similarity search | **New answer this document adds:** a separate, optional index alongside (not instead of) the structured store — relevant to exactly one query type identified in Phase 14 §L ("materials processed under similar conditions") and to literature/document discovery generally. Not required for anything else in this document. | Keeps a genuinely different capability (unstructured similarity) from leaking into the structured/graph indexes that don't need it. |
| InquiryState | In-memory, or a lightweight scratch file/log if persistence-for-audit is wanted (§F) — **not** a new storage subsystem | Consistent with design question 20's answer, §L below. |

---

## J. Provenance model

Extends Phase 14 §D by exactly one hop, and one new field:

```
Document -> Record -> Observation -> NormalizedRecord         (Phase 14, unchanged)
    -> [promotion gate, NEW] -> Knowledge Graph object          (NEW: adds
         promoted_at, promoted_by, promotion_method fields --
         the SAME discipline as everything else: append fields
         at the new hop, never rewrite the hops before it)
    -> [retrieved into an InquiryState, by reference, NEW] -> InquiryState entry
         (records only: which InquiryState, when, for what stated goal --
         the retrieval itself is provenance-worthy, since "why was this
         fact pulled into this inquiry" matters for audit)
    -> [promotion, EXISTING] -> CandidateChange.provenance.source =
         "knowledge_graph:<promoted_object_id>" (same string-convention
         mechanism Phase 12 and Phase 14 both already use — no core
         change, still)
    -> Version.provenance / StateDelta (EXISTING, plus Phase 13's fix)
```

Walking backward from a `Version`'s field to "page 17, table 4, row 8"
now has **one additional, optional hop** (through the promotion record)
but is otherwise exactly the query Phase 14 §L already named as the
validating use case for its provenance model. Nothing about that model
needed to change — it only needed one more link appended, which is
exactly what "append, never rewrite" predicts should be possible.

---

## K. Epistemic-status model

A small, closed vocabulary — deliberately not open-ended, per "the
smallest clean representation":

```
EpistemicStatus = Literal[
    "observed",      # a direct, minimally-processed measurement or reading
    "extracted",      # pulled from a document/source via parsing (human or automated)
    "inferred",         # derived via reasoning/computation from other facts, not a raw source
    "hypothesized",       # a proposed, not-yet-tested explanation or prediction
    "simulated",             # produced by executing a physics-based simulation
    "predicted",               # produced by a learned/ML model (distinct from simulated)
    "validated",                 # has crossed validate_candidate and is now canonical
]
```

This is **not a new mechanism invented from scratch** — it is a
deliberate generalization of the *existing* `MorphoRelation.is_canonical`
/ `inference_status: Literal["explicit", "inferred"]` distinction (§11 of
the frozen spec, already implemented and tested). `"validated"`
corresponds exactly to the existing `is_canonical=True` case; every other
value in this 7-way taxonomy corresponds to the existing broader
`"inferred"` case, refined enough to be useful across the Warehouse/
Graph/InquiryState layers where a flat binary is too coarse (an
`"observed"` Warehouse Observation and a `"hypothesized"` InquiryState
guess are both, today, simply "not canonical" — this taxonomy lets the
system say *which kind* of not-yet-canonical something is, without
touching the existing binary distinction at the Morpho boundary at all).

Every pool/graph/InquiryState object defined in this document and in
Phase 14 carries exactly one `epistemic_status` value. It is set once at
creation and never silently changed — a status transition (e.g.
`hypothesized` → `validated`) happens only by an object being
**superseded** by a new object with the new status and a `derived_from`/
`promoted_from` link back to the old one, the same "append, never
mutate" discipline used everywhere else in this architecture.

---

## L. InquiryState conceptual schema

**Conceptual only — not implemented this phase**, per the stop
condition. Sketched precisely enough that a future implementer has no
open questions about its *shape*, while its *storage mechanism* is
deliberately left as "whatever is convenient" (§I, §Q):

```python
# CONCEPTUAL SKETCH ONLY -- not implemented, no file created for this

InquiryState:
    id                            # ephemeral identifier; NOT content-addressed,
                                     # NOT versioned like a Version
    created_at
    goal: str                      # free text -- why this inquiry exists
    status: "open" | "closed" | "abandoned" | "promoted"

    retrieved_refs: [ ObjectRef ]   # references BY ID into Warehouse/Graph --
                                      # never copies; read-only; may include
                                      # explicitly-tagged not-yet-promoted
                                      # Warehouse evidence, distinguished from
                                      # promoted Graph references

    working_observations: [ Observation ]        # inquiry-local, epistemic_status
    working_relationships: [ ClaimedRelationship ] # in {inferred, hypothesized,
                                                      # simulated, predicted}
    derivations: [ Derived value ]                 # in-progress; the ONLY thing
                                                      # eligible for promotion (§D)
    notes: [ free-form ]                             # no schema -- mathematical
                                                        # notation, sketches,
                                                        # assumptions, anything
    operator_log: [ (operator, inputs, outputs, timestamp) ]  # optional, for
                                                                 # audit (§F nuance)
```

Every field except `id`/`created_at`/`goal`/`status` is optional and
freely mutable. Nothing in this schema is ever read by
`validate_candidate`, `compile_morpho`, or any backend — the *only*
path out of an `InquiryState` into anything persistent-and-authoritative
is one `derivations` entry being handed to the existing promotion path
(§D step 5), at which point it stops being InquiryState content and
becomes an ordinary `CandidateDelta`.

---

## M. Materials-domain example (FEP processing conditions)

Inquiry: *"Find promising FEP processing conditions associated with
viscosity, molecular weight, temperature, shear rate, and measured
mechanical properties."*

```
EXISTING EVIDENCE (Warehouse, per docs/PHASE_14 S:M):
  3 papers' worth of viscosity Observations at various temperatures,
  conflicting (1200/1250/1280 Pa.s at "260 C"), each with full
  provenance. Not yet all promoted.

GRAPH KNOWLEDGE (promoted subset):
  - Referent "FEP" (identity-resolved across the 3 papers -- an
    unresolved methodology, docs/PHASE_14 S, assumed already done for
    this example)
  - A promoted Derived value: median viscosity = 1250 Pa.s @ 260 C
    (from docs/PHASE_14 S:M's own worked example -- ALREADY IN THE GRAPH,
    not re-derived by this inquiry)
  - Promoted Observations for molecular_weight=85000, dispersity=1.72,
    tensile_strength=42.7 MPa from separate sources

INQUIRY-DERIVED RESULTS (InquiryState, this inquiry only):
  - Retrieved refs: the promoted median viscosity, molecular_weight,
    tensile_strength Graph objects above -- retrieval was CHEAP (§G),
    no re-extraction needed, because they were already promoted by an
    earlier inquiry or ingestion run.
  - A mathematical-analysis operator computes a working (inquiry-local)
    correlation between shear_rate and measured viscosity across the
    retrieved Observations -- epistemic_status="inferred".
  - A hypothesis-generation operator proposes: "processing at
    temperature=185C, shear_rate=120/s may yield tensile_strength
    approaching 45 MPa" -- epistemic_status="hypothesized". This
    coexists with a second, contradictory hypothesis from the same
    InquiryState (e.g. a different extrapolation) -- both are allowed
    to exist simultaneously, per the design brief.
  - A simulation operator is asked to check one hypothesis --
    epistemic_status="simulated" on the result.

PROPOSED CANDIDATES:
  - A Derived value: "recommended processing window: 183-187C,
    110-130/s shear rate, based on median historical viscosity + this
    inquiry's correlation + one supporting simulation" --
    derived_from=[the 3 retrieved Graph objects, the inquiry's
    correlation, the simulation result], method="inquiry:<id>,
    operator_chain=[math_analysis, simulation]".

VALIDATION:
  - This Derived value, if judged ready, goes through the EXISTING
    adapter -> validate_candidate path (docs/PHASE_14 S:O) against
    whatever StateSchema governs "recommended processing conditions"
    for this material -- exactly the same gate every other candidate in
    this repository has always gone through.

POSSIBLE PROMOTION:
  - If accepted: a new CanonicalState Version exists, compiles through
    Morpho exactly as before, and is visualizable via the SAME
    Three.js/SVG/graph backends already proven in Phase 9/12 -- nothing
    about the rendering path changed because a richer upstream produced
    the CandidateDelta this time.

DISTINCTIONS MADE EXPLICIT:
  - existing evidence: the 3 raw papers' Observations (Warehouse)
  - graph knowledge: the promoted median viscosity + property values
  - inquiry-derived results: the correlation, retrieved-and-combined
  - hypotheses: the two competing processing-window guesses
  - proposed candidate: the one Derived value actually sent for validation
```

---

## N. Relationship to existing repository architecture

| Existing abstraction | Role in this larger architecture | Needs extension? |
|---|---|---|
| `CandidateDelta` (`core/canonical/delta.py`) | Unchanged. The universal currency every promotion path — JSON adapter, CSV adapter, simulation, neural, and now InquiryState-derived candidates — converges on. | No |
| `validate_candidate` | Unchanged. Still the *only* function that mints an accepted `Version`. This document adds producers upstream of it, never a second gate beside it. | No |
| `Adapter` protocol (`adapters/interface.py`) | Unchanged. A future "InquiryState → CandidateDelta" bridge is just one more `Adapter` implementation, exactly like `JSONAdapter`/`CSVAdapter`. | No — this is the extension point, already designed for exactly this |
| `ProvenanceInfo` | Unchanged shape (Phase 12's `timestamp` addition already covers this). Its `.source` string is the hook for `"knowledge_graph:<id>"`, same convention as `"json_adapter:..."`. | No |
| Morpho IR | Unchanged, and stays that way — see §O and Phase 13/14's own conclusions, reaffirmed once more here | No |
| `adapters/` package | Gains conceptual *siblings* (the promotion-gate logic, entity resolution) that are **not** `Adapter` implementations themselves — they operate one layer further upstream, inside the Warehouse→Graph boundary, before anything reaches an `Adapter` | Yes, eventually — new modules, not changes to existing ones |
| `backends/simulation/interface.py`, `backends/neural/interface.py` | **Already, literally, operators** in this document's sense — a `CandidateNextState`/`BeliefState` producer that reads (implicitly) some context and writes a proposed candidate, never touching `CanonicalState` directly. This document's "operator" framing is not a new invention forced onto the codebase; it is what Phases 9-10 already built twice, now named and generalized. | No — the pattern already exists and already works |
| `runtime/feedback_loop.py` | Unchanged. Remains one instance of "candidate producer → validate_candidate", exactly as today; an InquiryState-derived candidate would use an analogous, new bridge function, not a modified `feedback_loop.py`. | No |

**The single strongest de-risking observation in this document:** every
new piece proposed here — operators-not-agents, read-Commons/write-
local-state, explicit gated promotion — is not a new pattern being
introduced into this codebase. It is the **same pattern Phases 9, 10,
and 12 already implemented three separate times** (simulation
interface, neural interface, JSON/CSV adapters), now recognized as one
general shape and extended one layer further upstream. This document
does not ask the architecture to learn a new trick; it asks it to keep
doing the one trick it already does well, at greater scale.

---

## O. Migration implications

None to `CanonicalState`, `Morpho`, `validate_candidate`, or any existing
test. Everything in this document is new, additive infrastructure
**upstream** of the existing adapter boundary — the same non-invasive
posture Phase 13 and Phase 14 both already established and this
document inherits without exception. The only genuinely new pieces of
future *implementation* surface (not proposed to be built now, §R) are:

1. The Warehouse→Graph promotion gate (a new mechanism, distinct from
   `validate_candidate`, per §A/§E).
2. A retrieval/query function that constructs (part of) an
   `InquiryState` from the Knowledge Graph.
3. An `Adapter` implementation that turns an `InquiryState`'s ready
   `Derived value` into a `CandidateDelta` — this one *does* fit
   directly into the existing `adapters/` package's established shape,
   unlike 1 and 2.

---

## P. Risks and failure modes

| Risk | Mechanism that mitigates it |
|---|---|
| Knowledge Graph pollution ("tragedy of the commons") if the promotion gate is too weak | A separate, deliberately stricter gate than raw Warehouse ingestion (§E); initial implementation should default to human review, per Phase 14 §R's sequencing |
| InquiryState hallucination leaking into the Graph or CanonicalState | The single write-only-to-InquiryState rule (§H) plus the unchanged `validate_candidate` gate — there is no path from a model's raw output to anything persistent that skips both |
| Provenance chain breaking at the new Warehouse→Graph hop | Same "append a new hop, never rewrite the ones before it" discipline used at every other hop (§J) |
| Conflating `CanonicalState`'s field-name identity with the Graph's cross-document entity-resolution identity | Explicit naming discipline, already flagged in Phase 14 (`Referent`, not `Entity`) — repeated here as still binding |
| The compute-economics argument failing for low-reuse, one-off inquiries | Named explicitly as a real, non-hypothetical limitation (§G) — the architecture should not force every inquiry through full promotion machinery regardless of expected reuse |
| Entity-resolution and confidence-scoring methodology remaining unresolved (inherited from Phase 14) | Still unresolved here too — repeated in §R, not silently assumed solved by this document |
| Two independent operators promoting near-duplicate Derived values for the same fact | The Warehouse's own duplicate-tolerance (§B) means this is survivable, not catastrophic — the promotion gate's non-duplication check (§E) is the intended, if still unspecified-in-detail, mitigation |

---

## Q. Recommended next implementation phase

In dependency order, extending Phase 14 §R (steps 1-6 of which remain
unchanged and still come first):

1. Everything in Phase 14 §R steps 1-6 (raw storage, deterministic
   extraction, normalization, conflict-tolerant Warehouse, the
   pool→adapter bridge, indexes) — unchanged prerequisite.
2. The Warehouse→Graph promotion gate (§A, §E) — deliberately *after*
   the pool→adapter bridge already works for the simpler Phase-14 case,
   so the harder, less-specified promotion logic isn't the first new
   mechanism ever exercised.
3. A minimal, in-memory-only `InquiryState` composition (§L) — no new
   storage subsystem, built entirely from existing/soon-to-exist
   primitives (references into the Graph, plain lists) — proving the
   "read Commons, write local state" operator discipline works before
   investing in anything heavier.
4. One operator (recommend: retrieval, the cheapest and most clearly
   specified) implemented end-to-end against a real, if small, promoted
   Graph.
5. The `InquiryState`-derived-`Derived-value` → `CandidateDelta` bridge
   (§O item 3) — reusing the existing `Adapter` shape.
6. Only then, additional operators (mathematical analysis, hypothesis
   generation, simulation-in-the-loop) — each independently, each
   provably not requiring the others to exist first, matching the
   "independent computation" principle this document argues for
   throughout.

---

## R. Explicit list of things NOT to implement yet

- Mistral or any local model deployment.
- An agent swarm, or any agent-to-agent messaging protocol.
- A vector database, graph database, or any other specific database
  product — §I stays a conceptual comparison, exactly as Phase 14's did.
- Cloud infrastructure, distributed systems, Kubernetes, message queues.
- Autonomous agent loops.
- An ontology/reasoning engine.
- The Warehouse→Graph promotion gate's exact algorithm (identity
  resolution and confidence scoring remain the same unresolved
  questions Phase 14 already named — this document does not resolve
  them either, and does not pretend to).
- `InquiryState` as a persisted, first-class storage subsystem — §Q
  recommends starting it as a pure in-memory composition, and this
  document does not establish that it will ever need to be more than
  that.
- Any change to `CanonicalState`, `Morpho`, `validate_candidate`,
  `core/projection/`, or `runtime/` — this document, like Phase 13 and
  14 before it, operates strictly upstream of the existing, unchanged
  adapter boundary.

---

## Final assessment

This document does not introduce a verdict token of its own (the prompt
did not request one) — its findings are instead summarized against the
Final Principle it was asked to test:

- **Build information once:** yes — extraction and promotion are
  one-time, amortized costs (§G).
- **Organize it well:** yes — the Warehouse/Graph split, plus the
  warehouse-index/graph-index hybrid inherited from Phase 14, gives each
  query type (§I) a fit-for-purpose structure without forcing everything
  into one representation.
- **Make it retrievable:** yes — retrieval into an `InquiryState` is
  cheap by construction, because the Graph is an immutable, indexed
  store, not something re-derived per query.
- **Reuse it many times:** yes, asymptotically — with the honest caveat
  (§G, §P) that one-off inquiries do not benefit and should not be
  forced through the full machinery regardless.
- **Compute deeply only when needed:** yes — reasoning/simulation
  compute is spent inside an `InquiryState`, on the *novel* part of a
  question only, with everything already known retrieved rather than
  recomputed.

No implementation file was changed to reach this assessment.
