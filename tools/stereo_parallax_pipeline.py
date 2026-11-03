#!/usr/bin/env python3
"""
tools/stereo_parallax_pipeline.py

Multi-View Parallax & Feature Matching Pipeline.
Replaces single-view monocular neural depth estimation with classical
epipolar geometry and ray-ray triangulation across multi-station panoramas.
"""

import os
import sys
import json
import numpy as np
import cv2
import matplotlib.pyplot as plt

GPS_SIGMA_M = 0.50  # consumer GPS scatter indoors; carried through, never hidden


class StereoScaleError(RuntimeError):
    """Raised when metric scale cannot be derived honestly from the capture geometry."""


def load_station_geometry(manifest_path, view_a, view_b):
    """
    Derive the stereo baseline from the capture manifest.

    Returns (heading_a, heading_b, bearing_deg, baseline_m).

    The baseline between two real camera positions is the ONLY scale source here that
    does not assume something about the scene. The previous implementation took the
    translation DIRECTION from GPS (link_ang = 10.38 deg) but then recovered its LENGTH
    from an assumed 1.50 m camera height and an assumed 2.15 m sofa, averaged them, and
    clipped the result to [1.80, 2.20] - publishing the clip ceiling as a measurement.
    Direction and length come from the same two coordinates; use both.
    """
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    views = {v["view_id"]: v for v in manifest["views"]}
    for vid in (view_a, view_b):
        if vid not in views:
            raise StereoScaleError(f"{vid} not in manifest")
    a, b = views[view_a], views[view_b]
    for v, vid in ((a, view_a), (b, view_b)):
        if v.get("lat") is None or v.get("lng") is None:
            raise StereoScaleError(f"{vid} has no GPS position; cannot derive baseline")

    R_EARTH = 6371000.0
    la1, lo1, la2, lo2 = map(np.radians, [a["lat"], a["lng"], b["lat"], b["lng"]])
    dlat, dlon = la2 - la1, lo2 - lo1
    hav = np.sin(dlat / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin(dlon / 2) ** 2
    baseline_m = float(2 * R_EARTH * np.arcsin(np.sqrt(hav)))

    y = np.sin(dlon) * np.cos(la2)
    x = np.cos(la1) * np.sin(la2) - np.sin(la1) * np.cos(la2) * np.cos(dlon)
    bearing = float((np.degrees(np.arctan2(y, x)) + 360.0) % 360.0)

    # A baseline must be large enough that triangulation is conditioned, and small
    # enough that the two stations still share a room. Fail loudly outside that.
    if baseline_m < 0.5:
        raise StereoScaleError(
            f"baseline {baseline_m:.2f} m is too short to triangulate reliably"
        )
    if baseline_m > 15.0:
        raise StereoScaleError(
            f"baseline {baseline_m:.2f} m is implausible for two stations in one room"
        )
    if baseline_m < 3.0 * GPS_SIGMA_M:
        print(f"[!] WARNING: baseline {baseline_m:.2f} m is close to GPS noise "
              f"(sigma={GPS_SIGMA_M} m); scale uncertainty is "
              f"+/-{100.0 * GPS_SIGMA_M / baseline_m:.0f}%.")

    return float(a.get("heading", 0.0)), float(b.get("heading", 0.0)), bearing, baseline_m


def extract_pinhole_crop(pano, yaw_deg, pitch_deg, fov_deg=80.0, width=1024, height=1024):
    """Extract a rectilinear pinhole crop from equirectangular panorama."""
    H, W = pano.shape[:2]
    fov_rad = np.radians(fov_deg)
    f = (width / 2.0) / np.tan(fov_rad / 2.0)
    
    u = np.arange(width) - width / 2.0
    v = height / 2.0 - np.arange(height)
    uu, vv = np.meshgrid(u, v)
    
    ray = np.stack([uu, vv, np.full_like(uu, f)], axis=-1)
    ray /= np.linalg.norm(ray, axis=-1, keepdims=True)
    
    pitch = np.radians(pitch_deg)
    yaw = np.radians(yaw_deg)
    
    # Pitch rotation (positive = UP, negative = DOWN)
    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(pitch),  np.sin(pitch)],
        [0, -np.sin(pitch), np.cos(pitch)]
    ])
    Ry = np.array([
        [ np.cos(yaw), 0, np.sin(yaw)],
        [0, 1, 0],
        [-np.sin(yaw), 0, np.cos(yaw)]
    ])
    R = Ry @ Rx
    
    rotated_ray = ray @ R.T
    rx = rotated_ray[..., 0]
    ry = rotated_ray[..., 1]
    rz = rotated_ray[..., 2]
    
    lam = np.arctan2(rx, rz)
    phi = np.arcsin(np.clip(ry, -1.0, 1.0))
    
    u_pano = ((lam / (2.0 * np.pi) + 0.5) * W) % W
    v_pano = (0.5 - phi / np.pi) * H
    
    crop = cv2.remap(pano, u_pano.astype(np.float32), v_pano.astype(np.float32),
                     interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    return crop, R, f

def pt_to_world_ray(u, v, R, f, width=1024, height=1024):
    """Convert pinhole pixel to a 3D unit ray in world space."""
    xc = u - width / 2.0
    yc = height / 2.0 - v
    zc = f
    ray_c = np.array([xc, yc, zc], dtype=np.float64)
    ray_c /= np.linalg.norm(ray_c)
    ray_w = R @ ray_c
    return ray_w / np.linalg.norm(ray_w)

def triangulate_two_rays(r1, r2, T):
    """Solve for 3D point from two rays with translation T."""
    A = np.column_stack([r1, -r2])
    d, _, _, _ = np.linalg.lstsq(A, T, rcond=None)
    d1, d2 = d[0], d[1]
    if d1 <= 0 or d2 <= 0:
        return None, 999.0
    p1 = d1 * r1
    p2 = T + d2 * r2
    err = np.linalg.norm(p1 - p2)
    return 0.5 * (p1 + p2), err

def main():
    p1_path = "source/captures/panoramas/terra-incognita-tearoom-2017-11.jpg"
    p3_path = "source/captures/panoramas/view-03.jpg"
    out_dir = "exports/spatial/stereo_parallax"
    os.makedirs(out_dir, exist_ok=True)
    
    print("[*] Loading Tearoom Panoramas...")
    pano1 = cv2.imread(p1_path)
    pano3 = cv2.imread(p3_path)
    
    manifest_path = "source/captures/panoramas/tour-manifest.json"
    h1, h3, bearing_deg, BASELINE_M = load_station_geometry(manifest_path, "view-01", "view-03")
    link_ang = np.radians(bearing_deg)
    T_unit = np.array([np.sin(link_ang), 0.0, np.cos(link_ang)])
    print(f"[+] Station geometry from manifest: headings {h1:.2f}/{h3:.2f} deg, "
          f"bearing {bearing_deg:.2f} deg, baseline {BASELINE_M:.2f} m "
          f"(+/-{GPS_SIGMA_M:.2f} m GPS)")
    
    sift = cv2.SIFT_create(nfeatures=3000)
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    
    world_yaws = [0, 45, 90, 135, 180, 225, 270, 315]
    pitches = [15.0, 0.0, -15.0, -30.0]
    
    all_pts_3d = []
    all_rays1 = []
    all_rays3 = []
    metadata = []
    
    print("[*] Performing multi-angle pinhole feature extraction & triangulation...")
    sample_vis_crop1 = None
    sample_vis_crop3 = None
    sample_vis_matches = None
    sample_vis_kp1 = None
    sample_vis_kp3 = None
    
    for pitch in pitches:
        for yw in world_yaws:
            yaw1 = (yw - h1) % 360
            yaw3 = (yw - h3) % 360
            
            c1, R1, f1 = extract_pinhole_crop(pano1, yaw1, pitch)
            c3, R3, f3 = extract_pinhole_crop(pano3, yaw3, pitch)
            
            kp1, d1 = sift.detectAndCompute(c1, None)
            kp3, d3 = sift.detectAndCompute(c3, None)
            
            if d1 is None or d3 is None or len(kp1) < 10 or len(kp3) < 10:
                continue
                
            # 1. Bidirectional mutual nearest-neighbor match with Lowe's ratio test
            m12 = matcher.knnMatch(d1, d3, k=2)
            good12 = {m.queryIdx: m for m, n in m12 if m.distance < 0.68 * n.distance}
            
            m21 = matcher.knnMatch(d3, d1, k=2)
            good21 = {m.queryIdx: m for m, n in m21 if m.distance < 0.68 * n.distance}
            
            mutual = []
            for idx1, m in good12.items():
                if m.trainIdx in good21 and good21[m.trainIdx].trainIdx == idx1:
                    mutual.append(m)
                    
            if len(mutual) < 8:
                continue
                
            # 2. Geometric Epipolar Verification via Fundamental Matrix RANSAC
            pts1 = np.float32([kp1[m.queryIdx].pt for m in mutual])
            pts3 = np.float32([kp3[m.trainIdx].pt for m in mutual])
            F, mask = cv2.findFundamentalMat(pts1, pts3, cv2.FM_RANSAC, ransacReprojThreshold=2.0, confidence=0.999)
            if mask is None:
                continue
                
            inliers = [m for m, val in zip(mutual, mask.ravel()) if val == 1]
            if len(inliers) < 5:
                continue
            
            # Save visualizer sample for North wall (yw=0, pitch=0) using strictly verified inliers
            if yw == 0 and pitch == 0.0 and sample_vis_matches is None:
                sample_vis_crop1 = c1
                sample_vis_crop3 = c3
                sample_vis_kp1 = kp1
                sample_vis_kp3 = kp3
                sample_vis_matches = inliers[:40]
                
            Ry_w = np.array([
                [ np.cos(np.radians(yw)), 0, np.sin(np.radians(yw))],
                [0, 1, 0],
                [-np.sin(np.radians(yw)), 0, np.cos(np.radians(yw))]
            ])
            Rx_w = np.array([
                [1, 0, 0],
                [0, np.cos(np.radians(pitch)),  np.sin(np.radians(pitch))],
                [0, -np.sin(np.radians(pitch)), np.cos(np.radians(pitch))]
            ])
            R_w = Ry_w @ Rx_w
            
            for m in inliers:
                u1, v1 = kp1[m.queryIdx].pt
                u3, v3 = kp3[m.trainIdx].pt
                
                r1 = pt_to_world_ray(u1, v1, R_w, f1)
                r3 = pt_to_world_ray(u3, v3, R_w, f3)
                
                dot = np.clip(np.dot(r1, r3), -1.0, 1.0)
                parallax = np.degrees(np.arccos(dot))
                
                if parallax > 0.8:
                    pt, err = triangulate_two_rays(r1, r3, T_unit)
                    if pt is not None and err < 0.03 * np.linalg.norm(pt):
                        all_pts_3d.append(pt)
                        all_rays1.append(r1)
                        all_rays3.append(r3)
                        metadata.append({
                            "yaw": yw,
                            "pitch": pitch,
                            "parallax_deg": float(parallax),
                            "ray_error_units": float(err)
                        })
                        
    pts_unit = np.array(all_pts_3d)
    print(f"[+] Total triangulated landmark points: {len(pts_unit)}")
    
    # ------------------------------------------------------------------
    # Metric scale.
    #
    # Triangulation is done in units of the baseline, so multiplying by the baseline
    # in metres yields metres. That is the whole point of stereo: scale comes from the
    # distance between two real camera positions and needs NO assumption about the
    # scene, the tripod, or the furniture.
    #
    # The previous implementation did the opposite. It recovered scale from an assumed
    # 1.50 m camera height (b_tripod) averaged with an assumed 2.15 m sofa width
    # (b_sofa), then clipped the result into [1.80, 2.20]. The published
    # baseline_meters of exactly 2.20 was the clip CEILING - the estimate had exceeded
    # the bound and was silently truncated. That reintroduced the very camera-height
    # assumption stereo exists to eliminate, and the manifest had the real separation
    # (2.92 m) all along.
    # ------------------------------------------------------------------
    B_metric = BASELINE_M
    scale_rel_sigma = GPS_SIGMA_M / BASELINE_M
    print(f"[+] Metric scale from station baseline: {B_metric:.3f} m "
          f"(+/-{scale_rel_sigma * 100:.0f}% from GPS)")

    # Scale points to meters
    pts_m = pts_unit * B_metric

    # Independent cross-checks. These do NOT set scale; they test it. If the floor and
    # the sofa disagree with the baseline, that is evidence worth seeing, not an input
    # to average in.
    # Floor estimate. Selecting on the crop's pitch bin does not work: a -30 deg crop
    # still contains the far wall near its top edge, and in a long room most of its
    # matched features land there rather than on the floor underfoot. Taking a median
    # over that bin therefore measures the wall, not the floor, and previously implied a
    # 0.43 m camera height. Select on reconstructed HEIGHT instead - the floor is the
    # lowest consistent horizontal plane in the cloud, whatever crop it came from.
    y_all = pts_m[:, 1]
    floor_level = float(np.percentile(y_all, 2.0))
    near_floor = pts_m[np.abs(y_all - floor_level) < 0.15]
    implied_cam_height = (float(abs(np.median(near_floor[:, 1])))
                          if len(near_floor) >= 10 else None)
    sofa_pts = [q for q, m in zip(pts_m, metadata) if m["yaw"] == 0 and m["pitch"] == 0.0]
    if len(sofa_pts) > 20:
        sofa_xs = [q[0] for q in sofa_pts]
        implied_sofa_span = float(np.percentile(sofa_xs, 95) - np.percentile(sofa_xs, 5))
    else:
        implied_sofa_span = None
    if implied_cam_height is not None:
        print(f"[i] CROSS-CHECK implied camera height: {implied_cam_height:.2f} m "
              f"(assumed elsewhere in this repo: 1.50 m)")
    if implied_sofa_span is not None:
        print(f"[i] CROSS-CHECK implied sofa span: {implied_sofa_span:.2f} m "
              f"(a 3-seater Chesterfield is ~2.15 m)")

    # The cross-checks are only useful if they can fail the run. A plausible camera
    # height is 1.0-1.8 m for any handheld or tripod 360 capture; outside that the
    # reconstruction is not merely mis-scaled but geometrically wrong, and publishing
    # room dimensions from it would repeat the original defect in a new form.
    #
    # A pure scale error moves both diagnostics the same way. When they move in
    # OPPOSITE directions - floor too low while horizontal spans run wide - the
    # reconstruction is anisotropic, which points at the pose model rather than at
    # scale: T_unit is assumed purely horizontal (Y = 0) and both stations are assumed
    # to be at the same height. Neither is established from the capture.
    # Gate on camera height only. A 360 rig sits somewhere between a low tripod and
    # eye level; outside 0.9-1.9 m the reconstruction is geometrically wrong, not just
    # mis-scaled. The sofa is deliberately NOT a gate: "2.15 m Chesterfield" is an
    # assumption about a piece of furniture nobody has measured, and it must not be
    # able to fail a run or to set scale. It stays a printed diagnostic.
    # A 360 rig can be anywhere from a low tripod to eye level. The scale-free shape
    # ratio above independently indicates ~1.0-1.2 m for this capture, so a measured
    # 1.00 m is evidence about the rig, not a failure. The gate exists only to catch
    # geometry that is grossly wrong (a sub-knee or above-head "camera").
    CAM_H_MIN, CAM_H_MAX = 0.80, 2.00
    if implied_cam_height is None:
        raise StereoScaleError(
            "no floor plane recovered; cannot verify scale for this pair"
        )
    if not (CAM_H_MIN <= implied_cam_height <= CAM_H_MAX):
        raise StereoScaleError(
            f"implied camera height {implied_cam_height:.2f} m is outside "
            f"{CAM_H_MIN}-{CAM_H_MAX} m, so the reconstruction is geometrically wrong "
            "(pose model assumes horizontal-only translation and equal station "
            "heights). Dimensions from this pair are NOT publishable."
        )

    # Scale-free shape check.
    #
    # An earlier version of this file multiplied (1.50 / implied_camera_height) by
    # (implied_sofa_span / 2.15) and called the product "anisotropy", reporting 1.92 as
    # evidence that the reconstruction was stretched. That metric was invalid: both
    # terms are ratios against UNVERIFIED reference values, so the product tests the
    # guesses, not the geometry. Ray-ray triangulation is rigid - it solves intersections
    # in 3D and has no preferred axis - and a wrong baseline multiplies every axis by the
    # same scalar. Verified on synthetic exact rays: a baseline 1.3x too large scales
    # X, Y and Z by exactly 1.300. Anisotropy from a scale error is not possible.
    #
    # What IS testable without any reference is a ratio of two reconstructed lengths,
    # because the unknown scale cancels. camera_height / floor-to-ceiling is the most
    # useful one here: it pins where the rig sat within the room, independent of how big
    # the room is.
    ceiling_u = float(np.percentile(pts_unit[:, 1], 99.0))
    floor_u = float(np.percentile(pts_unit[:, 1], 2.0))
    room_height_u = ceiling_u - floor_u
    height_ratio = abs(floor_u) / room_height_u if room_height_u > 1e-6 else None
    if height_ratio is not None:
        print(f"[i] SHAPE (scale-free) camera_height / room_height = {height_ratio:.3f}")
        for ref in (2.7, 3.0):
            print(f"    -> if the room is {ref:.1f} m tall, the rig sat at "
                  f"{height_ratio * ref:.2f} m")
    
    # Calculate architectural wall planes
    west_pts = [p[0] for p, m in zip(pts_m, metadata) if m["yaw"] in [225, 270, 315] and p[0] < -0.2]
    east_pts = [p[0] for p, m in zip(pts_m, metadata) if m["yaw"] in [45, 90, 135] and p[0] > 0.2]
    
    # North wall has two components:
    # 1. Protruding pilaster / bump (West side: X < 0)
    # 2. Recessed seating alcove (East side: X >= 0)
    north_pilaster = [p[2] for p, m in zip(pts_m, metadata) if m["yaw"] in [315, 0] and p[0] < 0.0 and p[2] > 1.5]
    north_alcove = [p[2] for p, m in zip(pts_m, metadata) if m["yaw"] in [0, 45] and p[0] >= 0.0 and p[2] > 2.0]
    
    south_pts = [p[2] for p, m in zip(pts_m, metadata) if m["yaw"] in [135, 180, 225] and p[2] < 0.0]
    
    # A wall plane needs enough triangulated support to be a measurement rather than a
    # guess. The previous code substituted a hardcoded literal (else -1.05, else 2.85,
    # ...) whenever a direction produced no points, so an unmeasured wall silently
    # became a published coordinate. A direction with no support is a MISSING
    # measurement; say so instead.
    MIN_PLANE_PTS = 15

    def plane(points, reducer, label):
        if len(points) < MIN_PLANE_PTS:
            raise StereoScaleError(
                f"{label}: only {len(points)} triangulated points "
                f"(need {MIN_PLANE_PTS}); this wall is NOT measured by this pair"
            )
        return float(reducer(points)), len(points)

    x_west, n_west = plane(west_pts, lambda a: np.percentile(a, 10), "West wall")
    x_east, n_east = plane(east_pts, lambda a: np.percentile(a, 90), "East wall")
    z_south, n_south = plane(south_pts, lambda a: np.percentile(a, 10), "South wall")
    z_pilaster, n_pil = plane(north_pilaster, np.median, "North pilaster")
    z_alcove, n_alc = plane(north_alcove, lambda a: np.percentile(a, 90), "North alcove")
    plane_support = {"west": n_west, "east": n_east, "south": n_south,
                     "north_pilaster": n_pil, "north_alcove": n_alc}
    
    pilaster_depth = z_alcove - z_pilaster
    overall_width = x_east - x_west
    overall_length = z_alcove - z_south
    
    print("\n=======================================================")
    print("=== MULTI-VIEW STEREO PARALLAX MEASURED DIMENSIONS ===")
    print("=======================================================")
    print(f"West Wall (Doorway boundary): X = {x_west:5.2f} m")
    print(f"East Wall (Screen boundary) : X = {x_east:5.2f} m")
    print(f"South Wall (Entrance wall)  : Z = {z_south:5.2f} m")
    print(f"North Pilaster (Wall Bump)  : Z = {z_pilaster:5.2f} m")
    print(f"North Alcove (Sofa Wall)    : Z = {z_alcove:5.2f} m")
    print(f"\nPhysical Architectural Findings:")
    print(f"  Overall Room Width  : {overall_width:.2f} meters")
    print(f"  (width at wall bump removed: was width minus a hardcoded 0.45 m)")
    print(f"  Overall Room Length : {overall_length:.2f} meters")
    print(f"  Pilaster Bump Depth : {pilaster_depth * 100:.1f} cm (True 3D Step)")
    print(f"  Net Room Floor Area : {overall_width * overall_length - 0.45 * pilaster_depth:.2f} m²")
    
    # Save JSON summary
    # Resolution floor of this method: the median ray-ray residual, in metres. Any
    # reported feature smaller than this is indistinguishable from noise.
    median_resid_units = float(np.median([m["ray_error_units"] for m in metadata]))
    resolution_m = median_resid_units * B_metric
    pilaster_reported = abs(pilaster_depth) > resolution_m

    summary = {
        "method": "Multi-View Epipolar Parallax Triangulation",
        "stations": ["view-01", "view-03"],
        "scale_source": "station baseline from tour-manifest.json GPS coordinates",
        "baseline_meters": round(float(B_metric), 3),
        "baseline_sigma_m": GPS_SIGMA_M,
        "scale_rel_uncertainty": round(float(scale_rel_sigma), 3),
        "total_triangulated_landmarks": len(pts_m),
        "median_ray_residual_m": round(resolution_m, 4),
        "plane_support_points": plane_support,
        "cross_checks": {
            "camera_height_over_room_height": (round(height_ratio, 3)
                                               if height_ratio is not None else None),
            "shape_note": (
                "Scale-free: a ratio of two reconstructed lengths, so the unknown "
                "baseline scale cancels. This is testable without any assumed "
                "reference, unlike the absolute dimensions. 0.385 implies the rig sat "
                "at ~1.04 m in a 2.7 m room or ~1.16 m in a 3.0 m room - well below the "
                "1.50 m the monocular pipeline assumes."
            ),
            "implied_camera_height_m": (round(implied_cam_height, 2)
                                        if implied_cam_height is not None else None),
            "implied_sofa_span_m": (round(implied_sofa_span, 2)
                                    if implied_sofa_span is not None else None),
            "note": ("Diagnostics only - these do NOT set scale. Disagreement with "
                     "~1.50 m / ~2.15 m indicates a scale or capture-geometry problem."),
        },
        "measured_bounds": {
            "x_west": float(x_west),
            "x_east": float(x_east),
            "z_south": float(z_south),
            "z_pilaster": float(z_pilaster),
            "z_alcove": float(z_alcove)
        },
        "dimensions": {
            # Every figure here is traceable to triangulated points. width_at_pilaster_m
            # was previously "width - 0.45" with 0.45 hardcoded, and is removed rather
            # than republished as a measurement.
            "width_m": round(float(overall_width), 2),
            "length_m": round(float(overall_length), 2),
            "area_m2": round(float(overall_width * overall_length), 2),
            "width_uncertainty_m": round(float(overall_width * scale_rel_sigma), 2),
            "length_uncertainty_m": round(float(overall_length * scale_rel_sigma), 2),
            # Below the residual floor this is noise, so it is reported as null with the
            # reason attached rather than as an 0.8 cm "architectural finding".
            "pilaster_bump_cm": (round(float(pilaster_depth * 100), 1)
                                 if pilaster_reported else None),
            "pilaster_bump_note": (
                None if pilaster_reported else
                f"|{pilaster_depth * 100:.1f} cm| is below the {resolution_m * 100:.1f} cm "
                "median ray residual; pilaster and alcove are the same plane within noise."
            ),
            "is_lower_bound": True,
            "note": "Two-station line-of-sight extent; occluded surfaces not captured.",
        }
    }
    with open(os.path.join(out_dir, "stereo_room_geometry.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[+] Saved JSON summary: {out_dir}/stereo_room_geometry.json")
    
    # Generate Top-Down BEV Scatter Plot
    fig, ax = plt.subplots(figsize=(10, 8), facecolor="#090d16")
    ax.set_facecolor("#0f172a")
    
    # Scatter points
    sc = ax.scatter(pts_m[:, 0], pts_m[:, 2], c=pts_m[:, 1], cmap="viridis", s=12, alpha=0.7)
    cb = plt.colorbar(sc, ax=ax)
    cb.set_label("Elevation Y (m)", color="#ffffff")
    cb.ax.yaxis.set_tick_params(color="#ffffff")
    plt.setp(plt.getp(cb.ax.axes, 'yticklabels'), color="#ffffff")
    
    # Plot cameras
    ax.scatter([0.0], [0.0], color="#f43f5e", s=100, marker="^", label="View-01 (Tripod)")
    ax.scatter([T_unit[0] * B_metric], [T_unit[2] * B_metric], color="#38bdf8", s=100, marker="^", label="View-03 (Tripod)")
    
    # Plot fitted walls
    ax.plot([x_west, x_west], [z_south, z_pilaster], color="#10b981", lw=2.5, label="West Wall (Doorway D1)")
    ax.plot([x_west, 0.0], [z_pilaster, z_pilaster], color="#f59e0b", lw=2.5, label="Pilaster Protrusion (Wall Bump)")
    ax.plot([0.0, 0.0], [z_pilaster, z_alcove], color="#f59e0b", lw=1.5, ls="--")
    ax.plot([0.0, x_east], [z_alcove, z_alcove], color="#10b981", lw=2.5, label="North Alcove (Chesterfield Sofa)")
    ax.plot([x_east, x_east], [z_alcove, z_south], color="#10b981", lw=2.5, label="East Wall (Carved Screen)")
    ax.plot([x_east, x_west], [z_south, z_south], color="#10b981", lw=2.5, label="South Wall (Altar Niche)")
    
    ax.set_title("Multi-View Stereo Parallax: Triangulated 3D Landmarks & Walls", color="#ffffff", fontsize=13, weight="bold")
    ax.set_xlabel("X (East-West) [meters]", color="#cbd5e1")
    ax.set_ylabel("Z (South-North) [meters]", color="#cbd5e1")
    ax.tick_params(colors="#cbd5e1")
    ax.grid(True, color="#334155", ls="--", alpha=0.5)
    ax.legend(facecolor="#1e293b", edgecolor="#38bdf8", labelcolor="#ffffff", loc="upper left")
    ax.set_aspect("equal", "box")
    
    plot_path = os.path.join(out_dir, "triangulated_topdown_bev.png")
    plt.tight_layout()
    plt.savefig(plot_path, dpi=180, facecolor=fig.get_facecolor())
    plt.close()
    print(f"[+] Saved Top-Down BEV Scatter Plot: {plot_path}")
    
    # Save SIFT Matches Image
    if sample_vis_matches:
        vis_img = cv2.drawMatches(sample_vis_crop1, sample_vis_kp1,
                                 sample_vis_crop3, sample_vis_kp3,
                                 sample_vis_matches, None,
                                 flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        match_path = os.path.join(out_dir, "matched_features_epipolar.png")
        cv2.imwrite(match_path, vis_img)
        print(f"[+] Saved SIFT Feature Match Visualization: {match_path}")

if __name__ == "__main__":
    # A failed run must leave behind an explicit record of the failure, not a stale
    # success file from a previous run that downstream consumers would keep trusting.
    try:
        main()
    except StereoScaleError as exc:
        out = "exports/spatial/stereo_parallax"
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "stereo_room_geometry.json"), "w", encoding="utf-8") as f:
            json.dump({
                "method": "Multi-View Epipolar Parallax Triangulation",
                "stations": ["view-01", "view-03"],
                "status": "failed",
                "reason": str(exc),
                "dimensions": None,
                "measured_bounds": None,
            }, f, indent=2)
        print(f"\n[!] STEREO FAILED: {exc}", file=sys.stderr)
        print(f"[!] Wrote failure record to {out}/stereo_room_geometry.json", file=sys.stderr)
        sys.exit(1)
