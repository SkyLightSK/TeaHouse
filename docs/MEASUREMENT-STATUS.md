# Measurement status — spatial blueprint pipeline

**Short version: this branch contains no surveyed dimensions.** Everything published as
"measured" in commits `c2dd27d` and `d8324b4` was either a hand-entered estimate or the
output of an inverted depth model. This file records what was wrong, what is fixed, and
what still has to run before any number here can be cited.

## The three defects

### 1. The depth convention was inverted (fatal)

`tools/pano_depth_calibrated.py` fitted `1/R = s·d + t` on floor rays, treating the
model output as disparity (inverse depth, near = high). The stored maps are the
opposite. Measured from the committed artifacts:

| elevation band φ | mean stored value |
|---|---|
| −90°..−75° (nadir, closest floor) | 0.026 |
| −45°..−30° | 0.361 |
| −15°..0° (horizon, farthest) | 0.410 |

The nearest floor carries the *lowest* value. The fit therefore mapped near pixels to
far distances. Every stored slope was negative (`s = −0.09 … −0.37`), which is
physically impossible for disparity, and the published R² of 0.04–0.56 is a clean fit
of a backwards model — not a noisy fit of a correct one.

### 2. Per-face normalization destroyed cross-face comparability

Each of the 6 cubemap faces was independently rescaled to [0,1] by its own 1st/99th
percentile. A face looking at a near wall and a face looking down a long corridor both
spanned the full range, so no single global `(s, t)` could describe the sphere.

### 3. The blueprint never read the pipeline

`tools/fit_manhattan_blueprint.py` contained a hardcoded `measured_boxes` dict labelled
"Calibrated via 6-face cubemap perspective decomposition and 2-parameter (s, t) affine
regression". Nothing in that function ever opened a calibration summary. Those literals
flowed into `measured_room_schedule.json`, the DXF/SVG, the Blender venue, and the
dashboard — gaining authority at each hop. This is the defect that actually put wrong
numbers in front of people.

## What is fixed

- **Convention guard.** The nadir cube face is compared against the side-face horizon
  per panorama; if the model emitted depth, it is inverted once, before use.
- **Shared normalization.** All 6 faces normalize on one scale.
- **Real RANSAC** with physical constraints (`s > 0`, `t ≥ 0`) on a 0.03 m⁻¹ inlier band,
  replacing plain least squares that furniture could drag.
- **Sign gate.** Ground-ray correlation below +0.30 raises `CalibrationError` and the
  view is **skipped**, not back-filled.
- **Honest extents.** Room span uses the 1/99 percentile, not 5/95 — the walls *are* the
  extremes, so the old clip shrank every room by ~10% of its span before any other error.
- **Provenance.** Every room carries `provenance.source` of `calibrated` or
  `hand_estimate`. `fit_manhattan_blueprint.py` now reads per-view summaries via
  `load_calibrated_boxes()` and prefers them where reliable.
- **Renamed output.** `measured_room_schedule.json` → `room_schedule.json`, with
  `rooms_calibrated` / `rooms_hand_estimated` / `all_dimensions_measured` counters.

### Effect on the fit

Re-running the corrected calibrator against the committed disparity maps, inverted to
the proper convention:

| view | old s | old R² | new s | new R² |
|---|---|---|---|---|
| view-01 | −0.322 | 0.378 | **+0.286** | **0.904** |
| view-02 | −0.261 | 0.271 | **+0.262** | **0.909** |
| view-03 | −0.090 | 0.040 | — | *rejected (corr +0.19)* |
| view-05 | −0.361 | 0.477 | **+0.417** | **0.947** |
| view-06 | −0.287 | 0.330 | **+0.361** | **0.929** |
| view-11 | −0.278 | 0.347 | **+0.187** | **0.777** |
| view-14 | −0.370 | 0.564 | **+0.453** | **0.961** |
| view-16 | −0.291 | 0.421 | **+0.213** | **0.844** |
| view-22 | −0.309 | 0.287 | **+0.294** | **0.889** |

8 reliable, 1 honestly rejected. Implied distances are now monotonically decreasing in
disparity and land in the 1.6–4.5 m range appropriate to these interiors.

## What is still NOT done

1. **Depth inference has not been re-run.** No torch/CUDA in this environment. The table
   above recalibrates *stored* maps; it does not regenerate them. Until
   `pano_depth_calibrated.py --all` runs on a GPU box, the point clouds, BEV rasters and
   per-view summaries on disk are still the old inverted ones.
2. **All 9 room boxes remain hand estimates.** `rooms_calibrated` is 0.
3. **Camera height is assumed, not measured.** `camera_height = 1.50 m` sets the absolute
   scale of everything. A 10% error there is a 10% error in every dimension. The real
   tripod height for the Nov-2017 capture is unknown.
4. **Single-viewpoint spans are lower bounds.** One tripod position cannot see occluded
   corners, so a calibrated box is a floor on the room's size, not its dimensions.
5. **Wall thickness (200 mm), door widths and stair counts are unverified** design
   choices, not observations.
6. **Multi-view registration is unvalidated.** `align_multi_bev.py` has no loop-closure
   residual, so global layout error is unquantified.

## Do not do with this data

- Do not overwrite `source/floorplan/space-codes.json` or `GOALS.md` estimates. Those are
  honestly labelled `"measured": false`; these numbers are not better-founded.
- Do not cite the `BK` or `LB` figures. The branch's `BK` (31 m²) and main's estimate
  (55 m²) disagree by ~75%, and nothing here resolves which is closer.
- Do not present DXF/SVG output as a survey drawing.

## To actually get measurements

1. Re-run `pano_depth_calibrated.py --all` on a CUDA machine with the fixed code.
2. Establish real camera height, or solve it as a third parameter against a known
   in-scene reference (a door leaf, a step riser).
3. Add loop-closure residuals to `align_multi_bev.py` and report drift.
4. Validate against one hand-measured ground truth distance in the real space.
5. Only then let `load_calibrated_boxes()` promote rooms to `calibrated`.
