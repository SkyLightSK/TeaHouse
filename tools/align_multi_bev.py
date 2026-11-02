#!/usr/bin/env python3
"""
tools/align_multi_bev.py

Multi-Panorama Registration and Unified Floorplan Generator.
Combines multiple individual panorama point clouds and BEV slices into a single
geometrically consistent multi-room floorplan and point cloud.
"""

import os
import sys
import json
import argparse
import numpy as np
import cv2
import ezdxf


def read_ply(filename):
    """Read binary little-endian PLY file."""
    with open(filename, 'rb') as f:
        header_lines = []
        while True:
            line = f.readline().decode('utf-8', errors='ignore')
            header_lines.append(line)
            if line.strip() == 'end_header':
                break
                
        # Parse vertex count
        n_verts = 0
        for hl in header_lines:
            if hl.startswith('element vertex'):
                n_verts = int(hl.split()[-1])
                break
                
        dt = np.dtype([
            ('x', '<f4'), ('y', '<f4'), ('z', '<f4'),
            ('r', 'u1'), ('g', 'u1'), ('b', 'u1')
        ])
        data = np.fromfile(f, dtype=dt, count=n_verts)
        
    pts = np.stack([data['x'], data['y'], data['z']], axis=-1)
    cols = np.stack([data['r'], data['g'], data['b']], axis=-1)
    return pts, cols


def write_binary_ply(filename, points, colors):
    """Save 3D point cloud as compact binary PLY."""
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


def compute_relative_offsets(manifest_path, view_ids, seed_id="view-01"):
    """
    Compute relative (X, Z) meter offsets from GPS lat/lng and link headings in tour-manifest.json.
    """
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
        
    views_by_id = {}
    for v in manifest.get('views', []):
        views_by_id[v.get('view_id')] = v
        
    if seed_id not in views_by_id:
        seed_id = list(views_by_id.keys())[0]
        
    seed_view = views_by_id[seed_id]
    seed_lat = seed_view['lat']
    seed_lng = seed_view['lng']
    
    # Meters per degree
    m_per_deg_lat = 111320.0
    m_per_deg_lng = 111320.0 * np.cos(np.radians(seed_lat))
    
    offsets = {}
    for vid in view_ids:
        if vid in views_by_id:
            v = views_by_id[vid]
            dlat = v['lat'] - seed_lat
            dlng = v['lng'] - seed_lng
            
            # X = East (longitude), Z = North (latitude)
            x_m = dlng * m_per_deg_lng
            z_m = dlat * m_per_deg_lat
            offsets[vid] = (float(x_m), float(z_m))
        else:
            offsets[vid] = (0.0, 0.0)
            
    return offsets


