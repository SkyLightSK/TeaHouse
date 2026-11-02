#!/usr/bin/env python3
"""
tools/pano_depth_bev.py

Equirectangular Panorama to Metric 3D Point Cloud and 2D BEV Vector Blueprint.

Pipeline:
1. Load 360 equirectangular panorama and optional tour-manifest metadata (heading, links).
2. Predict dense depth/disparity using Depth-Anything-V2 on GPU.
3. Calibrate metric scale using nadir floor ground plane geometry (tripod height anchor).
4. Unproject spherical rays to metric 3D point cloud (X=East/Right, Y=Up, Z=North/Forward).
5. Orient point cloud to global North using panorama compass heading.
6. Export colorized 3D point cloud (.ply) for Blender/CAD/CloudCompare.
7. Slice point cloud into horizontal elevation bands (walls, furniture, floor).
8. Project to 2D Bird's Eye View (BEV) density raster grid (1px = 2cm).
9. Extract structural wall line segments via morphological filtering and Hough/RANSAC.
10. Export vector blueprints in DXF (CAD) and SVG (Web) formats + metadata summary.
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path

import numpy as np
import cv2
from PIL import Image
import torch
from transformers import pipeline
import ezdxf


def load_manifest(manifest_path, view_id_or_file):
    """Find viewpoint metadata from tour-manifest.json."""
    if not manifest_path or not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for view in data.get('views', []):
            if view.get('view_id') == view_id_or_file or view.get('file') == view_id_or_file:
                return view
            if os.path.basename(view.get('file', '')) == os.path.basename(view_id_or_file):
                return view
    except Exception as e:
        print(f"[WARN] Failed to read manifest: {e}", file=sys.stderr)
    return None


def run_depth_estimation(image_path, model_name, device, width=2048, height=1024, pipe=None):
    """Run Depth-Anything-V2 to get relative disparity map."""
    print(f"[*] Loading panorama: {image_path}")
    orig_img = Image.open(image_path).convert('RGB')
    orig_w, orig_h = orig_img.size
    print(f"[*] Original resolution: {orig_w}x{orig_h}")

    # Resize for inference (2048x1024 provides excellent angular detail while fitting in VRAM)
    img_resized = orig_img.resize((width, height), Image.Resampling.LANCZOS)
    
    if pipe is None:
        print(f"[*] Initializing depth model '{model_name}' on device '{device}'...")
        pipe = pipeline('depth-estimation', model=model_name, device=device)
    
    t0 = time.time()
    print(f"[*] Running depth inference on {width}x{height} equirectangular frame...")
    res = pipe(img_resized)
    print(f"[+] Depth estimation finished in {time.time() - t0:.2f}s")
    
    disparity = np.array(res['predicted_depth'], dtype=np.float32)
    return orig_img, img_resized, disparity, pipe


def calibrate_nadir_scale(disparity, width, height, camera_height=1.50):
    """
    Calibrate metric scale s using nadir ground floor geometry.
    In Depth Anything, disparity d ~ 1/depth.
    On the floor plane: Y = R * ry = -h_cam => R = h_cam / |ry|
    Therefore s / d = h_cam / |ry| => s = (h_cam * d) / |ry|.
    We take the robust median across the floor cone (phi in [-75 deg, -45 deg]).
    """
    v = np.arange(height)
    phi = (0.5 - (v + 0.5) / height) * np.pi  # (height,)
    ry = np.sin(phi)  # (height,)
    
    # Broadcast ry across width
    ry_2d = np.tile(ry[:, np.newaxis], (1, width))
    phi_2d = np.tile(phi[:, np.newaxis], (1, width))
    
    # Filter downward floor cone
    floor_mask = (phi_2d < np.radians(-45)) & (phi_2d > np.radians(-75))
    
    # Avoid zero disparity or extreme noise
    valid = floor_mask & (disparity > 1e-3)
    
    if np.sum(valid) == 0:
        print("[WARN] No valid floor points found in nadir cone. Using fallback scale.", file=sys.stderr)
        return 10.0, phi_2d, ry_2d
    
    s_samples = (camera_height * disparity[valid]) / np.abs(ry_2d[valid])
    s_robust = float(np.median(s_samples))
    print(f"[+] Calibrated metric scale factor s = {s_robust:.4f} (from {np.sum(valid):,} floor rays)")
    return s_robust, phi_2d, ry_2d


def unproject_equirectangular(img_rgb, disparity, scale_s, camera_height=1.50, max_dist=12.0, heading_deg=0.0):
    """
    Unproject equirectangular disparity to 3D metric point cloud.
    Coordinates:
      X = East / Right
      Y = Height (Y=0 is floor, Y=camera_height is camera level)
      Z = North / Forward (rotated by heading)
    """
    height, width = disparity.shape
    u = np.arange(width)
    v = np.arange(height)
    uu, vv = np.meshgrid(u, v)
    
    # Spherical coordinates
    theta = (uu / width - 0.5) * 2.0 * np.pi  # azimuth [-pi, pi]
    phi = (0.5 - vv / height) * np.pi         # elevation [-pi/2, pi/2]
    
    # Rotate azimuth by heading (clockwise from North)
    # heading_deg rotates clockwise: theta_world = theta + radians(heading_deg)
    heading_rad = np.radians(heading_deg)
    theta_w = theta + heading_rad
    
    # Compute 3D unit rays (Right-handed, Y-up: X=sin(theta_w)*cos(phi), Z=cos(theta_w)*cos(phi), Y=sin(phi))
    rx = np.cos(phi) * np.sin(theta_w)
    ry = np.sin(phi)
    rz = np.cos(phi) * np.cos(theta_w)
    
    # Radial metric distance R in meters
    R = scale_s / np.maximum(disparity, 1e-4)
    
    # Filter points beyond max_dist or below ground threshold
    valid_mask = (R > 0.2) & (R <= max_dist) & (np.isfinite(R))
    
    X = R * rx
    Y = R * ry + camera_height  # Y=0 is ground floor
    Z = R * rz
    
    rgb_arr = np.array(img_rgb, dtype=np.uint8)
    
    points = np.stack([X[valid_mask], Y[valid_mask], Z[valid_mask]], axis=-1).astype(np.float32)
    colors = rgb_arr[valid_mask].astype(np.uint8)
    
    print(f"[+] Generated {len(points):,} metric 3D points (culling threshold: {max_dist}m)")
    return points, colors, (X, Y, Z, valid_mask)


def export_binary_ply(filename, points, colors):
    """Save 3D point cloud as compact binary little-endian PLY file."""
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    N = len(points)
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {N}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property uchar red\n"
        "property uchar green\n"
        "property uchar blue\n"
        "end_header\n"
    ).encode("utf-8")
    
    dt = np.dtype([
        ('x', '<f4'), ('y', '<f4'), ('z', '<f4'),
        ('r', 'u1'), ('g', 'u1'), ('b', 'u1')
    ])
    arr = np.empty(N, dtype=dt)
    arr['x'] = points[:, 0]
    arr['y'] = points[:, 1]
    arr['z'] = points[:, 2]
    arr['r'] = colors[:, 0]
    arr['g'] = colors[:, 1]
    arr['b'] = colors[:, 2]
    
    with open(filename, 'wb') as f:
        f.write(header)
        arr.tofile(f)
    print(f"[+] Exported 3D point cloud: {filename} ({os.path.getsize(filename)/(1024*1024):.2f} MB)")


def create_bev_density_slices(points, colors, meter_range=8.0, resolution_m=0.02):
    """
    Project points onto 2D Bird's Eye View (BEV) orthogonal grid.
    resolution_m = 0.02 (2 cm per pixel).
    Grid spans [-meter_range, +meter_range] along X and Z.
    """
    grid_pixels = int(np.ceil((2.0 * meter_range) / resolution_m))
    print(f"[*] Generating BEV slices: {grid_pixels}x{grid_pixels} px ({resolution_m*100:.1f} cm/px, range ±{meter_range}m)...")
    
    X = points[:, 0]
    Y = points[:, 1]
    Z = points[:, 2]
    
    # 2D Grid coordinates: X maps to col, Z maps to row
    # In BEV map: North (+Z) is UP (row 0 at +Z), South (-Z) is DOWN
    # East (+X) is RIGHT, West (-X) is LEFT
    col = ((X + meter_range) / (2.0 * meter_range) * (grid_pixels - 1)).astype(int)
    row = (((meter_range - Z)) / (2.0 * meter_range) * (grid_pixels - 1)).astype(int)
    
    in_bounds = (col >= 0) & (col < grid_pixels) & (row >= 0) & (row < grid_pixels)
    
    # Band definitions
    # 1. Wall band: Y in [1.2m, 2.2m] (above tables, sofas, counters; below ceiling)
    # 2. Furniture band: Y in [0.35m, 1.1m] (tables, chairs, tea counters, sofas)
    # 3. Floor band: Y in [0.0m, 0.3m]
    wall_mask = in_bounds & (Y >= 1.2) & (Y <= 2.2)
    furn_mask = in_bounds & (Y >= 0.35) & (Y < 1.1)
    
    wall_density = np.zeros((grid_pixels, grid_pixels), dtype=np.float32)
    np.add.at(wall_density, (row[wall_mask], col[wall_mask]), 1.0)
    
    furn_density = np.zeros((grid_pixels, grid_pixels), dtype=np.float32)
    np.add.at(furn_density, (row[furn_mask], col[furn_mask]), 1.0)
    
    # Accumulate colors for composite view
    color_acc = np.zeros((grid_pixels, grid_pixels, 3), dtype=np.float32)
    count_acc = np.zeros((grid_pixels, grid_pixels, 1), dtype=np.float32)
    np.add.at(color_acc, (row[in_bounds], col[in_bounds]), colors[in_bounds].astype(np.float32))
    np.add.at(count_acc, (row[in_bounds], col[in_bounds]), 1.0)
    
    valid_color = (count_acc > 0).squeeze()
    color_map = np.zeros((grid_pixels, grid_pixels, 3), dtype=np.uint8)
    color_map[valid_color] = np.clip(color_acc[valid_color] / count_acc[valid_color], 0, 255).astype(np.uint8)
    
    return wall_density, furn_density, color_map, grid_pixels


def extract_wall_segments(wall_density, meter_range, resolution_m):
    """
    Extract vector wall segments from wall density grid using morphology & Hough transform.
    Returns list of ((x1, z1), (x2, z2), length_m) in world meters.
    """
    grid_size = wall_density.shape[0]
    
    # Normalize density to uint8
    if wall_density.max() > 0:
        norm_density = np.clip(wall_density / np.percentile(wall_density[wall_density > 0], 95) * 255, 0, 255).astype(np.uint8)
    else:
        norm_density = np.zeros_like(wall_density, dtype=np.uint8)
        
    # Gaussian blur & threshold
    blurred = cv2.GaussianBlur(norm_density, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 40, 255, cv2.THRESH_BINARY)
    
    # Morphological closing to bridge small gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    # Edge skeleton / Canny
    edges = cv2.Canny(closed, 50, 150)
    
    # Probabilistic Hough Line Transform
    # minLineLength: at least 0.5 meter (0.5 / resolution_m pixels)
    # maxLineGap: bridge up to 0.25 meter gaps
    min_length_px = int(0.5 / resolution_m)
    max_gap_px = int(0.25 / resolution_m)
    
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=25, minLineLength=min_length_px, maxLineGap=max_gap_px)
    
    wall_segments = []
    if lines is not None:
        for line in lines:
            pts = line.reshape(-1)
            if len(pts) < 4:
                continue
            c1, r1, c2, r2 = pts[:4]
            # Convert pixel (c, r) back to world (X, Z) in meters
            # col = (X + meter_range) / (2 * meter_range) * (grid_size - 1)
            # row = (meter_range - Z) / (2 * meter_range) * (grid_size - 1)
            x1 = (c1 / (grid_size - 1)) * (2.0 * meter_range) - meter_range
            z1 = meter_range - (r1 / (grid_size - 1)) * (2.0 * meter_range)
            x2 = (c2 / (grid_size - 1)) * (2.0 * meter_range) - meter_range
            z2 = meter_range - (r2 / (grid_size - 1)) * (2.0 * meter_range)
            
            length = np.sqrt((x2 - x1)**2 + (z2 - z1)**2)
            wall_segments.append(((x1, z1), (x2, z2), length))
            
    print(f"[+] Detected {len(wall_segments)} candidate wall segments")
    return wall_segments, norm_density, closed


def export_cad_dxf(output_path, wall_segments, meter_range=8.0, camera_pos=(0.0, 0.0)):
    """Export clean 2D vector CAD blueprint in DXF format using ezdxf."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Layers
    doc.layers.add('WALLS', color=7)       # White/black
    doc.layers.add('GRID', color=8)        # Gray
    doc.layers.add('CAMERA', color=1)      # Red
    doc.layers.add('ANNOTATIONS', color=3) # Green
    
    # Grid lines (every 1 meter)
    for m in range(int(-meter_range), int(meter_range) + 1):
        msp.add_line((m, -meter_range), (m, meter_range), dxfattribs={'layer': 'GRID', 'linetype': 'DASHED'})
        msp.add_line((-meter_range, m), (meter_range, m), dxfattribs={'layer': 'GRID', 'linetype': 'DASHED'})
        
    # Camera marker
    cx, cz = camera_pos
    msp.add_circle((cx, cz), radius=0.15, dxfattribs={'layer': 'CAMERA'})
    msp.add_line((cx - 0.25, cz), (cx + 0.25, cz), dxfattribs={'layer': 'CAMERA'})
    msp.add_line((cx, cz - 0.25), (cx, cz + 0.25), dxfattribs={'layer': 'CAMERA'})
    msp.add_text("CAMERA", dxfattribs={'layer': 'CAMERA', 'height': 0.15}).set_placement((cx + 0.2, cz + 0.2))
    
    # Wall segments
    for (x1, z1), (x2, z2), length in wall_segments:
        msp.add_line((x1, z1), (x2, z2), dxfattribs={'layer': 'WALLS', 'lineweight': 35})
        
    doc.saveas(output_path)
    print(f"[+] Exported CAD DXF blueprint: {output_path}")


