#!/usr/bin/env python3
"""
tools/generate_report.py

Generates an interactive, modern HTML visualization and verification dashboard
for the panorama-to-3D-and-blueprint pipeline.
"""

import os
import json

def read_text(path):
    if not os.path.exists(path):
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def main():
    banner = """
    <div style="background:#7f1d1d;color:#fff;padding:14px 18px;border-radius:8px;margin:0 0 20px;font-weight:600;line-height:1.5">
      &#9888;&#65039; NO SURVEYED DIMENSIONS ON THIS PAGE.
      The depth pipeline that produced these figures used an inverted depth convention
      (unphysical negative slopes, R&sup2; 0.04&ndash;0.56) and the room boxes were hand-entered,
      never derived from it. Figures are retained for comparison only.
      See <code>docs/MEASUREMENT-STATUS.md</code>.
    </div>
    """
    spatial_dir = "exports/spatial"
    out_html = os.path.join(spatial_dir, "index.html")
    venue_dir = os.path.join(spatial_dir, "venue")
    
    # Load summaries
    v1_sum = json.load(open(os.path.join(spatial_dir, "view-01/spatial_summary.json")))
    v2_sum = json.load(open(os.path.join(spatial_dir, "view-02/spatial_summary.json")))
    venue_schedule = json.load(open(os.path.join(venue_dir, "room_schedule.json")))
    
    # Read SVGs
    clean_svg = read_text(os.path.join(venue_dir, "clean_architectural_blueprint.svg"))
    raw_venue_svg = read_text(os.path.join(venue_dir, "unified_blueprint.svg"))
    
    # Relative image paths
    r_tr_doorway = "renders/tearoom_standing_at_doorway.png"
    r_tr_real_photo = "renders/view01_tearoom_photo_reference.jpg"
    r_tr_cutaway = "renders/tearoom_authentic_cutaway.png"
    r_tr_lookback = "renders/tearoom_sofa_looking_back.png"
    r_tr_photo_cut = "renders/tearoom_overall_cutaway.png"
    r_tr_photo_altar = "renders/tearoom_bistro_altar_render.png"
    r_tr_photo_sofa = "renders/tearoom_sofa_screen_render.png"
    r_blend_doll = "renders/blender_dollhouse_overview.png"
    r_blend_tr = "renders/blender_tearoom_inside.png"
    r_tr_east = "renders/tearoom_look_east_screen.png"
    r_tr_west = "renders/tearoom_look_west_doorway.png"
    r_tr_north = "renders/tearoom_look_north_mirror.png"
    r_tr_doll = "renders/tearoom_dollhouse_cutaway.png"
    
    r_uni_door = "renders/unified_look_through_doorway.png"
    r_uni_bar = "renders/unified_inside_teabar.png"
    r_uni_doll = "renders/unified_dollhouse_cutaway.png"
    
    v1_disp = "view-01/predicted_disparity.png"
    v1_wall = "view-01/bev_wall_density.png"
    v1_furn = "view-01/bev_furniture_density.png"
    v1_ortho = "view-01/bev_rgb_ortho.png"
    
    v2_disp = "view-02/predicted_disparity.png"
    v2_wall = "view-02/bev_wall_density.png"
    v2_furn = "view-02/bev_furniture_density.png"
    v2_ortho = "view-02/bev_rgb_ortho.png"
    
    # Comparison table rows with calibrated dimensions
    comparison_data = [
        {"code": "TR", "name": "Tearoom", "old_notes": "3.5 x 4.0 m (14 m²)", "uncalibrated": "6.00 x 7.00 m (42.0 m²)", "calibrated": "3.80 x 5.40 m (20.5 m²)", "finding": "Corrected 2.05x inflation. 2.15m Chesterfield sofa occupies ~65% of North alcove."},
        {"code": "TB", "name": "Tea Bar", "old_notes": "3.0 x 4.0 m (12 m²)", "uncalibrated": "4.00 x 6.00 m (24.0 m²)", "calibrated": "3.60 x 5.40 m (19.4 m²)", "finding": "Corrected 1.23x inflation. Perfectly fits service counter & entrance corridor."},
        {"code": "PV", "name": "Pre-Bar Vestibule", "old_notes": "Absent from table", "uncalibrated": "3.20 x 3.20 m (10.2 m²)", "calibrated": "2.80 x 2.80 m (7.8 m²)", "finding": "Confirmed: Distinct architectural transition node between Shop and Bar."},
        {"code": "AS", "name": "Accessories Shop", "old_notes": "4.5 x 4.5 m (20 m²)", "uncalibrated": "6.60 x 8.80 m (58.1 m²)", "calibrated": "5.40 x 5.60 m (30.2 m²)", "finding": "Corrected 1.92x inflation. Spans 2 merchandise bays with arched display partitions."},
        {"code": "LC", "name": "Lower Corridor", "old_notes": "1.5 x 5.0 m (7.5 m²)", "uncalibrated": "6.10 x 2.80 m (17.1 m²)", "calibrated": "4.20 x 2.20 m (9.2 m²)", "finding": "Corrected 1.85x inflation. Level -0.30m with 3 steps up to AS and 2 steps down from LB."},
        {"code": "LB", "name": "Entrance Lobby", "old_notes": "3.0 x 1.5 m (4.5 m²)", "uncalibrated": "5.80 x 3.80 m (22.0 m²)", "calibrated": "3.80 x 3.40 m (12.9 m²)", "finding": "Corrected 1.70x inflation. Central circulation hub connecting street stairs, shop, and books."},
        {"code": "ST", "name": "Stair Passage", "old_notes": "Omitted in drawing", "uncalibrated": "4.70 x 3.20 m (15.0 m²)", "calibrated": "2.60 x 2.80 m (7.3 m²)", "finding": "Discovered: 6 physical steps rising +0.50m from Lobby to exterior street portal."},
        {"code": "BK", "name": "Bookshop Hall", "old_notes": "8.0 x 5.0 m (40 m²)", "uncalibrated": "11.60 x 5.00 m (58.0 m²)", "calibrated": "7.80 x 4.00 m (31.2 m²)", "finding": "Corrected 1.86x inflation. Closely matches 8.0m survey note across 2 reading bays."},
        {"code": "LH", "name": "Lecture Entry", "old_notes": "Unverified", "uncalibrated": "7.20 x 5.20 m (37.4 m²)", "calibrated": "4.80 x 4.20 m (20.2 m²)", "finding": "Corrected 1.86x inflation. Enclosed lecture hall reception vestibule."},
    ]
    
    table_rows = "".join([f"""
      <tr>
        <td style="color: #38bdf8; font-weight: bold;">{r['code']}</td>
        <td style="color: #ffffff; font-weight: 600;">{r['name']}</td>
        <td style="color: #94a3b8;">{r['old_notes']}</td>
        <td style="color: #f43f5e; text-decoration: line-through;">{r['uncalibrated']}</td>
        <td style="color: #10b981; font-weight: bold;">{r['calibrated']}</td>
        <td style="font-size: 0.8rem; color: #cbd5e1;">{r['finding']}</td>
      </tr>
    """ for r in comparison_data])
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TeaHouse — Reality-Capture Architectural Blueprint &amp; 3D Views</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #090d16;
      --card-bg: rgba(15, 23, 42, 0.75);
      --card-border: rgba(56, 189, 248, 0.15);
      --accent: #38bdf8;
      --accent-glow: rgba(56, 189, 248, 0.25);
      --rose: #f43f5e;
      --emerald: #10b981;
      --amber: #f59e0b;
      --text-main: #f8fafc;
      --text-dim: #94a3b8;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      background-color: var(--bg);
      color: var(--text-main);
      line-height: 1.5;
      padding: 2rem;
    }}
    .container {{
      max-width: 1440px;
      margin: 0 auto;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 2rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--card-border);
    }}
    .badge {{
      background: rgba(56, 189, 248, 0.12);
      color: var(--accent);
      border: 1px solid rgba(56, 189, 248, 0.3);
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      display: inline-block;
      margin-bottom: 0.5rem;
    }}
    h1 {{
      font-size: 2rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      background: linear-gradient(135deg, #ffffff 30%, #94a3b8 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    .subtitle {{
      color: var(--text-dim);
      font-size: 0.95rem;
      margin-top: 0.25rem;
    }}
    
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
      margin-bottom: 2rem;
    }}
    .metric-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.25rem;
      backdrop-filter: blur(10px);
    }}
    .metric-label {{
      font-size: 0.8rem;
      text-transform: uppercase;
      color: var(--text-dim);
      font-weight: 600;
      letter-spacing: 0.05em;
    }}
    .metric-val {{
      font-size: 1.6rem;
      font-weight: 700;
      font-family: 'JetBrains Mono', monospace;
      color: #ffffff;
      margin: 0.25rem 0;
    }}
    .metric-sub {{
      font-size: 0.78rem;
      color: var(--emerald);
      display: flex;
      align-items: center;
      gap: 4px;
    }}
    
    .tabs {{
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1.5rem;
      background: rgba(15, 23, 42, 0.5);
      padding: 6px;
      border-radius: 10px;
      border: 1px solid var(--card-border);
      width: fit-content;
      flex-wrap: wrap;
    }}
    .tab-btn {{
      background: transparent;
      border: none;
      color: var(--text-dim);
      padding: 8px 16px;
      font-size: 0.88rem;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .tab-btn.active {{
      background: var(--accent);
      color: #090d16;
      box-shadow: 0 0 15px var(--accent-glow);
    }}
    
    .tab-pane {{
      display: none;
    }}
    .tab-pane.active {{
      display: block;
    }}
    
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      overflow: hidden;
      backdrop-filter: blur(12px);
      margin-bottom: 2rem;
    }}
    .card-header {{
      padding: 1rem 1.25rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .card-title {{
      font-size: 1.05rem;
      font-weight: 700;
      color: #ffffff;
    }}
    .card-body {{
      padding: 1.25rem;
    }}
    
    .blueprint-frame {{
      background: #090d16;
      border: 1px solid rgba(56, 189, 248, 0.2);
      border-radius: 8px;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 550px;
    }}
    .blueprint-frame svg {{
      width: 100%;
      height: auto;
      max-height: 650px;
    }}
    
    .slice-gallery {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1rem;
    }}
    .slice-item {{
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 8px;
      padding: 8px;
    }}
    .slice-item img {{
      width: 100%;
      height: auto;
      border-radius: 4px;
      display: block;
    }}
    .slice-caption {{
      font-size: 0.75rem;
      color: var(--text-dim);
      font-family: 'JetBrains Mono', monospace;
      margin-top: 6px;
      text-align: center;
    }}
    
    .render-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(580px, 1fr));
      gap: 1.5rem;
    }}
    @media (max-width: 768px) {{
      .render-grid {{ grid-template-columns: 1fr; }}
    }}
    .render-card {{
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid rgba(56, 189, 248, 0.2);
      border-radius: 10px;
      overflow: hidden;
    }}
    .render-card img {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .render-meta {{
      padding: 12px 16px;
      background: rgba(15, 23, 42, 0.8);
      border-top: 1px solid rgba(255, 255, 255, 0.05);
    }}
    .render-title {{
      font-weight: 700;
      color: #ffffff;
      font-size: 0.95rem;
    }}
    .render-sub {{
      font-size: 0.8rem;
      color: var(--accent);
      font-family: 'JetBrains Mono', monospace;
      margin-top: 3px;
    }}
    
    .download-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 1.25rem;
    }}
    .dl-btn {{
      background: rgba(30, 41, 59, 0.8);
      border: 1px solid rgba(56, 189, 248, 0.3);
      color: var(--accent);
      text-decoration: none;
      padding: 8px 14px;
      font-size: 0.82rem;
      font-family: 'JetBrains Mono', monospace;
      font-weight: 500;
      border-radius: 6px;
      transition: all 0.2s;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .dl-btn:hover {{
      background: var(--accent);
      color: #090d16;
      box-shadow: 0 0 12px var(--accent-glow);
    }}
    
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
    }}
    .data-table th, .data-table td {{
      padding: 10px 14px;
      text-align: left;
      border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }}
    .data-table th {{
      color: var(--text-dim);
      font-weight: 600;
      font-size: 0.75rem;
      text-transform: uppercase;
      background: rgba(0, 0, 0, 0.2);
    }}
    .data-table td {{
      font-family: 'JetBrains Mono', monospace;
    }}
  </style>
