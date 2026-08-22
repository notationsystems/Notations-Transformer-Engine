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

## Foundry / Palantir Architectural Benchmark

This section adds a comparative reference point using Palantir Foundry's
publicly documented architecture — not to reproduce it, not to adopt its
dependencies, and not to build "Foundry but open source." Grounded
against current Palantir documentation (`palantir.com/docs/foundry/`,
fetched during this investigation, cited at the end of this section)
rather than only general prior knowledge, per the instruction to prefer
current docs over the older Operating System demo material.

### A. Foundry architectural summary

Foundry's own framing: an operating platform that connects an
organization's existing systems, turns their raw output into governed
datasets, models the business as an **Ontology** of objects and actions,
and serves applications that operators use to make decisions. Layered,
bottom to top:

1. **Connection** — connectors land raw data from ERPs, CRMs,
   warehouses, files, streams, APIs, with lineage attached from first
   sync.
2. **Pipelines** — SQL/Python/Java transforms turn raw tables into
   clean, versioned **datasets**, with health checks and data
   expectations.
3. **Ontology** — the semantic layer built on top of governed datasets,
   split into two kinds of elements:
   - **Semantic elements**: **Object Type** (schema for a real-world
     entity or event — object types relate to object instances the way
     a dataset schema relates to rows), **Property** (an object type's
     characteristics — analogous to columns), **Link Type** (a
     relationship between object types, functioning like a database
     join). Shared properties allow reuse across object types;
     Interfaces allow polymorphism across object types.
   - **Kinetic elements**: **Action Type** (a named, typed, reusable
     definition of a set of edits to objects/properties/links a user can
     take at once, including side effects), **Functions** (server-side
     code operating on Ontology objects within a governed execution
     environment — can read properties, traverse links, **and make
     edits**).
4. **Applications / Workshop / AIP** — built on top of the Ontology,
   consumed by human operators and, via AIP, by models that call
   Functions against the same governed Ontology.
5. **Lineage** is explicitly split into two distinct concepts: **Data
   Lineage** (the dataset/transform dependency graph — how data flows
   through pipelines) and **Workflow Lineage** (how applications,
   Functions, Actions, and automations interact operationally). Foundry
   treats these as genuinely separate views, not one merged graph.

### B. Similarities

- Both separate a semantic/identity layer from raw data (Foundry:
  Ontology above datasets; ours: Knowledge Graph above the Warehouse,
  `docs/PHASE_14_DATA_POOL_ARCHITECTURE.md`).
- Both use typed relationships as first-class citizens (Foundry: Link
  Types; ours: `EdgeRecord`/`ClaimedRelationship`).
- Both have a governed gate through which changes to the authoritative
  model must pass (Foundry: Action Types; ours: `validate_candidate`).
- Both explicitly separate *data* lineage from *process/operational*
  lineage rather than merging them into one graph — Foundry's Data
  Lineage vs. Workflow Lineage split is an independent validation of
  this document's own §J (evidence provenance chain) vs. §L
  (`InquiryState.operator_log`) split, arrived at separately and now
  confirmed by an external, mature precedent.
- Both exist to prevent the same waste this document's §G names
  explicitly: many independent consumers re-deriving the same facts
  from raw data, rather than computing once and sharing a governed,
  queryable result.

### C. Differences

| Axis | Foundry | Ours |
|---|---|---|
| Mutation | Actions **edit the live Ontology** (object/property/link state changes in place, with lineage tracked underneath) | **Never mutates** — every accepted change produces a wholly new, immutable, content-addressed `Version`; nothing is ever edited in place, anywhere |
| Compute write access | Functions **can make edits** to the Ontology directly (within governed permissions) | Operators can write **only** to a disposable `InquiryState` — never to the Warehouse, Knowledge Graph, or `CanonicalState` directly (§H) |
| Semantic scope | **One** integrated Ontology per deployment, modeling one organization | **Split**: one general, domain-agnostic Knowledge Graph (identity + evidentiary relationships only) **plus** many narrow, independently-versioned `StateSchema`-bound `CanonicalState` instances, one per bounded domain problem |
| Purpose | Operational decision support for a live, ongoing business | Reproducible scientific/technical inquiry, where an exact frozen state must be citable and replayable |
| Exploratory workspace | No clear first-class equivalent surfaced in this investigation's research (see §L below — not an exhaustive audit of every Foundry feature) | `InquiryState`: deliberately disposable, may hold mutually exclusive hypotheses, never required to be reviewed or persisted |

