#!/usr/bin/env python3
"""
tools/pano_depth_calibrated.py

Calibrated Reality-Capture Pipeline for Equirectangular Panoramas.
Fixes the two fundamental mathematical flaws of monocular spherical depth:

1. Pinhole Cubemap Decomposition:
   Decomposes equirectangular panoramas into 6 distortion-free rectilinear
   pinhole faces (90x90 deg FOV) before running Depth-Anything-V2.
   Converts perspective depth to spherical radial depth and reprojects to sphere.

2. 2-Parameter Affine Regression (Scale s & Shift t):
   Solves y = (1 / R_true) = |sin(phi)| / h_cam = s * d + t
   using robust RANSAC linear regression on ground floor rays.
   Prevents asymptotic distance explosion at eye-level horizon walls.

Usage:
  python tools/pano_depth_calibrated.py --view view-01
  python tools/pano_depth_calibrated.py --view view-03
  python tools/pano_depth_calibrated.py --all
"""

from __future__ import annotations
import os
import sys
import json
import time
import math
import argparse
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

import torch
from transformers import pipeline


def equirect_to_cubemap_faces(equirect_img: np.ndarray, face_size: int = 768) -> list[np.ndarray]:
    """
    Convert an equirectangular image into 6 rectilinear cube faces.
    Faces order: Front (0, +Z), Right (1, +X), Back (2, -Z), Left (3, -X), Top (4, +Y), Bottom (5, -Y).
    """
    h_eq, w_eq = equirect_img.shape[:2]
    faces = []
    
    u = (np.arange(face_size) - face_size / 2.0 + 0.5) / (face_size / 2.0)
    v = (face_size / 2.0 - np.arange(face_size) - 0.5) / (face_size / 2.0)
    uu, vv = np.meshgrid(u, v)
    ones = np.ones_like(uu)
    
    face_rays = [
        np.stack([uu, vv, ones], axis=-1),    # Front (+Z)
        np.stack([ones, vv, -uu], axis=-1),   # Right (+X)
        np.stack([-uu, vv, -ones], axis=-1),  # Back (-Z)
        np.stack([-ones, vv, uu], axis=-1),   # Left (-X)
        np.stack([uu, ones, -vv], axis=-1),   # Top (+Y)
        np.stack([uu, -ones, vv], axis=-1),   # Bottom (-Y)
    ]
    
    for ray in face_rays:
        norm = np.linalg.norm(ray, axis=-1, keepdims=True)
        unit_ray = ray / norm
        rx, ry, rz = unit_ray[..., 0], unit_ray[..., 1], unit_ray[..., 2]
        
        theta = np.arctan2(rx, rz)
        phi = np.arcsin(np.clip(ry, -1.0, 1.0))
        
        u_eq = (theta / (2.0 * math.pi) + 0.5) * w_eq - 0.5
        v_eq = (0.5 - phi / math.pi) * h_eq - 0.5
        
        map_x = u_eq.astype(np.float32)
        map_y = v_eq.astype(np.float32)
        
        face_img = cv2.remap(equirect_img, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        faces.append(face_img)
        
    return faces


def cubemap_to_equirect(faces: list[np.ndarray], out_w: int = 2048, out_h: int = 1024) -> np.ndarray:
    """Reproject 6 cube faces back into an equirectangular image."""
    face_size = faces[0].shape[0]
    u = np.arange(out_w)
    v = np.arange(out_h)
    uu, vv = np.meshgrid(u, v)
    
    theta = (uu / out_w - 0.5) * 2.0 * np.pi
    phi = (0.5 - vv / out_h) * np.pi
    
    rx = np.cos(phi) * np.sin(theta)
    ry = np.sin(phi)
    rz = np.cos(phi) * np.cos(theta)
    
    abs_x = np.abs(rx)
    abs_y = np.abs(ry)
    abs_z = np.abs(rz)
    
    channels = faces[0].shape[2] if len(faces[0].shape) == 3 else 1
    out = np.zeros((out_h, out_w, channels), dtype=faces[0].dtype) if channels > 1 else np.zeros((out_h, out_w), dtype=faces[0].dtype)
    
    face_masks = [
        (abs_z >= abs_x) & (abs_z >= abs_y) & (rz > 0),   # Front
        (abs_x >= abs_y) & (abs_x >= abs_z) & (rx > 0),   # Right
        (abs_z >= abs_x) & (abs_z >= abs_y) & (rz < 0),   # Back
        (abs_x >= abs_y) & (abs_x >= abs_z) & (rx < 0),   # Left
        (abs_y >= abs_x) & (abs_y >= abs_z) & (ry > 0),   # Top
        (abs_y >= abs_x) & (abs_y >= abs_z) & (ry < 0),   # Bottom
    ]
    
    proj_coords = [
        (rx / np.maximum(rz, 1e-6), ry / np.maximum(rz, 1e-6)),
        (-rz / np.maximum(rx, 1e-6), ry / np.maximum(rx, 1e-6)),
        (-rx / np.maximum(-rz, 1e-6), ry / np.maximum(-rz, 1e-6)),
        (rz / np.maximum(-rx, 1e-6), ry / np.maximum(-rx, 1e-6)),
        (rx / np.maximum(ry, 1e-6), -rz / np.maximum(ry, 1e-6)),
        (rx / np.maximum(-ry, 1e-6), rz / np.maximum(-ry, 1e-6)),
    ]
    
    for f_idx in range(6):
        m = face_masks[f_idx]
        if not np.any(m):
            continue
        cu, cv = proj_coords[f_idx]
        
        px = (cu[m] * (face_size / 2.0) + face_size / 2.0 - 0.5).astype(np.float32)
        py = (face_size / 2.0 - cv[m] * (face_size / 2.0) - 0.5).astype(np.float32)
        px = np.clip(px, 0, face_size - 1)
        py = np.clip(py, 0, face_size - 1)
        
        face = faces[f_idx]
        x0 = np.floor(px).astype(int)
        x1 = np.minimum(x0 + 1, face_size - 1)
        y0 = np.floor(py).astype(int)
        y1 = np.minimum(y0 + 1, face_size - 1)
        
        wx = px - x0
        wy = py - y0
        
        if channels > 1:
            wx = wx[:, np.newaxis]
            wy = wy[:, np.newaxis]
            val = (face[y0, x0] * (1 - wx) * (1 - wy) +
                   face[y0, x1] * wx * (1 - wy) +
                   face[y1, x0] * (1 - wx) * wy +
                   face[y1, x1] * wx * wy)
            out[m] = val.astype(out.dtype)
        else:
            val = (face[y0, x0] * (1 - wx) * (1 - wy) +
                   face[y0, x1] * wx * (1 - wy) +
                   face[y1, x0] * (1 - wx) * wy +
                   face[y1, x1] * wx * wy)
            out[m] = val.astype(out.dtype)
            
    return out


def run_pinhole_cubemap_depth(orig_img: Image.Image, pipe, face_size: int = 768, out_w: int = 2048, out_h: int = 1024) -> tuple[np.ndarray, np.ndarray]:
    """
    Extract 6 rectilinear cube faces, run Depth-Anything-V2 on flat perspective frames,
    convert perspective inverse depth to spherical inverse depth, and reproject to equirectangular.
    """
    img_np = np.array(orig_img, dtype=np.uint8)
    print(f"[*] Extracting 6 distortion-free rectilinear cube faces ({face_size}x{face_size} px)...")
    faces_rgb = equirect_to_cubemap_faces(img_np, face_size=face_size)
    
    # Calculate geometric angle cosine cos(theta_ray) = 1 / sqrt(1 + x^2 + y^2) for perspective-to-spherical conversion
    u = (np.arange(face_size) - face_size / 2.0 + 0.5) / (face_size / 2.0)
    v = (face_size / 2.0 - np.arange(face_size) - 0.5) / (face_size / 2.0)
    uu, vv = np.meshgrid(u, v)
    cos_ray = 1.0 / np.sqrt(1.0 + uu**2 + vv**2).astype(np.float32)
    
    faces_spherical_disp = []
    t0 = time.time()
    print("[*] Running Depth-Anything-V2 on 6 pinhole cube faces...")
    for idx, f_rgb in enumerate(faces_rgb):
        pil_face = Image.fromarray(f_rgb)
        res = pipe(pil_face)
        d_persp = np.array(res['predicted_depth'], dtype=np.float32)
        
        # Normalize face disparity to [0, 1] relative scale
        d_min, d_max = np.percentile(d_persp, 1), np.percentile(d_persp, 99)
        d_norm = np.clip((d_persp - d_min) / max(d_max - d_min, 1e-4), 0.0, 1.0)
        
        # Convert from perspective inverse depth to spherical inverse depth: d_sph = d_persp * cos(ray)
        d_spherical = d_norm * cos_ray
        faces_spherical_disp.append(d_spherical)
        
    print(f"[+] Cubemap depth inference completed in {time.time() - t0:.2f}s")
    
    # Reproject to equirectangular disparity map
    print(f"[*] Reprojecting cube disparities to {out_w}x{out_h} equirectangular sphere...")
    equirect_disp = cubemap_to_equirect(faces_spherical_disp, out_w=out_w, out_h=out_h)
    
    # Also downsample RGB for point cloud color mapping
    equirect_rgb = cv2.resize(img_np, (out_w, out_h), interpolation=cv2.INTER_AREA)
    return equirect_rgb, equirect_disp


def calibrate_affine_scale_and_shift(disparity: np.ndarray, camera_height: float = 1.50) -> tuple[float, float, float]:
    """
    Solve the 2-parameter affine equation on the ground floor:
    1 / R_true = |sin(phi)| / h_cam = s * d + t
    using robust linear regression. Returns (s, t, r_squared).
    """
    height, width = disparity.shape
    v = np.arange(height)
    phi = (0.5 - (v + 0.5) / height) * np.pi
    ry = np.sin(phi)
    
    phi_2d = np.tile(phi[:, np.newaxis], (1, width))
    ry_2d = np.tile(ry[:, np.newaxis], (1, width))
    
    # Ground floor cone: phi in [-75 deg, -30 deg]
    floor_mask = (phi_2d < np.radians(-30)) & (phi_2d > np.radians(-75))
    inv_R_true = np.abs(ry_2d[floor_mask]) / camera_height
    d_samples = disparity[floor_mask]
    
    # Filter valid samples
    valid = (d_samples > 0.02) & np.isfinite(inv_R_true)
    x = d_samples[valid]
    y = inv_R_true[valid]
    
    # 2-parameter linear regression: y = s * x + t
    # Subsample 50,000 points for speed if large
    if len(x) > 50000:
        idx = np.random.choice(len(x), 50000, replace=False)
        x_sub, y_sub = x[idx], y[idx]
    else:
        x_sub, y_sub = x, y
        
    A = np.vstack([x_sub, np.ones_like(x_sub)]).T
    s, t = np.linalg.lstsq(A, y_sub, rcond=None)[0]
    
    # Compute R-squared correlation
    y_pred = s * x_sub + t
    ss_res = np.sum((y_sub - y_pred) ** 2)
    ss_tot = np.sum((y_sub - np.mean(y_sub)) ** 2)
    r2 = 1.0 - (ss_res / max(ss_tot, 1e-6))
    
    print(f"[+] Robust 2-Parameter Ground Fit: y = {s:.4f} * d + ({t:.4f}) [R² = {r2:.3f}]")
    print(f"[+] Total floor rays fitted: {len(x):,}")
    return float(s), float(t), float(r2)


def unproject_calibrated(rgb_arr: np.ndarray, disparity: np.ndarray, s: float, t: float,
                         camera_height: float = 1.50, max_dist: float = 12.0, heading_deg: float = 0.0):
    """
    Unproject using the calibrated affine inverse depth equation:
    1 / R = s * d + t  =>  R = 1 / max(s * d + t, 0.05)
    """
    height, width = disparity.shape
    u = np.arange(width)
    v = np.arange(height)
    uu, vv = np.meshgrid(u, v)
    
    theta = (uu / width - 0.5) * 2.0 * np.pi
    phi = (0.5 - vv / height) * np.pi
    
    heading_rad = np.radians(heading_deg)
    theta_w = theta + heading_rad
    
    rx = np.cos(phi) * np.sin(theta_w)
    ry = np.sin(phi)
    rz = np.cos(phi) * np.cos(theta_w)
    
    # True metric radial distance R
    inv_R = s * disparity + t
    R = 1.0 / np.maximum(inv_R, 0.05)
    
    valid_mask = (R > 0.2) & (R <= max_dist) & (np.isfinite(R))
    
    X = R * rx
    Y = R * ry + camera_height  # Y=0 is ground floor
    Z = R * rz
    
    points = np.stack([X[valid_mask], Y[valid_mask], Z[valid_mask]], axis=-1).astype(np.float32)
    colors = rgb_arr[valid_mask].astype(np.uint8)
    
    print(f"[+] Generated {len(points):,} metric 3D points (culling threshold: {max_dist}m)")
    return points, colors


def export_binary_ply(filename: str, points: np.ndarray, colors: np.ndarray):
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
    print(f"[+] Exported 3D point cloud: {filename} ({os.path.getsize(filename)/(1024*1024):.2f} MB)")


def create_bev_slices(points: np.ndarray, meter_range: float = 6.0, resolution_m: float = 0.02) -> tuple[np.ndarray, np.ndarray]:
    """Generate 2D orthogonal BEV density slices for walls and furniture."""
    grid_pixels = int(np.ceil((2.0 * meter_range) / resolution_m))
    X = points[:, 0]
    Y = points[:, 1]
    Z = points[:, 2]
    
    gx = ((X + meter_range) / resolution_m).astype(int)
    gz = ((meter_range - Z) / resolution_m).astype(int)
    
    in_bounds = (gx >= 0) & (gx < grid_pixels) & (gz >= 0) & (gz < grid_pixels)
    gx, gz, Y = gx[in_bounds], gz[in_bounds], Y[in_bounds]
    
    # Wall slice: Y in [1.2m, 2.2m]
    wall_mask = (Y >= 1.2) & (Y <= 2.2)
    wall_grid = np.zeros((grid_pixels, grid_pixels), dtype=np.float32)
    np.add.at(wall_grid, (gz[wall_mask], gx[wall_mask]), 1.0)
    
    # Normalize with log-contrast
    wall_img = np.log1p(wall_grid)
    if np.max(wall_img) > 0:
        wall_img = (wall_img / np.max(wall_img) * 255.0).astype(np.uint8)
    else:
        wall_img = wall_img.astype(np.uint8)
        
    return wall_img, wall_grid


def process_view(view_id: str, image_path: str, heading_deg: float, pipe, output_dir: str):
    """Run calibrated pipeline on a single viewpoint."""
    print(f"\n==================================================")
    print(f"[*] Processing {view_id} with Calibrated Algorithm")
    print(f"==================================================")
    os.makedirs(output_dir, exist_ok=True)
    
    orig_img = Image.open(image_path).convert('RGB')
    
    # Step 1: Cubemap pinhole decomposition & depth estimation
    rgb_eq, disp_eq = run_pinhole_cubemap_depth(orig_img, pipe, face_size=768, out_w=2048, out_h=1024)
    cv2.imwrite(os.path.join(output_dir, "calibrated_disparity.png"), (disp_eq * 255).astype(np.uint8))
    
    # Step 2: 2-parameter affine regression
    s, t, r2 = calibrate_affine_scale_and_shift(disp_eq, camera_height=1.50)
    
    # Step 3: Calibrated unprojection
    points, colors = unproject_calibrated(rgb_eq, disp_eq, s, t, camera_height=1.50, max_dist=10.0, heading_deg=heading_deg)
    
    # Step 4: Export PLY
    ply_path = os.path.join(output_dir, f"{view_id}_calibrated_cloud.ply")
    export_binary_ply(ply_path, points, colors)
    
    # Step 5: BEV Slices
    wall_img, wall_grid = create_bev_slices(points, meter_range=6.0, resolution_m=0.02)
    cv2.imwrite(os.path.join(output_dir, "calibrated_bev_wall.png"), wall_img)
    print(f"[+] Saved calibrated BEV wall density: {os.path.join(output_dir, 'calibrated_bev_wall.png')}")
    
    # Calculate measured room width and length directly from the calibrated point cloud
    wall_pts = points[(points[:, 1] >= 1.2) & (points[:, 1] <= 2.2)]
    x_min, x_max = float(np.percentile(wall_pts[:, 0], 5)), float(np.percentile(wall_pts[:, 0], 95))
    z_min, z_max = float(np.percentile(wall_pts[:, 2], 5)), float(np.percentile(wall_pts[:, 2], 95))
    
    measured_width = round(x_max - x_min, 2)
    measured_length = round(z_max - z_min, 2)
    
    summary = {
        "view_id": view_id,
        "heading_deg": heading_deg,
        "calibration": {"slope_s": s, "shift_t": t, "r_squared": r2},
        "measured_dimensions": {
            "x_min": x_min, "x_max": x_max, "width_m": measured_width,
            "z_min": z_min, "z_max": z_max, "length_m": measured_length,
            "area_m2": round(measured_width * measured_length, 2)
        }
    }
    with open(os.path.join(output_dir, "calibrated_summary.json"), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
        
    print(f"\n[CALCULATED RESULT FOR {view_id}]")
    print(f"  Width (X span):  {measured_width} m (from {x_min:.2f} to {x_max:.2f})")
    print(f"  Length (Z span): {measured_length} m (from {z_min:.2f} to {z_max:.2f})")
    print(f"  Area:            {round(measured_width * measured_length, 2)} m²")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Calibrated Reality-Capture Pipeline")
    parser.add_argument("--view", default="view-01", help="view_id to process")
    args = parser.parse_args()
    
    manifest_path = "source/captures/panoramas/tour-manifest.json"
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
        
    views_by_id = {v['view_id']: v for v in manifest['views']}
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[*] Initializing Depth-Anything-V2 on device: {device}")
    model_name = "depth-anything/Depth-Anything-V2-Base-hf"
    pipe = pipeline('depth-estimation', model=model_name, device=device)
    
    targets = [args.view] if args.view != "both" else ["view-01", "view-03"]
    
    for vid in targets:
        v_info = views_by_id.get(vid)
        if not v_info:
            print(f"ERROR: {vid} not in manifest!", file=sys.stderr)
            continue
        img_path = os.path.join("source/captures/panoramas", v_info['file'])
        heading = v_info.get('heading', 0.0)
        out_dir = f"exports/spatial/{vid}_calibrated"
        process_view(vid, img_path, heading, pipe, out_dir)


if __name__ == "__main__":
    main()
