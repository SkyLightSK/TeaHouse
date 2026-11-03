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


# --- Calibration quality gates -------------------------------------------------
# Minimum Pearson correlation between disparity and true inverse ground range.
# Physically this must be strongly positive; anything near or below zero means the
# disparity convention is wrong and no honest scale can be recovered.
MIN_GROUND_CORRELATION = 0.30
# RANSAC inlier band on 1/R (metres^-1) and iteration budget.
RANSAC_INLIER_M = 0.03
RANSAC_ITERS = 400
# Views below this R-squared are emitted but flagged unreliable rather than published
# as measurements.
MIN_ACCEPTABLE_R2 = 0.60
# Largest believable radial range for these interiors, expressed in CAMERA HEIGHTS
# rather than metres. 1/t scales inversely with the assumed camera height, so an
# absolute metre threshold would reject or accept a view based on the scale assumption
# rather than on its geometry: at 1.50 m view-01 fits 11.9 m and passes, and at 1.12 m
# the identical fit becomes 13.3 m and fails. A scale-free multiple keeps the gate
# testing the same thing whatever height is assumed. 8.0 reproduces the original 12 m
# at the original 1.50 m.
MAX_RANGE_IN_CAMERA_HEIGHTS = 8.0
# Capture rig height. This single number sets the ABSOLUTE scale of every dimension
# this pipeline produces, so it is stated once, here, with its evidence.
#
# 1.50 m was an unverified assumption, and two independent lines of evidence now say it
# is ~25% too high, which matches this pipeline's ~20-25% over-scale exactly:
#   * the ceiling probe in this pipeline reads 3.42 m where the project estimates
#     2.70 m, implying a true rig height of 1.50 / 1.267 = 1.18 m;
#   * the stereo pipeline's scale-free shape ratio (camera_height / room_height =
#     0.389, which assumes no reference at all) implies 1.05 m in a 2.70 m room.
#
# Both land at ~1.0-1.2 m, consistent with a chest-height handheld 360 rig. The default
# below is the midpoint. It remains an ESTIMATE, not a measurement - override it with
# --camera-height once the real value is known.
DEFAULT_CAMERA_HEIGHT_M = 1.12


class CalibrationError(RuntimeError):
    """Raised when a view cannot be honestly calibrated; the view is skipped, not guessed."""



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
    raw_faces = []
    for idx, f_rgb in enumerate(faces_rgb):
        pil_face = Image.fromarray(f_rgb)
        res = pipe(pil_face)
        raw_faces.append(np.array(res['predicted_depth'], dtype=np.float32))

    # Depth-Anything-V2 emits RELATIVE INVERSE DEPTH (disparity): near surfaces read HIGH.
    # Verify that per panorama rather than assuming it. The bottom cube face (index 5,
    # nadir) sees the closest floor, so its centre must out-read the horizon band of the
    # side faces. If it does not, the head emitted depth and we invert once here, before
    # anything downstream consumes it.
    nadir = raw_faces[5]
    c0, c1 = int(face_size * 0.4), int(face_size * 0.6)
    nadir_centre = float(np.median(nadir[c0:c1, c0:c1]))
    side_horizon = float(np.median(np.concatenate([
        raw_faces[f][c0:c1, :].ravel() for f in (0, 1, 2, 3)
    ])))
    if nadir_centre <= side_horizon:
        print(f"[!] Model emitted DEPTH (nadir {nadir_centre:.3f} <= horizon {side_horizon:.3f}); inverting to disparity.")
        raw_faces = [-f for f in raw_faces]
    else:
        print(f"[+] Model emitted DISPARITY (nadir {nadir_centre:.3f} > horizon {side_horizon:.3f}).")

    # Normalize ONCE across all 6 faces on a shared scale. Per-face normalization (the
    # previous behaviour) rescaled every face to its own [0,1] range, so a face staring
    # at a near wall and a face down a long corridor both spanned 0..1. That destroys
    # cross-face comparability and leaves no single global (s, t) that can fit the sphere.
    stacked = np.concatenate([f.ravel() for f in raw_faces])
    d_min, d_max = np.percentile(stacked, 1), np.percentile(stacked, 99)
    scale = max(float(d_max - d_min), 1e-4)
    print(f"[+] Shared cross-face disparity normalization: p1={d_min:.4f} p99={d_max:.4f}")

    for d_persp in raw_faces:
        d_norm = np.clip((d_persp - d_min) / scale, 0.0, 1.0)
        # Perspective disparity -> spherical (radial) disparity.
        # R = z / cos_ray, so 1/R = (1/z) * cos_ray, i.e. disp_sph = disp_persp * cos_ray.
        d_spherical = d_norm * cos_ray
        faces_spherical_disp.append(d_spherical)
        
    print(f"[+] Cubemap depth inference completed in {time.time() - t0:.2f}s")
    
    # Reproject to equirectangular disparity map
    print(f"[*] Reprojecting cube disparities to {out_w}x{out_h} equirectangular sphere...")
    equirect_disp = cubemap_to_equirect(faces_spherical_disp, out_w=out_w, out_h=out_h)
    
    # Also downsample RGB for point cloud color mapping
    equirect_rgb = cv2.resize(img_np, (out_w, out_h), interpolation=cv2.INTER_AREA)
    return equirect_rgb, equirect_disp


