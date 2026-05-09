"""
Headless Blender export script.

Takes a .blend file and exports it to one of:
  - glb (glTF 2.0 binary, KHR_lights_punctual + extras preserved)
  - fbx (for Unity/Unreal)
  - usd (for Apple Vision Pro and NVIDIA Omniverse)

Custom properties (Object Properties > Custom Properties) on objects whose names
start with our portable prefixes (collider_, spawn_, sit_, interactable_, light_,
audio_, portal_, cam_) are exported as glTF "extras" so every runtime can read
them identically.

Usage:
  blender source/rooms/teahouse.blend --background --python tools/blender-export.py -- \
      --out exports/master/teahouse.glb [--format glb|fbx|usd] [--unpack-textures]

This script is meant to be run by tools/export-all.sh, not directly.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Blender's bpy is only available when running inside Blender.
try:
    import bpy  # type: ignore
except ImportError:
    print("ERROR: this script must be run via Blender's python (blender --background --python ...)", file=sys.stderr)
    sys.exit(2)


PORTABLE_PREFIXES = (
    "collider_",
    "spawn_",
    "sit_",
    "interactable_",
    "light_",
    "audio_",
    "portal_",
    "cam_",
)


def parse_args() -> argparse.Namespace:
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser(description="Headless Blender exporter")
    p.add_argument("--out", required=True, help="Output file path.")
    p.add_argument("--format", choices=["glb", "fbx", "usd"], default=None,
                   help="Output format. Inferred from extension if omitted.")
    p.add_argument("--unpack-textures", action="store_true",
                   help="Unpack textures into a sibling 'textures/' folder (FBX/Unity-friendly).")
    return p.parse_args(argv)


def infer_format(out_path: Path) -> str:
    ext = out_path.suffix.lower().lstrip(".")
    if ext in ("glb", "gltf"):
        return "glb"
    if ext == "fbx":
        return "fbx"
    if ext in ("usd", "usda", "usdc", "usdz"):
        return "usd"
    raise ValueError(f"Cannot infer format from extension: {ext}")


def annotate_portable_extras() -> None:
    """
    For every object whose name starts with a portable prefix, ensure its custom
    properties carry an "_portable": true marker so glTF exporter writes them as
    extras. Blender's glTF exporter exports custom props as extras by default
    when the 'Custom Properties' option is on, so this is mostly a no-op safety
    pass — but it also injects 'kind' / 'event' defaults for objects authored
    without them.
    """
    for obj in bpy.data.objects:
        name = obj.name
        if not any(name.startswith(p) for p in PORTABLE_PREFIXES):
            continue
        if "_portable" not in obj:
            obj["_portable"] = True
        # Sit/interactable objects without a 'kind' get a sensible default.
        if name.startswith("sit_") and "kind" not in obj:
            obj["kind"] = "chair"
        if name.startswith("interactable_") and "kind" not in obj:
            obj["kind"] = "pickup"


def export_glb(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(out),
        export_format="GLB",
        export_extras=True,                # writes custom properties as glTF extras
        export_lights=True,                # KHR_lights_punctual
        export_apply=True,                 # apply modifiers
        export_yup=True,                   # glTF expects +Y up
        export_cameras=False,
        export_animations=True,
        export_skins=True,
        export_morph=True,
        export_image_format="AUTO",        # JPEG for opaque, PNG with alpha
        export_texture_dir="",
    )


def export_fbx(out: Path, unpack_textures: bool) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if unpack_textures:
        try:
            bpy.ops.file.unpack_all(method="USE_LOCAL")
        except RuntimeError:
            pass
    bpy.ops.export_scene.fbx(
        filepath=str(out),
        use_selection=False,
        global_scale=1.0,
        apply_unit_scale=True,
        bake_space_transform=True,
        object_types={"MESH", "EMPTY", "LIGHT", "ARMATURE", "OTHER"},
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        path_mode="COPY",                   # copy textures next to fbx
        embed_textures=False,
        axis_forward="-Z",
        axis_up="Y",
    )


def export_usd(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.usd_export(
        filepath=str(out),
        selected_objects_only=False,
        visible_objects_only=True,
        export_animation=True,
        export_hair=False,
        export_uvmaps=True,
        export_normals=True,
        export_materials=True,
        use_instancing=True,
    )


def main() -> int:
    args = parse_args()
    out = Path(args.out).resolve()
    fmt = args.format or infer_format(out)

    annotate_portable_extras()

    if fmt == "glb":
        export_glb(out)
    elif fmt == "fbx":
        export_fbx(out, args.unpack_textures)
    elif fmt == "usd":
        export_usd(out)
    else:
        print(f"Unknown format: {fmt}", file=sys.stderr)
        return 1

    print(f"Exported {fmt}: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
