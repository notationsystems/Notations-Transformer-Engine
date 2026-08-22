# Architecture (as built)

This describes how the implementation maps onto
`docs/ARCHITECTURE_SPEC.md` ("Deterministic State Architecture — Frozen
Specification v1.0.0"). Read that document first; this one is a map from
its sections to the actual code, plus the concrete data flow through it.
For the three small grammar inconsistencies found in the spec itself
during implementation and how they were resolved, see
`docs/CONTRADICTIONS.md`.

## Module dependency graph

```
core/canonical  --->  core/projection  --->  morpho  --->  backends/*  --->  runtime
      ^                                                        |
      |                                                        v
      +--------------------------------------------------  (nothing; renderer/
                                                              only consumes
                                                              backends/threejs
                                                              output as JSON,
                                                              it is not a
                                                              Python dependency
                                                              of anything)
```

Enforced rules (checked by `tests/test_architecture_boundaries.py`,
which walks the actual `import`/`from ... import` statements in every
`.py` file under each package — not a hand-maintained list):

- `core/` never imports `morpho/`, `backends/`, or `runtime/`.
- `morpho/` never imports `backends/` or `runtime/`.
- `backends/threejs`, `backends/diagram`, `backends/graph`,
  `backends/simulation`, `backends/neural` never import each other.
  (`CandidateNextState`, needed by both `backends/simulation/interface.py`
  and `backends/neural/interface.py`, lives in `core/canonical/delta.py`
  — upstream of both — specifically so neither backend has to import the
  other; see that file's docstring.)
- Nothing under `core/`, `morpho/`, `backends/`, or `runtime/` imports
  `renderer/` (it isn't Python at all; it's the terminal JSON consumer).
- `core/canonical/validation.py` (the only function that may mint a
  `CanonicalState`/`Version`, §6) imports nothing from `morpho/` or
  `backends/` — checked directly in
  `core/canonical/test_validation.py::test_validation_module_has_no_dependency_on_morpho`.
- `backends/threejs/compiler.py` imports nothing from
  `core.canonical.validation` or `core.canonical.version` — checked in
  `tests/test_backends_threejs.py::test_threejs_backend_cannot_become_source_of_truth`.

## Data flow, concretely

```python
schema = StateSchema(...)                                  # core/canonical/schema.py
v0 = create_genesis_version(schema, timestamp)              # core/canonical/version.py
                                                               #   (the ONLY Version built
                                                               #    outside validate_candidate)

candidate = CandidateDelta(version_from=v0.id, changes=(...))  # core/canonical/delta.py
result = validate_candidate(schema, v0.state, candidate)        # core/canonical/validation.py
# result: Version | list[ValidationError] -- atomic, never partial

projected = project_state(result)                                 # core/projection/project.py
                                                                     #   pure, deterministic

ir_doc = compile_morpho(projected, CompilerConfig())                 # morpho/compiler.py
                                                                        #   pure, deterministic

scene = compile_threejs(ir_doc, ThreeJSRenderConfig())                  # backends/threejs/compiler.py
svg = compile_svg(ir_doc, DiagramLayoutConfig())                         # backends/diagram/compiler.py
report = analyze(ir_doc)                                                  # backends/graph/analysis.py
```

`renderer/index.html` then `fetch()`es a serialized `scene` (see
`scripts/generate_sample_scene.py`) and builds/updates `THREE.*` objects
from it. There is no function call from that page back into any of the
above.

The simulation/neural feedback path re-enters at the same door:

```python
candidate = simulator.step(dynamics_spec, action)     # -> CandidateNextState (backends/simulation/interface.py)
result = submit_simulation_candidate(                  # runtime/feedback_loop.py
    schema, base_state, candidate, tx_id, timestamp
)                                                         # internally just builds a
                                                            # CandidateDelta and calls
                                                            # validate_candidate -- same
                                                            # function, same atomicity
```

## Frozen-spec section → implementation map

| Spec section | File(s) |
|---|---|
| §3 Canonical State | `core/canonical/state.py` |
| §4 Version | `core/canonical/version.py` |
| §5 StateDelta | `core/canonical/delta.py` |
| §6 Schema / Validation | `core/canonical/schema.py`, `core/canonical/validation.py` |
| §7 Morpho HDL Grammar | `morpho/lexer.py`, `morpho/parser.py`, `morpho/ast.py` |
| §8 Morpho Semantic Model | `morpho/ir.py` |
| §9 Morpho Identity Model | `morpho/identity.py` |
| §10 Morpho Provenance Model | `morpho/provenance.py` |
| §11 Graph Semantics | `morpho/ir.py` (`MorphoRelation`), `backends/graph/analysis.py` |
| §12 Spatial Semantics | `morpho/ir.py` (`Vec3`, `Quaternion`, `Transform`, `CoordinateFrame`) |
| §13 Projection Contracts | `core/projection/project.py`, `morpho/compiler.py` |
| §14 Three.js Backend | `backends/threejs/compiler.py`, `renderer/index.html` |
| §15 Diagram/SVG Backend | `backends/diagram/compiler.py` |
| §16 Simulation Backend (interfaces only) | `backends/simulation/interface.py` |
| §17 Neural/Estimation (interfaces only) | `backends/neural/interface.py` |
| §18 Persistence / Snapshot | `core/canonical/version.py::InMemoryVersionStore` (in-memory only, per §18/§23) |
| §19 Deterministic Replay | `core/projection/project.py::restore_projection` |
| §21 Test Plan | see the file list in `README.md`'s "Running the tests" section |
| §22 Migration Plan | not applicable as a code artifact — see `docs/ARCHITECTURE_SPEC.md` §0/§22: no `primitive_N.py` files existed to migrate at implementation time, so this build follows the "starting from nothing" branch of that plan directly |
| §23 Do-not-implement-yet list | honored: no Kalman filter, no neural model, no physics engine, no database, no CRDT/Merkle structure, no distributed consensus anywhere in this tree |

## Determinism, concretely

- `Version.id` = `sha256(canonical_json(schema_version, fields, edges))`,
  where `canonical_json` sorts all map keys and uses fixed JSON
  separators (`core/canonical/version.py::canonical_json_bytes`).
- `project_state`, `compile_morpho`, `compile_threejs`, and `compile_svg`
  never branch on wall-clock time, randomness, or object identity/`id()`;
  where output order is observable (Morpho entity order, scene mesh
  order, SVG element order), iteration is always over explicitly
  `sorted()` keys, never raw `dict`/`set` iteration order.
- This was checked by running the full genesis-to-scene pipeline three
  times under `PYTHONHASHSEED=0`, `1`, and `12345` in separate process
  invocations and diffing the outputs (identical `Version.id` and mesh-id
  ordering in all three).