def calibrate_affine_scale_and_shift(disparity: np.ndarray, camera_height: float = DEFAULT_CAMERA_HEIGHT_M) -> tuple[float, float, float]:
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
    
    # Ground floor cone: phi in [-75 deg, -30 deg].
    # Excludes the nadir (tripod/photographer feet occlude it) and the horizon, where
    # |sin(phi)| -> 0 makes R_true asymptotically sensitive to pixel noise.
    floor_mask = (phi_2d < np.radians(-30)) & (phi_2d > np.radians(-75))
    inv_R_true = np.abs(ry_2d[floor_mask]) / camera_height
    d_samples = disparity[floor_mask]
    
    # Filter valid samples
    valid = (d_samples > 0.02) & np.isfinite(inv_R_true)
    x = d_samples[valid]
    y = inv_R_true[valid]

    if len(x) < 1000:
        raise CalibrationError(f"only {len(x)} usable floor rays; need >= 1000")

    # Subsample for speed
    rng = np.random.default_rng(12345)
    if len(x) > 50000:
        idx = rng.choice(len(x), 50000, replace=False)
        x_sub, y_sub = x[idx], y[idx]
    else:
        x_sub, y_sub = x, y

    # Physical sign check BEFORE fitting. Disparity is inverse depth: the steep-down
    # floor rays (phi -> -75 deg) are the CLOSEST floor, so they carry both the highest
    # 1/R_true and the highest disparity. Correlation must therefore be positive.
    # A negative correlation means the disparity map is inverted (depth, not disparity)
    # or the floor cone is dominated by furniture rather than floor. Fitting anyway is
    # what produced the s < 0 values in the original run: a clean fit of a model that
    # maps near pixels to far distances.
    corr = float(np.corrcoef(x_sub, y_sub)[0, 1])
    if not np.isfinite(corr) or corr < MIN_GROUND_CORRELATION:
        raise CalibrationError(
            f"ground-ray correlation {corr:+.3f} < {MIN_GROUND_CORRELATION:+.2f}; "
            "disparity map is inverted or the floor cone is occluded. Refusing to fit."
        )

    # RANSAC: the floor cone contains furniture legs, rugs and table tops that are not
    # the ground plane. Plain least squares (the original behaviour) lets those outliers
    # drag the line. Consensus on an inlier band recovers the true floor.
    best_inliers, best_s, best_t = None, None, None
    n = len(x_sub)
    for _ in range(RANSAC_ITERS):
        i, j = rng.choice(n, 2, replace=False)
        if abs(x_sub[i] - x_sub[j]) < 1e-3:
            continue
        s_c = (y_sub[i] - y_sub[j]) / (x_sub[i] - x_sub[j])
        t_c = y_sub[i] - s_c * x_sub[i]
        if s_c <= 0 or t_c < 0:          # enforce physics: near => nearer
            continue
        resid = np.abs(y_sub - (s_c * x_sub + t_c))
        inliers = resid < RANSAC_INLIER_M
        if best_inliers is None or inliers.sum() > best_inliers.sum():
            best_inliers, best_s, best_t = inliers, s_c, t_c

    if best_inliers is None or best_inliers.sum() < 0.20 * n:
        raise CalibrationError("RANSAC found no physically valid ground consensus (s > 0, t >= 0)")

    # Refit least squares on the inlier set only
    xi, yi = x_sub[best_inliers], y_sub[best_inliers]
    A = np.vstack([xi, np.ones_like(xi)]).T
    s, t = np.linalg.lstsq(A, yi, rcond=None)[0]

    if s <= 0:
        raise CalibrationError(f"refit slope s={s:.4f} <= 0; model inverted")

    # The refit can land outside the physical region even when the RANSAC sample was
    # inside it, so re-check here rather than trusting the sampling constraint.
    # t is the inverse distance at zero disparity, i.e. the far-field asymptote:
    #   t <= 0  => infinite or negative range at the horizon
    #   t small => R_max = 1/t explodes past any real room, and the point cloud extent
    #              is then set by the max_dist cull rather than by walls.
    # This is precisely the asymptotic divergence the original commit claimed to fix;
    # it survives a high R-squared because the floor cone constrains the NEAR field only.
    if t <= 0:
        raise CalibrationError(
            f"refit shift t={t:.4f} <= 0; implies infinite/negative far-field range"
        )
    r_max = 1.0 / t
    max_range = MAX_RANGE_IN_CAMERA_HEIGHTS * camera_height
    if r_max > max_range:
        raise CalibrationError(
            f"far-field range 1/t = {r_max:.1f} m exceeds {max_range:.1f} m "
            f"({MAX_RANGE_IN_CAMERA_HEIGHTS:.0f} camera heights); extent would be set "
            "by the distance cull, not by walls"
        )

    # R-squared on the inlier set
    y_pred = s * xi + t
    ss_res = np.sum((yi - y_pred) ** 2)
    ss_tot = np.sum((yi - np.mean(yi)) ** 2)
    r2 = 1.0 - (ss_res / max(ss_tot, 1e-6))

    inlier_frac = best_inliers.sum() / n
    print(f"[+] RANSAC Ground Fit: y = {s:.4f} * d + ({t:.4f}) [R² = {r2:.3f}, corr = {corr:+.3f}]")
    print(f"[+] Floor rays: {len(x):,} total, {int(best_inliers.sum()):,} inliers ({inlier_frac:.0%})")
    if r2 < MIN_ACCEPTABLE_R2:
        print(f"[!] WARNING: R² {r2:.3f} < {MIN_ACCEPTABLE_R2}; treat this view's scale as UNRELIABLE.")
    return float(s), float(t), float(r2)