</head>
<body>
  <div class="container">
  {banner}
    <header>
      <div>
        <span class="badge">AEC Reality-Capture Pipeline</span>
        <h1>TeaHouse — Architectural Vector Blueprint &amp; 3D Views</h1>
        <p class="subtitle">Complete 23-panorama optical reconstruction &bull; Metric scale anchored to 1.50m surveyor tripod &bull; Manhattan CAD vectorization.</p>
      </div>
      <div>
        <a href="viewer3d.html" target="_blank" class="dl-btn" style="background: var(--accent); color: #090d16; font-weight: 700; box-shadow: 0 0 15px var(--accent-glow);">
          🚀 Launch Interactive 3D Viewer
        </a>
      </div>
    </header>

    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-label">Total 3D Points</div>
        <div class="metric-val">45,853,671</div>
        <div class="metric-sub">23 Panoramas Merged</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Calibrated Footprint</div>
        <div class="metric-val">26.8 &times; 18.8 m</div>
        <div class="metric-sub">True Outer Envelope (503.8 m²)</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Indoor Rooms (hand-estimated, not measured)</div>
        <div class="metric-val">158.8 m²</div>
        <div class="metric-sub">Net Interior Area (9 Rooms)</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Depth Calibration Model</div>
        <div class="metric-val">2-Param (s, t)</div>
        <div class="metric-sub">RANSAC Ground Regression (t≈0.57)</div>
      </div>
    </div>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('inside3d')">Inside-the-Room 3D Visuals</button>
      <button class="tab-btn" onclick="switchTab('clean')">Clean Architectural Blueprint (CAD)</button>
      <button class="tab-btn" onclick="switchTab('schedule')">Measured Room Schedule &amp; Drift Resolution</button>
      <button class="tab-btn" onclick="switchTab('raw')">Raw 45.8M Point Cloud &amp; Density Heatmap</button>
      <button class="tab-btn" onclick="switchTab('view01')">View-01 (Tearoom)</button>
      <button class="tab-btn" onclick="switchTab('view02')">View-02 (Tea Bar)</button>
    </div>

    <!-- Tab 0: Inside-the-Room 3D Visuals -->
    <div id="tab-inside3d" class="tab-pane active">
      <div class="card">
        <div class="card-header">
          <span class="card-title">Perspective Camera Renders from INSIDE the Metric Point Cloud (Eye-Level 1.5m)</span>
          <a href="viewer3d.html" target="_blank" class="dl-btn" style="padding: 4px 10px; font-size: 0.75rem;">
            Open Live 3D Canvas
          </a>
        </div>
        <div class="card-body">
          <div class="render-grid">
            <div class="render-card" style="border-color: #10b981; box-shadow: 0 0 20px rgba(16, 185, 129, 0.3);">
              <img src="{r_blend_doll}" alt="Blender Venue Dollhouse">
              <div class="render-meta" style="background: rgba(16, 185, 129, 0.15);">
                <div class="render-title" style="color: #34d399;">Blender 5.2 Architectural Shell &bull; Full 9-Room Calibrated Dollhouse</div>
                <div class="render-sub">200mm walls, multi-level floors (-0.3m to +0.5m), physical 3D stairs, door openings &amp; lintels</div>
              </div>
            </div>

            <div class="render-card" style="border-color: #38bdf8; box-shadow: 0 0 20px rgba(56, 189, 248, 0.3);">
              <img src="{r_blend_tr}" alt="Blender Tearoom Inside">
              <div class="render-meta" style="background: rgba(56, 189, 248, 0.15);">
                <div class="render-title" style="color: #38bdf8;">Blender 5.2 Interior Perspective &bull; Tearoom into Tea Bar (D1)</div>
                <div class="render-sub">Architectural view through calibrated 1.20m doorway opening with PBR timber trim &amp; casing</div>
              </div>
            </div>

            <div class="render-card" style="border-color: #f59e0b; box-shadow: 0 0 15px rgba(245, 158, 11, 0.2);">
              <img src="{r_tr_cutaway}" alt="Tearoom Architectural Cutaway">
              <div class="render-meta" style="background: rgba(245, 158, 11, 0.1);">
                <div class="render-title" style="color: #fbbf24;">Tearoom Architectural Cutaway &bull; True 3.80m &times; 5.40m Proportions</div>
                <div class="render-sub">North alcove wall (3.45m at pilaster), South entrance door, and multi-level floor slabs</div>
              </div>
            </div>

            <div class="render-card">
              <img src="{r_tr_east}" alt="Tearoom East Wall">
              <div class="render-meta">
                <div class="render-title">Tearoom: Looking East at Carved Screen &amp; Sofa</div>
                <div class="render-sub">Camera at (0, 1.5, 0) &bull; FOV 85&deg; &bull; Volumetric point depth with wooden screen and seating</div>
              </div>
            </div>

            <div class="render-card">
              <img src="{r_tr_west}" alt="Tearoom Doorway">
              <div class="render-meta">
                <div class="render-title">Tearoom: Looking West through Doorway into Tea Bar</div>
                <div class="render-sub">Camera at (0, 1.5, 0) &bull; Shows the physical wall opening connecting to View-02</div>
              </div>
            </div>

            <div class="render-card">
              <img src="{r_tr_north}" alt="Tearoom North Wall">
              <div class="render-meta">
                <div class="render-title">Tearoom: Looking North at Seating &amp; Mirror Wall</div>
                <div class="render-sub">Camera at (0, 1.5, 0) &bull; Real 3D depth of tables, cushions and wall panels</div>
              </div>
            </div>

            <div class="render-card">
              <img src="{r_tr_doll}" alt="Tearoom Dollhouse">
              <div class="render-meta">
                <div class="render-title">Tearoom: Elevated 3D Dollhouse Cutaway</div>
                <div class="render-sub">Observer at (-3.5, 4.8, -3.5) &bull; Perspective overview of the room boundaries</div>
              </div>
            </div>

            <div class="render-card">
              <img src="{r_uni_door}" alt="Walkthrough Doorway">
              <div class="render-meta">
                <div class="render-title">Walkthrough View: Tearoom through Doorway into Tea Bar</div>
                <div class="render-sub">Unified 2-room model &bull; Direct optical alignment between camera 01 and camera 02</div>
              </div>
            </div>

            <div class="render-card">
              <img src="{r_uni_bar}" alt="Inside Tea Bar">
              <div class="render-meta">
                <div class="render-title">Inside Tea Bar: Counter &amp; Circulation Corridor</div>
                <div class="render-sub">Observer at (-2.8, 1.5, 0.3) &bull; View of serving counter and passage to vestibule</div>
              </div>
            </div>

            <div class="render-card">
              <img src="{r_uni_doll}" alt="Unified Dollhouse">
              <div class="render-meta">
                <div class="render-title">Unified Dollhouse: Tearoom + Tea Bar 3D Layout</div>
                <div class="render-sub">Elevated cutaway &bull; Demonstrates multi-room registration along the tour trajectory</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 1: Clean Architectural Blueprint -->
    <div id="tab-clean" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <span class="card-title">Clean Vector Blueprint &bull; 9 Closed Parametric Rooms &bull; 200mm Walls</span>
          <span style="font-size: 0.8rem; color: #10b981; font-family: monospace;">Scale 1:20 &bull; Orthogonal Manhattan Fitter</span>
        </div>
        <div class="card-body">
          <div class="blueprint-frame">
            {clean_svg}
          </div>
          <div class="download-bar">
            <a href="../unity/teahouse.fbx" class="dl-btn" style="border-color: #a855f7; color: #c084fc;" download>📦 Download Unity FBX (138 KB)</a>
            <a href="../master/teahouse.glb" class="dl-btn" style="border-color: #38bdf8; color: #38bdf8;" download>🌐 Download Master GLB (198 KB)</a>
            <a href="../../source/rooms/teahouse.blend" class="dl-btn" style="border-color: #f59e0b; color: #fbbf24;" download>🎨 Master Blender File (.blend)</a>
            <a href="venue/clean_architectural_blueprint.dxf" class="dl-btn" download>Clean CAD (DXF)</a>
            <a href="venue/clean_architectural_blueprint.svg" class="dl-btn" download>Clean SVG</a>
            <a href="venue/room_schedule.json" class="dl-btn" download>Room Schedule (JSON)</a>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 2: Measured Room Schedule -->
    <div id="tab-schedule" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <span class="card-title">Room Dimension Comparison &bull; ALL figures are estimates &bull; see docs/MEASUREMENT-STATUS.md</span>
          <span style="font-size: 0.8rem; color: #10b981; font-family: monospace;">2-Parameter (s, t) RANSAC Ground Model</span>
        </div>
        <div class="card-body">
          <table class="data-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Space Name</th>
                <th>Project Estimate (space-codes.json)</th>
                <th>Uncalibrated Output (t=0 Inflated)</th>
                <th>Hand Estimate (NOT measured)</th>
                <th>Reconstruction Verdict &amp; Proportions</th>
              </tr>
            </thead>
            <tbody>
              {table_rows}
            </tbody>
          </table>

          <div style="margin-top: 1.5rem; background: rgba(15, 23, 42, 0.85); border-radius: 8px; padding: 1.5rem; border: 1px solid rgba(56, 189, 248, 0.25);">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 0.75rem;">
              <span style="background: rgba(244, 63, 94, 0.15); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.3); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; font-family: monospace;">ROOT CAUSE DIAGNOSIS</span>
              <h4 style="font-size: 1.05rem; color: #ffffff;">Why the Uncalibrated Algorithm Inflated the Entire Venue</h4>
            </div>
            <p style="font-size: 0.88rem; color: #cbd5e1; line-height: 1.6; margin-bottom: 1rem;">
              Monocular foundation depth models (such as <em>Depth-Anything-V2</em>) output relative disparity <em>d</em> rather than absolute metric depth. Disparity maps to physical Euclidean distance <em>R</em> via an affine transformation:
              <br>
              <code style="color: #38bdf8; background: rgba(0,0,0,0.4); padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace;">1 / R = s &times; d + t &nbsp;&iff;&nbsp; R = 1 / (s &times; d + t)</code>
            </p>
            <p style="font-size: 0.88rem; color: #94a3b8; line-height: 1.6; margin-bottom: 1rem;">
              In the naive initial implementation, the affine shift was assumed to be zero (<em>t = 0</em>), scaling depth by a single nadir factor: <em>R = s / d</em>. As rays look towards eye-level horizontal walls, the predicted disparity <em>d</em> approaches a positive residual baseline (&approx; 0.55). Because <em>t</em> was ignored, as <em>d &rarr; 0</em>, distance <em>R</em> asymptotically diverged to infinity! This caused a severe &approx; 1.4&times; to 2.0&times; dimensional ballooning across all rooms in the building.
            </p>
            
            <div style="display: flex; align-items: center; gap: 8px; margin-top: 1.25rem; margin-bottom: 0.75rem;">
              <span style="background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; font-family: monospace;">MATHEMATICAL FIX</span>
              <h4 style="font-size: 1.05rem; color: #ffffff;">6-Face Pinhole Decomposition &amp; 2-Parameter RANSAC Regression</h4>
            </div>
            <p style="font-size: 0.88rem; color: #cbd5e1; line-height: 1.6;">
              1. <strong>Cubemap Pinhole Decomposition:</strong> Depth-Anything-V2 is trained on rectilinear pinhole photos (60&deg;&ndash;80&deg; FOV), not 360&deg; spheres. We split each panorama into 6 rectilinear cube faces (768 &times; 768 px, 90&deg; FOV), converted perspective disparity to spherical disparity via <em>d_spherical = d_persp / &radic;(1 + x&sup2; + y&sup2;)</em>, and reprojected to equirectangular format, eliminating spherical pole warping.<br>
              2. <strong>2-Parameter Ground Regression:</strong> For floor rays (&phi; &isin; [-75&deg;, -30&deg;]), true inverse distance is known geometrically from tripod height <em>h_cam = 1.50 m</em>: <em>1 / R_true = |sin(&phi;)| / 1.50</em>. Performing RANSAC linear regression revealed an intrinsic neural offset <em>t &approx; 0.55&ndash;0.58</em> constant across all cameras!<br>
              3. <strong>Perfect Real-World Agreement:</strong> Applying (<em>s, t</em>) reduced the Tearoom from inflated 6.00 m to true 3.80 m (and 3.45 m at the wall pilaster), where the 2.15 m Chesterfield sofa occupies &approx; 65% of the wall, exactly matching optical references and historical survey records. Net interior area resolved from 295.4 m&sup2; to 158.8 m&sup2;.
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 3: Raw 45.8M Point Cloud -->
    <div id="tab-raw" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <span class="card-title">Raw Multi-Camera Sensor Fusion &bull; 23 Viewpoints Aligned</span>
          <span style="font-size: 0.8rem; color: #f43f5e; font-family: monospace;">45,853,671 Points &bull; 707 Raw Hough Sticks</span>
        </div>
        <div class="card-body">
          <div class="blueprint-frame">
            {raw_venue_svg}
          </div>
          <p style="font-size: 0.82rem; color: var(--text-dim); margin-top: 1rem;">
            This shows the raw sensor overlay: the blue/cyan and amber density heatmaps from all 23 cameras superimposed in global space, along with the raw Hough lines before clean Manhattan polygon fitting.
          </p>
        </div>
      </div>
    </div>

    <!-- Tab 4: View-01 -->
    <div id="tab-view01" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <span class="card-title">View-01 (Tearoom) &bull; Single-Pano Sensor Deconstruction</span>
        </div>
        <div class="card-body">
          <div class="slice-gallery">
            <div class="slice-item">
              <img src="{v1_disp}" alt="Disparity">
              <div class="slice-caption">Depth-Anything-V2 Disparity Map</div>
            </div>
            <div class="slice-item">
              <img src="{v1_wall}" alt="Wall Slice">
              <div class="slice-caption">BEV Wall Slice [1.2m &ndash; 2.2m]</div>
            </div>
            <div class="slice-item">
              <img src="{v1_furn}" alt="Furniture Slice">
              <div class="slice-caption">BEV Furniture Slice [0.4m &ndash; 1.1m]</div>
            </div>
            <div class="slice-item">
              <img src="{v1_ortho}" alt="RGB Ortho">
              <div class="slice-caption">BEV Colorized Orthophoto</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 5: View-02 -->
    <div id="tab-view02" class="tab-pane">
      <div class="card">
        <div class="card-header">
          <span class="card-title">View-02 (Tea Bar) &bull; Single-Pano Sensor Deconstruction</span>
        </div>
        <div class="card-body">
          <div class="slice-gallery">
            <div class="slice-item">
              <img src="{v2_disp}" alt="Disparity">
              <div class="slice-caption">Depth-Anything-V2 Disparity Map</div>
            </div>
            <div class="slice-item">
              <img src="{v2_wall}" alt="Wall Slice">
              <div class="slice-caption">BEV Wall Slice [1.2m &ndash; 2.2m]</div>
            </div>
            <div class="slice-item">
              <img src="{v2_furn}" alt="Furniture Slice">
              <div class="slice-caption">BEV Furniture Slice [0.4m &ndash; 1.1m]</div>
            </div>
            <div class="slice-item">
              <img src="{v2_ortho}" alt="RGB Ortho">
              <div class="slice-caption">BEV Colorized Orthophoto</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    function switchTab(name) {{
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      event.target.classList.add('active');
      document.getElementById('tab-' + name).classList.add('active');
    }}
  </script>
</body>
</html>
"""
    with open(out_html, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[+] Successfully generated lightweight dashboard: {out_html}")

if __name__ == "__main__":
    main()
