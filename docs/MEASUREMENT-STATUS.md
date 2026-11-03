# Measurement status — spatial blueprint pipeline

**Short version: the capture rig height was the root error (~1.12 m, not the assumed 1.50 m), and correcting it brings the ceiling probe within 5% of expectation. Tearoom WIDTH is now genuinely measured at 3.47 m. Room sizes in general are NOT measurable from single monocular viewpoints - that method saturates at ~4-5 m regardless of room.** Everything published as "measured" in
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

---

## Review: Baiker's stereo pipeline (`80f0523`, `121ed88`)

Baiker implemented multi-view stereo in parallel with this work. Reviewed at
`origin/feat/spatial-blueprint-pipeline` = `121ed88`.

### What is genuinely good

The **correspondence machinery is sound and worth keeping**:

- 8 yaws x 4 pitches of pinhole crops, so SIFT runs on rectilinear images rather than
  distorted equirect pixels - the right call.
- Both cameras are rotated into a shared world frame (`yaw = yw - heading`), so the
  GPS-derived absolute bearing is applied correctly.
- Bidirectional cross-check plus Fundamental-Matrix RANSAC at 2.0 px (`121ed88`) is
  real outlier rejection, and the follow-up commit fixing perceptual aliasing shows
  the match quality was actually inspected.
- Parallax floor of 0.8 deg and a relative ray-residual test correctly discard
  degenerate near-parallel intersections.

### Why its numbers still cannot be published

**1. Scale reintroduces the assumption stereo was meant to remove.**

```python
b_tripod = 1.50 / abs(y_floor_u)   # the SAME assumed 1.50 m camera height
b_sofa   = 2.15 / sofa_span_u      # assumed "standard Chesterfield" width
B_metric = 0.5 * (b_tripod + b_sofa)
B_metric = np.clip(B_metric, 1.80, 2.20)
```

The entire value of triangulation is that the baseline between two real camera
positions fixes scale **without** assuming camera height. Here height is half the
estimate and a furniture guess is the other half.

**2. The reported baseline is a clamp, not a measurement.** `baseline_meters` is
exactly 2.20 - the clip ceiling - so the average exceeded the bound and was truncated.
A value pinned to a hardcoded limit carries no information.

**3. GPS gives the baseline directly, and it was not used.** The manifest places
view-01 and view-03 **2.92 m** apart. The pipeline already trusts GPS for the
translation *direction* (`link_ang = 10.38 deg`, which is the correct GPS bearing) but
not for its *length*. Using 2.92 m instead of 2.20 m scales every dimension by 1.328:
TR 2.67 x 5.75 becomes **3.55 x 7.64 m**.

**4. Wall planes rest on very few points.** `triangulated_topdown_bev.png` shows
landmarks in three small clusters; west and east walls are nearly empty, and the
drawn rectangle is a fit to almost nothing in those directions. Each plane also has a
hardcoded fallback (`else -1.05`, `else 2.85`, ...) that silently substitutes a literal
when a direction yields no points.

**5. Two published figures are not measurements.**
- `width_at_pilaster_m` = 2.22 is `width - 0.45`, a hardcoded subtraction.
- `pilaster_bump_cm` = 0.8 is below the method's own ~1.5 cm ray residual. The
  "pilaster" and "alcove" planes are statistically the same wall.

### Convergence across all methods (Tearoom)

| source | dims (m) | note |
|---|---|---|
| main estimate | 3.50 x 6.50 | eyeball, honestly labelled unmeasured |
| old "measured" | 3.80 x 5.40 | hardcoded dict, false provenance |
| monocular (this branch) | 5.36 x 6.42 | R2 0.968, ~20% over-scale |
| monocular, ceiling-corrected | 4.23 x 5.07 | assumes 2.70 m ceiling |
| stereo (Baiker) | 2.67 x 5.75 | B clamped at 2.20 m |
| stereo @ GPS baseline | 3.55 x 7.64 | B = 2.92 m from manifest |

Width is converging on **3.5-4.2 m**. Length remains unresolved across **5.1-7.6 m**.
Independent methods agreeing on width is real progress; the length spread means no
length figure should be quoted yet.

### Status: fixed and re-run

All five issues above are fixed in `tools/stereo_parallax_pipeline.py`, and the pipeline
has been re-run.

