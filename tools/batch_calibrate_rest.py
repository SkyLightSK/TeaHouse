import json
import os
import sys
import torch
from transformers import pipeline

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tools.pano_depth_calibrated import process_view

manifest_path = "source/captures/panoramas/tour-manifest.json"
manifest = json.load(open(manifest_path, 'r', encoding='utf-8'))
views_by_id = {v['view_id']: v for v in manifest['views']}

# Pick key representative viewpoints for each room:
# TB: view-02
# PV: view-05
# AS: view-06, view-08
# LC: view-11
# LB: view-14
# BK: view-16
# LH: view-22
sample_views = ["view-02", "view-05", "view-06", "view-11", "view-14", "view-16", "view-22"]

device = "cuda" if torch.cuda.is_available() else "cpu"
pipe = pipeline('depth-estimation', model="depth-anything/Depth-Anything-V2-Base-hf", device=device)

results = {}
for vid in sample_views:
    v = views_by_id[vid]
    img_p = os.path.join("source/captures/panoramas", v['file'])
    out_d = f"exports/spatial/{vid}_calibrated"
    res = process_view(vid, img_p, v.get('heading', 0.0), pipe, out_d)
    results[vid] = res

print("\n\n=======================================================")
print("=== CALIBRATION SUMMARY FOR ALL REPRESENTATIVE ROOMS ===")
print("=======================================================")
for vid, r in results.items():
    dim = r["measured_dimensions"]
    cal = r["calibration"]
    print(f"{vid:<10} | Width: {dim['width_m']:5.2f}m | Length: {dim['length_m']:5.2f}m | Area: {dim['area_m2']:6.2f}m² | (s={cal['slope_s']:.3f}, t={cal['shift_t']:.3f})")

