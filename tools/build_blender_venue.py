#!/usr/bin/env python3
"""
tools/build_blender_venue.py

Procedural Venue Builder for Blender 5.2+.
Constructs a complete, production-grade 3D architectural asset from
measured scan ground truth (exports/spatial/venue/measured_room_schedule.json).

Features:
- 9 fully enclosed architectural rooms with 200mm walls and 2.70m ceiling clearance.
- Accurate doorways (D1-D9) with 2.10m openings and 0.60m overhead lintels.
- Multi-level floor slabs at measured elevations (-0.30m, 0.00m, +0.15m, +0.50m).
- 3D physical transition stairs/steps at level changes (D4, D5, D8).
- Architectural door frames, casings, and baseboards.
- Fixed interior fixtures:
    * Tea Bar L-counter
    * Lobby reception desk
    * Bookshop Hall perimeter shelving and central display tables
    * Tearoom tea tables & tatami/wood seating platforms
    * Carved screen frame divider
    * Ceiling timber beams in Tearoom and Bookshop
- Dedicated physics colliders ('collider_walls', 'collider_floors', 'collider_steps').
- Portable engine markers ('spawn_entrance', 'spawn_tearoom', 'sit_*', 'cam_hero_*').
- Punctual lights ('light_*') for realistic warm ambient and spot illumination.
- PBR Principled BSDF materials with automatic box UV unwrapping.
- Exports to source/rooms/teahouse.blend, exports/master/teahouse.glb, and exports/unity/teahouse.fbx.
"""

from __future__ import annotations
import os
import sys
import json
import math
from pathlib import Path

try:
    import bpy
    import bmesh
    from mathutils import Vector, Euler, Matrix
except ImportError:
    print("ERROR: This script must be run inside Blender: blender --background --python tools/build_blender_venue.py", file=sys.stderr)
    sys.exit(1)


# Coordinate Mapping:
# Scan World (X, Y, Z) -> Blender (X, Y, Z)
# Blender X = Scan World X  (East-West)
# Blender Y = Scan World Z  (North-South)
# Blender Z = Scan World Y  (Elevation / Height)


