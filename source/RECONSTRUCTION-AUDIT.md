# TeaHouse reconstruction audit

Reviewed 2026-11-01. This is a source inspection and acquisition proposal, not a verified survey or runtime test. Existing local modifications to GOALS.md, StubRoom.tsx, and teahouse.room.json were preserved.

Follow-up: the initial inventory below predates the subsequent acquisition of [23 reference panoramas](captures/panoramas/README.md). See [the floor-plan comparison](floorplan/panorama-comparison.md) for evidence-based findings from that historical November 2017 tour. No measured Blender reconstruction has been produced yet.

## Assessment

Keep the portable architecture (`source → spec → exports → runtimes`). The project has a useful procedural room prototype and multiplayer scaffolding, but does not yet contain the evidence needed for an accurate reconstruction. Prioritize verified geometry and source acquisition before detailed props.

### Evidence in this checkout

| Item | Finding | Consequence |
|---|---|---|
| Capture folders | Only placeholders; no photos, videos, panoramas, scans, or splats | The asset plan's “many photos” are not available here |
| Existing visual references | Floor-plan PNG/PSD and a carved-screen image | Useful starting references, not a dimensional survey |
| Floor-plan measurements | Explicitly approximate, around 10–20%; 9 rooms | Treat dimensions as estimates |
| Current room spec | 12 rooms, 14 doorways, 3 floor levels; `capturedAt: null` | More developed layout, but no measurement provenance |
| Documentation drift | Books hall is 8 × 5 m in measurements and 12 × 6 m in JSON; spawn centers and room IDs also differ | Reconcile against evidence, not by copying one into the other |
| Master assets | No `.blend`, GLB, or populated export bundle in the inspected source/export tree | Export scripts exist, but there is nothing real to export yet |
| Web scene | `Scene.tsx` always renders `StubRoom` with warehouse environment lighting | Real asset loading, collider handling, and lighting integration still need implementation |
| Interactions | Client renders primitive props; server toggles ownership | Drinking behavior remains incomplete; independent of reconstruction |
| Server spawn | Hardcoded `[0,0,3.5]`, versus spec entrance `[1,0,0]` | Coordinate authority needs reconciliation before integration |
| Validation | JSON Schema validation only | A passing schema does not prove doorway alignment, walkability, or survey accuracy |
| Local tooling | Node available; pnpm and Blender not found on PATH; no root node_modules | No runtime/build/export validation performed; this does not prove Blender is not installed elsewhere |

The plan image has no dimension annotations. Its labels, walls, openings, and stair marks are useful topology evidence, but scaling the drawing alone cannot establish real dimensions. The north/east labels used in project coordinates should not be assumed to be surveyed geographic orientation.

## Google Maps: distinguish three different inputs

