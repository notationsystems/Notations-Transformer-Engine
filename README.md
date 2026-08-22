# Deterministic State Architecture

An implementation of `docs/ARCHITECTURE_SPEC.md` ("Deterministic State
Architecture — Frozen Specification v1.0.0"): a canonical-state compiler
pipeline where a single, versioned, immutable **CanonicalState** is the
sole source of truth, and every 3D view, diagram, graph analysis,
simulation, or ML system downstream is a deterministic projection or
compilation of a frozen version of it — never a place state can be
written back from.

```
CanonicalState --> Schema/Validation --> StateProjection --> Morpho IR --> backends
   (source)          (frontend)           (pure fn)          (IR)      (Three.js, SVG,
                                                                          graph, sim*, neural*)
                                                                          * interface stubs only
```

If you are new to this repo, read `docs/ARCHITECTURE_SPEC.md` first — it
is the frozen contract everything here implements. `docs/ARCHITECTURE.md`
explains how this codebase maps onto that contract, and
`docs/CONTRADICTIONS.md` documents three small internal inconsistencies
found in the spec's own grammar during implementation, and the minimal
fixes applied.

## Layout

```
core/canonical/     CanonicalState, Field, EdgeRecord, Version, VersionStore,
                     StateDelta, StateSchema, validate_candidate
core/projection/     project_state() / restore_projection()
morpho/               Morpho HDL: lexer, parser, AST, semantic IR, identity
                       model, provenance model, compile_morpho()
backends/threejs/       Morpho IR -> declarative Three.js scene descriptor
backends/diagram/        Morpho IR -> SVG document string
backends/graph/            Morpho IR -> descriptive graph metrics
backends/simulation/        interface/protocol shapes only (no engine)
backends/neural/              interface/protocol shapes only (no model)
runtime/                        feedback_loop.py: the only bridge from a
                                 simulation/neural candidate back into
                                 canonical state, and it goes through
                                 validate_candidate like everything else
adapters/                         interface.py: external-data -> CandidateDelta
                                   boundary (Protocol shape only, no real
                                   adapter implemented). NOT part of the
                                   original frozen spec's 23 sections --
                                   added on explicit request as a provisional
                                   extension; see docs/ARCHITECTURE.md
renderer/                        index.html: the only place a real
                                  THREE.* object is constructed
scripts/                          generate_sample_scene.py: demo data
tests/                             one file per architectural phase
                                    (test_canonical, test_versioning,
                                    test_delta, test_projection,
                                    test_morpho_compiler,
                                    test_backends_threejs,
                                    test_backends_diagram, test_replay),
                                    plus test_representation_equivalence.py
                                    (one canonical state -> multiple
                                    backends), test_live_state_bridge.py
                                    (delta/replay scenarios), test_adapters.py,
                                    and test_architecture_boundaries.py
runtime/test_feedback_loop.py        kept colocated with the module it tests
                                      (verifies the "only validation.py may
                                      mint a Version" rule for the simulation/
                                      neural feedback path)
```

## Canonical state

`CanonicalState` holds `schema_version`, an immutable map of `Field`
(`id`, `type`, `value`, `unit`), and a tuple of `EdgeRecord` (explicit
relationships only — never inferred). `Field.id` must equal its own
dictionary key; a mismatch raises, it is never silently corrected.
Everything is a frozen dataclass over an immutable mapping, so "updating"
state always means "produce a new `CanonicalState`."

## Versioning

`Version.id` is a SHA-256 hex digest of `(schema_version, fields, edges)`
only — `id`, `parent`, `provenance`, and `timestamp` are excluded from the
hash. Two states with identical content always get the same id, from any
process, regardless of dict/set iteration order (verified in CI-style
checks across multiple `PYTHONHASHSEED` values — see the implementation
report). The genesis `Version` is the only one ever built outside the
validation pipeline; every later `Version` comes from
`validate_candidate`.

## Deltas

`diff(old, new, provenance)` produces path-addressed, leaf-level
`Change`s (`fields.mass.value`, `edges[0].type`, ...) with `add` /
`remove` / `replace` operations, in deterministic sorted order. `move`
and `rename` are reserved in the `Operation` type but never emitted in
v1.

## Validation: the one door into a new version

```
candidate --> schema validation --> constraint validation --> accept --> new Version
                    |                        |
                    +---- fail: reject, no state/version is touched ----+
```

`validate_candidate` in `core/canonical/validation.py` is the **only**
function in the whole codebase that can produce a new `CanonicalState` or
`Version`. Nothing in `morpho/`, `backends/`, or `renderer/` imports it or
anything capable of reaching it directly — see
`tests/test_architecture_boundaries.py` and the module-boundary checks
noted per-file below.

## Morpho: the intermediate representation

Morpho HDL is a small, human-readable, domain-neutral IR — entities,
relations, coordinate frames, groups, and constraints, each carrying
explicit provenance. `morpho/lexer.py` and `morpho/parser.py` implement
its grammar (`docs/ARCHITECTURE_SPEC.md` §7, as corrected by
`docs/CONTRADICTIONS.md`); `morpho/ir.py` is its semantic model;
`morpho/compiler.py::compile_morpho` is the pure, deterministic canonical
compilation path (`ProjectedState -> MorphoDocument`).

**Graph semantics.** Every `MorphoRelation` carries two independent flags:
`is_canonical` (was it backed by a real `CanonicalState.edges` entry?) and
`inference_status` (`"explicit"` or `"inferred"`). It is structurally
impossible to construct one with `is_canonical=True` and
`inference_status="inferred"` — the dataclass itself raises. Nothing in
`backends/` or `morpho/` has a code path back into `CanonicalState.edges`,
so an inferred relation can never silently become canonical.

**Identity.** `morpho/identity.py`'s four functions
(`node_id`/`cell_id`/`visual_id`/`geometry_id`) are all the identity
function on `field_name` in v1 — no hashing, no UUIDs, no namespacing.
They exist as separate named functions specifically so a future schema
version can change one without touching call sites.

## Backends

- **`backends/threejs/compiler.py`** — `compile_threejs` returns a plain,
  JSON-serializable `ThreeJSSceneDescriptor` (`geometries`, `materials`,
  `meshes`, `hierarchy`). It never constructs a `THREE.*` object.
- **`backends/diagram/compiler.py`** — `compile_svg` returns a complete,
  deterministically laid-out SVG document string.
- **`backends/graph/analysis.py`** — descriptive graph metrics
  (node/edge counts, adjacency, degree) over whatever the IR already
  contains; it does not itself invent inferred relations.
- **`backends/simulation/interface.py`**, **`backends/neural/interface.py`**
  — protocol/dataclass shapes only, per §16/§17. No engine, no model.

## Renderer

`renderer/index.html` is the only file in the repository that constructs
a real `THREE.*` object. It fetches a `ThreeJSSceneDescriptor` (see
`scripts/generate_sample_scene.py` for how one is produced) and keeps a
`geometry_id`/`visual_id`-keyed cache so that a value-only change updates
existing `THREE.Mesh` objects in place rather than recreating them, and so
a deleted entity's mesh is removed from the scene. It has no import, fetch
target, or code path back into canonical state — see
`tests/test_backends_threejs.py::test_renderer_html_never_references_canonical_mutation_endpoints`.
three.js itself is vendored at `renderer/vendor/three.module.js` (MIT
licensed) so the page has no runtime dependency on an external CDN.

## Feedback loop

`runtime/feedback_loop.py` is the only bridge from a simulation
`CandidateNextState` or a neural `BeliefState` back toward canonical
state, and it does so by handing the candidate to `validate_candidate` —
the same function a manual edit goes through. There is no alternate fast
path.

## Determinism

Every "compiler stage" function (`project_state`, `compile_morpho`,
`compile_threejs`, `compile_svg`) is a pure function of its inputs: no
wall-clock reads, no randomness, no reliance on dict/set iteration order
(iteration is always over explicitly `sorted()` keys where order is
observable in output). Verified by running the same pipeline under
multiple `PYTHONHASHSEED` values and asserting identical output.

## Running the tests

```
pip install pytest
python3 -m pytest
```

Tests live in `tests/`, one file per architectural phase (`test_canonical`
= Phase 1, `test_versioning` = Phase 2, `test_delta` = Phase 3,
`test_projection`/`test_replay` = Phase 4, `test_morpho_compiler`
= Phases 5-6, `test_backends_threejs`/`test_backends_diagram`
= Phases 7-8), plus `test_architecture_boundaries.py` for the dependency-
direction audit. `runtime/test_feedback_loop.py` stays colocated with
`runtime/feedback_loop.py` since it verifies that module's specific
invariant (Phase 10). This mirrors the flat `tests/` tree requested for
this build; `docs/ARCHITECTURE_SPEC.md` §21 originally specified a
colocated-per-module layout instead -- both cover the same 18 acceptance
tests plus additional coverage, this is a file-organization choice, not
an architectural one.

## Generating the demo scene

```
python3 scripts/generate_sample_scene.py
```

Writes `renderer/scene_v1.json` and `renderer/scene_v2.json` (the same
entities after one accepted value-only update), then open
`renderer/index.html` via a local HTTP server (not `file://`, since it
`fetch()`es the descriptor) and use the two buttons to switch between
them.