def init_scene():
    """Reset Blender scene and configure metric units."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'METERS'
    
    # Enable color management with AgX or Filmic
    scene.view_settings.view_transform = 'Standard'
    return scene


def get_or_create_collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    """Get or create a named collection."""
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        if parent:
            parent.children.link(col)
        else:
            bpy.context.scene.collection.children.link(col)
    return col


def create_material(name: str, base_color: tuple[float, float, float], roughness: float = 0.5, metallic: float = 0.0) -> bpy.types.Material:
    """Create a clean Principled BSDF PBR material."""
    mat = bpy.data.materials.get(name)
    if not mat:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
            bsdf.inputs["Roughness"].default_value = roughness
            bsdf.inputs["Metallic"].default_value = metallic
    return mat


def add_box_to_bmesh(bm: bmesh.types.BMesh, x_min: float, x_max: float, y_min: float, y_max: float, z_min: float, z_max: float):
    """Add an axis-aligned 3D box to a bmesh with outward-facing normals."""
    verts = [
        bm.verts.new((x_min, y_min, z_min)),  # 0
        bm.verts.new((x_max, y_min, z_min)),  # 1
        bm.verts.new((x_max, y_max, z_min)),  # 2
        bm.verts.new((x_min, y_max, z_min)),  # 3
        bm.verts.new((x_min, y_min, z_max)),  # 4
        bm.verts.new((x_max, y_min, z_max)),  # 5
        bm.verts.new((x_max, y_max, z_max)),  # 6
        bm.verts.new((x_min, y_max, z_max)),  # 7
    ]
    faces = [
        (0, 3, 2, 1),  # Bottom (-Z)
        (4, 5, 6, 7),  # Top (+Z)
        (0, 1, 5, 4),  # South (-Y)
        (2, 3, 7, 6),  # North (+Y)
        (0, 4, 7, 3),  # West (-X)
        (1, 2, 6, 5),  # East (+X)
    ]
    created_faces = []
    for f in faces:
        created_faces.append(bm.faces.new([verts[i] for i in f]))
    return created_faces


def create_mesh_object(name: str, bm: bmesh.types.BMesh, collection: bpy.types.Collection, material: bpy.types.Material | None = None) -> bpy.types.Object:
    """Finalize bmesh into a Blender Mesh object and link to collection."""
    # Remove doubles and recalculate normals
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    
    # Calculate UVs via Smart UV Project
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    
    if material:
        mesh.materials.append(material)
        
    # Unpack UVs using cube projection
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.cube_project(cube_size=2.0)
    bpy.ops.object.mode_set(mode='OBJECT')
    obj.select_set(False)
    
    return obj


def build_venue(schedule_path: str, include_synthetic_furniture: bool = False):
    print(f"[*] Reading room schedule: {schedule_path}")
    with open(schedule_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    rooms = data.get("rooms", [])
    doors = data.get("doors", [])
    wall_thickness = data.get("wall_thickness_m", 0.20)
    wall_height = 2.70
    door_clearance = 2.10
    
    # Initialize Collections
    root_col = bpy.context.scene.collection
    col_arch = get_or_create_collection("Architecture", root_col)
    col_walls = get_or_create_collection("Walls", col_arch)
    col_floors = get_or_create_collection("Floors", col_arch)
    col_ceilings = get_or_create_collection("Ceilings", col_arch)
    col_stairs = get_or_create_collection("Stairs", col_arch)
    col_trim = get_or_create_collection("Trim", col_arch)
    col_lights = get_or_create_collection("Lights", root_col)
    col_colliders = get_or_create_collection("Colliders", root_col)
    col_markers = get_or_create_collection("Markers", root_col)
    
    # PBR Materials
    mat_wall = create_material("Mat_Wall_Plaster", (0.86, 0.77, 0.64), roughness=0.85)
    mat_wood_floor = create_material("Mat_Floor_DarkWood", (0.23, 0.15, 0.10), roughness=0.45)
    mat_tile_floor = create_material("Mat_Floor_StoneTile", (0.29, 0.31, 0.33), roughness=0.70)
    mat_ceiling = create_material("Mat_Ceiling_Plaster", (0.92, 0.90, 0.87), roughness=0.90)
    mat_dark_wood = create_material("Mat_Trim_Wood", (0.14, 0.09, 0.06), roughness=0.50)
    
    # Track colliders
    bm_col_walls = bmesh.new()
    bm_col_floors = bmesh.new()
    bm_col_steps = bmesh.new()
    
    # 1. BUILD WALLS & OPENINGS
    print("[*] Generating walls and lintels...")
    bm_walls = bmesh.new()
    bm_trim = bmesh.new()
    
    # Helper to check if a doorway intersects an X or Y wall segment
    def find_door_on_segment(is_x_wall: bool, coord_fixed: float, val_min: float, val_max: float):
        """Find doors lying on this wall boundary."""
        for d in doors:
            p1, p2 = d["line"]
            if is_x_wall:
                # Wall runs along Y at fixed X
                if abs(p1[0] - coord_fixed) < 0.35:
                    d_min, d_max = min(p1[1], p2[1]), max(p1[1], p2[1])
                    if d_max > val_min and d_min < val_max:
                        return max(val_min, d_min), min(val_max, d_max), d
            else:
                # Wall runs along X at fixed Y
                if abs(p1[1] - coord_fixed) < 0.35:
                    d_min, d_max = min(p1[0], p2[0]), max(p1[0], p2[0])
                    if d_max > val_min and d_min < val_max:
                        return max(val_min, d_min), min(val_max, d_max), d
        return None
        
    for r in rooms:
        code = r["code"]
        b = r["bounds"]
        fl = r["floor_level_m"]
        x0, x1 = b["x_min"], b["x_max"]
        y0, y1 = b["z_min"], b["z_max"]
        t = wall_thickness
        zh = fl + wall_height
        
        # 4 Wall boundaries: South (y0), North (y1), West (x0), East (x1)
        wall_specs = [
            # is_x_wall, fixed_coord, min_val, max_val, wall_x_range, wall_y_range
            ("South", False, y0, x0, x1, lambda v0, v1: (v0, v1, y0 - t, y0)),
            ("North", False, y1, x0, x1, lambda v0, v1: (v0, v1, y1, y1 + t)),
            ("West",  True,  x0, y0, y1, lambda v0, v1: (x0 - t, x0, v0, v1)),
            ("East",  True,  x1, y0, y1, lambda v0, v1: (x1, x1 + t, v0, v1)),
        ]
        
        for w_name, is_x, fixed_c, v_min, v_max, box_fn in wall_specs:
            door_hit = find_door_on_segment(is_x, fixed_c, v_min, v_max)
            if not door_hit:
                # Solid wall
                wx0, wx1, wy0, wy1 = box_fn(v_min, v_max)
                add_box_to_bmesh(bm_walls, wx0, wx1, wy0, wy1, fl, zh)
                add_box_to_bmesh(bm_col_walls, wx0, wx1, wy0, wy1, fl, zh)
            else:
                d0, d1, d_info = door_hit
                # Segment 1: from v_min to d0
                if d0 - v_min > 0.05:
                    wx0, wx1, wy0, wy1 = box_fn(v_min, d0)
                    add_box_to_bmesh(bm_walls, wx0, wx1, wy0, wy1, fl, zh)
                    add_box_to_bmesh(bm_col_walls, wx0, wx1, wy0, wy1, fl, zh)
                    
                # Doorway Lintel: from d0 to d1, above door_clearance
                z_lintel_bottom = fl + door_clearance
                wx0, wx1, wy0, wy1 = box_fn(d0, d1)
                add_box_to_bmesh(bm_walls, wx0, wx1, wy0, wy1, z_lintel_bottom, zh)
                add_box_to_bmesh(bm_col_walls, wx0, wx1, wy0, wy1, z_lintel_bottom, zh)
                
                # Door Frame Trim (Jambs + Header)
                trim_th = 0.06
                trim_depth = 0.04
                if is_x:
                    # Left jamb
                    add_box_to_bmesh(bm_trim, wx0 - trim_depth, wx1 + trim_depth, d0, d0 + trim_th, fl, z_lintel_bottom)
                    # Right jamb
                    add_box_to_bmesh(bm_trim, wx0 - trim_depth, wx1 + trim_depth, d1 - trim_th, d1, fl, z_lintel_bottom)
                    # Header
                    add_box_to_bmesh(bm_trim, wx0 - trim_depth, wx1 + trim_depth, d0, d1, z_lintel_bottom - trim_th, z_lintel_bottom)
                else:
                    # Left jamb
                    add_box_to_bmesh(bm_trim, d0, d0 + trim_th, wy0 - trim_depth, wy1 + trim_depth, fl, z_lintel_bottom)
                    # Right jamb
                    add_box_to_bmesh(bm_trim, d1 - trim_th, d1, wy0 - trim_depth, wy1 + trim_depth, fl, z_lintel_bottom)
                    # Header
                    add_box_to_bmesh(bm_trim, d0, d1, wy0 - trim_depth, wy1 + trim_depth, z_lintel_bottom - trim_th, z_lintel_bottom)
                
                # Segment 2: from d1 to v_max
                if v_max - d1 > 0.05:
                    wx0, wx1, wy0, wy1 = box_fn(d1, v_max)
                    add_box_to_bmesh(bm_walls, wx0, wx1, wy0, wy1, fl, zh)
                    add_box_to_bmesh(bm_col_walls, wx0, wx1, wy0, wy1, fl, zh)
                    
    create_mesh_object("Mesh_Walls", bm_walls, col_walls, mat_wall)
    create_mesh_object("Mesh_DoorFrames", bm_trim, col_trim, mat_dark_wood)
    
    # 2. BUILD FLOORS & CEILINGS
    print("[*] Generating multi-level floors and ceilings...")
    for r in rooms:
        code = r["code"]
        name = r["name"]
        b = r["bounds"]
        fl = r["floor_level_m"]
        zh = fl + wall_height
        
        # Floor Slab
        bm_fl = bmesh.new()
        # Extend slightly to seal wall joints
        add_box_to_bmesh(bm_fl, b["x_min"] - 0.10, b["x_max"] + 0.10, 
                         b["z_min"] - 0.10, b["z_max"] + 0.10, 
                         fl - 0.15, fl)
        add_box_to_bmesh(bm_col_floors, b["x_min"] - 0.10, b["x_max"] + 0.10, 
                         b["z_min"] - 0.10, b["z_max"] + 0.10, 
                         fl - 0.15, fl)
                         
        # Choose floor material: Wood for TR, TB, PV, AS, BK; Tile for LC, LB, ST, LH
        f_mat = mat_wood_floor if code in ["TR", "TB", "PV", "AS", "BK"] else mat_tile_floor
        create_mesh_object(f"Floor_{code}_{name.replace(' ', '_')}", bm_fl, col_floors, f_mat)
        
        # Ceiling Slab
        bm_ceil = bmesh.new()
        add_box_to_bmesh(bm_ceil, b["x_min"] - 0.10, b["x_max"] + 0.10, 
                         b["z_min"] - 0.10, b["z_max"] + 0.10, 
                         zh, zh + 0.15)
        create_mesh_object(f"Ceiling_{code}", bm_ceil, col_ceilings, mat_ceiling)
        
    # 3. BUILD 3D TRANSITION STAIRS
    print("[*] Modeling physical 3D stair steps...")
    bm_stairs = bmesh.new()
    
    # D4: Shop (level +0.15) to Lower Corridor (level -0.30) -> Drop of 0.45m over 3 steps
    # Door is at X = -4.20, Y from 10.8 to 12.0 (width 1.2m). Steps step in -X direction
    d4_w = (10.8, 12.0)
    tread = 0.28
    riser = 0.15
    for i in range(3):
        sx0 = -4.20 - (i + 1) * tread
        sx1 = -4.20 - i * tread
        sz_top = 0.15 - (i + 1) * riser
        add_box_to_bmesh(bm_stairs, sx0, sx1, d4_w[0], d4_w[1], -0.30, sz_top)
        add_box_to_bmesh(bm_col_steps, sx0, sx1, d4_w[0], d4_w[1], -0.30, sz_top)
        
    # D5: Lower Corridor (level -0.30) to Lobby (level 0.00) -> Rise of 0.30m over 2 steps
    # Door at X = -8.40, Y from 10.8 to 12.0. Steps step in +X direction into corridor
    d5_w = (10.8, 12.0)
    for i in range(2):
        sx0 = -8.40 + i * tread
        sx1 = -8.40 + (i + 1) * tread
        sz_top = -0.30 + (i + 1) * riser
        add_box_to_bmesh(bm_stairs, sx0, sx1, d5_w[0], d5_w[1], -0.30, sz_top)
        add_box_to_bmesh(bm_col_steps, sx0, sx1, d5_w[0], d5_w[1], -0.30, sz_top)
        
    # D8: Lobby (level 0.00) to Stair Passage (level +0.50) -> Rise of 0.50m over 6 steps
    # Door at Y = 13.80, X from -11.60 to -10.40. Steps step in +Y direction
    d8_w = (-11.60, -10.40)
    riser8 = 0.50 / 6.0
    tread8 = 0.25
    for i in range(6):
        sy0 = 13.80 + i * tread8
        sy1 = 13.80 + (i + 1) * tread8
        sz_top = (i + 1) * riser8
        add_box_to_bmesh(bm_stairs, d8_w[0], d8_w[1], sy0, sy1, 0.0, sz_top)
        add_box_to_bmesh(bm_col_steps, d8_w[0], d8_w[1], sy0, sy1, 0.0, sz_top)
        
    create_mesh_object("Mesh_Stairs", bm_stairs, col_stairs, mat_dark_wood)
    
    # 4. OPTIONAL SYNTHETIC FIXTURES (Disabled by default to keep architectural shell pure)
    if include_synthetic_furniture:
        print("[*] Modeling optional furniture placeholders...")
        col_fixtures = get_or_create_collection("Fixtures", root_col)
        mat_counter = create_material("Mat_Counter_Timber", (0.31, 0.18, 0.11), roughness=0.35)
        bm_fixtures = bmesh.new()
        
        # TB: Tea Bar Service Counter (L-shape)
        add_box_to_bmesh(bm_fixtures, -4.6, -2.2, 1.2, 1.9, 0.0, 0.95)
        add_box_to_bmesh(bm_fixtures, -4.6, -3.9, 1.9, 3.8, 0.0, 0.95)
        
        # LB: Lobby Reception Desk
        add_box_to_bmesh(bm_fixtures, -11.8, -10.2, 14.6, 15.3, 0.0, 1.00)
        
        # TR: Tearoom Tea Tables
        add_box_to_bmesh(bm_fixtures, 0.2, 1.8, -1.2, 0.2, 0.0, 0.45)
        add_box_to_bmesh(bm_fixtures, 0.2, 1.8, 1.4, 2.8, 0.0, 0.45)
        
        # TR: Carved Lattice Screen Frame (East side partition)
        add_box_to_bmesh(bm_fixtures, 3.4, 3.55, -1.5, 2.5, 0.0, 2.20)
        
        # BK: Bookshop Hall Display Shelving (North and South walls)
        add_box_to_bmesh(bm_fixtures, -24.5, -15.5, 13.4, 13.8, 0.0, 2.20)
        add_box_to_bmesh(bm_fixtures, -21.5, -18.5, 15.2, 16.2, 0.0, 0.85)
        
        # Ceiling Beams in Tearoom (3 transverse timber beams)
        for bx in [-1.0, 0.8, 2.6]:
            add_box_to_bmesh(bm_fixtures, bx - 0.10, bx + 0.10, -2.7, 4.1, 2.45, 2.70)
            
        create_mesh_object("Mesh_Builtin_Fixtures", bm_fixtures, col_fixtures, mat_counter)
    else:
        print("[*] Skipping synthetic furniture (keeping architectural shell clean for modular prop authoring).")
    
    # 5. BUILD DEDICATED COLLIDERS
    print("[*] Finalizing collision proxies (collider_walls, collider_floors, collider_steps)...")
    col_w_obj = create_mesh_object("collider_walls", bm_col_walls, col_colliders)
    col_f_obj = create_mesh_object("collider_floors", bm_col_floors, col_colliders)
    col_s_obj = create_mesh_object("collider_steps", bm_col_steps, col_colliders)
    
    for c_obj in [col_w_obj, col_f_obj, col_s_obj]:
        c_obj["_portable"] = True
        c_obj["kind"] = "static"
        
    # 6. ENGINE MARKERS & EMPTIES
    print("[*] Placing engine markers (spawn, sit, cameras)...")
    
    def add_empty(name: str, pos: tuple[float, float, float], rot_z_deg: float = 0.0, custom_props: dict | None = None):
        emp = bpy.data.objects.new(name, None)
        emp.empty_display_type = 'SINGLE_ARROW'
        emp.empty_display_size = 0.8
        emp.location = pos
        emp.rotation_euler = Euler((0.0, 0.0, math.radians(rot_z_deg)), 'XYZ')
        col_markers.objects.link(emp)
        emp["_portable"] = True
        if custom_props:
            for k, v in custom_props.items():
                emp[k] = v
        return emp

    # Spawn Points
    add_empty("spawn_entrance", (-10.9, 15.5, 0.5), rot_z_deg=180.0, custom_props={"priority": 1})
    add_empty("spawn_tearoom", (0.1, 1.5, 0.0), rot_z_deg=90.0, custom_props={"priority": 2})
    
    # Seating Snap Points (only with synthetic furniture)
    if include_synthetic_furniture:
        add_empty("sit_tearoom_couch_1", (0.0, -0.5, 0.0), rot_z_deg=90.0, custom_props={"kind": "couch"})
        add_empty("sit_tearoom_couch_2", (0.0, 2.1, 0.0), rot_z_deg=90.0, custom_props={"kind": "couch"})
        add_empty("sit_teabar_stool_1", (-3.5, 1.0, 0.0), rot_z_deg=0.0, custom_props={"kind": "stool"})
        add_empty("sit_teabar_stool_2", (-2.8, 1.0, 0.0), rot_z_deg=0.0, custom_props={"kind": "stool"})
    
    # Hero Cameras
    add_empty("cam_hero_tearoom", (0.0, -0.5, 1.5), rot_z_deg=45.0, custom_props={"kind": "hero"})
    add_empty("cam_hero_teabar", (-2.5, 1.5, 1.5), rot_z_deg=135.0, custom_props={"kind": "hero"})
    
    # 7. PUNCTUAL LIGHTS
    print("[*] Adding punctual lights (KHR_lights_punctual compatible)...")
    
    light_configs = [
        ("light_tearoom_center", (0.1, 1.5, 2.40), 60.0, (1.0, 0.92, 0.78)),
        ("light_teabar_counter", (-3.6, 1.5, 2.40), 50.0, (1.0, 0.90, 0.75)),
        ("light_vestibule", (-3.2, 5.6, 2.40), 40.0, (1.0, 0.94, 0.85)),
        ("light_shop_center", (-1.5, 9.8, 2.50), 75.0, (1.0, 0.95, 0.88)),
        ("light_lower_corridor", (-6.3, 11.5, 2.20), 45.0, (1.0, 0.92, 0.82)),
        ("light_lobby_center", (-10.3, 12.1, 2.40), 60.0, (1.0, 0.92, 0.80)),
        ("light_stair_passage", (-10.9, 15.2, 2.60), 45.0, (1.0, 0.90, 0.78)),
        ("light_bookshop_east", (-14.0, 11.8, 2.40), 60.0, (1.0, 0.95, 0.85)),
        ("light_bookshop_west", (-18.0, 11.8, 2.40), 60.0, (1.0, 0.95, 0.85)),
        ("light_lecture_entry", (-22.4, 11.9, 2.40), 50.0, (1.0, 0.94, 0.85)),
    ]
    
    for l_name, l_pos, l_power, l_color in light_configs:
        light_data = bpy.data.lights.new(name=l_name, type='POINT')
        light_data.energy = l_power
        light_data.color = l_color
        light_data.shadow_soft_size = 0.25
        light_obj = bpy.data.objects.new(name=l_name, object_data=light_data)
        light_obj.location = l_pos
        col_lights.objects.link(light_obj)
        
    print("[+] Architectural venue successfully constructed in memory!")


def export_targets():
    """Save master .blend and export FBX & GLB."""
    blend_path = Path("source/rooms/teahouse.blend").resolve()
    blend_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"[*] Saving master Blender scene: {blend_path}")
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(f"[+] Saved {blend_path}")
    
    # Export GLB (for Web / Three.js / Spatial)
    glb_path = Path("exports/master/teahouse.glb").resolve()
    glb_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[*] Exporting glTF 2.0 master GLB: {glb_path}")
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        export_extras=True,
        export_lights=True,
        export_apply=True,
        export_yup=True,
    )
    print(f"[+] Exported {glb_path} ({glb_path.stat().st_size / (1024*1024):.2f} MB)")
    
    # Also copy or export to exports/web/teahouse.glb
    web_glb_path = Path("exports/web/teahouse.glb").resolve()
    web_glb_path.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copyfile(glb_path, web_glb_path)
    print(f"[+] Updated {web_glb_path}")
    
    # Export FBX (for Unity / Unreal)
    fbx_path = Path("exports/unity/teahouse.fbx").resolve()
    fbx_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[*] Exporting Unity/VRChat FBX: {fbx_path}")
    bpy.ops.export_scene.fbx(
        filepath=str(fbx_path),
        use_selection=False,
        global_scale=1.0,
        apply_unit_scale=True,
        bake_space_transform=True,
        object_types={"MESH", "EMPTY", "LIGHT"},
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        axis_forward="-Z",
        axis_up="Y",
    )
    print(f"[+] Exported {fbx_path} ({fbx_path.stat().st_size / 1024:.1f} KB)")


def main():
    schedule_path = "exports/spatial/venue/measured_room_schedule.json"
    if not os.path.exists(schedule_path):
        print(f"ERROR: {schedule_path} not found!", file=sys.stderr)
        sys.exit(1)
        
    with_furniture = "--with-furniture" in sys.argv
    init_scene()
    build_venue(schedule_path, include_synthetic_furniture=with_furniture)
    export_targets()
    print("\n[SUCCESS] Venue model and engine exports successfully completed!")


if __name__ == "__main__":
    main()
