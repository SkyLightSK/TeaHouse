#!/usr/bin/env python3
"""
Regression tests for the ground-plane calibration in tools/pano_depth_calibrated.py.

These lock down the defect that produced the branch's published "measurements":
a model fitted with an inverted depth convention, yielding unphysical negative
slopes that still reported a plausible-looking R-squared.

Run:  python3 tests/test_calibration.py
"""
import sys
import types
import importlib.util
from pathlib import Path

import numpy as np

# Stub the GPU stack so the module imports without torch/transformers installed.
for _name in ("torch", "transformers", "ezdxf"):
    sys.modules.setdefault(_name, types.ModuleType(_name))
sys.modules["torch"].cuda = types.SimpleNamespace(is_available=lambda: False)
sys.modules["transformers"].pipeline = lambda *a, **k: None

_spec = importlib.util.spec_from_file_location(
    "cal", Path(__file__).resolve().parents[1] / "tools" / "pano_depth_calibrated.py"
)
cal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cal)

H, W = 512, 1024
CAM_H = 1.50


def _phi_grid():
    phi = (0.5 - (np.arange(H) + 0.5) / H) * np.pi
    return np.tile(phi[:, None], (1, W))


def synthetic_disparity(s=0.35, t=0.25, noise=0.0, seed=0):
    """Build a disparity map consistent with 1/R = s*d + t over a flat floor."""
    phi2 = _phi_grid()
    inv_R = np.abs(np.sin(phi2)) / CAM_H
    d = (inv_R - t) / s
    if noise:
        d = d + np.random.default_rng(seed).normal(0, noise, d.shape)
    return np.clip(d, 0.0, 1.0)


def test_recovers_known_parameters():
    s_true, t_true = 0.35, 0.25
    s, t, r2 = cal.calibrate_affine_scale_and_shift(
        synthetic_disparity(s_true, t_true), camera_height=CAM_H
    )
    assert s > 0, f"slope must be positive, got {s}"
    assert abs(s - s_true) < 0.05, f"s={s} vs {s_true}"
    assert abs(t - t_true) < 0.05, f"t={t} vs {t_true}"
    assert r2 > 0.95, f"R2={r2}"
    print(f"  PASS recovers known params (s={s:.3f}, t={t:.3f}, R2={r2:.3f})")


def test_rejects_inverted_disparity():
    """The exact defect: a depth map fed in where disparity is expected."""
    inverted = 1.0 - synthetic_disparity()
    try:
        s, t, r2 = cal.calibrate_affine_scale_and_shift(inverted, camera_height=CAM_H)
    except cal.CalibrationError as exc:
        print(f"  PASS rejects inverted input ({str(exc)[:52]}...)")
        return
    raise AssertionError(f"inverted map must be rejected, fitted s={s:.4f} R2={r2:.3f}")


def test_never_returns_negative_slope():
    """No input may yield s < 0; that is physically impossible for disparity."""
    rng = np.random.default_rng(7)
    for i in range(12):
        noisy = np.clip(synthetic_disparity(noise=0.12, seed=i), 0, 1)
        try:
            s, _, _ = cal.calibrate_affine_scale_and_shift(noisy, camera_height=CAM_H)
        except cal.CalibrationError:
            continue
        assert s > 0, f"negative slope {s} leaked through on seed {i}"
    for i in range(6):
        noise_only = rng.random((H, W)).astype(np.float32)
        try:
            s, _, _ = cal.calibrate_affine_scale_and_shift(noise_only, camera_height=CAM_H)
        except cal.CalibrationError:
            continue
        assert s > 0, f"negative slope {s} leaked through on pure noise {i}"
    print("  PASS never returns a negative slope")


def test_robust_to_furniture_outliers():
    """Furniture in the floor cone must not drag the fit the way lstsq did."""
    d = synthetic_disparity(0.35, 0.25)
    rng = np.random.default_rng(3)
    mask = rng.random(d.shape) < 0.25
    d[mask] = np.clip(d[mask] + 0.35, 0, 1)
    s, t, r2 = cal.calibrate_affine_scale_and_shift(d, camera_height=CAM_H)
    assert s > 0
    assert abs(s - 0.35) < 0.12, f"RANSAC dragged by outliers: s={s}"
    print(f"  PASS robust to 25% outliers (s={s:.3f}, R2={r2:.3f})")


def test_stored_artifacts_are_valid():
    """
    The committed disparity maps are now regenerated under the corrected convention,
    so every one that calibrates must do so with a physical, non-divergent fit.
    (Before the fix these were all inverted and every stored slope was negative.)
    """
    import cv2
    root = Path(__file__).resolve().parents[1]
    maps = sorted(root.glob("exports/spatial/*_calibrated/calibrated_disparity.png"))
    if not maps:
        print("  SKIP no stored artifacts present")
        return
    fitted = rejected = 0
    for m in maps:
        im = cv2.imread(str(m), cv2.IMREAD_UNCHANGED)
        if im is None:
            continue
        if im.ndim == 3:
            im = im[..., 0]
        try:
            s, t, _ = cal.calibrate_affine_scale_and_shift(im.astype(np.float32) / 255.0, CAM_H)
        except cal.CalibrationError:
            rejected += 1          # an honest refusal is a valid outcome
            continue
        assert s > 0, f"{m.parent.name}: negative slope {s}"
        assert t > 0, f"{m.parent.name}: non-positive shift {t}"
        assert 1.0 / t <= cal.MAX_PLAUSIBLE_RANGE_M, f"{m.parent.name}: divergent far field"
        fitted += 1
    assert fitted > 0, "no stored map calibrated successfully"
    print(f"  PASS {fitted} stored maps fit physically, {rejected} honestly rejected")


if __name__ == "__main__":
    failures = 0
    for fn in (
        test_recovers_known_parameters,
        test_rejects_inverted_disparity,
        test_never_returns_negative_slope,
        test_robust_to_furniture_outliers,
        test_stored_artifacts_are_valid,
    ):
        try:
            fn()
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL {fn.__name__}: {exc}")
    print("OK" if not failures else f"{failures} FAILED")
    sys.exit(1 if failures else 0)