def export_vector_svg(output_path, wall_segments, wall_density, meter_range=8.0, camera_pos=(0.0, 0.0)):
    """Export vector SVG with background density overlay for web and visual inspection."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    grid_size = wall_density.shape[0]
    
    # Save a background thumbnail
    bg_rel_path = "bev_density_bg.png"
    bg_abs_path = os.path.join(os.path.dirname(output_path), bg_rel_path)
    
    # Invert density for clean blueprint background (dark on light or blueprint dark theme)
    # Let's create a sleek architectural blueprint theme: deep blue background (#0f172a)
    bg_img = np.zeros((grid_size, grid_size, 3), dtype=np.uint8)
    bg_img[:, :] = [15, 23, 42]  # #0f172a
    
    # Density glow in cyan/blue
    if wall_density.max() > 0:
        norm = np.clip(wall_density / np.percentile(wall_density[wall_density > 0], 95) * 255, 0, 255).astype(np.uint8)
        # Apply colormap
        heat = cv2.applyColorMap(norm, cv2.COLORMAP_OCEAN)
        mask = norm > 15
        bg_img[mask] = cv2.addWeighted(bg_img[mask], 0.3, heat[mask], 0.7, 0)
        
    cv2.imwrite(bg_abs_path, bg_img)
    
    # Build SVG content
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {grid_size} {grid_size}" width="100%" height="100%">',
        f'  <defs>',
        f'    <style>',
        f'      .wall-line {{ stroke: #38bdf8; stroke-width: 3.5; stroke-linecap: round; filter: drop-shadow(0 0 3px #0284c7); }}',
        f'      .grid-line {{ stroke: #334155; stroke-width: 0.8; stroke-dasharray: 4,4; }}',
        f'      .camera-marker {{ fill: #f43f5e; stroke: #ffffff; stroke-width: 1.5; }}',
        f'      .text-label {{ fill: #94a3b8; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 14px; }}',
        f'    </style>',
        f'  </defs>',
        f'  <image href="{bg_rel_path}" width="{grid_size}" height="{grid_size}" />',
    ]
    
    # Grid lines every 1m
    for m in range(int(-meter_range), int(meter_range) + 1):
        c = int((m + meter_range) / (2.0 * meter_range) * (grid_size - 1))
        r = int((meter_range - m) / (2.0 * meter_range) * (grid_size - 1))
        svg_lines.append(f'  <line x1="{c}" y1="0" x2="{c}" y2="{grid_size}" class="grid-line" />')
        svg_lines.append(f'  <line x1="0" y1="{r}" x2="{grid_size}" y2="{r}" class="grid-line" />')
        if m % 2 == 0:
            svg_lines.append(f'  <text x="{c + 4}" y="20" class="text-label">{m}m</text>')
            svg_lines.append(f'  <text x="6" y="{r - 4}" class="text-label">{m}m</text>')
            
    # Camera position
    cx, cz = camera_pos
    cam_c = int((cx + meter_range) / (2.0 * meter_range) * (grid_size - 1))
    cam_r = int((meter_range - cz) / (2.0 * meter_range) * (grid_size - 1))
    svg_lines.append(f'  <circle cx="{cam_c}" cy="{cam_r}" r="6" class="camera-marker" />')
    svg_lines.append(f'  <text x="{cam_c + 10}" y="{cam_r + 4}" fill="#f43f5e" font-weight="bold" font-family="monospace" font-size="13">CAM (0,0)</text>')
    
    # Walls
    for (x1, z1), (x2, z2), length in wall_segments:
        c1 = (x1 + meter_range) / (2.0 * meter_range) * (grid_size - 1)
        r1 = (meter_range - z1) / (2.0 * meter_range) * (grid_size - 1)
        c2 = (x2 + meter_range) / (2.0 * meter_range) * (grid_size - 1)
        r2 = (meter_range - z2) / (2.0 * meter_range) * (grid_size - 1)
        svg_lines.append(f'  <line x1="{c1:.1f}" y1="{r1:.1f}" x2="{c2:.1f}" y2="{r2:.1f}" class="wall-line" />')
        
    # Compass indicator
    svg_lines.append(f'  <!-- Compass -->')
    svg_lines.append(f'  <g transform="translate({grid_size - 60}, 60)">')
    svg_lines.append(f'    <circle r="30" fill="#1e293b" stroke="#475569" stroke-width="1.5" />')
    svg_lines.append(f'    <polygon points="0,-22 7,-4 0,-10 -7,-4" fill="#f43f5e" />')
    svg_lines.append(f'    <polygon points="0,22 7,4 0,10 -7,4" fill="#64748b" />')
    svg_lines.append(f'    <text x="-4" y="-8" fill="#f43f5e" font-size="11" font-weight="bold" font-family="sans-serif">N</text>')
    svg_lines.append(f'  </g>')
    
    svg_lines.append(f'</svg>')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg_lines))
    print(f"[+] Exported Vector SVG blueprint: {output_path}")


def process_panorama(image_path, output_dir, view_id="view-01", manifest_path=None,
                      model_name="depth-anything/Depth-Anything-V2-Base-hf",
                      camera_height=1.50, meter_range=8.0, resolution_m=0.02,
                      max_dist=12.0, device="cuda", pipe=None):
    """Full execution pipeline for a single equirectangular panorama."""
    print("=" * 70)
    print(f"PROCESSING PANORAMA: {view_id} -> {image_path}")
    print("=" * 70)
    os.makedirs(output_dir, exist_ok=True)
    
    meta = load_manifest(manifest_path, view_id) or load_manifest(manifest_path, os.path.basename(image_path))
    heading_deg = 0.0
    pano_id = None
    if meta:
        heading_deg = float(meta.get('heading', 0.0))
        pano_id = meta.get('pano_id')
        print(f"[+] Manifest match: heading={heading_deg}°, pano_id={pano_id}")
    else:
        print(f"[!] No manifest metadata found. Using heading={heading_deg}°")

    # Step 1: Depth Estimation
    orig_img, resized_img, disparity, pipe = run_depth_estimation(image_path, model_name, device, pipe=pipe)
    
    # Save disparity preview
    disp_norm = (disparity - disparity.min()) / (disparity.max() - disparity.min() + 1e-6)
    disp_colored = cv2.applyColorMap((disp_norm * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
    cv2.imwrite(os.path.join(output_dir, "predicted_disparity.png"), disp_colored)
    
    # Step 2: Metric Floor Scale Calibration
    scale_s, phi_2d, ry_2d = calibrate_nadir_scale(disparity, disparity.shape[1], disparity.shape[0], camera_height)
    
    # Step 3: Unproject to 3D Point Cloud with Heading Alignment
    points, colors, (X, Y, Z, valid_mask) = unproject_equirectangular(
        resized_img, disparity, scale_s,
        camera_height=camera_height, max_dist=max_dist, heading_deg=heading_deg
    )
    
    # Step 4: Export 3D PLY
    ply_path = os.path.join(output_dir, f"{view_id}_metric_cloud.ply")
    export_binary_ply(ply_path, points, colors)
    
    # Step 5: BEV Multi-Band Slices
    wall_density, furn_density, color_map, grid_size = create_bev_density_slices(
        points, colors, meter_range=meter_range, resolution_m=resolution_m
    )
    
    # Save raster BEV maps
    cv2.imwrite(os.path.join(output_dir, "bev_wall_density.png"), 
                np.clip(wall_density / (np.percentile(wall_density[wall_density > 0], 95) + 1e-6) * 255, 0, 255).astype(np.uint8))
    cv2.imwrite(os.path.join(output_dir, "bev_furniture_density.png"), 
                np.clip(furn_density / (np.percentile(furn_density[furn_density > 0], 95) + 1e-6) * 255, 0, 255).astype(np.uint8))
    cv2.imwrite(os.path.join(output_dir, "bev_rgb_ortho.png"), cv2.cvtColor(color_map, cv2.COLOR_RGB2BGR))
    
    # Step 6: Wall Extraction
    wall_segments, norm_density, closed = extract_wall_segments(wall_density, meter_range, resolution_m)
    
    # Step 7: Export DXF CAD
    dxf_path = os.path.join(output_dir, f"{view_id}_blueprint.dxf")
    export_cad_dxf(dxf_path, wall_segments, meter_range=meter_range, camera_pos=(0.0, 0.0))
    
    # Step 8: Export SVG Vector
    svg_path = os.path.join(output_dir, f"{view_id}_blueprint.svg")
    export_vector_svg(svg_path, wall_segments, wall_density, meter_range=meter_range, camera_pos=(0.0, 0.0))
    
    # Step 9: Metadata & Summary JSON
    summary = {
        "view_id": view_id,
        "image_file": os.path.basename(image_path),
        "pano_id": pano_id,
        "heading_deg": heading_deg,
        "camera_height_m": camera_height,
        "metric_scale_factor": scale_s,
        "num_3d_points": len(points),
        "num_wall_segments": len(wall_segments),
        "meter_range": meter_range,
        "resolution_cm_per_px": resolution_m * 100.0,
        "bounds": {
            "x_min_m": float(points[:, 0].min()),
            "x_max_m": float(points[:, 0].max()),
            "y_min_m": float(points[:, 1].min()),
            "y_max_m": float(points[:, 1].max()),
            "z_min_m": float(points[:, 2].min()),
            "z_max_m": float(points[:, 2].max()),
        },
        "wall_segments": [
            {
                "start": [float(p1[0]), float(p1[1])],
                "end": [float(p2[0]), float(p2[1])],
                "length_m": float(l)
            }
            for p1, p2, l in wall_segments
        ]
    }
    with open(os.path.join(output_dir, "spatial_summary.json"), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(f"[+] Spatial summary exported: {os.path.join(output_dir, 'spatial_summary.json')}")
    print("=" * 70 + "\n")
    return summary, pipe


def main():
    parser = argparse.ArgumentParser(description="Convert equirectangular panoramas to metric 3D point cloud & CAD blueprint.")
    parser.add_argument("--image", type=str, help="Path to equirectangular JPG/PNG panorama.")
    parser.add_argument("--view-id", type=str, default="view-01", help="Identifier for viewpoint (e.g. view-01).")
    parser.add_argument("--batch", nargs="+", help="List of view IDs to process in batch (e.g. view-01 view-02 view-03).")
    parser.add_argument("--all", action="store_true", help="Process all 23 views from tour-manifest.json.")
    parser.add_argument("--manifest", type=str, default="source/captures/panoramas/tour-manifest.json", help="Path to tour-manifest.json.")
    parser.add_argument("--output-dir", type=str, default="exports/spatial", help="Directory for output deliverables.")
    parser.add_argument("--model", type=str, default="depth-anything/Depth-Anything-V2-Base-hf", help="Hugging Face depth model.")
    parser.add_argument("--camera-height", type=float, default=1.50, help="Camera height above floor in meters.")
    parser.add_argument("--meter-range", type=float, default=8.0, help="Half-width of BEV grid in meters.")
    parser.add_argument("--resolution-m", type=float, default=0.02, help="BEV grid resolution in meters per pixel (default: 0.02 = 2cm).")
    parser.add_argument("--max-dist", type=float, default=12.0, help="Max distance threshold in meters.")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu", help="PyTorch compute device.")
    args = parser.parse_args()

    pipe = None
    if args.all or args.batch:
        with open(args.manifest, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        views_to_run = manifest.get('views', [])
        if args.batch:
            views_to_run = [v for v in views_to_run if v.get('view_id') in args.batch]
            
        print(f"[*] Starting batch processing of {len(views_to_run)} panoramas...")
        t_start = time.time()
        for idx, v in enumerate(views_to_run):
            vid = v.get('view_id')
            fname = v.get('file')
            img_path = os.path.join(os.path.dirname(args.manifest), fname)
            out = os.path.join(args.output_dir, vid)
            _, pipe = process_panorama(
                img_path, out, view_id=vid, manifest_path=args.manifest,
                model_name=args.model, camera_height=args.camera_height,
                meter_range=args.meter_range, resolution_m=args.resolution_m,
                max_dist=args.max_dist, device=args.device, pipe=pipe
            )
        print(f"[+] Successfully batch-processed {len(views_to_run)} views in {time.time() - t_start:.2f}s!")
    elif args.image:
        out = os.path.join(args.output_dir, args.view_id)
        process_panorama(
            args.image, out, view_id=args.view_id, manifest_path=args.manifest,
            model_name=args.model, camera_height=args.camera_height,
            meter_range=args.meter_range, resolution_m=args.resolution_m,
            max_dist=args.max_dist, device=args.device
        )
    else:
        print("[!] No --image, --batch, or --all specified.", file=sys.stderr)


if __name__ == "__main__":
    main()
