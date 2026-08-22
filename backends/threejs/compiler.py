"""Three.js backend (§14): Morpho IR -> declarative scene descriptor.

This module never constructs a THREE.Object3D, THREE.Mesh,
THREE.Material, or any WebGL handle -- it returns plain, JSON-serializable
data. `renderer/index.html` is the only place real THREE.* objects are
built (I8). `compile_threejs` is pure and deterministic: the same
(ir, config) always produces the same descriptor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Tuple

from core.canonical.schema import FieldValue
from morpho.ir import MorphoDocument

DEFAULT_MATERIAL_ID = "default_material"
_LAYOUT_SPACING = 2.0


@dataclass(frozen=True)
class ThreeJSRenderConfig:
    # Extrinsic, non-canonical (§12): camera/viewport defaults, never
    # sourced from CanonicalState or Morpho IR.
    camera: Mapping[str, FieldValue] = field(default_factory=dict)
    viewport: Mapping[str, FieldValue] = field(default_factory=dict)


@dataclass(frozen=True)
class ThreeJSSceneDescriptor:
    geometries: Tuple[Dict, ...]
    materials: Tuple[Dict, ...]
    meshes: Tuple[Dict, ...]
    hierarchy: Tuple[Dict, ...]


def _layout_position(entity_id: str, index: int, ir: MorphoDocument) -> Tuple[float, float, float]:
    """Deterministic pure function of the IR: entities carrying an
    intrinsic CoordinateFrame (§12) are placed at that frame's position;
    everything else gets a fixed deterministic grid slot derived only
    from sorted entity-id order (never from wall-clock time, randomness,
    or renderer state)."""
    for frame in ir.frames:
        if frame.id == entity_id:
            p = frame.transform.position
            return (p.x, p.y, p.z)
    return (index * _LAYOUT_SPACING, 0.0, 0.0)


def compile_threejs(ir: MorphoDocument, config: ThreeJSRenderConfig) -> ThreeJSSceneDescriptor:
    from morpho.identity import geometry_id, visual_id

    geometries = []
    materials = [{"id": DEFAULT_MATERIAL_ID, "kind": "standard", "color": "#3366cc"}]
    meshes = []
    hierarchy = []

    sorted_entities = sorted(ir.entities, key=lambda e: e.id)
    for index, entity in enumerate(sorted_entities):
        gid = geometry_id(entity.id)
        vid = visual_id(entity.id)
        geometries.append({"id": gid, "kind": "box", "params": {"size": [1.0, 1.0, 1.0]}})
        position = _layout_position(entity.id, index, ir)
        meshes.append(
            {
                "id": vid,
                "geometry": gid,
                "material": DEFAULT_MATERIAL_ID,
                "position": list(position),
                "orientation": [0.0, 0.0, 0.0, 1.0],
                "scale": [1.0, 1.0, 1.0],
            }
        )

    frames_by_id = {f.id: f for f in ir.frames}
    for frame in ir.frames:
        if frame.parent is not None and frame.parent in frames_by_id:
            hierarchy.append({"child": visual_id(frame.id), "parent": visual_id(frame.parent)})

    return ThreeJSSceneDescriptor(
        geometries=tuple(geometries),
        materials=tuple(materials),
        meshes=tuple(meshes),
        hierarchy=tuple(hierarchy),
    )
