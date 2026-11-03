#!/usr/bin/env python3
"""
tools/fit_manhattan_blueprint.py

Architectural Manhattan Blueprint Fitter.
Converts multi-room reality-capture point clouds into clean, orthogonal,
closed-polygon architectural blueprints with uniform wall thickness,
parametric door openings, stair marks, and dimensional schedules.
"""

import os
import sys
import json
import argparse
import numpy as np
import ezdxf

def load_calibrated_boxes(spatial_dir, view_to_space, min_r2=0.60):
    """
    Collect per-view calibrated fits and group them by space code.

    Returns {space_code: {"box": {...}, "views": [...], "r_squared": float}} containing
    ONLY spaces backed by at least one reliable fit. Views that failed calibration, fell
    below min_r2, or carry no measured extent are ignored rather than averaged in.

    Note the resulting box is a union of single-viewpoint line-of-sight spans, so it is a
    LOWER BOUND on the room: surfaces occluded from every tripod position are not in it.
    """
    out = {}
    if not os.path.isdir(spatial_dir):
        return out
    grouped = {}
    for entry in sorted(os.listdir(spatial_dir)):
        if not entry.endswith("_calibrated"):
            continue
        path = os.path.join(spatial_dir, entry, "calibrated_summary.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                s = json.load(f)
        except (ValueError, OSError):
            continue
        if s.get("status") not in (None, "ok"):
            continue
        cal = s.get("calibration") or {}
        dims = s.get("measured_dimensions") or {}
        r2 = cal.get("r_squared")
        if r2 is None or r2 < min_r2:
            continue
        if not all(isinstance(dims.get(k), (int, float)) for k in ("x_min", "x_max", "z_min", "z_max")):
            continue
        code = view_to_space.get(s.get("view_id"))
        if not code:
            continue
        grouped.setdefault(code, []).append((s["view_id"], dims, float(r2)))

    for code, items in grouped.items():
        # Each view's cloud sits in its OWN tripod-centred frame (x, z ~ 0 at the camera).
        # Unioning raw bounds across views therefore overlays two local frames and
        # inflates the room - that bug produced an 11 m "entrance lobby". Until
        # align_multi_bev.py supplies validated world transforms, take the per-view
        # SPAN and keep the largest, which is the best-supported lower bound from a
        # single vantage point.
        spans = [(v, d["x_max"] - d["x_min"], d["z_max"] - d["z_min"], r) for v, d, r in items]
        best = max(spans, key=lambda s: s[1] * s[2])
        v_best, w, l, r_best = best

        # SATURATION. A single monocular viewpoint measures line of sight, and in a
        # cluttered interior that saturates around 4-5 m whatever the room actually is.
        # Measured across the 12 reliable views, spans have a coefficient of variation
        # of only ~21% while the real rooms differ by ~10x in area (LB ~4 m2 against
        # BK ~55 m2). The number below is therefore dominated by the depth model's
        # usable range, not by the walls, and it must not be presented as a room size.
        #
        # It is retained as a LOWER BOUND - the room is at least this big - which is the
        # strongest honest claim a single viewpoint supports.
        # Report in a local frame centred on the camera; absolute placement is the job
        # of registration, which has not been validated.
        out[code] = {
            "box": {"x": [round(-w / 2.0, 2), round(w / 2.0, 2)],
                    "z": [round(-l / 2.0, 2), round(l / 2.0, 2)]},
            "views": [v for v, _, _ in items],
            "driving_view": v_best,
            "r_squared": round(r_best, 3),
            "per_view_spans": [
                {"view": v, "width_m": round(ww, 2), "length_m": round(ll, 2)}
                for v, ww, ll, _ in spans
            ],
            "placement_validated": False,
            "range_saturated": True,
            "saturation_note": (
                "Single-viewpoint line-of-sight span, saturated by the depth model's "
                "usable range (~4-5 m) rather than by the walls. A LOWER BOUND on the "
                "room, not its size. Across all reliable views these spans vary by only "
                "~21% while the real rooms differ by ~10x in area."
            ),
        }
    return out


def build_architectural_model(spatial_dir="exports/spatial", manifest_path="source/captures/panoramas/tour-manifest.json"):
    """
    Fit orthogonal architectural walls and openings from measured viewpoint point clouds.
    """
    # Load manifest and space observations
    manifest = json.load(open(manifest_path, 'r', encoding='utf-8'))
    obs_path = "source/captures/panoramas/view-observations.json"
    obs = json.load(open(obs_path, 'r', encoding='utf-8')) if os.path.exists(obs_path) else []
    
    view_to_space = {o['view_id']: o['space_codes'][0] for o in obs}
    
    # Room metadata & definitions
    rooms_def = {
        "TR": {"name": "Tearoom", "floor_level": 0.0, "color": "#0284c7"},
        "TB": {"name": "Tea Bar", "floor_level": 0.0, "color": "#0ea5e9"},
        "PV": {"name": "Pre-Bar Vestibule", "floor_level": 0.0, "color": "#38bdf8"},
        "AS": {"name": "Accessories Shop", "floor_level": 0.15, "color": "#14b8a6"},
        "LC": {"name": "Lower Corridor", "floor_level": -0.30, "color": "#6366f1"},
        "LB": {"name": "Entrance Lobby", "floor_level": 0.0, "color": "#8b5cf6"},
        "ST": {"name": "Stair Passage", "floor_level": 0.50, "color": "#a855f7"},
        "BK": {"name": "Bookshop Hall", "floor_level": 0.0, "color": "#10b981"},
        "LH": {"name": "Lecture Hall Entrance", "floor_level": 0.0, "color": "#f59e0b"},
    }
    
    # ------------------------------------------------------------------
    # PROVENANCE WARNING - READ BEFORE TRUSTING ANY NUMBER BELOW.
    #
    # These boxes are HAND-ENTERED ESTIMATES. They are NOT outputs of the depth
    # pipeline. No calibrated point cloud has ever been fitted to produce them:
    # the pipeline writes per-view summaries to exports/spatial/<view>_calibrated/,
    # and nothing in this function reads those files.
    #
    # The comment previously here claimed these were "Calibrated via 6-face cubemap
    # perspective decomposition and 2-parameter (s, t) affine regression". That was
    # false, and it is how unmeasured guesses reached measured_room_schedule.json,
    # the DXF/SVG blueprints, the Blender venue and the dashboard - each step
    # presenting them with more authority than the last.
    #
    # Until load_calibrated_boxes() below finds enough reliable per-view fits, the
    # outputs of this module are a SKETCH, not a survey. They are emitted with
    # "provenance": "hand_estimate" so no downstream consumer can mistake them.
    # See docs/MEASUREMENT-STATUS.md.
    # ------------------------------------------------------------------
    # [x_min, x_max, z_min, z_max] in world meters
    estimated_boxes = {
        "TR": {"x": [-1.80, 2.00], "z": [-1.20, 4.20]},
        "TB": {"x": [-5.40, -1.80], "z": [-1.20, 4.20]},
        "PV": {"x": [-4.60, -1.80], "z": [4.20, 7.00]},
        "AS": {"x": [-4.20, 1.20], "z": [7.00, 12.60]},
        "LC": {"x": [-8.40, -4.20], "z": [10.40, 12.60]},
        "LB": {"x": [-12.20, -8.40], "z": [10.40, 13.80]},
        "ST": {"x": [-12.20, -9.60], "z": [13.80, 16.60]},
        "BK": {"x": [-20.00, -12.20], "z": [9.80, 13.80]},
        "LH": {"x": [-24.80, -20.00], "z": [9.80, 14.00]},
    }
    
    # Door openings [room_a, room_b, (x1, z1), (x2, z2), label]
    doors = [
        {"from": "TR", "to": "TB", "line": [(-1.80, 0.60), (-1.80, 1.80)], "label": "D1 (Tearoom/Bar)"},
        {"from": "TB", "to": "PV", "line": [(-3.60, 4.20), (-2.40, 4.20)], "label": "D2 (Bar/Vestibule)"},
        {"from": "PV", "to": "AS", "line": [(-3.60, 7.00), (-2.40, 7.00)], "label": "D3 (Vestibule/Shop)"},
        {"from": "AS", "to": "LC", "line": [(-4.20, 10.80), (-4.20, 12.00)], "label": "D4 (Shop/Corridor - 3 Steps)", "stairs": 3},
        {"from": "LC", "to": "LB", "line": [(-8.40, 10.80), (-8.40, 12.00)], "label": "D5 (Corridor/Lobby - 2 Steps)", "stairs": 2},
        {"from": "LB", "to": "BK", "line": [(-12.20, 11.20), (-12.20, 12.40)], "label": "D6 (Lobby/Bookshop)"},
        {"from": "BK", "to": "LH", "line": [(-20.00, 11.20), (-20.00, 12.40)], "label": "D7 (Bookshop/Lecture Entry)"},
        {"from": "LB", "to": "ST", "line": [(-11.60, 13.80), (-10.40, 13.80)], "label": "D8 (Lobby/Street Stairs)", "stairs": 6},
        {"from": "ST", "to": "OUT", "line": [(-11.60, 16.60), (-10.40, 16.60)], "label": "D9 (Exterior Street Portal)"},
    ]
    
    # Prefer real calibrated measurements wherever the depth pipeline produced a
    # reliable fit; fall back to the hand estimates above, per room, and record which
    # was used. This is the seam that was missing: the pipeline's own output now has
    # a path into the blueprint instead of being computed and discarded.
    calibrated = load_calibrated_boxes(spatial_dir, view_to_space)
    boxes = {}
    provenance = {}
    for code, est in estimated_boxes.items():
        if code in calibrated:
            boxes[code] = calibrated[code]["box"]
            provenance[code] = {
                "source": "calibrated",
                "views": calibrated[code]["views"],
                "driving_view": calibrated[code]["driving_view"],
                "per_view_spans": calibrated[code]["per_view_spans"],
                "r_squared": calibrated[code]["r_squared"],
                "is_lower_bound": True,
                "placement_validated": False,
            }
        else:
            boxes[code] = est
            provenance[code] = {"source": "hand_estimate", "views": [], "r_squared": None}

    n_cal = sum(1 for v in provenance.values() if v["source"] == "calibrated")
    print(f"[i] Room boxes: {n_cal} calibrated, {len(boxes) - n_cal} hand-estimated")
    if n_cal == 0:
        print("[!] NO calibrated measurements available - every dimension below is an ESTIMATE.")

    # Compute room schedule
    room_schedule = []
    wall_thickness = 0.20 # 20cm walls
    
    for code, box in boxes.items():
        w = box['x'][1] - box['x'][0]
        l = box['z'][1] - box['z'][0]
        area = w * l
        info = rooms_def.get(code, {"name": code, "floor_level": 0.0})
        room_schedule.append({
            "code": code,
            "provenance": provenance.get(code, {"source": "hand_estimate"}),
            "name": info["name"],
            "floor_level_m": info["floor_level"],
            "width_m": round(w, 2),
            "length_m": round(l, 2),
            "area_m2": round(area, 2),
            "bounds": {
                "x_min": box['x'][0], "x_max": box['x'][1],
                "z_min": box['z'][0], "z_max": box['z'][1]
            }
        })
        
    return room_schedule, doors, wall_thickness


def export_clean_cad_dxf(output_path, room_schedule, doors, wall_thickness=0.20):
    """Export professional multi-layer CAD DXF blueprint."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # Architectural Layers
    doc.layers.add('A-WALL-INNR', color=7)      # White (Inner wall)
    doc.layers.add('A-WALL-OUTR', color=8)      # Gray (Outer wall 200mm)
    doc.layers.add('A-DOOR', color=3)           # Green (Doorways)
    doc.layers.add('A-ANNO-TEXT', color=2)      # Yellow (Labels)
    doc.layers.add('A-ANNO-DIMS', color=4)      # Cyan (Dimensions)
    doc.layers.add('A-FLOR-STRS', color=1)      # Red (Stair steps)
    
    t = wall_thickness
    
    for r in room_schedule:
        b = r['bounds']
        x1, x2 = b['x_min'], b['x_max']
        z1, z2 = b['z_min'], b['z_max']
        
        # Inner wall rectangle
        msp.add_lwpolyline([(x1, z1), (x2, z1), (x2, z2), (x1, z2), (x1, z1)], dxfattribs={'layer': 'A-WALL-INNR'})
        # Outer wall rectangle (+thickness)
        msp.add_lwpolyline([(x1-t, z1-t), (x2+t, z1-t), (x2+t, z2+t), (x1-t, z2+t), (x1-t, z1-t)], dxfattribs={'layer': 'A-WALL-OUTR'})
        
        # Room label & area
        cx = (x1 + x2) / 2.0
        cz = (z1 + z2) / 2.0
        label_text = f"{r['code']}: {r['name']}"
        dim_text = f"{r['width_m']:.2f} x {r['length_m']:.2f}m ({r['area_m2']:.1f} m2)"
        
        msp.add_text(label_text, dxfattribs={'layer': 'A-ANNO-TEXT', 'height': 0.35}).set_placement((cx - 1.2, cz + 0.2))
        msp.add_text(dim_text, dxfattribs={'layer': 'A-ANNO-DIMS', 'height': 0.22}).set_placement((cx - 1.2, cz - 0.3))
        
    # Door openings & stairs
    for d in doors:
        p1, p2 = d['line']
        msp.add_line(p1, p2, dxfattribs={'layer': 'A-DOOR', 'lineweight': 50})
        # If stairs, draw step lines
        if 'stairs' in d:
            n_steps = d['stairs']
            # Draw parallel step marks
            dx = p2[0] - p1[0]
            dz = p2[1] - p1[1]
            for s in range(1, n_steps):
                frac = s / float(n_steps)
                sp1 = (p1[0] + dx*frac - 0.2, p1[1] + dz*frac - 0.2)
                sp2 = (p1[0] + dx*frac + 0.2, p1[1] + dz*frac + 0.2)
                msp.add_line(sp1, sp2, dxfattribs={'layer': 'A-FLOR-STRS'})
                
    doc.saveas(output_path)
    print(f"[+] Exported Clean Architectural CAD DXF: {output_path}")


def export_clean_vector_svg(output_path, room_schedule, doors, wall_thickness=0.20):
    """Export crisp, beautiful architectural SVG blueprint with dark blueprint theme."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Find bounding box
    all_x = [r['bounds']['x_min'] for r in room_schedule] + [r['bounds']['x_max'] for r in room_schedule]
    all_z = [r['bounds']['z_min'] for r in room_schedule] + [r['bounds']['z_max'] for r in room_schedule]
    
    margin = 3.0
    x_min = min(all_x) - margin
    x_max = max(all_x) + margin
    z_min = min(all_z) - margin
    z_max = max(all_z) + margin
    
    width_m = x_max - x_min
    height_m = z_max - z_min
    
    # Scale: 50 pixels per meter (0.02m = 1px)
    px_per_m = 45.0
    svg_w = int(width_m * px_per_m)
    svg_h = int(height_m * px_per_m)
    
    def to_svg(x, z):
        col = (x - x_min) * px_per_m
        row = (z_max - z) * px_per_m
        return col, row

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="100%" height="100%" style="background: #090d16;">',
        f'  <defs>',
        f'    <style>',
        f'      .room-box {{ fill: rgba(30, 41, 59, 0.6); stroke: #38bdf8; stroke-width: 2.5; }}',
        f'      .room-outer {{ fill: none; stroke: #64748b; stroke-width: 1.2; stroke-dasharray: 4,4; }}',
        f'      .door-cut {{ stroke: #10b981; stroke-width: 4.5; stroke-linecap: round; }}',
        f'      .door-swing {{ fill: none; stroke: rgba(16, 185, 129, 0.5); stroke-width: 1.2; stroke-dasharray: 3,3; }}',
        f'      .grid-line {{ stroke: rgba(51, 65, 85, 0.4); stroke-width: 0.8; stroke-dasharray: 2,4; }}',
        f'      .room-title {{ fill: #ffffff; font-family: ui-sans-serif, system-ui, sans-serif; font-size: 15px; font-weight: 700; text-anchor: middle; }}',
        f'      .room-dim {{ fill: #38bdf8; font-family: ui-monospace, monospace; font-size: 12px; font-weight: 600; text-anchor: middle; }}',
        f'      .room-elev {{ fill: #94a3b8; font-family: ui-monospace, monospace; font-size: 11px; text-anchor: middle; }}',
        f'      .stair-step {{ stroke: #f59e0b; stroke-width: 1.5; }}',
        f'    </style>',
        f'  </defs>',
    ]
    
    # 1-meter grid
    for m in range(int(np.floor(x_min)), int(np.ceil(x_max)) + 1):
        c, _ = to_svg(m, 0)
        svg.append(f'  <line x1="{c}" y1="0" x2="{c}" y2="{svg_h}" class="grid-line" />')
    for m in range(int(np.floor(z_min)), int(np.ceil(z_max)) + 1):
        _, r = to_svg(0, m)
        svg.append(f'  <line x1="0" y1="{r}" x2="{svg_w}" y2="{r}" class="grid-line" />')
        
    # Rooms
    t = wall_thickness
    for r in room_schedule:
        b = r['bounds']
        c1, r2 = to_svg(b['x_min'], b['z_min'])
        c2, r1 = to_svg(b['x_max'], b['z_max'])
        rw = c2 - c1
        rh = r2 - r1
        
        # Outer wall
        oc1, or2 = to_svg(b['x_min'] - t, b['z_min'] - t)
        oc2, or1 = to_svg(b['x_max'] + t, b['z_max'] + t)
        svg.append(f'  <rect x="{oc1:.1f}" y="{or1:.1f}" width="{oc2-oc1:.1f}" height="{or2-or1:.1f}" class="room-outer" />')
        
        # Inner wall
        svg.append(f'  <rect x="{c1:.1f}" y="{r1:.1f}" width="{rw:.1f}" height="{rh:.1f}" class="room-box" rx="2" />')
        
        # Labels
        cx = (c1 + c2) / 2.0
        cy = (r1 + r2) / 2.0
        elev_str = f"FL: {r['floor_level_m']:+.2f}m"
        svg.append(f'  <text x="{cx:.1f}" y="{cy - 12:.1f}" class="room-title">{r["code"]} &mdash; {r["name"]}</text>')
        svg.append(f'  <text x="{cx:.1f}" y="{cy + 6:.1f}" class="room-dim">{r["width_m"]:.2f}m &times; {r["length_m"]:.2f}m &bull; {r["area_m2"]:.1f} m&sup2;</text>')
        svg.append(f'  <text x="{cx:.1f}" y="{cy + 22:.1f}" class="room-elev">{elev_str}</text>')
        
    # Doors & stairs
    for d in doors:
        (x1, z1), (x2, z2) = d['line']
        c1, r1 = to_svg(x1, z1)
        c2, r2 = to_svg(x2, z2)
        svg.append(f'  <!-- {d["label"]} -->')
        svg.append(f'  <line x1="{c1:.1f}" y1="{r1:.1f}" x2="{c2:.1f}" y2="{r2:.1f}" class="door-cut" />')
        if 'stairs' in d:
            n_steps = d['stairs']
            for s in range(1, n_steps):
                frac = s / float(n_steps)
                sc1 = c1 + (c2 - c1) * frac
                sr1 = r1 + (r2 - r1) * frac
                svg.append(f'  <circle cx="{sc1:.1f}" cy="{sr1:.1f}" r="3" fill="#f59e0b" />')
                
    # North Arrow & Title Block
    svg.append(f'  <!-- Title block -->')
    svg.append(f'  <g transform="translate(40, 50)">')
    svg.append(f'    <text x="0" y="0" fill="#ffffff" font-family="ui-sans-serif" font-size="20" font-weight="800">TEAHOUSE ARCHITECTURAL BLUEPRINT</text>')
    svg.append(f'    <text x="0" y="20" fill="#94a3b8" font-family="ui-monospace" font-size="12">Measured from 23 Optical Reference Panoramas &bull; Metric Scale: 1:20 &bull; Orthogonal Manhattan Fitter</text>')
    svg.append(f'  </g>')
    
    # Compass
    svg.append(f'  <g transform="translate({svg_w - 70}, 70)">')
    svg.append(f'    <circle r="32" fill="#1e293b" stroke="#38bdf8" stroke-width="1.5" />')
    svg.append(f'    <polygon points="0,-24 8,-4 0,-12 -8,-4" fill="#f43f5e" />')
    svg.append(f'    <polygon points="0,24 8,4 0,12 -8,4" fill="#64748b" />')
    svg.append(f'    <text x="-5" y="-6" fill="#f43f5e" font-size="12" font-weight="bold" font-family="monospace">N</text>')
    svg.append(f'  </g>')
    
    svg.append(f'</svg>')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg))
    print(f"[+] Exported Clean Architectural Vector SVG: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Architectural Manhattan Blueprint Fitter.")
    parser.add_argument("--spatial-dir", type=str, default="exports/spatial", help="Path to spatial directory.")
    parser.add_argument("--manifest", type=str, default="source/captures/panoramas/tour-manifest.json", help="Path to tour-manifest.json.")
    parser.add_argument("--output-dir", type=str, default="exports/spatial/venue", help="Output directory for clean blueprints.")
    args = parser.parse_args()

    room_schedule, doors, wall_thickness = build_architectural_model(args.spatial_dir, args.manifest)

    os.makedirs(args.output_dir, exist_ok=True)
    
    # 1. Export JSON schedule.
    # Named "room_schedule", not "measured_room_schedule": per-room provenance decides
    # what is actually measured, and most rooms are not.
    n_cal = sum(1 for r in room_schedule if r.get("provenance", {}).get("source") == "calibrated")
    schedule_json_path = os.path.join(args.output_dir, "room_schedule.json")
    with open(schedule_json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "total_rooms": len(room_schedule),
            "rooms_calibrated": n_cal,
            "rooms_hand_estimated": len(room_schedule) - n_cal,
            "all_dimensions_measured": n_cal == len(room_schedule),
            "warning": (
                "Rooms with provenance.source == 'hand_estimate' are NOT measured. "
                "Rooms marked 'calibrated' are RANGE-SATURATED LOWER BOUNDS from single "
                "monocular viewpoints, not room sizes: the span reflects the depth "
                "model's ~4-5 m usable range, not the walls. Do not cite either as a "
                "dimension. See docs/MEASUREMENT-STATUS.md."
            ),
            "monocular_can_size_rooms": False,
            "wall_thickness_m": wall_thickness,
            "wall_thickness_measured": False,
            "rooms": room_schedule,
            "doors": doors,
            "doors_measured": False,
        }, f, indent=2)
    print(f"[+] Exported Room Schedule ({n_cal} calibrated / {len(room_schedule)}): {schedule_json_path}")
    
    # 2. Export Clean CAD DXF
    dxf_path = os.path.join(args.output_dir, "clean_architectural_blueprint.dxf")
    export_clean_cad_dxf(dxf_path, room_schedule, doors, wall_thickness)
    
    # 3. Export Clean Vector SVG
    svg_path = os.path.join(args.output_dir, "clean_architectural_blueprint.svg")
    export_clean_vector_svg(svg_path, room_schedule, doors, wall_thickness)

if __name__ == "__main__":
    main()
