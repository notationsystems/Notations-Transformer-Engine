# DAF — Data Acquisition Fabric

This document describes `daf/`: the layer one step upstream of SCOUT
(`docs/SCOUT_ARCHITECTURE.md`) responsible for turning "we asked a
source for something" into a provenance-complete acquisition record,
before anything is flattened into `evidence.types`. Deliverable
(implementation) is `daf/`; deliverable (tests) is
`tests/test_daf_*.py`.

## 0. What this document is not

This is not SCOUT, and it does not replace it. `scout.interface.SourceAdapter`
already has a `fetch() -> RawDocument` boundary; DAF does not compete with
that shape, it sits in front of it, answering a question SCOUT's own
model was never designed to answer: given a source that was polled more
than once, which polls returned the *same* content, and which returned
*different* content? SCOUT's `RawDocument` has no concept of "the same
content, acquired twice" — every `fetch()` call is just a tuple of
documents. DAF's job is to make that distinction a first-class, testable
thing, before a `Document`/`Record` is ever created.

DAF also does not touch `core.canonical`, for the same reason `evidence/`
and `scout/` do not (`docs/SCOUT_ARCHITECTURE.md` §1): it terminates at
`daf.bridge`, which hands admitted `evidence.types` objects to an
`EvidencePool` and stops.

## 1. The identity contradiction this design fixes

An earlier draft of this module gave an acquired artifact two identities:

```
content_hash    = H(canonical_content)
version_id      = H(artifact_id, version_index)
```

and then asserted, as a test, that re-acquiring identical content at a
different time produces a *different* `version_id`. Both cannot be
true simultaneously: `version_id` was computed from `version_index`
alone, so two acquisitions passed the same index collapse to one id
regardless of whether their `acquisition_time` differed, and a caller
that *did* vary the index on every call would instead mint a brand-new
version for byte-identical content every single time it was re-polled —
neither behavior is "content-addressed."

The fix is not a smaller patch to that formula; it is recognizing that
the design was answering three different questions with one identity:

| Question | Answer |
|---|---|
| What resource are we talking about? | `Artifact` |
| What exact bytes did that resource contain? | `ArtifactVersion` |
| When/how did we observe that content? | `AcquisitionRecord` |

Three questions, three identities, three types (`daf/identity.py`,
`daf/acquisition.py`). See those modules' docstrings for the exact
mechanics; `tests/test_daf_identity.py` is the test that would have
caught the original contradiction —
`test_acquisition_record_id_differs_for_different_occurrence_time`
asserts two different occurrences of the *same* content produce two
different `AcquisitionRecord.id`s while the underlying
`ArtifactVersion.id` stays the same.

## 2. The four layers

```
Source (evidence.types.Source)
    |
Artifact                          daf/identity.py
    |  id = H(source_id, canonical_locator) -- STABLE
    |
BaseAcquisitionAdapter.acquire()  daf/acquisition.py, daf/fixtures.py
    |
    +--> ArtifactVersion           daf/identity.py
    |    id = H(artifact_id, raw_content_hash)
    |    raw_content_hash = H(raw_bytes) -- PURE, no metadata
    |
    +--> AcquisitionRecord         daf/acquisition.py
         id = H(artifact_id, artifact_version_id, job_id,
                 acquisition_time, status)
    |
    v
Parser.parse()                    daf/normalization.py
    |
    v
NormalizedRecord
    id = H(artifact_version_id, schema_version_id, parser_version,
            normalized_content_hash)
    normalized_content_hash = H(data)   -- semantic identity, separate
    |
    v
daf.bridge.artifact_version_to_evidence()   daf/bridge.py
    |
    v
evidence.types.Document / Record / Observation   (admission-gated,
                                                    evidence.admission)
```

`ArtifactVersionStore` / `AcquisitionRecordStore` / `NormalizedRecordStore`
(`daf/store.py`, `daf/normalization.py`) are in-memory only (v1 scope —
the same deferral `evidence/pool.py` makes for `core.canonical`'s
eventual real database). A real backend (object storage for raw bytes,
Parquet/SQL for normalized records and metadata) is future work, not
implemented here — same "do NOT overbuild" instruction
`scout/fixtures.py` and `adapters/interface.py` were both built under.

## 3. Two distinct histories

Because content identity (`ArtifactVersion`) and occurrence identity
(`AcquisitionRecord`) are separate, a single Artifact naturally supports
two different temporal questions, answered by two different stores:

- **State history** (`ArtifactVersionStore.get_versions_for_artifact`):
  how did the resource's content actually change over time? One entry
  per distinct `raw_content_hash` ever observed.
