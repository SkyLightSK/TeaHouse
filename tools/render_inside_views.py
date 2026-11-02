#!/usr/bin/env python3
"""
tools/render_inside_views.py

Renders realistic, perspective camera views from INSIDE the 3D point clouds.
Simulates a human or tripod observer standing inside the room looking around.
"""

import os
import sys
import time
import numpy as np
import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tools.align_multi_bev import read_ply

def render_pinhole(pts, cols, cam_pos, target_pos, fov_deg=80.0, width=1280, height=720, point_radius=2):
    """Render a perspective image from a 3D point cloud using painter's algorithm."""
    cam_pos = np.array(cam_pos, dtype=np.float32)
    target_pos = np.array(target_pos, dtype=np.float32)
    
    forward = target_pos - cam_pos
    dist = np.linalg.norm(forward)
    if dist < 1e-4:
        forward = np.array([0, 0, 1], dtype=np.float32)
    else:
        forward = forward / dist
        
    up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    right = np.cross(forward, up)
    norm_r = np.linalg.norm(right)
    if norm_r < 1e-4:
        right = np.array([1, 0, 0], dtype=np.float32)
    else:
        right = right / norm_r
    true_up = np.cross(right, forward)
    
    R = np.stack([right, true_up, forward], axis=0) # (3, 3)
    
    # Transform to camera coordinates
    P_c = (pts - cam_pos) @ R.T
    
    # Perspective projection
    f = (width / 2.0) / np.tan(np.radians(fov_deg / 2.0))
    z_c = P_c[:, 2]
    valid = z_c > 0.2
    
    P_c = P_c[valid]
    cols_v = cols[valid]
    z_c = z_c[valid]
    
    u = (f * P_c[:, 0] / z_c + width / 2.0).astype(int)
    v = (height / 2.0 - f * P_c[:, 1] / z_c).astype(int)
    
    in_screen = (u >= 0) & (u < width) & (v >= 0) & (v < height)
    u = u[in_screen]
    v = v[in_screen]
    z_c = z_c[in_screen]
    cols_v = cols_v[in_screen]
    
    # Sort far-to-near (painter's algorithm)
    order = np.argsort(-z_c)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:, :] = [15, 23, 42] # deep slate background
    
    u_sorted = u[order]
    v_sorted = v[order]
    cols_sorted = cols_v[order]
    
    # Draw points in BGR for cv2
    bgr_cols = np.stack([cols_sorted[:, 2], cols_sorted[:, 1], cols_sorted[:, 0]], axis=-1)
    
    for i in range(len(u_sorted)):
        cv2.circle(canvas, (int(u_sorted[i]), int(v_sorted[i])), point_radius, 
                   (int(bgr_cols[i, 0]), int(bgr_cols[i, 1]), int(bgr_cols[i, 2])), -1)
                   
    return canvas


def main():
    out_dir = "exports/spatial/renders"
    os.makedirs(out_dir, exist_ok=True)
    
    # 1. Load View-01 (Tearoom)
    print("[*] Loading View-01 point cloud...")
    v1_pts, v1_cols = read_ply("exports/spatial/view-01/view-01_metric_cloud.ply")
    
    # Views from inside Tearoom (camera at Y=1.5m, eye level)
    inside_views_v1 = [
        {
            "name": "tearoom_look_east_screen.png",
            "title": "Tearoom: Looking East at Carved Screen & Sofa",
            "cam": [0.0, 1.5, 0.0],
            "target": [3.6, 1.4, 0.2],
            "fov": 85.0
        },
        {
            "name": "tearoom_look_west_doorway.png",
            "title": "Tearoom: Looking West through Doorway to Tea Bar",
            "cam": [0.0, 1.5, 0.0],
            "target": [-3.5, 1.5, 0.8],
            "fov": 85.0
        },
        {
            "name": "tearoom_look_north_mirror.png",
            "title": "Tearoom: Looking North at Seating & Mirror Wall",
            "cam": [0.0, 1.5, 0.0],
            "target": [0.2, 1.5, 3.5],
            "fov": 85.0
        },
        {
            "name": "tearoom_dollhouse_cutaway.png",
            "title": "Tearoom: Elevated 3D Dollhouse Cutaway",
            "cam": [-3.5, 4.8, -3.5],
            "target": [0.5, 1.2, 0.5],
            "fov": 75.0
        }
    ]
    
    for v in inside_views_v1:
        img = render_pinhole(v1_pts, v1_cols, v["cam"], v["target"], fov_deg=v["fov"], width=1280, height=720, point_radius=2)
        # Add sleek architectural caption overlay
        cv2.putText(img, v["title"], (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(img, f"Observer: ({v['cam'][0]:.1f}m, {v['cam'][1]:.1f}m, {v['cam'][2]:.1f}m) | FOV: {v['fov']} deg", 
                    (30, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (56, 189, 248), 1, cv2.LINE_AA)
        p = os.path.join(out_dir, v["name"])
        cv2.imwrite(p, img)
        print(f"[+] Rendered {p}")
        
    # 2. Load Unified 2-Room Model (Tearoom + Tea Bar)
    print("\n[*] Loading Unified 2-Room point cloud...")
    uni_pts, uni_cols = read_ply("exports/spatial/unified_pilot/unified_rooms_cloud.ply")
    
    multi_room_views = [
        {
            "name": "unified_look_through_doorway.png",
            "title": "Walkthrough View: Tearoom through Doorway into Tea Bar",
            "cam": [1.0, 1.5, 0.0],
            "target": [-2.8, 1.4, 0.5],
            "fov": 90.0
        },
        {
            "name": "unified_inside_teabar.png",
            "title": "Inside Tea Bar: Counter & Circulation Corridor",
            "cam": [-2.8, 1.5, 0.3],
            "target": [-2.7, 1.4, 3.5],
            "fov": 90.0
        },
        {
            "name": "unified_dollhouse_cutaway.png",
            "title": "Unified Dollhouse: Tearoom + Tea Bar 3D Layout",
            "cam": [-1.0, 8.5, -6.5],
            "target": [-1.5, 1.0, 1.5],
            "fov": 70.0
        }
    ]
    
    for v in multi_room_views:
        img = render_pinhole(uni_pts, uni_cols, v["cam"], v["target"], fov_deg=v["fov"], width=1280, height=720, point_radius=2)
        cv2.putText(img, v["title"], (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(img, f"Observer: ({v['cam'][0]:.1f}m, {v['cam'][1]:.1f}m, {v['cam'][2]:.1f}m) | FOV: {v['fov']} deg", 
                    (30, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (16, 185, 129), 1, cv2.LINE_AA)
        p = os.path.join(out_dir, v["name"])
        cv2.imwrite(p, img)
        print(f"[+] Rendered {p}")

if __name__ == "__main__":
    main()