### D. Concepts worth borrowing (adopt)

- **Strong object/entity identity** (A) — already present as `Referent`
  (Phase 14); Foundry's Object Type/instance split is external validation
  of the same shape, not a new idea to import.
- **Typed relationships** (B) — already present as
  `EdgeRecord`/`ClaimedRelationship`; same validation, not new work.
- **Data lineage** (C) — already core to §J's provenance chain; Foundry's
  emphasis on "which dataset/transform produced this value" maps
  directly onto our Document→Record→Observation→NormalizedRecord chain.
- **Semantic abstraction above raw datasets** (F) — already the
  Knowledge Graph's relationship to the Warehouse (Phase 14); validated,
  not new.
- **Shared representation consumed by many applications** (G) — already
  Morpho's relationship to `backends/*` (Phases 7-9), one layer down
  from where Foundry's Ontology serves many applications. Same pattern,
  already proven in this codebase before this investigation began.
- **Provenance and auditability** (H) — already core to every phase of
  this project.

### E. Concepts worth adapting (not adopting wholesale)

- **Transformation lineage** (D) — Foundry tracks lineage of named
  pipeline transforms; we already track `extraction_method`/
  `normalization_method`/`derived_from`+`method` as free-text labels
  (Phase 14 §D, this document §J). Adapt by eventually making these
  **named, versioned, reusable transformation definitions** rather than
  free-text strings — a natural refinement, not a new concept, and not
  needed yet (only a handful of methods exist today).
- **Explicit actions** (E) — Foundry's Action Type (a named, typed,
  reusable "kind of change") is a genuinely useful discipline. Adapt the
  **naming/typing discipline**; reject the **in-place-mutation target**
  it edits toward in Foundry. Our equivalent already exists in spirit —
  `CandidateDelta` submitted via a specific `Adapter` — just not yet
  formally *named and typed* per kind of change the way Foundry names
  "Approve Purchase Order." Not needed while there are only a handful of
  producer kinds (JSON adapter, CSV adapter, simulation, neural).
- **Reusable data transformations** (I) — same reasoning as
  Transformation lineage above; a future refinement of already-present
  string-labeled methods, not a new mechanism.
- **Operational feedback loops** (J) — Foundry's "operational decisions
  feed back into monitored datasets" is structurally similar to our own
  hypothesis→experiment→measurement→updated-knowledge loop (§10 of the
  original prompt this document answers, and §M below) — adapt the
  **loop shape**; the semantics differ (ours is validation-gated
  knowledge update, not operational/KPI feedback).

### F. Concepts to defer

- **Enterprise permission models** (row/column-level security, org-based
  RBAC) — not needed at current scale; would become relevant only if
  this became genuinely multi-institution shared infrastructure.
  Deferred, not rejected — the same "do not overbuild" discipline every
  phase of this project has already applied.
- **Centralized application-platform assumptions** — Foundry is a
  platform you build governed apps *on top of*, with a control plane.
  Our operators/backends are independent, loosely coupled functions, not
  apps registered against a platform. Could matter at much larger scale;
  not now.

### G. Concepts to reject

- **Mutable operational state** — rejected for our core, deliberately
  and permanently, not merely deferred. See §K (Immutability) below for
  the full reasoning; this is the single clearest "do not borrow" finding
  in this investigation.