- **Observation history** (`AcquisitionRecordStore.get_records_for_artifact`
  / `get_records_for_version`): when did DAF observe each state, and how
  many times? One entry per acquisition attempt, including repeated
  observations of an unchanged state.

`tests/test_daf_store.py::test_state_history_vs_observation_history_are_distinct`
is the test that proves these diverge: three acquisitions, two distinct
content states — the assertion is `len(versions) == 2` alongside
`len(records) == 3`.

## 4. The bridge does not invent identity

`daf/bridge.py::artifact_version_to_evidence` converts one acquired
`ArtifactVersion` (+ its `AcquisitionRecord`, + optionally a
`NormalizedRecord`) into `evidence.types.Document` / `Record` /
`Observation`, admitted through `evidence.admission` exactly as
`scout.pipeline.run_scout` admits its own findings — no path in this
module calls `pool.put_*` without a preceding `admit_*` call succeeding.

Two concrete bugs an earlier draft of this bridge had, both now covered
by `tests/test_daf_bridge.py`:

1. **Invented record ids.** A placeholder implementation built an
   `Observation` referencing `record_ids=("record_1",)` — a string with
   no corresponding `Record` ever admitted to the pool, which
   `admit_observation`'s `UNKNOWN_RECORD` check would reject outright.
   The fix: the bridge builds the `Record` itself via
   `evidence.types.make_record` and reads `record.id` back off the
   object it just built, never a guessed string
   (`test_bridge_produces_observation_referencing_the_real_record_id`).
2. **A nonexistent attribute.** A placeholder implementation read
   `artifact_version.artifact.source_id` — but `ArtifactVersion` only
   ever carries `artifact_id` (a string), never a reference to the
   `Artifact` object (`daf/identity.py`). The fix: the bridge takes
   `artifact: Artifact` as an explicit parameter, and validates
   `artifact_version.artifact_id == artifact.id` before doing anything
   else.

## 5. Invariants and their tests

| Invariant | Enforced by | Test |
|---|---|---|
| Artifact identity is stable, scoped to (source, locator) | `make_artifact` | `test_artifact_identity_stable_for_same_source_and_locator`, `test_artifact_identity_changes_with_locator` |
| `raw_content_hash` is a pure function of bytes alone | `make_artifact_version` | `test_raw_content_hash_is_pure_ignores_source_revision` |
| `ArtifactVersion.id` is scoped to its Artifact | `make_artifact_version` | `test_artifact_version_id_scoped_to_artifact` |
| `ArtifactVersion` is immutable | `frozen=True` + `bytes` | `test_artifact_version_immutable` |
| `AcquisitionRecord` is deeply immutable | `MappingProxyType` in `__post_init__` | `test_acquisition_record_deep_immutability` |
| A `success` record always references a version | `AcquisitionRecord.__post_init__` | `test_acquisition_record_success_requires_artifact_version_id` |
| Idempotent content acquisition collapses to one `ArtifactVersion` | `ArtifactVersionStore.put_version` keyed by `(artifact_id, raw_content_hash)` | `test_idempotent_content_collapses_to_one_version`, `test_repeated_acquisition_of_unchanged_content_is_idempotent` |
| State history != observation history | `ArtifactVersionStore` vs. `AcquisitionRecordStore` | `test_state_history_vs_observation_history_are_distinct` |
| Transformation provenance: `data = f(ArtifactVersion, Parser, SchemaVersion)` | `make_normalized_record` | `test_transformation_provenance_carries_all_three_inputs`, `test_reproducible_reconstruction_same_inputs_same_output` |
| Semantic dedup via `normalized_content_hash`, independent of `NormalizedRecord.id` | `content_hash(data)` | `test_normalized_record_id_differs_when_source_version_differs`, `test_semantic_deduplication_via_store` |
| Bridge never invents an id; requires the Source already admitted | `artifact_version_to_evidence` | `test_bridge_produces_observation_referencing_the_real_record_id`, `test_bridge_rejects_document_when_source_not_yet_in_pool` |

## 6. Deliberately out of scope

Same "do not overbuild" instruction `scout/fixtures.py` and
`adapters/interface.py` were both built under: no live HTTP/API adapter
(`daf.fixtures.FixtureSourceAdapter` is the only implementation, exactly
as `scout.adapters.FixtureSourceAdapter` is SCOUT's), no event bus or
scheduler, no MinIO/Parquet/SQL storage backend, no schema-validating
parser (`daf.normalization.JSONParser` only checks "is this a JSON
object"). Each is a straightforward extension of the shapes already
defined here (`BaseAcquisitionAdapter`, `ArtifactVersionStore`,
`BaseParser`) — none requires revisiting the identity model this
document describes.
