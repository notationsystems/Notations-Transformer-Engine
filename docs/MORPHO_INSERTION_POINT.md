# Target G -- Where Morpho Would Sit (Mapping Only, No Implementation)

Read from the in-repo `morpho/` package as it actually exists (lexer,
parser, AST, IR, deterministic `compile_morpho: ProjectedState ->
MorphoDocument`, entity-derived identity, canonical provenance) -- not
from the external `morphohdl` fork.

## The concrete mapping

```text
Morpho representation          MorphoDocument -- entities, relations,
                               coordinate frames, transforms; built
                               deterministically by compile_morpho or
                               parsed from .morpho source
        |
        v
executable representation      << THE GAP: nothing lowers a
                               MorphoDocument to a computation. The
                               five in-repo morpho backends (threejs /
                               diagram / graph / simulation / neural)
                               are REPRESENTATION backends -- they
                               render structure; they do not compute
                               new scientific values.
        |
        v
ExecutionSpecification         ALREADY REPRESENTABLE, exactly:
                                 program       = a kernel descriptor
                                                 (what to compute)
                                 configuration = solver parameters
                                 input_payload = the canonical byte
                                                 encoding of the
                                                 MorphoDocument's
                                                 numerical content
        |
        v
STE seam                       unchanged (SpecificationDispatcher)
        |
        v
scientific engine              unchanged (native kernels / external
                               processes / proved guests)
        |
        v
ExecutionResult -> evidence    unchanged (the existing admission path)
```

## Already representable, today

- **Structure -> input bytes.** A MorphoDocument's entities carry Vec3
  positions and typed relations; `encode_positions` is precisely the
  degenerate case of "canonical byte encoding of a structural document."
  A deterministic `MorphoDocument -> input bytes` encoder is the
  caller-side canonicalization burden this architecture has named since
  Phase 128 -- a defined slot, not a new concept.
- **Structure identity.** MorphoDocuments are already deterministic and
  content-comparable (`compile_morpho` is pure); their canonical bytes
  can feed `InputIdentity` unchanged.
- **Provenance discipline.** `morpho.provenance.canonical_provenance`
  already mirrors the declared-not-witnessed epistemics.

## Not representable yet (the honest gap, in order of size)

1. **The lowering.** `MorphoDocument -> kernel descriptor + input
   encoding` -- a compiler from structural representation to one of the
   registered computational programs. This is the only genuinely new
   component Morpho integration would require.
2. **Result lift-back.** `ExecutionResult -> MorphoDocument deltas`
   (e.g. minimized positions back into entities) if round-tripping is
   wanted; optional.
3. **Provable lowering.** If the lowering itself should be trusted, it
   is exactly the bytes-vs-behavior gap one level up -- and the same
   remedy applies (run the lowering inside a guest). Far future; noted,
   not proposed.

## Verdict

Morpho slots in ABOVE `ExecutionSpecification` as a representation
layer, touching nothing below it. No substrate change is required to
admit it; one new component (the lowering compiler) is required to use
it. No implementation in this stage, per the directive.
