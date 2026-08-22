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

## TrustGraph / Context-Graph Benchmark

Grounded in TrustGraph's current documentation and guides
([docs.trustgraph.ai](https://docs.trustgraph.ai/),
[trustgraph.ai/guides](https://trustgraph.ai/guides/key-concepts/context-graphs/),
[GitHub](https://github.com/trustgraph-ai/trustgraph)), fetched during this
investigation. TrustGraph describes itself as "the deterministic context
engineering platform for open source AI" — infrastructure for building
knowledge graphs and packaging them as portable, queryable context for
LLM agents. It is prior art for the layer *between* persistent knowledge
and an agent, which is exactly the layer §14 (this document) and
`docs/PHASE_14_DATA_POOL_ARCHITECTURE.md` left least resolved: retrieval,
context packaging, and statement-level provenance.

### A. Grounded architectural summary

TrustGraph is a message-driven microservices system (Apache Pulsar as the
messaging fabric; Cassandra for metadata; S3-compatible object storage for
documents; pluggable graph stores — Cassandra, Neo4j, Memgraph, FalkorDB —
and pluggable vector stores — Qdrant, Milvus). The ingestion pipeline is a
processor chain: `pdf-decoder → chunker → kg-extract-relationships →
triple-store`. Query execution runs the reverse shape:
`api-gateway → graph-rag → prompt → text-completion`. An agent runtime
implements ReAct (Reasoning + Acting) as a loop of messages back into an
"agent manager," invoking TrustGraph capabilities or external tools via MCP.

Three concepts matter most for this benchmark:

- **Context Graph** — described (with some variation between TrustGraph's
  own docs and guides pages, noted honestly rather than reconciled) as
  three layers over a base knowledge graph: an ontological/type-system
  grounding layer, an AI-optimized retrieval layer (vector embeddings +
  graph traversal), and a third layer whose description varies by page —
  one page describes it as reification of agentic behavior (recording
  what actions agents took), another as a temporal feedback loop
  (freshness evaluation, conflict detection, confidence-score updates).
  Both are plausible parts of the same evolving product; this document
  does not have enough source material to say which is authoritative, so
  both are reported rather than one being silently discarded.
- **Holon** — TrustGraph's atomic unit: an RDF-1.2-reified
  subject-predicate-object triple bundled with its own source document,
  confidence score, and provenance, so each fact is simultaneously
  "autonomous" (self-describing, carries full context) and "cooperative"
  (linked into the global graph). Ontologies (OWL/SKOS/SHACL) constrain
  what can be extracted.
- **Context Core** — the deployable, portable unit of *knowledge*, distinct
  from a Context Graph (the dynamic, query-time traversal). A Context Core
  packages graph edges (relationships), schema (entity typing), and graph
  embeddings (vector space mapping) for one document or one domain. It has
  three lifecycle states — offline (downloadable file), online (loaded into
  a knowledge-management store, not yet queryable), loaded (in retrieval
  stores, queryable). Cores appear to hold copied/derived data (edges,
  schema, embeddings), not references back to the source document —
  see §D below for what that implies.

Statement-level provenance is already built, not proposed: TrustGraph
maintains three named graphs in one RDF store — a default graph (core
knowledge facts), `urn:graph:source` (extraction provenance: how a fact
entered the system), and `urn:graph:retrieval` (query-time reasoning
traces: how a fact was used). This is the single most directly relevant
piece of prior art in this benchmark — see §F.

### B. Concept-by-concept extraction

| Concept | Problem it solves | How TrustGraph solves it | Do we have this problem? | Already solved here? | Verdict |
|---|---|---|---|---|---|
| Context Graph (3-layer) | Turning a static knowledge graph into something an agent can query with grounding, freshness, and explainability | Ontology layer + retrieval layer + agentic/temporal layer over one graph | Yes — Phase 14's evidence layer has no retrieval or context-packaging story yet | Partially — Knowledge Graph (Phase 14) gives grounding; nothing gives retrieval or freshness yet | **Adapt** — the layering is a reasonable target shape, not a library to adopt |
| Context Core | Packaging extracted knowledge into a portable, versioned, loadable/unloadable unit | Per-document artifact: edges + schema + embeddings, three lifecycle states | Yes — "domain contexts" (§J below) need exactly this kind of unit | No — nothing in Phases 12-14 defines a portable knowledge unit | **Adapt** — conceptually useful; see §E for why we would prefer it hold references, not copies |
| Holon (reified triple + provenance) | Attaching provenance to individual facts, not just documents | RDF 1.2 reification: each triple carries source, confidence, provenance inline | Yes — this is exactly Phase 14's `ClaimedRelationship` problem | Partially — Phase 14 named the object type but did not resolve the provenance granularity question | **Borrow the idea, not the format** — see §F |
| Three named graphs (default / source / retrieval) | Separating "what is true," "how we learned it," and "how it was used," without three separate systems | Named-graph partitioning within one RDF store | Yes, precisely — this is retrieval lineage (§H) plus statement provenance (§F) | No | **Adapt** — the *separation* is the lesson; RDF/named-graphs is one implementation, not a requirement (see §F, §H on why we do not adopt RDF itself yet) |
| Graph + vector retrieval | Neither pure keyword/vector search nor pure graph traversal alone answers "relevant, structurally connected, numerically filtered" queries | Combines vector similarity, graph traversal, and (per docs) metadata/provenance filtering in one retrieval layer | Yes — Phase 14 explicitly flagged retrieval as unresolved | No — nothing implemented | **Defer** — real requirement, no infrastructure decision needed yet (§I) |
| Holonic / modular context | Avoiding "rebuild the whole knowledge environment" for every domain-specific inquiry | Holons compose into "context graphs" as bespoke, temporary per-query subgraphs; Context Cores compose as reusable domain packages | Yes — FEP + rheology + extrusion is exactly this shape | No | **Adapt** — the composition idea, not the RDF/OWL mechanism (§J) |
| ReAct agent runtime over Pulsar | Giving an agent a controlled loop to invoke retrieval/tools/graph operations | Message-driven ReAct loop, MCP tool invocation, agent manager | Yes — this is the eventual Mistral/agent question (§K) | No | **Defer entirely** — explicitly out of scope this phase, and even then only the *boundary discipline*, not the runtime, would be adopted |
| Ontology scaffolding (OWL/SKOS/SHACL) | Constraining extraction so facts are well-typed | Ontology defines classes/properties before extraction runs | Partially — `StateSchema`/domain schemas already constrain `CanonicalState`; the Evidence layer (Phase 14) is pre-schema by design | Yes, at the CanonicalState layer; deliberately no at the Evidence layer | **Reject as a global requirement** — Phase 14 already argued evidence must tolerate being unschematized before extraction; a mandatory upfront ontology would reintroduce the rigidity Phase 14 explicitly avoided |

### C. The central question

*"It is wasteful for every agent or inquiry to repeatedly reconstruct
relevant context from raw documents, datasets, and graph data."*

TrustGraph is real, working prior art for exactly this claim, and it
answers it the same direction we would: build the knowledge layer once
(ingestion → extraction → Context Core), retrieve a relevant slice
(context graph traversal at query time), and only then let an agent
reason. The proposed chain —

```
persistent information -> organized knowledge -> efficient retrieval
   -> reusable context -> temporary inquiry state -> reasoning
```

— matches TrustGraph's own shape (`triple-store -> context core ->
graph-rag retrieval -> prompt -> agent`) closely enough that this
document treats the hypothesis as **supported by independent prior art**,
not merely internally plausible. The one addition TrustGraph's own
architecture does not make explicit — and that this document keeps as a
distinguishing feature, not a gap to close — is a separately named,
governed *InquiryState* between "context was retrieved" and "the agent
reasoned." TrustGraph's docs describe agent iterations looping through an
agent manager; they do not describe a promotion gate an agent's derived
claims must pass before re-entering the graph. That absence is discussed
in §K.

### D. Four different things, kept distinct

| Layer | Owns | Analogous existing/proposed object | Mutability |
|---|---|---|---|
| Persistent Knowledge | The authoritative record of what is known and where it came from | Evidence + Warehouse + Knowledge Graph (Phase 14) + `CanonicalState` | Append-only / immutable-by-promotion |
| Retrieved Context | A selected, query-specific *view* over Persistent Knowledge | (proposed) `ContextPackage` — §E | Immutable once assembled; re-derivable, never edited in place |
| InquiryState | Temporary computation built from that view — hypotheses, derived values, candidate regions | `InquiryState` (Phase 14, still conceptual only) | Freely mutable, disposable, may hold contradictions |
| Agent / Operator | Nothing — it consumes ContextPackages, writes only into InquiryState | Any future Mistral agent, or any of the three operators already implemented (simulation/neural/adapters) | N/A — a function, not a store |

This separation is the one place TrustGraph's own architecture is
*ambiguous* rather than a model to copy: its "context graph" is both the
name for a dynamic per-query traversal (closer to our proposed
`ContextPackage`) and, in different docs pages, treated as near-synonymous
with the underlying knowledge graph itself. Keeping Persistent Knowledge,
Retrieved Context, InquiryState, and Agent as four distinct objects with
four distinct owners — rather than TrustGraph's looser two-way split of
"graph" and "agent" — is judged a **genuine strengthening**, not
something to weaken to match TrustGraph. This mirrors the same judgment
call already made against Foundry's single conflated Ontology (see
"Foundry / Palantir Architectural Benchmark," §H above): a system's
popularity is not evidence that its coarsest distinction is the right
one for us.

### E. Context Core analogue: what a `ContextPackage` would contain (not implemented)

TrustGraph's Context Core is the closest existing precedent, but it is a
*persisted, portable knowledge unit* (holds copied edges/schema/embeddings,
survives independently of the source documents once extracted). A
`ContextPackage` in our architecture would instead be a *retrieval
result* — the output of one query against Persistent Knowledge, not a
new unit of knowledge in its own right. Conceptually it would need:

```
ContextPackage (conceptual — NOT implemented):
    query                     # what was asked
    retrieval_config          # what retrieval strategy/filters produced this
    source_refs               # Warehouse Document/Record ids (references)
    entity_refs                # Knowledge Graph Referent ids (references)
    relationship_refs           # ClaimedRelationship ids (references)
    evidence_refs                 # Observation/Claim/Measurement ids (references)
    knowledge_graph_version_id      # which Knowledge Graph snapshot was queried
    retrieval_timestamp
    reproducibility_metadata          # enough to re-run the same retrieval later
```

The central design question the prompt raises — copies vs. references —
has one clear answer given everything already established in this
project: **references, not copies.** `CanonicalState` is content-addressed
and immutable; the Knowledge Graph (this document, §Persistence) is
promotion-gated and immutable-by-version. A `ContextPackage` that copied
data out of that substrate would immediately create a second, driftable
copy of already-authoritative information — exactly the failure mode
Phase 14 rejected when it insisted evidence stay reference-linked to its
Warehouse source rather than duplicated. TrustGraph's Context Core copies
data (edges, schema, embeddings) because it is designed to be portable
across deployments with no shared backing store — a real requirement for
a multi-tenant SaaS product, and *not* a requirement we have, since our
Persistent Knowledge layer is always reachable by reference within the
same architecture. This is a case where TrustGraph's design choice is
correct for TrustGraph's problem and wrong for ours — **explicitly
rejected as a pattern to copy, adopted only as an argument in favor of
references.**

### F. Context ≠ InquiryState — worked example

Using the prompt's own numbers: a persistent substrate of 100,000
documents / 50,000 measurements / 20,000 graph entities / 500 simulations;
a query "which FEP processing conditions should we investigate?"; a
retrieval step selecting 42 documents, 310 entities, 890 relationships, 17
measurements, 6 simulations. That selection is a `ContextPackage` — a
*view*, referencing rather than copying, with no computational content of
its own. Everything the inquiry then produces — hypotheses, derived
quantities, constraints, candidate processing regions, annotations,
simulation requests, model predictions — belongs to `InquiryState`, not
the `ContextPackage`, because it did not exist in Persistent Knowledge and
has not been validated. **This separation should become an explicit
architectural principle**, not left implicit: a `ContextPackage` answers
"what did we look at," `InquiryState` answers "what did we do with it."
Conflating them (as an easy implementation might, by letting an inquiry
write directly back into the retrieval result) would make every retrieval
result mutable — reintroducing exactly the identity/provenance problems
`CanonicalState`'s immutability was built to prevent, one layer up.

### G. Statement-level provenance

TrustGraph's three-named-graph design is direct, working prior art for
provenance below the entity level. Mapped onto our existing types:

| Provenance level | TrustGraph equivalent | Our existing type | Status |
|---|---|---|---|
| Entity level | Default graph node | `Referent` (Phase 14) | Exists conceptually |
| Observation level | Holon (reified triple + source doc) | `Observation`/`Claim`/`Measurement` (Phase 14) | Exists conceptually |
| Relationship/claim level | Holon's reified predicate + confidence | `ClaimedRelationship` (Phase 14) | Exists conceptually |
| Transformation level | `urn:graph:source` named graph (how a fact entered) | `ProvenanceInfo`/`ProvenanceRecord` — but see the gap below | **Gap, confirmed real** |

The worked example in the prompt (`Measurement_472` carrying sample,
property, value, temperature, shear rate, instrument, timestamp, and
source all at once) is already representable as one `Observation` with a
rich attribute set in the Phase 14 vocabulary — no redesign needed there.
The gap TrustGraph's example makes concrete is upstream of that: this
project's own `validation.py::validate_candidate` (documented as a known
finding during Phase 13) collapses a whole batch's provenance down to
`candidate.changes[0].provenance` — i.e., **we do not yet have
per-field/per-statement provenance surviving into `Version`, even though
the delta model (`Change.provenance` per Phase 12) already carries it up
to that point.** TrustGraph keeps provenance at the same granularity as
the fact itself, all the way through retrieval. This is the clearest,
most concrete lesson of this whole benchmark: **statement-level
provenance should become first-class**, and the first place to fix it
is the known `validate_candidate` collapse point — not a new subsystem,
a bug in how far existing per-change provenance is allowed to survive.
No redesign is proposed here per the instruction; this is a finding, not
a change.

### H. Retrieval lineage

TrustGraph's `urn:graph:retrieval` named graph answers "how was this fact
used," which is the mirror image of "how did this fact enter" —
confirming retrieval lineage is a distinct, real requirement, not
something statement-level provenance alone covers. The minimum metadata
a reproducible retrieval needs, based on TrustGraph's own design plus
the `ContextPackage` sketch in §E: the query itself, the retrieval
configuration (strategy/filters/weights), the exact set of references
returned, the Persistent Knowledge version(s) queried (so "reconstruct
this inquiry later" is answerable even after the Knowledge Graph has
grown), and a timestamp. All five already fall out of the `ContextPackage`
shape in §E — **retrieval lineage does not need a new object, only the
discipline of keeping `ContextPackage`s immutable and stored, not
transient.** This too is a "should become first-class" finding, not an
implementation.

### I. Graph + vector retrieval

TrustGraph confirms this is a real combination worth planning for
eventually (graph traversal for structural/relational queries, vector
search for semantic similarity, plus metadata/provenance/numerical
filtering layered on top) — neither replaces the other, and TrustGraph's
own pluggable-store design (separate graph stores and vector stores,
composed at query time) treats them as complementary rather than
convergent. This confirms the requirement is real. It does **not**
justify introducing a graph database or a vector database now: Phase 14
already concluded storage-architecture decisions should wait until real
query patterns exist, and nothing in this benchmark changes that
conclusion — it only adds one more independent source agreeing retrieval
will eventually need both. **Deferred, not implemented, per explicit
instruction.**

### J. Holonic / modular context

TrustGraph's answer to "avoid rebuilding the whole knowledge environment
per inquiry" is two mechanisms working together: Context Cores as
persisted, per-domain (or per-document) packages, and context graphs as
ephemeral, per-query traversals composed from them. Mapped onto the FEP
example (polymer chemistry, FEP, rheology, extrusion, mechanical
properties, crystallinity, simulation, manufacturing telemetry as
candidate domains): the better fit for our architecture is **named
subgraphs of the Knowledge Graph plus `ContextPackage`s that compose
them**, not a separate "domain dataset" or "typed knowledge module"
object. A named subgraph is just a query saved by name (e.g. "FEP domain"
= every `Referent`/`ClaimedRelationship` reachable from a `Referent`
tagged `domain=FEP`); composing "FEP + rheology + extrusion" is then
composing three saved queries into one `ContextPackage`, with no new
storage or persistence concept required. This is judged the smallest
addition that captures the lesson — Context Cores' portability
(copy-based, cross-deployment) solves a problem (multi-tenant SaaS
distribution) we do not have, per §E.

### K. Agent boundary

TrustGraph's ReAct agent runtime is real precedent that an
"agent-consumes-context, does-not-own-knowledge" boundary is buildable in
production, not just theoretically desirable — the agent manager invokes
retrieval and tools, it does not appear (from available documentation) to
have a direct write path into the triple store. That much supports our
proposed boundary. What this research did **not** find, and explicitly
flags as unconfirmed rather than assumed absent, is a described
promotion/validation gate analogous to `validate_candidate` sitting
between agent output and the graph — TrustGraph's docs describe extraction
writing to the graph and agents reading from it, but do not document
(in the pages fetched for this benchmark) a governed path for
agent-derived claims to re-enter the graph as new, audited facts. Our
architecture's stricter rule — operators write only to `InquiryState`;
promotion to Persistent Knowledge always passes through
`validate_candidate` — is not contradicted by anything found in
TrustGraph's documentation, and is judged the more conservative, and for
scientific/reproducibility purposes the more appropriate, design. **Kept
as-is; TrustGraph is supporting precedent for the read side of the
boundary, not a reason to relax the write side.**

### L. Compute economics

Where TrustGraph's pipeline suggests computation is amortized (done once,
reused many times): ingestion/extraction (LLM-based relationship
extraction, run once per document, not once per query), embedding
generation (computed once per Context Core, reused across every retrieval
that touches it), graph construction (triple-store writes happen at
ingestion, not query time), and Context Core packaging itself. What stays
inquiry-specific in TrustGraph's own design: the query, the graph
traversal/context-graph assembly for that specific question, and the
prompt/agent reasoning. This maps directly onto our own pipeline: in our
terms, ingestion/extraction/entity-resolution/provenance-construction are
Warehouse-and-Knowledge-Graph-time costs (paid once), while
retrieval/context-assembly/reasoning are InquiryState-time costs (paid
per question) — the same split this document's Phase 14 compute/energy
analysis already argued for, now with an independent second system
(TrustGraph) drawing the amortization line in the same place.

---

## Foundry + TrustGraph Synthesis

### M. Three-way comparison

| Dimension | Palantir Foundry | TrustGraph | Our architecture |
|---|---|---|---|
| Data ingestion | Pipelines (Connection → transforms) | Processor chain (`pdf-decoder → chunker → kg-extract`) | Adapters (`json_adapter`/`csv_adapter`) → `CandidateDelta` |
| Warehouse | Datasets (versioned, lineage-tracked) | Triple store + object storage for source docs | Warehouse (Phase 14, conceptual: `Source`/`Document`/`Record`) |
| Ontology | One unified Ontology (semantic + kinetic) | Ontology (OWL/SKOS/SHACL) constrains extraction only | No single ontology — Evidence + Identity + Graph + DomainSchemas + `CanonicalState` + Morpho, kept deliberately separate |
| Identity | Object Type / primary key | Holon (reified triple identity) | `Referent` (Phase 14) / deterministic `field_name` identity (`CanonicalState`) |
| Knowledge graph | Ontology graph (mutable, governed) | Context Graph (queried dynamically from holons) | Knowledge Graph (Phase 14, promotion-gated, immutable-by-version) |
| Provenance | Data lineage (dataset-level) | Statement-level, via named graphs | Entity/observation/claim conceptually defined (Phase 14); **not yet surviving to `Version`** (§G gap) |
| Lineage | First-class, dataset + workflow, both directions | `urn:graph:source` (backward only, per docs found) | Backward only (Foundry benchmark §J); forward query is a named future gap |
| Statement provenance | Not first-class (lineage is dataset-grained) | First-class (named graphs) | Not yet first-class — confirmed gap, §G |
| Retrieval | Search/Ontology queries (operational, not context-packaging) | Graph + vector + metadata retrieval, purpose-built for agents | Not designed yet (Phase 14 explicitly deferred) |
| Semantic search | Not a primary concern | Core capability | Not implemented |
| Vector search | Not a primary concern | Core capability (pluggable) | Not implemented, not committed to |
| Reusable context | Not modeled as a first-class object | Context Core / context graph | `ContextPackage`, conceptual only (§E) |
| Temporary state | Not modeled — Ontology objects are the only state | Not modeled as distinct from context graph (§C) | `InquiryState`, conceptual only, explicitly the sharper distinction of the three |
| Computation | Functions (governed write access to Ontology) | Agent tool invocation via MCP | Operators (simulation/neural/adapters), write only to `CandidateDelta` |
| Simulation | Not a primary concern | Not a primary concern | First-class interface (`backends/simulation`) |
| Agents | Functions/AIP act with write access | ReAct loop, read-heavy, write path undocumented | Explicitly never own or mutate Persistent Knowledge/CanonicalState (design principle, not yet an agent) |
| Validation | Not a distinct gate — writes are governed by permissions, not a schema/constraint pipeline | Not documented as a distinct gate | `validate_candidate` — the sole, atomic, non-bypassable gate |
| Immutability | Datasets append-only; Ontology objects mutable | Graph is appended-to; no stated immutability guarantee | `CanonicalState`/`Version` immutable by construction; Knowledge Graph promotion-gated |
| Operational workflows | First-class (Actions, Workshop apps) | Not a focus | Explicitly out of scope (Phase 14 §non-goals) |

Classified per the instruction's five buckets, at the level of individual
ideas rather than whole products: **borrow** — statement-level provenance
discipline, retrieval-as-a-first-class-lineage-tracked-operation, holonic
domain composition via named subgraphs; **adapt** — the Context
Graph/Context Core split (as `ContextPackage`, reference-based rather
than copy-based), the three-layer context-graph shape as a target for a
future retrieval layer; **defer** — graph+vector retrieval
infrastructure, any RDF/graph-database/vector-database adoption, agent
runtimes; **reject** — copy-based portable knowledge units (§E), a single
universal ontology (already rejected against Foundry, reconfirmed here),
mutable Ontology-style write access for agents; **already solved** — the
sole-validation-gate/immutable-version model, deterministic identity,
operator-not-agent framing for existing computational producers
(simulation/neural/adapters).

No forced convergence: Foundry and TrustGraph solve materially different
problems (governed *operational* enterprise state vs. *agent-facing
retrieval* over a knowledge graph) and neither is "the same architecture
as ours wearing a different name." Where all three agree — a governed
boundary between persistent knowledge and whatever reasons over it, and
typed/identified relationships over flat data — that agreement is
evidence the boundary is a real architectural requirement, not evidence
we should adopt either system's specific mechanism for it.

### N. The proposed three-plane information flow

The prompt's Persistent Data Plane → Context Plane → Computational Plane
model is a faithful redrawing of everything already established across
this document and the Foundry benchmark, with one addition: it names the
Context Plane as a plane in its own right, distinct from both Persistent
Data and Computation. That is judged useful and consistent with §D's
four-layer separation — the Context Plane is exactly `ContextPackage`
construction (retrieval), the Computational Plane is exactly
`InquiryState` plus operators. **This model is adopted as the
organizing description of the target architecture, with the explicit
caveat (per the instruction not to assume it is correct) that it has not
been tested against a real multi-step inquiry** — the FEP example in §F
exercises Persistent Data → Context → one InquiryState, not iteration
back into the Context Plane for a follow-up query, which is the harder
case a real implementation would need to handle.

### O. Mistral deployment order

Given everything else in this document, the dependency order is judged
correct as proposed, with one clarification: "data quality" and "data
organization" are not sequential phases but the same phase Phase 14
already scoped (Evidence → Warehouse → Knowledge Graph). The corrected
minimum order:

```
1. Evidence/Warehouse quality & normalization  (Phase 14, conceptual)
2. Knowledge Graph promotion + provenance survival fix (§G gap)
3. Retrieval (graph + vector + filters)         -- not built
4. ContextPackage construction + lineage         -- not built
5. InquiryState (conceptual schema exists; not implemented)
6. Operators (3 of 4 kinds already exist: simulation, neural, adapters)
7. Agent (Mistral or otherwise) -- consumes 1-6, owns none of them
```

The concrete minimum before a Mistral agent should be deployed, per this
ordering: steps 1-2 are documented but not implemented; steps 3-5 are not
implemented at all. **An agent deployed today would have nothing to
retrieve from and no `ContextPackage`/`InquiryState` boundary to respect
— it would necessarily fall back to exactly the "reconstruct the
environment from raw documents" pattern this whole investigation exists
to avoid.** That is the concrete, falsifiable form of "not yet ready,"
not a generic caution.

### P. Ten proposed principles, evaluated

| # | Principle | Verdict |
|---|---|---|
| 1 | Persistent knowledge is built once and reused | **Supported** — matches TrustGraph's ingestion/Context-Core split and Foundry's dataset/lineage model; already the design intent of Phases 12-14 |
| 2 | Retrieval should be cheaper than reconstructing context | **Supported, not yet built** — real requirement per §I, §L; no retrieval infrastructure exists |
| 3 | Context is distinct from computational state | **Supported and sharpened** — §D, §F; the clearest, most concrete lesson of this benchmark alongside #7 |
| 4 | InquiryState is temporary and reproducible | **Supported as designed; reproducibility depends on #7** — an `InquiryState` is only reconstructible if its `ContextPackage`'s lineage (§H) is captured |
| 5 | Agents consume context rather than own the knowledge substrate | **Supported** — confirmed by both Foundry (rejected) and TrustGraph (apparently followed, on the read side) as a real, achievable boundary |
| 6 | Agents propose changes rather than directly mutate authoritative state | **Supported, and stricter than either benchmark system** — neither Foundry (Functions have governed write access) nor TrustGraph (write path undocumented) enforces this as strictly as `validate_candidate` already does |
| 7 | Provenance exists at entity, observation, statement and transformation levels | **Partially true today — confirmed real gap** — conceptually defined (Phase 14) but does not yet survive `validate_candidate` (§G); this is the single most actionable finding in this document |
| 8 | Persistent state remains immutable/versioned | **Already true** — `CanonicalState`/`Version`, unchanged by this research |
| 9 | Multiple computational representations derive from shared state | **Already true** — Three.js/SVG/graph-analysis backends, Phase 12's convergence tests |
| 10 | The persistent graph is independent of any particular LLM | **Already true by construction** — nothing in `core/`, `morpho/`, `adapters/`, or `backends/` references a model; TrustGraph's own architecture is consistent with this (the graph outlives any one agent session) but this project already had it |

### Final questions, answered directly

**1. What does TrustGraph already solve that we should not reinvent?**
Statement-level provenance via reified triples plus separated
provenance/retrieval named graphs, and the operational shape of
graph+vector+metadata retrieval composed together. These are working,
documented mechanisms; if/when a retrieval layer is built, study
TrustGraph's named-graph provenance split as a reference design rather
than deriving one from scratch — while still evaluating RDF itself on
its own merits at that time (see Q6).

**2. What does Foundry solve that TrustGraph does not?**
Governed operational write access at scale (Actions/Functions with
permissions), enterprise lineage across heterogeneous pipelines, and a
single unified semantic layer serving many downstream applications.
TrustGraph is agent/retrieval-focused and does not appear to solve — or
attempt to solve — governed operational mutation at all.

**3. What remains unsolved by both?**
A first-class, typed distinction between "context I retrieved" and
"state I computed from it" (§D) — TrustGraph's context graph blurs the
two, Foundry does not model a temporary workspace at all. Also unsolved
by both: reproducible retrieval lineage as a queryable, storable object
(TrustGraph tracks *that* retrieval happened via named graphs, not
clearly a replayable `ContextPackage` with its own identity).

**4. Is persistent knowledge -> reusable context -> InquiryState a
useful decomposition?**
Yes — confirmed by independent convergence with TrustGraph's own
ingestion-to-agent shape (§C), and judged an improvement on TrustGraph's
own two-way split because it keeps computation state out of the context
object entirely (§D, §F).

**5. Should Context and InquiryState remain separate concepts?**
Yes, unconditionally — this is the sharpest, most concrete conclusion of
this benchmark. Every failure mode this document can construct
(unreproducible inquiries, provenance loss, accidental mutation of a
retrieval result) traces back to conflating the two.

**6. Should statement-level provenance become first-class?**
Yes. This is not a hypothetical — §G identified a real, already-existing
gap: per-change provenance is captured in `Change`/`CandidateChange`
(Phase 12) but collapses to `changes[0].provenance` inside
`validate_candidate` before reaching `Version`. Becoming first-class does
not require RDF or a new subsystem; it requires that collapse point to
stop discarding information it already has. (Not implemented here, per
this phase's explicit no-implementation constraint — recorded as a
finding for a future phase.)

**7. Should retrieval lineage become first-class?**
Yes, once retrieval exists at all — it does not yet. The minimum
metadata (§H) is small and falls directly out of the `ContextPackage`
sketch; there is no reason to build retrieval without also making its
lineage capturable from day one, rather than retrofitting it later the
way statement-level provenance now needs retrofitting (Q6).

**8. Should agents permanently remain outside the authoritative graph?**
Yes. Neither benchmark system argues against this as strictly as our own
existing `validate_candidate` gate already enforces it (§K, principle 6
in §P) — if anything, both systems' weaker guarantees here (Foundry's
governed-but-real write access, TrustGraph's undocumented write path)
are an argument for keeping our stricter rule, not relaxing it toward
either.

**9. What is the minimum information infrastructure we should build
BEFORE deploying Mistral?**
Per §O: the provenance-survival fix in `validate_candidate` (§G), a
retrieval layer (graph + filters, vector search deferred until a real
semantic-search need appears), a persisted `ContextPackage` object with
lineage metadata, and an implemented (not just conceptual)
`InquiryState`. Deploying an agent before those four exist means the
agent reconstructs its own environment every time — the exact waste this
whole investigation was commissioned to evaluate.

**10. What should the next implementation phase actually build?**
Per this document's own no-implementation constraint, this is a
recommendation for a *future* phase, not this one: (a) fix the
`validate_candidate` provenance-collapse bug so per-change provenance
survives into `Version` — smallest, most concrete, and already fully
specified by the existing gap; (b) implement `ContextPackage` as a real,
reference-only, retrieval-result type with lineage metadata, without yet
building the retrieval strategies that populate it; (c) implement
`InquiryState` as a real but storage-backend-agnostic conceptual object
(in-memory only, per the existing "no databases yet" constraint),
proving the promotion path from `InquiryState` back through
`CandidateDelta`/`validate_candidate` with a synthetic example before any
retrieval or agent work begins.

**Sources consulted** (TrustGraph's current documentation, fetched during
this investigation):
[Documentation • TrustGraph](https://docs.trustgraph.ai/) ·
[Architecture • TrustGraph](https://docs.trustgraph.ai/overview/architecture.html) ·
[Understanding Context Graphs • TrustGraph](https://trustgraph.ai/guides/key-concepts/context-graphs/) ·
[Working with Context Cores • TrustGraph](https://docs.trustgraph.ai/guides/context-cores/) ·
[Holons, Context Graphs, and Ontologies • TrustGraph](https://trustgraph.ai/guides/key-concepts/ontologies-holons-context-graphs/) ·
[trustgraph-ai/trustgraph • GitHub](https://github.com/trustgraph-ai/trustgraph)

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
