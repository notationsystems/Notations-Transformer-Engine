# Phase 14 — Research Data Pool / Evidence Layer Investigation

Status: **research only**. No implementation file was read for the
purpose of modification, and none was modified. This document designs a
layer that sits entirely *upstream* of `adapters/` — nothing here
proposes touching `core/canonical/`, `morpho/`, `core/projection/`, or
`runtime/`.

Central principle, stated once and held throughout:
**DATA DISCOVERY ≠ CANONICAL STATE.** Everything below describes a place
for uncertain, incomplete, duplicated, and conflicting information to
live *before* it earns the right to become a `CandidateDelta` — which
remains the unchanged, existing entry point into the unchanged, existing
`validate_candidate` gate.

---

## A. Purpose

The evidence/data pool must let the system **continuously accumulate**
scientific and industrial information from heterogeneous sources —
papers, datasets, patents, manufacturer datasheets, simulation outputs,
experiments, process data, sensor records, databases, APIs, web
documents, future proprietary data — **without requiring that every
discovered fact immediately become `CanonicalState`.**

Minimum purpose, stated precisely (not "support every source," per the
instruction not to attempt that):

1. Capture raw evidence with full fidelity and traceable provenance,
   never destroying the original on later processing.
2. Let uncertain, duplicate, and *conflicting* claims about the same
   fact coexist without forcing premature resolution.
3. Support progressive refinement (raw → extracted → normalized) as a
   chain of *additional*, separately-stored artifacts, not in-place
   transformation.
4. Provide a queryable substrate from which a curated, sufficiently-
   validated subset can be handed to the **existing, unchanged** adapter
   boundary as ordinary `CandidateDelta`s.
5. Never become authoritative itself. Canonical authority stays exactly
   where Phases 1-13 established it.

Everything else in this document is in service of these five points,
not an attempt to build a general research database.

---

## B. Evidence model

### Information classes: which are genuinely distinct

Not every noun in the prompt's list needs its own top-level type.
Applying "do not create abstractions without justification":

