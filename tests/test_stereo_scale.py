#!/usr/bin/env python3
"""
Regression tests for scale handling in tools/stereo_parallax_pipeline.py.

These lock down the defect that made the stereo run look authoritative: scale was
recovered from an assumed camera height averaged with an assumed sofa width, then
clipped into [1.80, 2.20] - and the clip ceiling was published as `baseline_meters`.

Run:  python3 tests/test_stereo_scale.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "sp", Path(__file__).resolve().parents[1] / "tools" / "stereo_parallax_pipeline.py"
)
sp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sp)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "source" / "captures" / "panoramas" / "tour-manifest.json"


def _manifest(views):
    fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump({"views": views}, fh)
    fh.close()
    return fh.name


def test_baseline_comes_from_gps_not_assumptions():
    """Baseline must be the real station separation, ~2.92 m, not a clamp at 2.20."""
    _, _, bearing, baseline = sp.load_station_geometry(str(MANIFEST), "view-01", "view-03")
    assert abs(baseline - 2.92) < 0.05, f"expected ~2.92 m, got {baseline:.3f}"
    assert abs(bearing - 10.38) < 0.5, f"expected ~10.38 deg, got {bearing:.2f}"
    assert not (1.79 < baseline < 2.21), "baseline fell inside the old clamp range"
    print(f"  PASS baseline from GPS ({baseline:.2f} m, bearing {bearing:.2f} deg)")


def test_no_clip_to_hardcoded_bounds():
    """The old np.clip(B, 1.80, 2.20) must be gone from the source."""
    src = (ROOT / "tools" / "stereo_parallax_pipeline.py").read_text()
    assert "np.clip(B_metric" not in src, "baseline is still clamped"
    assert "2.15 / sofa_span" not in src, "sofa still sets scale"
    assert "1.50 / abs(y_floor_u)" not in src, "camera height still sets scale"
    print("  PASS scale no longer derived from assumptions or clamped")


def test_rejects_degenerate_baselines():
    """Too-short and implausibly-long baselines must raise, not silently proceed."""
    for lat2, label in ((46.47921717984453, "zero"), (46.60, "huge")):
        path = _manifest([
            {"view_id": "a", "lat": 46.47921717984453, "lng": 30.740971554693285, "heading": 0},
            {"view_id": "b", "lat": lat2, "lng": 30.740971554693285, "heading": 0},
        ])
        try:
            sp.load_station_geometry(path, "a", "b")
        except sp.StereoScaleError:
            continue
        raise AssertionError(f"{label} baseline should have been rejected")
    print("  PASS degenerate baselines rejected")


def test_missing_gps_is_an_error():
    """A station without coordinates cannot yield a baseline; it must not default."""
    path = _manifest([
        {"view_id": "a", "lat": 46.479, "lng": 30.741, "heading": 0},
        {"view_id": "b", "heading": 0},
    ])
    try:
        sp.load_station_geometry(path, "a", "b")
    except sp.StereoScaleError:
        print("  PASS missing GPS raises instead of defaulting")
        return
    raise AssertionError("missing GPS must raise")


def test_published_output_is_honest():
    """If a geometry file exists, it must carry provenance and uncertainty."""
    out = ROOT / "exports" / "spatial" / "stereo_parallax" / "stereo_room_geometry.json"
    if not out.exists():
        print("  SKIP no stereo output present")
        return
    d = json.loads(out.read_text())
    if d.get("status") == "failed":
        assert d.get("dimensions") is None, "failed run must not publish dimensions"
        print("  PASS failed run publishes no dimensions")
        return
    assert d["scale_source"].startswith("station baseline"), "scale provenance missing"
    assert d["baseline_meters"] != 2.2, "baseline is still the old clamp ceiling"
    dims = d["dimensions"]
    for k in ("width_uncertainty_m", "length_uncertainty_m"):
        assert k in dims, f"{k} missing; dimensions published without uncertainty"
    assert "width_at_pilaster_m" not in dims, "hardcoded 0.45 m subtraction is back"
    bump = dims.get("pilaster_bump_cm")
    if bump is not None:
        assert abs(bump) / 100.0 > d["median_ray_residual_m"], "sub-noise bump published"
    print("  PASS published geometry carries provenance and uncertainty")


if __name__ == "__main__":
    failures = 0
    for fn in (
        test_baseline_comes_from_gps_not_assumptions,
        test_no_clip_to_hardcoded_bounds,
        test_rejects_degenerate_baselines,
        test_missing_gps_is_an_error,
        test_published_output_is_honest,
    ):
        try:
            fn()
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL {fn.__name__}: {exc}")
    print("OK" if not failures else f"{failures} FAILED")
    sys.exit(1 if failures else 0)
