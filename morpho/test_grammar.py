"""§21 test 15: Morpho contains no renderer-specific objects.

This is enforced at the grammar level (no keyword, production, or AST/IR
node type for THREE.js/WebGL/DOM/camera/material concepts exists at
all) rather than by a runtime check.
"""

from morpho import ast, ir
from morpho.lexer import KEYWORDS
from morpho.parser import parse_document

FORBIDDEN_TERMS = {
    "three", "webgl", "camera", "material", "mesh", "dom", "canvas",
    "shader", "renderer", "viewport", "texture",
}

FULL_EXAMPLE = """
morpho "1.0.0";

entity mass {
    id: "mass";
    type: "scalar";
    value: 10;
    unit: "kg";
    provenance {
        source: "canonical";
        origin_version: "5f2a...c91";
    }
}

relation A_depends_on_B {
    from: "mass";
    to: "mass";
    type: "depends_on";
    provenance {
        source: "canonical";
        origin_version: "5f2a...c91";
    }
}

frame root_frame {
    position: [0, 0, 0];
    orientation: [0, 0, 0, 1];
    scale: [1, 1, 1];
}

group readings {
    members: ["mass"];
}

constraint mass_nonnegative {
    on: "mass";
    rule: "value >= 0";
}
"""

ALLOWED_AST_DECL_TYPES = (ast.EntityDecl, ast.RelationDecl, ast.FrameDecl, ast.GroupDecl, ast.ConstraintDecl)


def test_keywords_exclude_renderer_concepts():
    for keyword in KEYWORDS:
        assert keyword.lower() not in FORBIDDEN_TERMS, f"keyword {keyword!r} looks renderer-specific"


def test_parsed_document_contains_only_spec_construct_types():
    document = parse_document(FULL_EXAMPLE)
    assert len(document.declarations) == 5
    for decl in document.declarations:
        assert isinstance(decl, ALLOWED_AST_DECL_TYPES)


def test_semantic_ir_contains_only_spec_construct_types():
    document = parse_document(FULL_EXAMPLE)
    morpho_ir = ir.from_ast(document, compiler_version="1.0.0")

    assert len(morpho_ir.entities) == 1 and isinstance(morpho_ir.entities[0], ir.Entity)
    assert len(morpho_ir.relations) == 1 and isinstance(morpho_ir.relations[0], ir.MorphoRelation)
    assert len(morpho_ir.frames) == 1 and isinstance(morpho_ir.frames[0], ir.CoordinateFrame)
    assert len(morpho_ir.groups) == 1 and isinstance(morpho_ir.groups[0], ir.Group)
    assert len(morpho_ir.constraints) == 1 and isinstance(morpho_ir.constraints[0], ir.Constraint)

    # No forbidden term appears anywhere in the parsed content itself.
    rendered = repr(morpho_ir).lower()
    for term in FORBIDDEN_TERMS:
        assert term not in rendered, f"IR unexpectedly mentions renderer concept {term!r}"