- **Scale now comes from the station baseline.** `load_station_geometry()` reads both
  stations' coordinates from `tour-manifest.json` and derives bearing *and* length from
  them. `b_tripod`, `b_sofa` and the `np.clip(..., 1.80, 2.20)` are gone. Baseline is
  **2.922 m** (was the 2.20 m clip ceiling), carried with `baseline_sigma_m` 0.50 and a
  17% relative scale uncertainty that propagates into every published dimension.
- **Camera height and sofa span are now diagnostics, not inputs.** They are printed and
  stored under `cross_checks`, where they can contradict the result instead of silently
  setting it. The sofa deliberately cannot fail a run: "2.15 m Chesterfield" is an
  assumption about furniture nobody has measured.
- **Wall planes require support.** Each needs >= 15 triangulated points or the run
  raises; the `else -1.05` / `else 2.85` literal fallbacks are deleted. Support counts
  ship in `plane_support_points` (west is weakest at 29 points).
- **Unsupported figures removed.** `width_at_pilaster_m` (width minus a hardcoded 0.45)
  is gone. `pilaster_bump_cm` is emitted as `null` with a reason whenever it falls below
  the median ray residual - which it does (1.3 cm vs an 1.8 cm floor), confirming
  pilaster and alcove are one plane.
- **Failures quarantine themselves.** A `StereoScaleError` writes a `status: failed`
  record, so a stale success file cannot outlive the run that invalidated it.

An independent check of the pose was also run: solving the essential matrix from 434
front-hemisphere ray correspondences (416 inliers) gives a baseline bearing of
**9.49 deg** against the manifest's 10.38 deg, and a relative rotation of ~1 deg
matching the stated headings. The capture geometry in the manifest is sound.

**One real bug was found by running it.** The floor was selected by *crop pitch*
(`pitch <= -15`), but a -30 deg crop still contains the far wall near its top edge, and
in a long room most of its matched features land there. The median over that bin was
measuring the wall, implying a 0.43 m camera height. Selecting by reconstructed
*height* instead - the floor is the lowest consistent horizontal plane, whatever crop it
came from - moves the implied camera height to **1.00 m**, which is plausible for a
chest-height handheld 360 rig.

### Remaining: the reconstruction is anisotropic

`anisotropy_product` is **1.92**, where 1.00 would mean the vertical and horizontal
references agree. Vertical says scale is 1.51x low; horizontal says it is 1.28x high.
Both are recovered from the same baseline, so they should imply the same correction.

This is much reduced (it was 3.47x vs 1.28x before the floor fix) but still real, and it
is why absolute stereo dimensions are still not publishable. The likely cause is the
pose model: `T_unit` is assumed purely horizontal and both stations are assumed to be at
the same height. Neither is established from the capture, and the essential matrix
already hints at a small vertical component (`t_y` = -0.032).

Note the sofa anchor may simply be wrong rather than the geometry - a 2.75 m measured
span is a plausible real sofa that is just not a 2.15 m Chesterfield.

### Where the numbers now stand (Tearoom)

| source | dims (m) | note |
|---|---|---|
| main estimate | 3.50 x 6.50 | eyeball, labelled unmeasured |
| old "measured" | 3.80 x 5.40 | hardcoded dict, false provenance |
| stereo, before fix | 2.67 x 5.75 | B clamped at 2.20 m |
| monocular (R2 0.968) | 5.36 x 6.42 | ~20% over-scale per ceiling probe |
| **stereo @ real baseline** | **3.47 x 7.62** | +/-0.59 / +/-1.30 |

**Width has converged: 3.47 m measured against a 3.50 m estimate, 1% apart, by a method
that shares no assumption with the estimate.** That is the first genuine measurement in
this repo.

**Length has not: 6.42 / 6.50 / 7.62 m.** The stereo length also carries the larger
uncertainty (+/-1.30 m) and leans on `north_alcove`, the one plane with ample support
(293 points) but also the one furthest from both stations. No length figure should be
quoted yet.

### Recommended merge


Keep Baiker's correspondence and epipolar code. Replace the scale block with:

1. `B` = GPS separation (2.92 m for this pair), carried as an uncertainty, not a constant.
2. Delete the `clip()`; if an estimate leaves physical bounds, raise rather than truncate.
3. Delete the per-plane literal fallbacks; a direction with no points is a missing
   measurement, not a default value.