def unproject_calibrated(rgb_arr: np.ndarray, disparity: np.ndarray, s: float, t: float,
                         camera_height: float = DEFAULT_CAMERA_HEIGHT_M, max_dist: float = 12.0, heading_deg: float = 0.0):
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


def process_view(view_id: str, image_path: str, heading_deg: float, pipe, output_dir: str,
                 camera_height: float = DEFAULT_CAMERA_HEIGHT_M):
    """Run calibrated pipeline on a single viewpoint."""
    print(f"\n==================================================")
    print(f"[*] Processing {view_id} with Calibrated Algorithm")
    print(f"==================================================")
    os.makedirs(output_dir, exist_ok=True)
    
    orig_img = Image.open(image_path).convert('RGB')
    
    # Step 1: Cubemap pinhole decomposition & depth estimation
    rgb_eq, disp_eq = run_pinhole_cubemap_depth(orig_img, pipe, face_size=768, out_w=2048, out_h=1024)
    cv2.imwrite(os.path.join(output_dir, "calibrated_disparity.png"), (disp_eq * 255).astype(np.uint8))
    
    # Step 2: 2-parameter affine regression.
    # A view that cannot be honestly calibrated is SKIPPED, not back-filled with a guess.
    try:
        s, t, r2 = calibrate_affine_scale_and_shift(disp_eq, camera_height=camera_height)
    except CalibrationError as exc:
        print(f"[!] {view_id}: calibration FAILED - {exc}")
        summary = {
            "view_id": view_id,
            "heading_deg": heading_deg,
            "status": "failed",
            "reason": str(exc),
            "calibration": None,
            "measured_dimensions": None,
        }
        with open(os.path.join(output_dir, "calibrated_summary.json"), 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        return summary
    
    # Step 3: Calibrated unprojection
    points, colors = unproject_calibrated(rgb_eq, disp_eq, s, t, camera_height=camera_height, max_dist=10.0, heading_deg=heading_deg)
    
    # Step 4: Export PLY
    ply_path = os.path.join(output_dir, f"{view_id}_calibrated_cloud.ply")
    export_binary_ply(ply_path, points, colors)
    
    # Step 5: BEV Slices
    wall_img, wall_grid = create_bev_slices(points, meter_range=6.0, resolution_m=0.02)
    cv2.imwrite(os.path.join(output_dir, "calibrated_bev_wall.png"), wall_img)
    print(f"[+] Saved calibrated BEV wall density: {os.path.join(output_dir, 'calibrated_bev_wall.png')}")
    
    # Calculate measured room width and length directly from the calibrated point cloud.
    # Use the 1/99 percentile, not 5/95: the walls ARE the extremes of the distribution,
    # so a 5/95 clip discards the very geometry being measured and shrinks every room by
    # roughly a tenth of its span before any other error is counted.
    wall_pts = points[(points[:, 1] >= 1.2) & (points[:, 1] <= 2.2)]
    if len(wall_pts) < 500:
        x_min = x_max = z_min = z_max = float('nan')
    else:
        x_min, x_max = float(np.percentile(wall_pts[:, 0], 1)), float(np.percentile(wall_pts[:, 0], 99))
        z_min, z_max = float(np.percentile(wall_pts[:, 2], 1)), float(np.percentile(wall_pts[:, 2], 99))
    
    measured_width = round(x_max - x_min, 2)
    measured_length = round(z_max - z_min, 2)

    # Independent scale probe: the ceiling plane. Absolute scale rests entirely on the
    # ASSUMED camera height, so a ceiling that disagrees with the building's known storey
    # height is the cheapest available evidence that the assumption is off. We record it;
    # we do NOT rescale by it, because the expected ceiling height is itself an estimate
    # and folding one guess into another would launder it into a measurement.
    ceiling_m = float(np.percentile(points[:, 1], 99.0)) if len(points) else float('nan')

    # A single panorama sees only what is in line of sight from one tripod position.
    # Occluded corners and surfaces behind furniture are NOT measured, so this span is a
    # lower bound on the room, never the authoritative room dimension.
    reliable = bool(r2 >= MIN_ACCEPTABLE_R2) and np.isfinite(measured_width)

    summary = {
        "view_id": view_id,
        "heading_deg": heading_deg,
        "status": "ok" if reliable else "low_confidence",
        "calibration": {
            "slope_s": s, "shift_t": t, "r_squared": r2,
            "camera_height_m": camera_height,
            "camera_height_assumed": True,
            "camera_height_source": (
                "estimate reconciled from the ceiling probe and the stereo scale-free "
                "shape ratio; see DEFAULT_CAMERA_HEIGHT_M"
            ),
            "ceiling_probe_m": round(ceiling_m, 2),
            "ceiling_probe_note": (
                "Observed ceiling height at this assumed camera height. If it disagrees "
                "with the real storey height, every dimension is off by the same ratio."
            ),
        },
        "measured_dimensions": {
            "x_min": x_min, "x_max": x_max, "width_m": measured_width,
            "z_min": z_min, "z_max": z_max, "length_m": measured_length,
            "area_m2": round(measured_width * measured_length, 2),
            "is_lower_bound": True,
            "note": "Single-viewpoint line-of-sight span; occluded extents not captured.",
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
    parser.add_argument("--all", action="store_true", help="process every view in the manifest")
    parser.add_argument("--camera-height", type=float, default=DEFAULT_CAMERA_HEIGHT_M,
                        help=f"capture rig height in metres (default {DEFAULT_CAMERA_HEIGHT_M}); "
                             "sets absolute scale for every output")
    args = parser.parse_args()
    
    manifest_path = "source/captures/panoramas/tour-manifest.json"
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
        
    views_by_id = {v['view_id']: v for v in manifest['views']}
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[*] Initializing Depth-Anything-V2 on device: {device}")
    model_name = "depth-anything/Depth-Anything-V2-Base-hf"
    pipe = pipeline('depth-estimation', model=model_name, device=device)
    
    if args.all:
        targets = [v["view_id"] for v in manifest["views"]]
    elif args.view == "both":
        targets = ["view-01", "view-03"]
    else:
        targets = [args.view]
    
    for vid in targets:
        v_info = views_by_id.get(vid)
        if not v_info:
            print(f"ERROR: {vid} not in manifest!", file=sys.stderr)
            continue
        img_path = os.path.join("source/captures/panoramas", v_info['file'])
        heading = v_info.get('heading', 0.0)
        out_dir = f"exports/spatial/{vid}_calibrated"
        process_view(vid, img_path, heading, pipe, out_dir, camera_height=args.camera_height)


if __name__ == "__main__":
    main()