1. **Indoor Street View / business panoramas:** spherical photographs from individual camera positions. Looking around one panorama changes viewing direction, not camera position. It does not expose a complete room mesh. Multiple actual camera positions may support reconstruction if overlap and image quality are sufficient.
2. **Photorealistic 3D Tiles:** textured exterior meshes derived from satellite/aerial imagery, intended for compatible map renderers. They are not an indoor survey. See [Google's Map Tiles overview](https://developers.google.com/maps/documentation/tile/overview).
3. **Original photographer files:** independent source photographs or panoramas obtained directly with appropriate reuse permission. These are the preferred inputs for a portable Blender asset.

Google's standard [Maps Platform terms, section 3.2.3](https://cloud.google.com/maps-platform/terms) restrict extraction outside the services, caching, and creating content from Maps content. [Map Tiles policies](https://developers.google.com/maps/documentation/tile/policies) also restrict offline use and non-visualization extraction. A paid API key is not an offline asset license. Attribution alone does not resolve those restrictions. For ordinary Maps use, also consult the [Maps additional terms](https://www.google.com/help/terms_maps/).

Therefore, browser tile stitching or GPU mesh capture is not the proposed production pipeline. Obtain originals from the rights holder, or use independently captured/licensed sources. The business owner may not own the photographer's copyright; establish who can authorize textures, reconstruction, and redistribution. Do not automatically apply the repository's CC-BY-NC label to third-party material.

The repository's Maps short link could not be opened by the research browser. The venue identity, current imagery, capture dates, and number of available indoor viewpoints remain unverified.

## Corrections to the old asset plan

- Street View Static API returns a selected view controlled by heading, pitch, and field of view; it is not an arbitrary-resolution full equirectangular downloader. [Official request documentation](https://developers.google.com/maps/documentation/streetview/request-streetview).
- Street View Tiles can supply panorama tiles and metadata for a compliant viewer; that functionality does not authorize baking them into a redistributed GLB. [Official tile documentation](https://developers.google.com/maps/documentation/tile/streetview).
- Saving an LDR JPEG as HDR/EXR does not recover clipped brightness or real scene lighting range. Use it as an LDR reference/environment where licensed; obtain bracketed captures for measured HDR lighting.
- A single panorama or AI depth prediction cannot establish hidden surfaces or reliable metric scale. Generated geometry should be marked inferred.
- Ordinary overlapping photographs can support room reconstruction. A 360 video is not required for photogrammetry, and a video alone does not guarantee a useful reconstruction. [COLMAP's tutorial](https://colmap.github.io/tutorial.html) describes sparse camera/point recovery followed by dense reconstruction.
- AI props can approximate appearance; they do not provide evidence of dimensions or unseen shapes.
- Loading a GLB requires more than a one-line swap: asset delivery, collider separation, object IDs, interactive props, coordinate conversion, and runtime lighting need explicit integration.
- Exporting a Blender world environment is not equivalent to packaging runtime environment lighting; plan that asset separately.
- The exFAT/Linux mirror instructions describe an older environment. This checkout is on Windows at `E:\Projects\TeaHouse`; determine actual filesystem/tool requirements before following those instructions.

## Acquisition plan

First confirm the venue, interior/exterior scope, and target date of the reconstruction. A current model and a recreation of an older interior may require different sources. Do not silently combine furniture or wall layouts from different dates.

Create an evidence register as material arrives: source ID, original file/URL, photographer, capture date (unknown if unavailable), room/viewpoint, permitted uses, dimensions, and confidence. For measurements record endpoints, units, method, uncertainty, and source IDs. Keep measured, inferred, and unknown values distinct.

**If on-site capture is possible:**

- Measure room wall lengths and at least one diagonal, ceiling heights, door offsets/widths/heights, and wall thickness where accessible.
- Record each floor elevation relative to one stable entrance datum; measure stair risers, treads, count, and direction.
- Capture overlapping photographs while moving through each room, including corners and both sides of doorways. Avoid relying on rotation from one position. Keep lighting and furniture stable where practical.
- Capture several connected 360 positions for visual coverage, plus close-ups of distinctive furniture and materials. Include scale references and record camera locations/heights where possible.
- Reserve several measurements and photographs for independent validation rather than fitting.

**If reconstruction must be remote:** request the original virtual-tour files and any measured plan from the owner/photographer. Multiple connected panorama positions are more useful than many crops from one position. With only isolated pictures and no scale anchors, build an explicitly approximate reconstruction and list uncertainties; do not promise survey accuracy.

## Blender workflow

1. **Pilot one connected area:** tearoom → teabar → corridor, including a doorway. Establish evidence quality and scale before committing to the whole building.
2. **Create a measured shell:** meters, native Blender Z-up; walls, floors, openings, ceilings, and stairs. Use the existing JSON only as a provisional layout reference. Represent shared walls once rather than blindly copying each room's independent wall slabs.
3. **Align source imagery/scans:** use photogrammetry where suitable, then align and scale it to measured anchors. Licensed panoramas can support manual camera matching. If converting panoramas to perspective views, preserve the fact that views from one panorama share a camera center; those crops are not independent capture positions.
4. **Check architecture first:** compare held-out dimensions and matched camera views. Log residuals and unobserved areas. Set tolerances according to the available measurement method; do not infer precision from visual plausibility.
5. **Add appearance:** model furniture to measured bounds, project licensed photographs where useful, and clean up scan geometry. Keep optional splats separate from the walkable collision shell.
6. **Separate scene roles:** render meshes, simple `collider_*` proxies, `spawn_*`/`sit_*` markers, interactive props, and lights. Keep reference imagery/scans in excluded collections.
7. **Export and integrate:** use `source/rooms/teahouse.blend` as the planned master, export GLB, implement the web loader/colliders, and synchronize runtime metadata through one documented authority. Avoid duplicating cups or lights between the GLB and JSON-driven components.

Coordinate contract: the current spec is Y-up. With the intended default glTF axis conversion, a spec position `(x,y,z)` corresponds to Blender `(x,-z,y)`. Confirm this with asymmetric markers and a known facing direction before a full export; rotations require their own conversion check.

## First milestone and acceptance

A verified pilot is complete when it has a source register, dimensioned plan, Blender shell, comparison views, and an error/unknowns list. Its exported GLB must preserve scale and orientation, align spawn/seats/props, and allow walking through the doorway without collision problems.

Then extend to the remaining rooms and stairs. Validate room connectivity, boundary openings, elevation transitions, and navigation in addition to JSON Schema compliance. Detailed decorations and tea interactions can follow without holding up the spatial survey.

Pending inputs: current venue link/name, whether the surrounding street is in scope, whether new capture is possible, and whether original panorama files can be obtained. No imagery was downloaded and no existing layout values were changed during this audit.
