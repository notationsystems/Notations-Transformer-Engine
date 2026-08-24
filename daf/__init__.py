"""DAF: the Data Acquisition Fabric.

DAF sits one layer *upstream* of SCOUT (`scout/`): where a
`scout.interface.SourceAdapter` hands back an already-flattened
`RawDocument` (content + a handful of strings), DAF is the layer
responsible for turning "we asked a source for something" into a
provenance-complete acquisition record before anything is flattened --
what resource was asked for, exactly what bytes came back, when/how the
asking happened, and (optionally) what a parser made of those bytes --
each with its own explicit, content-addressed identity. See
`docs/DAF_ARCHITECTURE.md` for the full design and the reasoning behind
splitting three identities where an earlier draft of this module used
one.

DAF does not replace SCOUT and does not touch `core.canonical`. Its one
output boundary is `daf.bridge`, which converts an acquired
`ArtifactVersion` (+ its `AcquisitionRecord`, + optionally a
`NormalizedRecord`) into `evidence.types.Document` / `Record` /
`Observation` and admits them through `evidence.admission` -- the same
one door `scout.pipeline.run_scout` already uses. Nothing in this
package ever calls `pool.put_*` without a preceding `admit_*` call
succeeding first.

Layout:

    daf/identity.py        Artifact (stable resource identity),
                            ArtifactVersion (content-addressed, immutable
                            snapshot of what a resource contained)
    daf/acquisition.py      AcquisitionJob, AcquisitionRecord (a single
                            acquisition occurrence -- separate from
                            ArtifactVersion on purpose), AcquisitionResult,
                            BaseAcquisitionAdapter (Protocol)
    daf/fixtures.py           FixtureSourceAdapter -- deterministic synthetic
                            adapter, no live network, mirrors
                            scout/fixtures.py's own discipline
    daf/store.py               In-memory ArtifactVersionStore /
                            AcquisitionRecordStore (v1 only -- a real
                            backend is future work, same deferral
                            evidence/pool.py makes for core.canonical)
    daf/normalization.py       SchemaVersion, NormalizedRecord,
                            BaseParser (Protocol), JSONParser,
                            NormalizedRecordStore
    daf/bridge.py               DAF -> evidence.types, admission-gated

What is deliberately NOT here (same "do not overbuild" instruction
`adapters/interface.py` and `scout/fixtures.py` were both built under):
no live HTTP/API adapter, no event bus, no MinIO/Parquet/SQL backend,
no scheduler. `FixtureSourceAdapter` is the only adapter implementation,
exactly as `scout.adapters.FixtureSourceAdapter` is SCOUT's.
"""