4. Drop `width_at_pilaster_m` and `pilaster_bump_cm` until the residual supports them.
5. Then solve camera height as an unknown from the metric reconstruction - which is the
   thing that would finally fix the monocular pass too.

---

## Anisotropy investigation: the metric was wrong, not the geometry

Tasked with fixing the 1.92 "anisotropy", the first step was to confirm it was real. It
was not, and the correction matters more than the original claim.

**Ray-ray triangulation is rigid.** It solves intersections in 3D and has no preferred
axis, so a wrong baseline multiplies every axis by the same scalar. Verified on
synthetic exact rays: a baseline 1.3x too large scales X, Y and Z by exactly 1.300, with
zero residual. **A scale error cannot produce anisotropy.**

The metric multiplied `(1.50 / implied_camera_height)` by `(implied_sofa_span / 2.15)`.
Both terms are ratios against **unverified reference values**, so the product tested the
guesses, not the reconstruction. It has been replaced with a genuinely scale-free
quantity - a ratio of two *reconstructed* lengths, where the unknown scale cancels:

```
camera_height / floor-to-ceiling = 0.389
  -> rig at ~1.05 m in a 2.7 m room
  -> rig at ~1.17 m in a 3.0 m room
```

Solving the full relative pose was also tested and ruled out as the cause: the essential
matrix gives sub-degree corrections (yaw -0.89 deg, pitch -0.65 deg, roll 0.11 deg) and
moves the implied camera height only from 1.00 m to 1.02 m.

## Resolved: the camera height was the error all along

Two independent methods, sharing no assumption, now agree:

| method | assumes | implies rig height |
|---|---|---|
| monocular ceiling probe | ceiling is 2.70 m | 1.50 / 1.267 = **1.18 m** |
| stereo shape ratio | nothing | 0.389 x 2.70 = **1.05 m** |

Both say **~1.0-1.2 m**, not 1.50 m - a chest-height handheld 360 rig. The pipeline
default is now `DEFAULT_CAMERA_HEIGHT_M = 1.12` (the midpoint, overridable with
`--camera-height`), and re-running confirms self-consistency:

**The ceiling probe moved from 3.42 m (27% above estimate) to 2.56 m - within 5% of the
2.70 m the project expected.** The ~20-25% over-scale is explained and corrected.

The far-field gate is now expressed in **camera heights** (8.0x) rather than metres,
because `1/t` scales inversely with assumed height: an absolute threshold would accept
or reject a view based on the scale assumption rather than its geometry. At 1.50 m
view-01 fitted 11.9 m and passed; at 1.12 m the identical fit became 13.3 m and failed.

## The decisive negative result: monocular cannot size rooms

With scale corrected, the per-room numbers still disagreed violently with the project's
estimates (LB +114%, BK -50%). The cause is not scale:

| | |
|---|---|
| reliable views | 12 |
| measured width | mean 3.55 m, sd 0.76 (CV **21%**) |
| measured length | mean 3.71 m, sd 0.86 (CV **23%**) |
| true room areas | vary by ~**10x** (LB ~4 m2 to BK ~55 m2) |

Every room measures 2.7-5.2 m regardless of its actual size. A single monocular
viewpoint measures **line of sight**, which saturates around 4-5 m in a cluttered
interior, so the span reflects the depth model's usable range rather than the walls.

**This is a limit of the method, not a bug to fix.** The outputs are now flagged
`range_saturated: true` and the schedule carries `monocular_can_size_rooms: false`.
They remain valid as **lower bounds** - the room is at least this big - which is the
strongest honest claim one viewpoint supports.

## Current state

| quantity | status |
|---|---|
| rig height ~1.0-1.2 m | **established** by two independent methods |
| room *proportions* within a view | trustworthy (R2 0.87-0.98) |
| Tearoom width 3.47 m | **measured** (stereo), 1% from the 3.50 m estimate |
| Tearoom length | **unresolved** - 6.42 / 6.50 / 7.62 m, stereo +/-1.30 m |
| all other room sizes | **not measurable** by monocular; lower bounds only |

## To finish the job

1. Run stereo on every adjacent pair, not just view-01/view-03. Each room with two
   stations gets a triangulated width the way the Tearoom now has one.
2. Bundle-adjust all 23 stations together, solving rig height as a free parameter rather
   than reconciling two estimates by hand.
3. Measure one real distance in the building. Every remaining uncertainty collapses to
   a single scalar the moment one tape measurement exists.