- **Vendor-specific infrastructure** (Spark-based pipeline execution,
  Palantir's proprietary runtime, its specific connector ecosystem) —
  irrelevant to our architecture and would violate "do not add
  dependencies."
- **UI-driven architecture** (Workshop app-builder, Object Explorer) —
  rejected as a load-bearing dependency. Consistent with how this
  codebase already treats `renderer/index.html`: a pure downstream
  consumer, never required for anything upstream to be correct. A UI can
  be layered on later without being architectural.
- **Excessive Ontology responsibilities** — Foundry's Ontology is
  simultaneously the semantic model, the mutation target, the security
  boundary, and the object-view aggregation point. We reject this
  *conflation* specifically: keeping Knowledge Graph (semantic),
  `CanonicalState` (mutation-gated, versioned), and Morpho
  (representation) as three separate, non-overlapping responsibilities
  is a deliberate divergence from Foundry's more monolithic Ontology,
  not an oversight.
- **Tightly coupled action/workflow systems** (an Action Type triggering
  Function side effects, notifications, and downstream automations as
  one bundled definition) — rejected specifically for the reason
  Phases 1-12 already established `validate_candidate` must stay narrow:
  schema and constraint validation only, no side-effecting automation
  baked into the gate itself.
- **Enterprise-specific workflow assumptions** (approval chains,
  org-chart-based routing) — not applicable to a research/scientific
  substrate; would be pure unused surface area if imported now.
- **Operational transaction semantics** (keeping live external business
  systems in sync, e.g. two-phase commit against an ERP) — our
  "transactions" are content-addressed version acceptances against our
  own store, a fundamentally different and, for our purposes, already
  sufficient model. Nothing external needs to stay synchronously
  consistent with us.

### H. Ontology comparison

Answering §8 of the original prompt directly: **no, our system should
not have one universal ontology.** It should have exactly the
decomposition this document and Phase 14 already specify: Evidence +
Identity (Warehouse `Referent`s) + a typed, domain-agnostic Knowledge
Graph (identity/relationship primitives only) + many independent,
narrow domain `StateSchema`s + `CanonicalState` (schema-bound, versioned,
one per bounded problem) + Morpho (representation, unchanged).

Why one universal ontology would bottleneck across chemistry, materials,
manufacturing, mathematics, simulation, physics, process control, and
ML: each domain has genuinely different structural needs (molecular
structure representations for chemistry; continuous control-loop
semantics for process control; symbolic/notational structures for
mathematics) that a single shared schema would either flatten to a
lowest-common-denominator that fits none of them well, or balloon trying
to accommodate — which is exactly the "universal ontology engine"
anti-pattern already identified and rejected in both
`docs/PHASE_13_ARCHITECTURE_INVESTIGATION.md` and
`docs/PHASE_14_DATA_POOL_ARCHITECTURE.md`. Foundry's own architecture
does not actually contradict this: Foundry's Ontology is deliberately
*not* the raw data layer (that stays flat, in datasets) — it is one
additional semantic layer *above* flat storage, which is structurally
the same "flat storage + typed semantic layer, kept distinct" shape
Phase 13 already recommended, just built for one domain (an
organization's operations) rather than several unrelated scientific
ones. The lesson borrowed is the *layering*, not the *singularity* of
the ontology.

### I. Object/relationship comparison

Connects directly to `docs/PHASE_13_ARCHITECTURE_INVESTIGATION.md`'s
own A/B/C/D evaluation (structured `CanonicalState` vs. pure Morpho
inference vs. the recommended hybrid). Re-expressed against this
document's four options:

| Option | Description | Foundry precedent | Verdict |
|---|---|---|---|
| A. Flat fields | Current `CanonicalState.fields` | Foundry's raw datasets (flat, tabular) | Correct for the *storage* layer — keep |
| B. Hierarchical records | Nested values inside `CanonicalState` itself | Not how Foundry does it either — Foundry does not nest structure into dataset rows | Rejected, consistent with Phase 13's own rejection of "Option A" there |
| C. Typed entity/relation graph | A graph of typed objects/links as the *primary* store | Foundry's Ontology, exactly — but as a layer *above* flat storage, not instead of it | Correct for the *semantic* layer (Knowledge Graph), not as a replacement for `CanonicalState` |
| D. Hybrid (flat storage + typed graph layer above it, kept distinct) | Phase 13's actual recommendation: flat `CanonicalState` + reserved-edge-type-driven Morpho `Sequence`/`Composite` | **This is structurally what Foundry independently arrived at** (flat datasets + Ontology graph above, kept as separate layers) | **Confirmed, not changed** — external precedent increases confidence in Phase 13's existing recommendation without altering it |

No implementation follows from this section — Phase 13's recommendation
already stands, and its own explicit "STOP" condition (do not implement
without a decision) is unaffected. This section only adds outside
evidence that the decision already made was the right one.

### J. Lineage comparison

Foundry's Data-Lineage/Workflow-Lineage split (§A) validates this
document's own provenance-chain/operator-log split (§J, §L). The prompt's
target lineage chain —

```
Source Document -> Extracted Observation -> Canonical Field -> Graph Entity
  -> Inquiry Retrieval -> InquiryState -> Derived Quantity
  -> Simulation/Analysis -> Candidate -> Validation -> New Knowledge Version
```

— is, checked link by link, **already fully representable** by what this
document and Phase 13/14 already specify: Document→Record→Observation
(Phase 14) → NormalizedRecord → promotion → Knowledge Graph object (this
document §J) → `InquiryState.retrieved_refs` (§L) → `derivations` (§L) →
existing simulation/analysis interfaces (Phases 9-10) → `CandidateDelta`
→ `validate_candidate` → `Version` + `StateDelta` (Phase 13's retention
fix). **No new storage mechanism is required to make this chain exist.**

What genuinely is missing, confirmed by this comparison: everything
above is a **backward** chain (why does X exist — walk back through
references). Foundry's own Data Lineage tool visualizes both directions.
"What depends on this source/measurement/property" needs a **forward**
index — the same reference fields, traversed the other way — which is a
derived-index concern (§I: indexes are derived, never primary storage),
not a new stored field. **Recommendation: a future lineage capability
should expose both `lineage_of(id)` (backward) and `dependents_of(id)`
(forward) as query functions over the already-specified reference
fields — design it, do not implement it yet**, consistent with the
original prompt's explicit instruction for this section.

### K. Action/state-transition comparison (the immutability question)

Foundry: `Action -> mutable Ontology object` (edits happen in place;
lineage/versioning exists underneath the pipelines that feed the
Ontology, but the *object a query returns* is its current, live state).

Ours: `Action -> CandidateDelta -> Validation -> new immutable Version`
(already the existing, proven architecture — nothing changes here).

This is not "Foundry got it wrong" — a live, current-state model is the
*correct* choice for Foundry's actual purpose: an operator asking "what
is our inventory right now" needs the current answer, not a citation to
a frozen historical version. Evaluating our case on its own terms:

- **Reproducibility.** A scientific conclusion must be traceable to and
  replayable against an *exact* frozen state, not "whatever the live
  state happens to be by the time someone checks." Immutable,
  content-addressed versioning gives this natively (already proven:
  109 tests, byte-for-byte deterministic across `PYTHONHASHSEED` values).
  A governed-mutable model would need a separate, additional
  point-in-time-snapshot mechanism to achieve the same guarantee.
- **Non-repudiation of prior belief.** A correction supersedes; it never
  erases what was previously believed at a given time — essential for a
  scientific audit trail ("what did we know when this hypothesis was
  formed"), and already how this architecture works by construction, not
  by an added audit log bolted on afterward.
- **Safe concurrent `InquiryState`s.** Multiple inquiries can reference
  the *same* frozen `Version` with zero risk of observing another
  inquiry's in-progress, uncommitted edit — a free consequence of
  content-addressed immutability, whereas a live-mutable Ontology model
  needs its own read-isolation/locking discipline to provide the same
  guarantee.

**Conclusion: the existing `Action -> CandidateDelta -> Validation ->
new immutable Version` model is confirmed as correct for this
architecture's actual purpose, not merely preserved by inertia.** This
section is evaluation, not a change — nothing here alters
`validate_candidate` or `CanonicalState`, both of which already work
exactly this way.

### L. InquiryState comparison

Per the instruction not to assume `InquiryState` is unique: it is not,
and claiming otherwise would be exactly the kind of overclaiming this
whole project has avoided elsewhere. The general idea of a **disposable,
non-authoritative exploratory workspace** is well precedented outside
Foundry entirely:

- **Version-control branches** — a divergent, discardable working copy,
  isolated from the authoritative history until merged. Similar in
  "disposable, non-authoritative until integrated"; different in that a
  branch is normally one coherent state, not a deliberate superposition
  of mutually exclusive hypotheses the way `InquiryState` is specified
  to allow (§L of this document, unchanged).
- **Database transactions / MVCC snapshots** — isolated, invisible to
  others, disposable via rollback. Similar in isolation and
  disposability; shorter-lived and structurally poorer than
  `InquiryState` (no notation, hypotheses, or heterogeneous exploratory
  content).
- **Computational notebooks** (e.g. Jupyter-style workflows) — plausibly
  the closest general analogue: a disposable, exploratory workspace that
  can hold half-finished calculations and wrong turns without affecting
  any authoritative system. The genuinely more specific part of this
  proposal is not "a scratch space exists" (well precedented) but the
  **structured, mandatory promotion mechanism** connecting that scratch
  space to a schema-validated, content-addressed, immutable store
  through the *exact same gate* every other candidate source in this
  codebase already uses — and the explicit epistemic-status taxonomy
  (§K of this document) distinguishing *why* something in the scratch
  space isn't yet authoritative.
- **Foundry itself** — no first-class equivalent surfaced during this
  investigation's research (branches/drafts on Foundry datasets and
  Ontology edits generally exist to eventually merge into the *same*
  live Ontology, not to be permanently, unreviewed, discardable). This
  is not an exhaustive audit of every Foundry feature, so it is stated
  as "not found in this research," not "does not exist."

**Conclusion: the disposable-workspace idea is not novel. The novelty,
such as it is, is entirely in the promotion discipline connecting it to
the rest of this specific architecture** — which is exactly the part
Phases 1-12 already proved works, now extended one layer further
upstream rather than invented from nothing.

### M. Scientific/materials example

Same inquiry as §M of this document's main body — *"find promising FEP
processing conditions balancing viscosity and mechanical properties"* —
walked through both architectures side by side:

```
FOUNDRY-STYLE HANDLING:
  connectors ingest process/telemetry/lab-system datasets
    -> pipelines produce governed, versioned datasets
    -> Material/Process/Measurement modeled as Object Types with
       typed Links, in ONE shared Ontology for this deployment
    -> an analyst queries/analyzes via a Workshop app or a Function
    -> exploratory "what if" analysis happens in a scratch tool, or as
       a draft/branch of the SAME live Ontology
    -> a recommended processing window, if adopted, becomes an ACTION
       that edits/creates a live Ontology object (e.g. a "Recommended
       Process Parameters" object) -- current, mutable, audited
    -> "what was recommended last month" is retrievable mainly through
       audit/versioning tooling layered on top of a fundamentally
       mutable current-state model

OUR ARCHITECTURE:
  papers/datasets/experiments/simulations acquired
    -> Warehouse (conflicting viscosity reports coexist untouched,
       Phase 14 S:E)
    -> promotion gate -> Knowledge Graph (validated FEP Referent,
       promoted property Observations/Derived-values)
    -> retrieval into an InquiryState (cheap -- already promoted,
       S:G)
    -> operators compute correlations, generate COMPETING hypotheses
       that coexist (not possible as a single Ontology object's
       current state)
    -> a Derived value synthesizing a recommendation
    -> EXISTING validate_candidate gate (unchanged)
    -> a BRAND NEW immutable CanonicalState Version -- the prior
       recommendation is never overwritten, remains natively queryable,
       byte-for-byte reproducible (already proven, 109 tests)
    -> compiles through Morpho to Three.js/SVG/graph exactly as already
       proven in Phases 9/12 -- nothing about the rendering path
       changes because a richer upstream produced the CandidateDelta
```

Concrete difference this surfaces: "what was recommended and why, as of
last month" is a *native* property of our architecture (every
recommendation is its own immutable, content-addressed, replayable
`Version`) rather than a capability that has to be added on top of a
fundamentally mutable model.

### N. Architectural lessons

1. A shared, typed, governed semantic layer above raw data is worth
   having — we already have it (Knowledge Graph over Warehouse); Foundry
   is external confirmation, not a reason to change anything.
2. Splitting data lineage from operational/workflow lineage is worth
   doing — we already do it; same conclusion.
3. Flat storage plus a distinct typed graph layer above it, kept
   separate, is a validated real-world pattern, not just an internally
   convenient choice — directly reinforces Phase 13's existing
   recommendation without changing it.
4. A named, typed "kind of change" abstraction (Action Types) is a
   useful discipline worth adopting **in naming**, once there are enough
   producer kinds to warrant it — not yet, and not with Foundry's
   in-place-mutation semantics attached.
5. Governing what compute is allowed to write is the load-bearing safety
   property in both architectures — Foundry does it through Ontology
   permissions on Functions; we do it more strictly, by construction,
   through the write-only-to-`InquiryState` rule (§H) plus the unchanged
   `validate_candidate` gate.
6. Live/mutable-with-audit and immutable/content-addressed are both
   legitimate architectural choices — the correct one depends on
   whether the system's job is "reflect current operational reality" or
   "produce citable, replayable scientific conclusions." We are the
   latter; the choice already made (Phases 1-12) is confirmed correct
   for that job, not merely inherited.

### O. Explicit conclusion

**We are not building another Foundry.** Foundry is a shared,
*operational*, live-mutable representation of *one organization's*
business, governed by Actions with side effects, serving decisions that
affect that same organization's ongoing operations. Our architecture is
a shared, *evidentiary*, immutable representation of a *domain* (not an
organization), from which temporary, disposable, contradiction-tolerant
inquiry-specific worlds are constructed, gated back into permanence only
through validation — never through an operational side effect. The
distinction the prompt proposed —

> Foundry: shared operational representation of an organization.
> Ours: shared computational representation of a domain, from which
> temporary inquiry-specific worlds can be constructed.

— holds up under the rigor this section applied to it: every genuine
difference found (mutation model, write-access discipline, semantic
scope, purpose, the missing `InquiryState` analogue) traces back to
exactly this one distinction, not to unrelated implementation details.

### Comparison table

| Concept | Foundry | Our Architecture | Decision |
|---|---|---|---|
| Data layer | Connectors + versioned pipeline datasets (governed, Spark-based transforms) | Warehouse: `Document`/`Record`/`Observation`, conflict-tolerant, content-addressed blobs (Phase 14) | Adopt the *shape* (raw → governed), not the technology |
| Semantic layer | One integrated Ontology (Object/Property/Link types) per deployment | Split: general Knowledge Graph (`Referent`/`ClaimedRelationship`) + many narrow, independent `StateSchema`s | Deliberately diverge — §H |
| Object identity | Object Type + object instance, platform-managed | `Referent`; identity-resolution methodology still open work (Phase 14 §S) | Adopt the concept; resolution algorithm remains unresolved |
| Relationships | Link Types, DB-join-like | `EdgeRecord` (canonical) / `ClaimedRelationship` (evidentiary) | Adopt |
| Lineage | Data Lineage (dataset/transform graph) + Workflow Lineage (app/action graph), kept separate | Provenance chain (§J) + `InquiryState.operator_log` (§L), already separately specified | Validated by precedent; add backward+forward query later (§J above) |
| Actions | Action Type: named, typed, reusable, **mutates the live Ontology** | `CandidateDelta` via `Adapter`, **immutable**, never mutates | Adopt naming/typing discipline; reject in-place mutation |
| State | Live, current, mutable (audit trail underneath) | Immutable, content-addressed, versioned, deterministic (proven, 109 tests) | Preserve as a core, non-negotiable distinction — §K |
| Inquiry workspace | No clear first-class equivalent found in this research | `InquiryState`: ephemeral, mutable, may hold competing hypotheses | Primary intentional differentiator — §L |
| AI/model layer | AIP: models call Functions, which **can write** to the Ontology (governed) | Operators: read Commons + `InquiryState`, **write only** `InquiryState` | Deliberately stricter than Foundry — §H (main body) |
| Simulation | Not a native primitive — modeled as a Function/pipeline | `backends/simulation` interface (existing, unchanged) + Warehouse re-entry as new evidence | Already-existing pattern; no change needed |
| Validation | Action-level business rules/permissions, potentially workflow-coupled | `validate_candidate`: schema + constraint, single deterministic gate, deliberately not workflow-coupled | Keep narrow — §G |
| Immutability | Not a first principle — governed mutability + lineage underneath | A first principle, proven, unchanged by this investigation | Preserve — §K |

### Final question, answered directly

**"If Palantir spent years building Foundry, what architectural
knowledge can we extract from that work without inheriting Foundry's
assumptions?"**

The value of a shared, typed, governed semantic layer sitting above raw
data, kept structurally distinct from that raw data (§I). The value of
splitting data lineage from operational/workflow lineage rather than
merging them (§J). The value of a named, typed "kind of change"
abstraction, independent of whatever that change's target semantics turn
out to be (§E, §K). The practical necessity of governing exactly what
compute is allowed to write to shared state (§D, §K) — which we already
do, more strictly than Foundry does. None of this required reading
Foundry's specific mutation model, permission system, or application
framework as something to copy — only as evidence that the *shape* of
several decisions already made independently in this project (Phases
1-14) match what a mature, differently-motivated system converged on
too.

**"What is the smallest architecture we can build that captures the
useful lessons while preserving our stronger distinction between
persistent knowledge and temporary computational worlds?"**

Exactly what is already specified, and no more: Warehouse (Phase 14) →
promotion gate → Knowledge Graph (this document) → `InquiryState`
(conceptual, this document) → the existing, unchanged
`CandidateDelta`/`validate_candidate`/`CanonicalState`/Morpho pipeline.
This benchmark adds exactly two things worth eventually building, both
already named above as future, non-urgent work: a backward-and-forward
lineage **query** capability over reference fields that already exist
(§J), and a named/typed convention for "kinds of change" once there are
enough producer kinds to justify it (§E). Nothing else. The smallest
architecture that captures Foundry's genuine lessons is the one this
project had already converged on before this benchmark was run — which
is itself the most reassuring finding in this section: independent
convergence, not a gap this comparison needed to close.

**Sources consulted** (Palantir's current documentation, fetched during
this investigation):
[Core concepts • Ontology • Palantir](https://www.palantir.com/docs/foundry/ontology/core-concepts) ·
[Overview • Ontology • Palantir](https://www.palantir.com/docs/foundry/ontology/overview) ·
[Object and link types • Types reference • Palantir](https://www.palantir.com/docs/foundry/object-link-types/type-reference) ·
[Ontology architecture • Palantir](https://www.palantir.com/docs/foundry/object-backend/overview) ·
[Functions on objects • Objects and links • Palantir](https://www.palantir.com/docs/foundry/functions/api-objects-links) ·
[Action types • Overview • Palantir](https://www.palantir.com/docs/foundry/action-types/overview) ·
[Data Lineage • Overview • Palantir](https://www.palantir.com/docs/foundry/data-lineage/overview) ·
[Overview • Data integration • Palantir](https://www.palantir.com/docs/foundry/data-integration/overview)

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
