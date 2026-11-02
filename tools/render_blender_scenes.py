#!/usr/bin/env python3
"""
tools/render_blender_scenes.py

High-quality camera rendering script for Blender 5.2+.
Renders dollhouse cutaways and room perspective views directly from source/rooms/teahouse.blend.
"""

import os
import math
import bpy
from mathutils import Vector, Euler

def setup_camera(name, loc, target, fov_deg=65.0):
    cam = bpy.data.cameras.get(name)
    if not cam:
        cam = bpy.data.cameras.new(name)
    cam.lens_unit = 'FOV'
    cam.angle = math.radians(fov_deg)
    cam.clip_start = 0.1
    cam.clip_end = 150.0
    
    obj = bpy.data.objects.get(name)
    if not obj:
        obj = bpy.data.objects.new(name, cam)
        bpy.context.scene.collection.objects.link(obj)
        
    obj.location = Vector(loc)
    direction = Vector(target) - Vector(loc)
    rot_quat = direction.to_track_quat('-Z', 'Y')
    obj.rotation_euler = rot_quat.to_euler()
    return obj

def render_view(scene, cam_obj, filepath, width=1920, height=1080):
    scene.camera = cam_obj
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = os.path.abspath(filepath)
    print(f"[*] Rendering {cam_obj.name} -> {filepath}...")
    bpy.ops.render.render(write_still=True)
    print(f"[+] Render complete: {filepath}")

def main():
    blend_path = "source/rooms/teahouse.blend"
    if not os.path.exists(blend_path):
        print(f"ERROR: {blend_path} not found!")
        return
        
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    scene = bpy.context.scene
    
    # Configure render engine (use EEVEE for clean fast rendering)
    scene.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'RenderSettings') and 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
    
    # Enable ambient light / world
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    bg_node = scene.world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs["Color"].default_value = (0.04, 0.06, 0.10, 1.0)
        bg_node.inputs["Strength"].default_value = 0.7
        
    # Add an exterior sun / directional fill light for dollhouse clarity
    sun_data = bpy.data.lights.new("Sun_Fill", type='SUN')
    sun_data.energy = 2.5
    sun_data.color = (0.95, 0.93, 0.90)
    sun_obj = bpy.data.objects.new("Sun_Fill", sun_data)
    sun_obj.location = (-10.0, 5.0, 18.0)
    sun_obj.rotation_euler = (math.radians(45.0), math.radians(25.0), math.radians(-35.0))
    scene.collection.objects.link(sun_obj)
    
    renders_dir = "exports/spatial/renders"
    os.makedirs(renders_dir, exist_ok=True)
    
    # Hide ceilings for dollhouse views
    ceilings_col = bpy.data.collections.get("Ceilings")
    if ceilings_col:
        ceilings_col.hide_render = True
        
    # 1. OVERALL VENUE DOLLHOUSE OVERVIEW
    # Venue bounds: X: [-24.8, 2.0], Y: [-1.2, 16.6]
    # Center: (-11.4, 7.7)
    cam_doll = setup_camera("Cam_Dollhouse_Overview", (-9.0, -14.0, 22.0), (-11.4, 8.0, 0.5), fov_deg=62.0)
    render_view(scene, cam_doll, os.path.join(renders_dir, "blender_dollhouse_overview.png"), 1920, 1080)
    
    # 2. TEAROOM CUTAWAY (Architectural Shell)
    cam_tr_cut = setup_camera("Cam_Tearoom_Cutaway", (-4.2, -3.2, 5.5), (0.1, 1.5, 0.8), fov_deg=55.0)
    render_view(scene, cam_tr_cut, os.path.join(renders_dir, "tearoom_authentic_cutaway.png"), 1920, 1080)
    
    # Unhide ceilings for interior eye-level cameras
    if ceilings_col:
        ceilings_col.hide_render = False
        
    # 3. TEAROOM INSIDE: Looking West through Doorway D1 into Tea Bar
    # Door D1 is at X = -1.8, Y from 0.6 to 1.8. Camera in Tearoom at (0.8, 1.2, 1.5)
    cam_tr_in = setup_camera("Cam_Tearoom_Inside", (0.80, 1.20, 1.50), (-3.60, 1.20, 1.30), fov_deg=75.0)
    render_view(scene, cam_tr_in, os.path.join(renders_dir, "blender_tearoom_inside.png"), 1920, 1080)
    render_view(scene, cam_tr_in, os.path.join(renders_dir, "tearoom_standing_at_doorway.png"), 1920, 1080)

if __name__ == "__main__":
    main()