def generate_unified_blueprint(view_configs, output_dir, resolution_m=0.02):
    """
    Combine multiple registered viewpoint point clouds into a single unified floorplan.
    view_configs: list of dicts: {'view_id': str, 'ply_path': str, 'offset': (x, z)}
    """
    os.makedirs(output_dir, exist_ok=True)
    all_pts = []
    all_cols = []
    cam_positions = []
    
    print("[*] Merging viewpoint point clouds...")
    for cfg in view_configs:
        vid = cfg['view_id']
        ply_path = cfg['ply_path']
        ox, oz = cfg['offset']
        cam_positions.append((vid, ox, oz))
        
        if not os.path.exists(ply_path):
            print(f"[WARN] PLY not found: {ply_path}", file=sys.stderr)
            continue
            
        pts, cols = read_ply(ply_path)
        # Apply translation (ox, 0, oz)
        pts[:, 0] += ox
        pts[:, 2] += oz
        all_pts.append(pts)
        all_cols.append(cols)
        print(f"  + Added {vid} at offset ({ox:.2f}m, {oz:.2f}m): {len(pts):,} points")
        
    unified_pts = np.concatenate(all_pts, axis=0)
    unified_cols = np.concatenate(all_cols, axis=0)
    print(f"[+] Total unified points: {len(unified_pts):,}")
    
    # Save unified 3D point cloud
    unified_ply_path = os.path.join(output_dir, "unified_rooms_cloud.ply")
    write_binary_ply(unified_ply_path, unified_pts, unified_cols)
    print(f"[+] Saved unified PLY: {unified_ply_path} ({os.path.getsize(unified_ply_path)/(1024*1024):.2f} MB)")
    
    # Calculate bounding box
    X = unified_pts[:, 0]
    Y = unified_pts[:, 1]
    Z = unified_pts[:, 2]
    
    x_min, x_max = np.percentile(X, 1) - 1.0, np.percentile(X, 99) + 1.0
    z_min, z_max = np.percentile(Z, 1) - 1.0, np.percentile(Z, 99) + 1.0
    
    # Grid dimensions
    width_m = x_max - x_min
    height_m = z_max - z_min
    grid_w = int(np.ceil(width_m / resolution_m))
    grid_h = int(np.ceil(height_m / resolution_m))
    print(f"[*] Unified BEV bounds: X [{x_min:.2f}, {x_max:.2f}]m, Z [{z_min:.2f}, {z_max:.2f}]m -> Grid {grid_w}x{grid_h} px")
    
    col = ((X - x_min) / width_m * (grid_w - 1)).astype(int)
    row = (((z_max - Z)) / height_m * (grid_h - 1)).astype(int)
    
    in_bounds = (col >= 0) & (col < grid_w) & (row >= 0) & (row < grid_h)
    
    # Wall slice: Y in [1.2m, 2.2m]
    wall_mask = in_bounds & (Y >= 1.2) & (Y <= 2.2)
    # Furniture slice: Y in [0.4m, 1.1m]
    furn_mask = in_bounds & (Y >= 0.4) & (Y < 1.1)
    
    wall_grid = np.zeros((grid_h, grid_w), dtype=np.float32)
    furn_grid = np.zeros((grid_h, grid_w), dtype=np.float32)
    np.add.at(wall_grid, (row[wall_mask], col[wall_mask]), 1.0)
    np.add.at(furn_grid, (row[furn_mask], col[furn_mask]), 1.0)
    
    # Extract wall line segments
    if wall_grid.max() > 0:
        norm_wall = np.clip(wall_grid / np.percentile(wall_grid[wall_grid > 0], 95) * 255, 0, 255).astype(np.uint8)
    else:
        norm_wall = np.zeros_like(wall_grid, dtype=np.uint8)
        
    blurred = cv2.GaussianBlur(norm_wall, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 35, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    edges = cv2.Canny(closed, 50, 150)
    
    min_length_px = int(0.5 / resolution_m)
    max_gap_px = int(0.3 / resolution_m)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=25, minLineLength=min_length_px, maxLineGap=max_gap_px)
    
    wall_segments = []
    if lines is not None:
        for line in lines:
            pts = line.reshape(-1)
            if len(pts) < 4:
                continue
            c1, r1, c2, r2 = pts[:4]
            x1 = x_min + (c1 / (grid_w - 1)) * width_m
            z1 = z_max - (r1 / (grid_h - 1)) * height_m
            x2 = x_min + (c2 / (grid_w - 1)) * width_m
            z2 = z_max - (r2 / (grid_h - 1)) * height_m
            length = np.sqrt((x2 - x1)**2 + (z2 - z1)**2)
            wall_segments.append(((x1, z1), (x2, z2), length))
            
    print(f"[+] Detected {len(wall_segments)} unified structural wall segments")
    
    # Export DXF
    dxf_path = os.path.join(output_dir, "unified_blueprint.dxf")
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    doc.layers.add('WALLS', color=7)
    doc.layers.add('GRID', color=8)
    doc.layers.add('CAMERAS', color=1)
    
    for (x1, z1), (x2, z2), l in wall_segments:
        msp.add_line((x1, z1), (x2, z2), dxfattribs={'layer': 'WALLS', 'lineweight': 35})
        
    for vid, cx, cz in cam_positions:
        msp.add_circle((cx, cz), radius=0.2, dxfattribs={'layer': 'CAMERAS'})
        msp.add_text(vid, dxfattribs={'layer': 'CAMERAS', 'height': 0.18}).set_placement((cx + 0.25, cz + 0.25))
        
    doc.saveas(dxf_path)
    print(f"[+] Exported unified CAD DXF: {dxf_path}")
    
    # Export SVG
    svg_path = os.path.join(output_dir, "unified_blueprint.svg")
    bg_img = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)
    bg_img[:, :] = [15, 23, 42]  # #0f172a
    
    # Wall glow (cyan) and Furniture glow (amber)
    if wall_grid.max() > 0:
        norm_w = np.clip(wall_grid / np.percentile(wall_grid[wall_grid > 0], 95) * 255, 0, 255).astype(np.uint8)
        norm_f = np.clip(furn_grid / (np.percentile(furn_grid[furn_grid > 0], 95) + 1e-5) * 255, 0, 255).astype(np.uint8)
        
        # Walls in Cyan (B=255, G=200, R=50)
        # Furniture in Orange (B=50, G=150, R=255)
        bg_img[norm_f > 20] = [30, 120, 220]
        bg_img[norm_w > 20] = [220, 180, 50]
        
    bg_png_path = os.path.join(output_dir, "unified_density_bg.png")
    cv2.imwrite(bg_png_path, bg_img)
    
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {grid_w} {grid_h}" width="100%" height="100%">',
        f'  <defs>',
        f'    <style>',
        f'      .wall-line {{ stroke: #38bdf8; stroke-width: 3.0; stroke-linecap: round; filter: drop-shadow(0 0 4px #0284c7); }}',
        f'      .camera-node {{ fill: #f43f5e; stroke: #ffffff; stroke-width: 1.5; }}',
        f'      .camera-label {{ fill: #f8fafc; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 13px; font-weight: bold; }}',
        f'      .link-line {{ stroke: #f43f5e; stroke-width: 1.8; stroke-dasharray: 6,4; opacity: 0.8; }}',
        f'    </style>',
        f'  </defs>',
        f'  <image href="unified_density_bg.png" width="{grid_w}" height="{grid_h}" />',
    ]
    
    # Camera links
    if len(cam_positions) >= 2:
        for i in range(len(cam_positions) - 1):
            _, c1x, c1z = cam_positions[i]
            _, c2x, c2z = cam_positions[i+1]
            p1c = (c1x - x_min) / width_m * (grid_w - 1)
            p1r = (z_max - c1z) / height_m * (grid_h - 1)
            p2c = (c2x - x_min) / width_m * (grid_w - 1)
            p2r = (z_max - c2z) / height_m * (grid_h - 1)
            svg_lines.append(f'  <line x1="{p1c:.1f}" y1="{p1r:.1f}" x2="{p2c:.1f}" y2="{p2r:.1f}" class="link-line" />')
            
    # Camera nodes
    for vid, cx, cz in cam_positions:
        c = (cx - x_min) / width_m * (grid_w - 1)
        r = (z_max - cz) / height_m * (grid_h - 1)
        svg_lines.append(f'  <circle cx="{c:.1f}" cy="{r:.1f}" r="7" class="camera-node" />')
        svg_lines.append(f'  <text x="{c + 10:.1f}" y="{r - 5:.1f}" class="camera-label">{vid}</text>')
        
    # Wall segments
    for (x1, z1), (x2, z2), length in wall_segments:
        c1 = (x1 - x_min) / width_m * (grid_w - 1)
        r1 = (z_max - z1) / height_m * (grid_h - 1)
        c2 = (x2 - x_min) / width_m * (grid_w - 1)
        r2 = (z_max - z2) / height_m * (grid_h - 1)
        svg_lines.append(f'  <line x1="{c1:.1f}" y1="{r1:.1f}" x2="{c2:.1f}" y2="{r2:.1f}" class="wall-line" />')
        
    svg_lines.append(f'</svg>')
    
    with open(svg_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg_lines))
    print(f"[+] Exported unified Vector SVG: {svg_path}")
    
    # Export summary JSON
    summary = {
        "viewpoints": cam_positions,
        "num_total_points": len(unified_pts),
        "num_wall_segments": len(wall_segments),
        "bounds_m": {
            "x_min": float(x_min), "x_max": float(x_max),
            "z_min": float(z_min), "z_max": float(z_max),
            "width_m": float(width_m), "height_m": float(height_m)
        }
    }
    with open(os.path.join(output_dir, "unified_summary.json"), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Multi-Panorama Registration and Unified Floorplan Generator.")
    parser.add_argument("--views", nargs="+", default=["view-01", "view-02"], help="List of view IDs to align.")
    parser.add_argument("--manifest", type=str, default="source/captures/panoramas/tour-manifest.json", help="Path to tour-manifest.json.")
    parser.add_argument("--spatial-dir", type=str, default="exports/spatial", help="Path to individual spatial exports.")
    parser.add_argument("--output-dir", type=str, default="exports/spatial/unified_pilot", help="Output directory for unified deliverables.")
    parser.add_argument("--resolution-m", type=float, default=0.02, help="BEV resolution in meters per pixel.")
    args = parser.parse_args()

    offsets = compute_relative_offsets(args.manifest, args.views, seed_id=args.views[0])
    
    view_cfgs = []
    for vid in args.views:
        ply_path = os.path.join(args.spatial_dir, vid, f"{vid}_metric_cloud.ply")
        view_cfgs.append({
            'view_id': vid,
            'ply_path': ply_path,
            'offset': offsets.get(vid, (0.0, 0.0))
        })
        
    generate_unified_blueprint(view_cfgs, args.output_dir, resolution_m=args.resolution_m)


if __name__ == "__main__":
    main()