| Concept | Distinct type, or a specialization/metadata of another? | Reasoning |
|---|---|---|
| Source | **Distinct.** | Identity independent of any one document; tracked for trust/quality over time. |
| Document | **Distinct.** | An immutable, retrieved artifact — the raw-evidence anchor everything else traces back to. |
| Dataset | **Specialization of Document** (a Document whose content is structured/tabular). | Avoids a parallel type for "PDF" vs. "CSV" that differ only in content shape, not in how they're provenanced or stored. |
| Record | **Distinct.** | A raw structural unit *within* a Document (one CSV row, one API response object) — still mechanical, not yet semantic. |
| Observation | **Distinct.** | A semantic, extracted fact ("FEP melt viscosity at 260°C = X") tied to one or more Records. |
| Measurement | **Specialization of Observation** (one with a numeric value + unit + method/instrument). | A Measurement is an Observation with more required structure, not a different kind of thing. |
| Claim | **Distinct, and broader than Observation.** | Not every asserted proposition is measured data — "we conclude X is suitable for high-temperature use" is a Claim but not an Observation. Hierarchy: `Claim ⊇ Observation ⊇ Measurement`. |
| Entity (referent) | **Distinct — but see naming warning below.** | The material/instrument/process/sample a Claim is *about*. Needs entity resolution (is "FEP" in paper A the same referent as "FEP" in paper B?) — a hard, explicitly deferred problem (§S). |
| Relationship | **Distinct — but see naming warning below.** | A claimed connection between two referent Entities. |
| Evidence | **Not a new stored type.** | Used descriptively to mean "a Claim/Observation together with its full provenance chain back to a Document." Inventing a wrapper type here would just duplicate Claim + a join. |
| Derived value | **Distinct.** | A value computed *from* other Observations/Claims (an average, a curator's selection, a simulation-derived estimate) — its provenance graph has a different shape (fan-in from multiple Observations plus a stated method), which is what makes it a real, separate concept. |
| Candidate | **Not a new type — reuses the existing `CandidateDelta`.** | The pool's output boundary is the adapter interface that already exists. Inventing a parallel "pool candidate" type would create two candidate mechanisms feeding one validation gate — rejected explicitly (see anti-pattern check, "multiple sources of truth"). |
| Canonical state | **Unchanged, outside the pool entirely.** | — |

**Naming collision warning (concrete, implementation-relevant):**
`morpho/ir.py` already defines `Entity` and `MorphoRelation`. Whatever
implements this pool must **not** reuse those names for the pool's
referent/relationship concepts — recommend `Referent` (not `Entity`) and
`ClaimedRelationship` (not `Relationship`) specifically to keep the two
layers textually and conceptually unconfusable, given they will likely
be imported in adjacent code (an adapter bridging pool → `CandidateDelta`
touches both).

### Per-concept properties (the eight questions, tabulated)

| Concept | Represents | Mutable? | Identity? | Provenance? | Can conflict? | Can become canonical? | Agent-creatable? | Deletable? | In graph relationships? |
|---|---|---|---|---|---|---|---|---|---|
| Source | Origin of documents | Metadata (quality score) may evolve; the source's own referent identity does not | Yes — stable reference | Has its own (who registered it) | N/A (a source doesn't assert facts) | No | Yes, with review | No — archived, not deleted | Yes (Source —published→ Document) |
| Document | A retrieved artifact | **No** — immutable once ingested; a changed webpage is a *new* Document version, mirroring `Version`'s own immutability | Yes — content hash + retrieval metadata | Yes (Source, retrieval method/time) | No (a container, not an assertion) | No | Yes | **No — never deleted**, only archived/deprecated | Yes (—contains→ Record/Observation) |
| Dataset | A structured Document | Same as Document | Same as Document | Same as Document | No | No | Yes | No | Same as Document |
| Record | One raw unit within a Document | No | Yes — scoped to its Document | Yes (Document + locator) | No (mechanical, not yet a claim) | No | Yes | No | Yes (—part_of→ Document) |
| Observation / Measurement | A semantic, extracted fact | No — a correction is a *new* Observation, linked, not an edit | Yes | Yes (Record(s) + extraction method/agent/time) | **Yes — by design** (§E) | No, directly | Yes | No — superseded, not deleted | Yes (—about→ Referent, —measures→ Property, —under→ Condition) |
| Claim (general) | Any asserted proposition | No | Yes | Yes | Yes | No, directly | Yes | No | Yes |
| Referent (Entity) | A specific material/instrument/process/sample | No (its *description* can grow; its identity doesn't change) | Yes — subject to entity resolution (§S, unresolved) | Yes (first-observed-in) | Two Referents can be *proposed* as the same thing — that proposal is itself evidence, not automatic merge | No, directly | Yes | No | Yes — the primary graph node type |
| ClaimedRelationship | An asserted connection between two Referents | No | Yes | Yes | Yes (two sources can claim different relationships) | No, directly | Yes | No | Is itself a graph edge |
| Derived value | A value computed from other Observations | No — a re-derivation is a new Derived value | Yes | Yes, **and** references every input Observation + method | Can itself be superseded by a better derivation | **This is the only pool concept eligible to seed a Candidate** (§O) | Yes, but high-stakes derivations should default to requiring review before being proposed as a Candidate | No | Yes (—derived_from→ Observation, ×N) |
| Candidate (`CandidateDelta`) | Unchanged existing concept | N/A | N/A | N/A | N/A | This *is* "becoming canonical," pending `validate_candidate` | N/A | N/A | N/A |

---

## C. Data model

### Raw → Extracted → Normalized (three pool-internal layers, before the existing Candidate stage)

```
RAW            Document, Record        (verbatim; e.g. the PDF bytes, one CSV row)
  |
EXTRACTED      Observation / Claim      ("FEP melt viscosity at 260 C = X",
  |                                       tied to the Record(s) it came from)
  |
NORMALIZED     NormalizedRecord         (material="FEP", property="melt_viscosity",
                                          condition={temperature: 260 "C"}, value=X)
```

**The original is never destroyed.** Each stage is a *new, separately
stored* object referencing its predecessor by id
(`Record.document_id`, `Observation.record_ids`,
`NormalizedRecord.observation_id`) — never an in-place edit. This is a
direct, deliberate mirror of how `CanonicalState`/`Version` already work
in this codebase: "update" always means "produce a new immutable
object," never mutate the old one. The pool inherits that discipline
rather than inventing a different one.

`NormalizedRecord` is the layer that finally speaks the vocabulary a
`StateSchema` could plausibly declare (`property`, `value`, `unit`) —
but it is **still not a Candidate.** Promotion to `CandidateDelta` is a
separate, explicit act (§O), never automatic.

---

## D. Provenance model

Minimum provenance graph, one hop per stage, each hop a real stored
reference (not a flattened string until the very last hop):

```
Document (id, source_id, retrieval_method, retrieval_timestamp,
          content_hash)
    |
Record (id, document_id, locator, raw_content)
    |
Observation (id, record_ids: [...], extraction_method, extracted_by,
             extracted_at, raw_text_span)
    |
NormalizedRecord (id, observation_id, property, value, unit,
                  condition_ids: [...], normalization_method, confidence)
    |
  [pool boundary -- existing, unchanged from here down]
    |
CandidateChange.provenance.source = "evidence_pool:normalized_record:<id>"
    |
Version.provenance  (existing ProvenanceInfo, unchanged shape)
```

**`Locator` is deliberately loosely typed** — page/table/row for a PDF,
a CSS selector for HTML, a cell reference for a spreadsheet, a JSON
Pointer for an API response. Forcing one rigid locator schema across
every document format would be exactly the "universal ontology" the
prompt warns against; an open, format-appropriate locator payload (a
plain dict, validated only against a per-format convention chosen by
whichever extractor produced it) is the smaller, more honest choice.
This is a deliberate design decision, not a gap.

**The existing `ProvenanceInfo.source: str` field (`core/canonical/`,
unchanged) is the correct, sufficient hook** for connecting the two
worlds — exactly as Phase 12 already used it (`"json_adapter:lab_run_42"`)
for a shallower case. No change to `ProvenanceInfo`'s shape is proposed
or needed: `"evidence_pool:normalized_record:<id>"` is just a longer,
equally-valid string following the same convention. Walking *backward*
from a `Version`'s field to "page 17, table 4, row 8" means: read
`ProvenanceInfo.source`, parse the `normalized_record` id out of it,
then walk the pool's own stored chain — a query entirely inside the pool,
never requiring canonical-layer code to know anything about `Document`/
`Record`/`Observation`.

---

## E. Conflict model

Given three sources reporting three different viscosities, **the pool
stores all three `Observation`s side by side, unmodified, forever.**
Nothing is averaged, deduplicated, or silently reconciled at ingestion.

Each `Observation` independently carries: its own provenance chain
(§D), its own `condition_ids` (§F — *not* optional; an Observation
without recorded conditions is a materially weaker piece of evidence and
should be flagged as such, not silently treated as comparable to one
with conditions recorded), a `confidence` (required for anything
model-extracted, optional/typically `1.0` for a verbatim table
transcription), the *Source*'s independently-tracked quality score
(a property of Source, not copied onto every Observation — avoids
duplicating a value that can change as more evidence about a source's
reliability accumulates), and its own timestamp.

**Resolving a conflict is itself an evidentiary act, not a system
operation.** It is modeled as a `Derived value` whose provenance is
`derived_from: [O1, O2, O3], method="manual_curation", by="<curator>"`
(or, later, `method="median"`, `method="model:mistral-v..."` — same
shape). This reuses the `Derived value` concept from §B rather than
inventing a separate "resolution" or "conflict" type — a conflict
resolution *is* a derived value, nothing more specialized is needed.
**Only a `Derived value` (never a raw `Observation` directly) is
eligible to become the basis of a `CandidateDelta`** — see §O for why
this single rule is what keeps `CanonicalState` from ever silently
absorbing an unreconciled conflict.

---

## F. Context model

`viscosity = 1200 Pa·s` is close to meaningless without
`temperature = 190°C`, `shear_rate = 100 s⁻¹`, `material grade = "FEP
grade X"`. Where should that context live?

**Recommendation: context is not a new type.** A `Condition` is
structurally identical to a small set of `Observation`s (a
(property, value, unit) triple is exactly what an `Observation` already
is) — so *conditions are just Observations that contextualize another
Observation*, linked by an explicit `under` `ClaimedRelationship`,
exactly matching the example diagram
(`Observation —under→ Condition`). This avoids two failure modes at
once: baking context into compound property names
(`"viscosity_at_190C_100s-1"`, which doesn't compose and can't be
queried by range — rejected, and it's exactly the kind of ad hoc string
convention this whole project has been careful about elsewhere), and
inventing a second, parallel schema for "condition data" that would
duplicate `Observation`'s shape for no reason.

Context lives at the `Observation` level (each Observation optionally
links to N context Observations), never string-encoded, and never
forced into `CanonicalState` merely to be recorded — a `CandidateDelta`
built later from a `Derived value` can choose to promote relevant
condition fields into the eventual canonical record (e.g. as sibling
scalar fields plus a `"contains"` edge, per
`docs/PHASE_13_ARCHITECTURE_INVESTIGATION.md`) or leave them as
pool-only context, depending on whether the target `StateSchema` cares.

---

## G. Graph strategy

Given the relationship-heavy shape of this data (`Document —contains→
Observation —about→ Referent —processed_by→ Process —produces→
Measurement`), a graph view is clearly the right *query* model for
relationship/provenance navigation. It is **not** proposed as primary
storage.

**Recommendation: graph = a derived index over structured records, not
the primary store.** Every pool object (`Document`, `Record`,
`Observation`, `NormalizedRecord`, `Referent`, `ClaimedRelationship`,
`Derived value`) is a plain record with explicit id-reference fields
(`document_id`, `record_ids`, `derived_from`, etc.) — the graph is
*constructed* from those references (adjacency lists, or a real graph
index later) rather than being the thing that's authoritative. This
mirrors §16's Morpho conclusion exactly: structure is compiled/derived,
never a second source of truth (the same discipline
`docs/PHASE_13_ARCHITECTURE_INVESTIGATION.md` §G already established for
`CanonicalState`/Morpho, reapplied one layer upstream, consistently).

## H. Warehouse strategy

Bulk numeric queries (§14's range/aggregation examples) are exactly what
a warehouse-style, columnar/tabular index over `NormalizedRecord`
(indexed on `property`, `value`, `unit`, `condition` fields) is good at,
and exactly what a graph traversal is *not* good at. Recommendation:
**warehouse + graph index, not one representation forced to serve both
query shapes** — directly answering §7/§8's own framing, confirmed
rather than assumed, by walking through §14's concrete query list below.

---

## I. Storage comparison

No product is chosen; no dependency is added. Conceptual fit only:

| Option | Best fit in this architecture | Weak fit for |
|---|---|---|
| A. Files + metadata index | Raw `Document` storage (PDFs, HTML snapshots genuinely are files) + a lightweight catalog | Analytics, graph traversal |
| B. Relational database | `NormalizedRecord` storage, analytical range queries | Rapidly evolving/heterogeneous claim shapes pre-normalization |
| C. Document store (schema-flexible) | `Record`/`Observation` storage (heterogeneous, evolving shape) | Numeric analytics |
| D. Columnar analytical store | Bulk `NormalizedRecord`/`Measurement` analytics, time series | Graph traversal, document retrieval |
| E. Graph database | Relationship/provenance navigation, multi-hop queries | Bulk numeric aggregation |
| F. Vector database | Literature/document *similarity* search (embeddings) — a genuinely different capability (unstructured-text retrieval), relevant later for agent-driven discovery, not for the structured evidence itself | Structured numeric/relational queries |
| G. Object storage + metadata DB + graph index | This is essentially the recommended shape already | — |
| H. Hybrid | **Recommended**, see below | — |

**Recommendation (architectural shape, not a product choice):**
content-addressed blob storage for raw `Document`s (hash the bytes for
the id — the same content-addressing discipline `Version.id` already
uses, applied one layer upstream, for the same reason: detect silent
source changes, guarantee immutability); a structured record store for
`Record`/`Observation`/`NormalizedRecord`/`Referent`/
`ClaimedRelationship`/`Derived value` (small-scale, this could be plain
files or SQLite — both zero new dependencies; larger-scale, a real
document or relational store); a graph *index* derived from the
structured store's own reference fields (§G); optionally, later, a
vector index over document text for similarity search (§I's `F`,
relevant to one specific query type only, see §L). The point of stating
it this way is that the **architecture doesn't commit to a technology**
— it commits to three roles (blob store, structured store, derived
index), each independently satisfiable at whatever scale is actually
needed when this is built.

---

## J. Agent boundary

```
Agent
  |
  v
Acquisition Task   (a durable, queryable work item -- "fetch + extract
  |                  document X" -- stored in the SAME structured store
  |                  as everything else in the pool, not a separate
  |                  queue/broker system)
  v
Evidence           (Document / Record / Observation -- written to the
  |                  pool; NOT yet canonical, NOT yet a Candidate)
  v
Candidate Record   (a Derived value flagged "ready for proposal" --
  |                  still a pool object, still not a CandidateDelta)
  v
Validation / Review (a human, or a higher-trust process, decides
                      whether to construct an actual CandidateDelta via
                      the EXISTING, UNCHANGED adapter mechanism and
                      submit it to validate_candidate)
```

**Explicitly allowed:** search, retrieve, scrape, parse, extract,
classify, deduplicate, entity-link (propose only — see §S), normalize,
enrich, propose `ClaimedRelationship`s, propose `Derived value`s as
Candidate Records.

**Explicitly forbidden, and why the model already prevents each:**
directly mutate `CanonicalState` (no pool object type is a
`CanonicalState`/`Version`; the only path in is the unchanged
`validate_candidate`); bypass validation (there is no second entry
point — §O); delete authoritative history (Document/Record/Observation
are never deleted, only superseded/archived, per §B's table); rewrite
provenance (every pool object's provenance fields are set once at
creation, never edited — same immutability discipline as `Version`);
alter Version IDs (agents never touch `core/canonical/version.py` or
anything it produces); silently resolve conflicts (§E: resolution is
itself a `Derived value`, itself subject to the same review-before-
Candidate-promotion rule as anything else — "propose," never "decide").

**Stateless workers, not persistent agent processes.** Given the
instruction not to choose a distributed architecture prematurely: an
agent should be a stateless task worker that reads one `Acquisition
Task` from the shared store, does its work, writes results back to the
pool, and can crash and restart without losing anything — because
*all* durable state lives in the pool's own structured store (Tasks
included), never in the agent process. This needs nothing beyond "a
table with a status column" conceptually; no message broker, actor
system, or distributed coordination layer is implied or required at
this stage.

---

## K. Mistral / local-model boundary

Plausible future roles: document/table extraction, scientific entity
recognition, property/relation extraction, document classification,
deduplication assistance, entity-resolution assistance, query
expansion, evidence ranking, candidate generation.

**Deterministic processing vs. probabilistic inference — kept
structurally distinct, not just conventionally distinct:** every
`Observation`/`NormalizedRecord`/`ClaimedRelationship`/`Derived value`
already carries `extraction_method` (§D) and, per §B's table,
`confidence`. The rule: **`confidence` is required, not optional, for
any pool object whose `extraction_method` names a model** (e.g.
`"model:mistral-v3"`); it may be omitted (or defaulted to `1.0`) for a
verbatim, deterministic transcription (a human typing in a table value,
a regex-based unit parse). This is not a new mechanism — it directly
mirrors the *existing* architecture's own `is_canonical`/
`inference_status` distinction on `MorphoRelation` (§11 of the frozen
spec): a model's output is structurally treated the same way an
*inferred* relation already is — never directly authoritative, always
flagged, always subject to the same gate as anything else. Reusing that
existing discipline, rather than inventing a parallel one, is the point.

**Where inference sits in the pipeline:** only at the Extraction and
Normalization stages (§C) — a model may read raw `Document`/`Record`
content and propose `Observation`s or `NormalizedRecord`s. It never sits
downstream of the pool boundary; it has no more access to
`validate_candidate` than any other producer (§J).

---

## L. Query requirements

Working through the prompt's own example queries determines which index
(warehouse-style vs. graph-style vs., in one case, vector) each needs —
confirming §G/§H's hybrid recommendation with evidence rather than
assertion:

| Query | Index needed |
|---|---|
| "Polymers with Tg > X" | Warehouse: numeric range over `NormalizedRecord(property="glass_transition")` |
| "FEP viscosity measurements above 180°C" | Warehouse: range query, joined against `under`-linked Condition Observations (§F) |
| "Experiments performed under pressure > X" | Warehouse: same pattern |
| "Sources supporting this property" | **Graph**: `Observation —about→ Referent`, reverse-traverse `—extracted_from→ Document —published_by→ Source` |
| "Conflicting measurements of this property" | Warehouse: group-by `(Referent, property, condition-signature)`, surface groups with >1 distinct value |
| "Materials processed under similar conditions" | Mixed: numeric distance over Condition bundles (warehouse), OR embedding similarity (**this is the one query that plausibly justifies a future vector index**, §I option F) |
| "Simulation results associated with this material" | **Graph**: multi-hop traversal |
| "Candidate formulations derived from these observations" | **Graph**: traverse `derived_from` edges |
| "All evidence that contributed to this canonical state" | **Graph, seeded from OUTSIDE the pool**: start at a `Version`'s field, read `ProvenanceInfo.source`, walk backward through §D's chain — this is the query that *validates* §D's provenance model is sufficient, not just a nice-to-have |

Both a numeric/range index and a relationship index are genuinely
required by different queries in this list — not a stylistic preference,
a conclusion this table demonstrates directly.

---

## M. Materials-domain example

```
SOURCE: "Journal of Polymer Science, Vol. 40"
  -> DOCUMENT: paper.pdf (content-addressed, retrieved 2026-08-01)
       -> RECORD: page 17, table 4, row 8 (raw cell contents, verbatim)
            -> OBSERVATION: "FEP melt viscosity at 260 C = 1250 Pa.s"
                 (extraction_method="human_transcription", confidence=1.0)
                 --under--> OBSERVATION (context): "temperature = 260 C"
                 --about--> REFERENT: "FEP" (grade unresolved -- flagged, §S)
                 -> NORMALIZED RECORD: {property: melt_viscosity,
                       value: 1250, unit: "Pa.s",
                       condition: {temperature: 260 "C"}, confidence: 1.0}

[ two more sources report 1200 and 1280 for the same nominal condition --
  all three NormalizedRecords coexist, per §E ]

  -> DERIVED VALUE: median(1250, 1200, 1280) = 1250,
       derived_from=[NR1, NR2, NR3], method="median", by="curator_jane"
       -- flagged as a Candidate Record

  -> [pool boundary] existing adapter builds a CandidateDelta from the
     Derived Value's {property, value, unit} -> existing StateSchema
     -> validate_candidate() -> Version -> CanonicalState -> Morpho
     -> Three.js / SVG / graph backend representations

  Uncertainty and provenance retained at every step: the three raw
  NormalizedRecords are never deleted after the median is taken: they
  remain queryable ("find conflicting measurements of this property",
  §L) even after a canonical value exists.
```

## N. FEP / free-energy domain example (architectural exercise only — no FEP implemented)

Classifying each item from the prompt's list by pool layer:

| Item | Layer |
|---|---|
| Molecular structures, force fields, lambda schedules, simulation parameters | **Raw evidence** (Document/Record — e.g. an input file) or, once parsed, **Observation** (a parameter value extracted from a config) |
| Trajectories | **Raw evidence** (Document, likely large-object/blob-stored, referenced not embedded) |
| Free-energy estimates, uncertainty, convergence diagnostics | **Derived value** — computed from a simulation run, `derived_from` referencing the run's parameters/trajectory Document, `method="simulation:<engine>+<estimator>"` |
| Replicas | Each replica's result is its own `Observation`/`Derived value`; the reported estimate across replicas is itself a further `Derived value` (`derived_from` = the per-replica values) — the same two-level derivation pattern as §M's median, reused without a new concept |
| Thermodynamic conditions | **Context Observations**, linked `—under→`, exactly as §F |
| Experimental reference values | **Observation**, same as any other measured data — coexists with the simulation-derived `Derived value` for the *same* property, subject to the exact same conflict model (§E): a simulation estimate and an experimental measurement of "the same" free energy are two independent Observations until a curator (or later, a reviewed model) proposes a reconciliation as a further `Derived value`. |

No new pool concept was needed for this domain — confirms the primitive
set from §B is not accidentally polymer-specific.

---

## O. CanonicalState boundary

```
DATA POOL                          CANONICAL STATE
  uncertain                          validated
  conflicting                        versioned
  incomplete                         immutable
  duplicated                         authoritative
  exploratory                        reproducible
  machine-extracted  ─┐
  human-generated     ├─ ALL COEXIST   only a Derived Value, reviewed and
  simulation-derived ─┘                promoted through the UNCHANGED
                                        adapter -> validate_candidate gate,
                                        ever crosses this line
```

**The one crossing rule, stated precisely:** only a `Derived value` — never
a raw `Observation` directly — is eligible to seed a `CandidateDelta`.
This single rule is what makes the boundary enforceable rather than
aspirational: it means "propose a Candidate" is always, structurally, an
act of *synthesis with a stated method*, even when the method is trivial
("accept this one Observation as-is, no conflict existed"). A `Derived
value` with exactly one input and `method="accept_as_is"` is a
completely ordinary case of this rule, not a special case — no separate
"direct promotion" path is needed or proposed.

`CanonicalState` is explicitly **not** asked to become the warehouse:
the pool retains everything (§E); canonical state retains only what was
actually promoted, exactly as today.

## P. Morpho boundary

**Recommendation: Morpho remains scoped to `CanonicalState` only — it
does not become a second IR for pool/evidence structure.**

Justification: Morpho's entire proven value (Phases 7-9) rests on being
a *pure, deterministic function of one frozen, validated
`CanonicalState`*. Pool data is, by design (§A), uncertain, mutable-by-
addition, and conflicting — feeding it through `compile_morpho` would
either force Morpho to somehow represent "three conflicting values for
one property" (breaking its determinism/purity contract, since "the"
value wouldn't be well-defined) or silently pick one (recreating exactly
the "silently resolve conflicts" anti-pattern §J forbids for agents,
now committed by the compiler instead).

If the evidence pool itself eventually needs visualization (e.g., "show
me the provenance graph behind this canonical value"), that is a
**separate, pool-native concern** with its own (much simpler — likely
just the graph index from §G rendered directly) representation path,
outside `backends/`, never routed through `compile_morpho`. This keeps
Morpho from becoming a database or an ontology engine, per the explicit
warning, and keeps the "no renderer/representation concept leaks
upstream into canonical state or Morpho" invariant — proven repeatedly
in Phases 7-12 — intact for a new reason: because the *evidence pool*
now also can't leak downstream into Morpho, closing the boundary from
the other side.

---

## Q. Recommended architecture

```
                         EXTERNAL WORLD
                              |
         +----------+---------+---------+----------+
         v          v         v         v          v
      papers    datasets   sensors     APIs   manufacturer
                                                  data
         |          |         |         |          |
         +----------+---------+---------+----------+
                              v
                       ACQUISITION
              (Agent, stateless, task-queue-driven, S3)
                              |
                              v
                       RAW EVIDENCE
                  (Document, Record -- blob store,
                   content-addressed, never deleted)
                              |
                              v
                        EXTRACTION
              (Observation / Claim -- deterministic or
               model-assisted, extraction_method + confidence
               always recorded, S10)
                              |
                              v
                      NORMALIZATION
                  (NormalizedRecord -- property/value/unit/
                   condition, still pool-only)
                              |
                              v
                  EVIDENCE / DATA POOL
           (structured store: Referent, ClaimedRelationship,
            Derived value; conflicts coexist, S5)
                              |
                +-------------+-------------+
                v                           v
        analytical/warehouse           graph index
        index (range/aggregate          (relationship/
        queries, S14)                    provenance nav, S14)
                |                           |
                +-------------+-------------+
                              v
                    [ curated selection --
                      Derived value flagged
                      "ready for proposal" ]
                              |
                              v
   ============ POOL BOUNDARY -- NOTHING BELOW THIS LINE CHANGES ============
                              v
                          ADAPTERS                (existing, unchanged)
                              |
                              v
                      CANDIDATE STATE              (existing CandidateDelta)
                              |
                              v
                      VALIDATION GATE              (existing validate_candidate)
                              |
                              v
                     CANONICAL STATE               (existing Version/CanonicalState)
                              |
                              v
                        MORPHO IR                  (existing compile_morpho)
                              |
                  +-----------+-----------+
                  v           v           v
               Three.js      SVG        Graph
                  |
                  v
         simulation / ML / optimization / analysis   (interface-only, unchanged)
```

Refined from the prompt's sketch in two ways, both load-bearing: (1) the
pool explicitly produces **two** index types (warehouse + graph, §H/§L),
not one generic "graph/index" box; (2) there is an explicit **curated
selection** step between the pool and the adapter boundary — the pool
never hands raw, unreviewed, conflicting Observations to an adapter,
only reviewed `Derived value`s (§O).

---

## R. Recommended future implementation sequence

Purely sequential dependency order, each step independently useful and
testable before the next begins (matching how every prior phase in this
project was actually run):

1. `Document`/`Record` raw storage (content-addressed blob store +
   minimal catalog) — no extraction, no normalization yet. Proves
   ingestion + immutability + non-deletion.
2. `Observation`/`Claim` extraction, deterministic sources only (e.g. a
   CSV-native extractor — the lowest-risk case, since Phase 12's CSV
   adapter already proves the downstream shape works). No model
   involved yet.
3. `NormalizedRecord` + `Condition` (`under`-linked Observations, §F).
4. `Derived value` + the conflict-coexistence model (§E) — the first
   point at which multiple sources for the same fact are exercised.
5. The pool→adapter bridge: a `Derived value` → existing
   `CandidateDelta` construction path (this is where §O's "only a
   Derived value may seed a Candidate" rule becomes enforced code, not
   just a design rule).
6. Graph + warehouse indexes (§G/§H) over what steps 1-4 already
   produced — deliberately *last* among the storage concerns, since
   indexes are derived and can be rebuilt; getting the underlying record
   shapes right first avoids re-deriving a wrong index twice.
7. Model-assisted extraction/normalization (§K), only once steps 2-3's
   deterministic path is proven, so the `confidence`/`extraction_method`
   discipline has a working non-model baseline to be compared against.
8. Agent task-queue automation (§J) — last, once every stage it
   orchestrates already works when invoked manually/by a human.

---

## S. Things explicitly NOT to implement yet

- Mistral or any local model deployment (§K describes the *boundary*
  only).
- Autonomous agents or agent loops (§J describes the *interface* only).
- Any actual database (relational, document, columnar, graph, or
  vector) — §I is a conceptual comparison, not a selection.
- Distributed workers, message brokers, or actor systems (§J's
  "stateless task worker over a shared table" needs none of this yet).
- Scraping infrastructure.
- An ontology/reasoning engine, or any external unit/ontology reference
  (consistent with `docs/PHASE_13_ARCHITECTURE_INVESTIGATION.md` §L's
  same conclusion, one layer upstream).
- **Entity resolution / deduplication algorithm.** Genuinely unresolved
  (see verdict below) — this document defines *where* a proposed match
  would live (a `ClaimedRelationship` of type `same_as` between two
  `Referent`s, itself subject to review like any other claim) but not
  *how* matches are proposed. That is a real, hard, separate research
  question requiring domain expertise this investigation does not have
  the evidence to resolve.
- **Confidence / source-quality scoring methodology.** This document
  establishes *that* every model-derived object must carry a confidence
  value (§K) and *that* Source has an independently-tracked quality
  score (§E), but not the formula/model for computing either. Also
  genuinely unresolved.
- Any change to `CanonicalState`, `Morpho`, `validate_candidate`,
  `core/projection/`, or `runtime/` — this entire document operates
  strictly upstream of the existing, unchanged adapter boundary.

---

## Final verdict

Most of this investigation reaches the same bar Phase 13 did: concrete
types (§B), a concrete provenance chain (§D), a concrete conflict model
(§E) with a single enforceable crossing rule (§O), a concrete storage
shape (§I) without committing to a product, and a concrete, dependency-
ordered implementation sequence (§R).

However, two decisions named directly in §S are **not** resolved to
implementation-detail level, and both are exactly the kind of decision
an implementing engineer would otherwise have to make themselves:

1. The entity-resolution/deduplication algorithm (how two `Referent`s
   get proposed as "the same material") — only the *shape* of where a
   proposal lives is specified, not how one gets generated or scored.
2. The confidence/source-quality scoring methodology — only that these
   values must exist and where they attach, not how they are computed
   or calibrated.

Everything else in this document is specified precisely enough to build
from. These two are not — and pretending otherwise would violate the
same discipline this whole project has maintained about not overclaiming
readiness.

**DATA POOL ARCHITECTURE NOT YET READY**

(Narrowly: ready on every point except entity-resolution methodology and
confidence/quality scoring methodology, both explicitly deferred to
their own, separate investigation before Phase 15 implementation begins
on the steps in §R that depend on them — steps 1-6 of §R do not depend
on either and could proceed once reviewed.)
