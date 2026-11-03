# Measurement status — spatial blueprint pipeline

**Short version: room PROPORTIONS are now measured and trustworthy. Absolute SIZES are
still ~20% too large and must not be cited.** Everything published as "measured" in
commits `c2dd27d` and `d8324b4` was either a hand-entered estimate or the output of an
inverted depth model. The pipeline has since been fixed and re-run on GPU; this file
records what was wrong, what the re-run produced, and what remains before any absolute
number here can be cited.

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

## Pipeline has now been re-run (RTX 5090, torch 2.11+cu130)

Depth inference was re-run over all 23 panoramas with the corrected code. The
convention guard fired on live inference, confirming the diagnosis from the artifacts:

```
[!] Model emitted DEPTH (nadir 2.081 <= horizon 3.379); inverting to disparity.
[+] RANSAC Ground Fit: y = 0.6315 * d + (0.0842) [R2 = 0.968, corr = +0.819]
[+] Floor rays: 522,764 total, 31,899 inliers (64%)
```

Final state: **14 views calibrate reliably (R2 0.87-0.978), 9 are rejected.**
Rejections are honest refusals, not failures to produce output:

| reason | count | meaning |
|---|---|---|
| far-field range 1/t > 12 m | 5 | extent would be set by the distance cull, not walls |
| ground-ray correlation < +0.30 | 3 | nadir occluded by tripod/clutter; no usable floor |
| refit shift t <= 0 | 1 | implies infinite/negative range at the horizon |

Two further defects were found and fixed only because the run happened:

1. **Cross-frame union.** `load_calibrated_boxes` unioned per-view bounds, but each
   cloud sits in its own tripod-centred frame. Overlaying two local frames produced an
   "entrance lobby" of 7.6 x 11.0 m. Now the largest single-view span is used and the
   per-view spans are published so disagreement is visible.
2. **Far-field divergence.** `t` constrained only during RANSAC sampling, not the
   refit. view-06 came back with t = -0.0067 (negative distance at the horizon) while
   still reporting R2 = 0.962 - the floor cone constrains the near field only, so a high
   R2 does not imply a sane far field.

`room_schedule.json` is now **8 of 9 rooms calibrated** (TB falls back to hand estimate;
both its views were rejected).

## The absolute scale is still wrong, and we can prove it

Ceiling height is an independent probe: it was never fitted, so it tests the one
assumption everything rests on. Across reliable views the ceiling lands at
**3.10-3.42 m (median 3.42)** against this project's own 2.6-2.9 m estimate.

That is a consistent ~15-25% over-scale, and it points at `camera_height = 1.50 m`.
If the true ceiling is 2.70 m, the implied capture height is 1.50 / (3.35/2.70) =
**~1.21 m** - plausible for a handheld or low-tripod 360 rig, and not 1.50 m.

The code records `ceiling_probe_m` per view but deliberately does **not** rescale by it.
The expected ceiling height is itself an estimate; folding one guess into another would
launder a guess into a measurement. Scale needs one real reference, not a second guess.

So: room *proportions* are now trustworthy (views within a room agree - AS reads
3.86x3.58, 3.78x4.19, 4.24x4.29 across three viewpoints). Absolute *dimensions* are
still systematically inflated by an unknown factor near 1.2.

## Multi-view parallax (stereo triangulation): yes, and it is the right next step

Asked whether real sizes can come from stereo instead of monocular depth. Checked, and
the tour geometry supports it well:

- **Baselines are usable.** GPS positions give a mean consecutive spacing of **3.73 m**
  (2.8-3.0 m within rooms), and all 23 positions are distinct.
- **Overlap is ample.** ORB matching on consecutive pairs yields **317-395 good matches**
  (Hamming < 50) per pair at 2048x1024.
- **Precision is far better than monocular.** For spherical stereo,
  `dR = R^2 * dtheta / B`. At 10000 px equirect width, dtheta = 0.63 mrad, so with
  B = 2.8 m at R = 3 m the error is ~0.2 cm per matched pixel; even at 5 px matching
  error that is **~5 cm at 3 m range**.

The decisive advantage is not precision but **provenance**: triangulation derives scale
from the baseline between two real camera positions, so it needs no assumed camera
height at all. It replaces the single assumption that is currently wrong.

Caveats worth planning around: GPS baselines indoors are themselves uncertain and should
be solved rather than trusted (bundle adjustment over the matches, using GPS only as an
initial guess); textureless walls will not match and will leave holes that monocular
depth can fill; and 2.8 m baselines inside 4 m rooms mean wide-angle geometry with real
occlusion between views.

Recommended order: solve relative poses from the ORB matches, triangulate the matched
points, use that metric reconstruction to **solve camera height as an unknown** rather
than assume it, then re-run the monocular pass with the solved height to densify.

## What is still NOT done


1. **Camera height is assumed, not measured.** `camera_height = 1.50 m` sets the absolute
   scale of everything. A 10% error there is a 10% error in every dimension. The real
   tripod height for the Nov-2017 capture is unknown.
2. **Single-viewpoint spans are lower bounds.** One tripod position cannot see occluded
   corners, so a calibrated box is a floor on the room's size, not its dimensions.
3. **Wall thickness (200 mm), door widths and stair counts are unverified** design
   choices, not observations.
4. **Multi-view registration is unvalidated.** `align_multi_bev.py` has no loop-closure
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
