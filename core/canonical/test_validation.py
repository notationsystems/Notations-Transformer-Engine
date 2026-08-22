"""§21 tests 5-6: no inferred edges enter canonical state, and inferred
relations parsed from Morpho source stay marked inferred."""

import ast as pyast
import inspect

from core.canonical import validation
from core.canonical.delta import CandidateChange, CandidateDelta
from core.canonical.schema import EdgeSchema, FieldSchema, StateSchema
from core.canonical.validation import ValidationError, validate_candidate
from core.canonical.version import ProvenanceInfo, create_genesis_version
from morpho.ir import from_ast
from morpho.parser import parse_document

INFERRED_RELATION_SOURCE = """
morpho "1.0.0";

inferred relation A_near_B {
    from: "A";
    to: "B";
    type: "spatial_adjacency";
    confidence: 0.82;
    provenance {
        source: "graph_backend:adjacency_heuristic_v1";
        origin_version: "5f2a...c91";
    }
}
"""

DERIVED_RELATION_SOURCE = """
morpho "1.0.0";

derived relation A_linked_B {
    from: "A";
    to: "B";
    type: "manual_link";
    provenance {
        source: "diagram_tool:manual_edit";
        origin_version: "5f2a...c91";
    }
}
"""


def test_validation_module_has_no_dependency_on_morpho():
    """core.canonical.validation is the ONLY function that may mint a
    Version/EdgeRecord (§6). It must not import anything from morpho/ or
    backends/ -- there is structurally no path from a Morpho construct
    (canonical or inferred) into canonical state (§11, §20)."""
    source = inspect.getsource(validation)
    tree = pyast.parse(source)
    imported_modules = []
    for node in pyast.walk(tree):
        if isinstance(node, pyast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, pyast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    for module_name in imported_modules:
        assert not module_name.startswith("morpho"), f"validation.py must not import {module_name}"
        assert not module_name.startswith("backends"), f"validation.py must not import {module_name}"


def test_inferred_relation_parses_as_inferred_and_noncanonical():
    document = parse_document(INFERRED_RELATION_SOURCE)
    ir = from_ast(document, compiler_version="1.0.0")
    assert len(ir.relations) == 1
    relation = ir.relations[0]
    assert relation.inference_status == "inferred"
    assert relation.is_canonical is False


def test_derived_relation_parses_as_explicit_but_noncanonical():
    document = parse_document(DERIVED_RELATION_SOURCE)
    ir = from_ast(document, compiler_version="1.0.0")
    assert len(ir.relations) == 1
    relation = ir.relations[0]
    assert relation.inference_status == "explicit"
    assert relation.is_canonical is False


def _edge_schema_with_type(edge_type: str) -> StateSchema:
    return StateSchema(
        schema_version="1.0.0",
        fields={
            "A": FieldSchema(id="A", type="scalar", default=1),
            "B": FieldSchema(id="B", type="scalar", default=2),
        },
        edges=(EdgeSchema(type=edge_type),),
    )


def test_explicit_edge_add_and_remove_round_trip_through_validation():
    schema = _edge_schema_with_type("depends_on")
    v0 = create_genesis_version(schema, "2026-08-22T00:00:00Z")
    assert v0.state.edges == ()

    provenance = ProvenanceInfo(author="test", transaction_id="tx1", source="manual_edit")
    add_candidate = CandidateDelta(
        version_from=v0.id,
        transaction_id="tx1",
        timestamp="2026-08-22T00:01:00Z",
        changes=(
            CandidateChange(
                path="edges[0]",
                operation="add",
                old_value=None,
                new_value={"id": "e1", "from": "A", "to": "B", "type": "depends_on", "attributes": {}},
                provenance=provenance,
            ),
        ),
    )
    v1 = validate_candidate(schema, v0.state, add_candidate)
    assert not isinstance(v1, list), v1
    assert len(v1.state.edges) == 1
    assert v1.state.edges[0].id == "e1"
    assert v1.state.edges[0].from_ == "A"
    assert v1.state.edges[0].to == "B"

    remove_candidate = CandidateDelta(
        version_from=v1.id,
        transaction_id="tx2",
        timestamp="2026-08-22T00:02:00Z",
        changes=(
            CandidateChange(
                path="edges[0]",
                operation="remove",
                old_value={"id": "e1", "from": "A", "to": "B", "type": "depends_on", "attributes": {}},
                new_value=None,
                provenance=provenance,
            ),
        ),
    )
    v2 = validate_candidate(schema, v1.state, remove_candidate)
    assert not isinstance(v2, list), v2
    assert v2.state.edges == ()


def test_edge_add_rejected_when_schema_declares_no_edge_types():
    schema = StateSchema(
        schema_version="1.0.0",
        fields={"A": FieldSchema(id="A", type="scalar", default=1), "B": FieldSchema(id="B", type="scalar", default=2)},
        edges=(),  # empty => no edges may ever be asserted (§6)
    )
    v0 = create_genesis_version(schema, "2026-08-22T00:00:00Z")
    provenance = ProvenanceInfo(author="test", transaction_id="tx1", source="manual_edit")
    candidate = CandidateDelta(
        version_from=v0.id,
        transaction_id="tx1",
        timestamp="2026-08-22T00:01:00Z",
        changes=(
            CandidateChange(
                path="edges[0]",
                operation="add",
                old_value=None,
                new_value={"id": "e1", "from": "A", "to": "B", "type": "depends_on", "attributes": {}},
                provenance=provenance,
            ),
        ),
    )
    result = validate_candidate(schema, v0.state, candidate)
    assert isinstance(result, list)
    assert all(isinstance(e, ValidationError) for e in result)
    assert v0.state.edges == ()
