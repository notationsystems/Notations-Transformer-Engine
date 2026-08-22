"""Phase 8: SVG/diagram backend (§15). No test coverage existed for this
backend before this pass -- this file is new, not a relocation.
"""

import ast as pyast
import inspect
import xml.etree.ElementTree as ET

import pytest

from backends.diagram import compiler as diagram_compiler
from backends.diagram.compiler import DiagramLayoutConfig, compile_svg
from core.projection.project import project_state
from morpho.compiler import CompilerConfig, compile_morpho
from morpho.ir import Entity, MorphoDocument, MorphoRelation
from morpho.provenance import canonical_provenance, derived_provenance


def _entity(entity_id, value=10):
    return Entity(
        id=entity_id,
        attributes={"type": "scalar", "value": value, "unit": None},
        provenance=canonical_provenance(origin_version="v0", compiler_version="1.0.0"),
    )


def test_compile_svg_produces_well_formed_xml(genesis_version):
    ir_doc = compile_morpho(project_state(genesis_version), CompilerConfig())
    svg = compile_svg(ir_doc, DiagramLayoutConfig())
    root = ET.fromstring(svg)  # raises if malformed
    assert root.tag.endswith("svg")


def test_compile_svg_is_deterministic(genesis_version):
    ir_doc = compile_morpho(project_state(genesis_version), CompilerConfig())
    config = DiagramLayoutConfig()
    svg1 = compile_svg(ir_doc, config)
    svg2 = compile_svg(ir_doc, config)
    assert svg1 == svg2


def test_compile_svg_renders_every_entity(genesis_version):
    ir_doc = compile_morpho(project_state(genesis_version), CompilerConfig())
    svg = compile_svg(ir_doc, DiagramLayoutConfig())
    for field_id in genesis_version.state.fields:
        assert f'data-entity-id="{field_id}"' in svg


def test_compile_svg_distinguishes_inferred_from_explicit_relations():
    doc = MorphoDocument(
        entities=(_entity("A"), _entity("B")),
        relations=(
            MorphoRelation(
                id="explicit_rel", from_id="A", to_id="B", type="depends_on",
                is_canonical=True, inference_status="explicit",
                provenance=canonical_provenance(origin_version="v0", compiler_version="1.0.0"),
            ),
            MorphoRelation(
                id="inferred_rel", from_id="A", to_id="B", type="near",
                is_canonical=False, inference_status="inferred",
                provenance=derived_provenance(
                    source="graph_backend:adjacency_heuristic_v1", origin_version="v0", compiler_version="1.0.0"
                ),
                confidence=0.7,
            ),
        ),
    )
    svg = compile_svg(doc, DiagramLayoutConfig())
    assert 'data-relation-id="explicit_rel"' in svg
    assert 'data-relation-id="inferred_rel"' in svg
    # Visually distinguishable: inferred relations are dashed, explicit are not.
    lines = [line for line in svg.splitlines() if "<line" in line]
    explicit_line = next(l for l in lines if 'data-relation-id="explicit_rel"' in l)
    inferred_line = next(l for l in lines if 'data-relation-id="inferred_rel"' in l)
    assert "stroke-dasharray" not in explicit_line
    assert "stroke-dasharray" in inferred_line


def test_compile_svg_rejects_nondeterministic_layout_algorithm():
    doc = MorphoDocument(entities=(_entity("A"),))
    with pytest.raises(ValueError):
        compile_svg(doc, DiagramLayoutConfig(layout_algorithm="force_directed_random_v1"))


def test_compile_svg_handles_empty_document():
    svg = compile_svg(MorphoDocument(), DiagramLayoutConfig())
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")


def test_compile_svg_escapes_entity_content():
    doc = MorphoDocument(entities=(_entity('A"<script>'),))
    svg = compile_svg(doc, DiagramLayoutConfig())
    ET.fromstring(svg)  # must still be well-formed XML despite hostile content
    assert "<script>" not in svg


def test_diagram_backend_cannot_become_source_of_truth():
    """Same CRITICAL RULE as the Three.js backend: no backend may mutate
    canonical state, and none may import the machinery that mints a
    Version."""
    source = inspect.getsource(diagram_compiler)
    tree = pyast.parse(source)
    imported_modules = []
    for node in pyast.walk(tree):
        if isinstance(node, pyast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, pyast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    disallowed_prefixes = ("core.canonical.validation", "core.canonical.version")
    for module_name in imported_modules:
        assert not module_name.startswith(disallowed_prefixes), (
            f"backends/diagram/compiler.py must not import {module_name}"
        )
    assert "validate_candidate" not in source
