# Source Authoring Conventions

This file is the contract between **how you author the master Blender scene** and **how every runtime adapter reads the exported asset bundle**. Following these rules makes the bundle truly portable across web (R3F), Spatial.io, Mozilla Hubs, VRChat, Unreal, and any future runtime.

## Folder roles

| Folder | What goes here | Edit by hand? |
|---|---|---|
| `source/rooms/` | The master `.blend` per room (e.g. `teahouse.blend`) | Yes |
| `source/props/` | One `.blend` per stand-alone prop (teacup, teapot, screen, …) | Yes |
| `source/captures/photos/` | Raw phone photos of the real space | Drop in |
| `source/captures/videos/` | Walkthrough video files | Drop in |
| `source/captures/raw-splats/` | `.ply` from Luma / Polycam / Postshot | Drop in |
| `source/captures/raw-photogrammetry/` | `.obj` / `.fbx` from Meshroom / RealityCapture | Drop in |
| `source/textures/` | Source PBR textures (4K PNG / EXR) | Yes |
| `source/references/` | Mood-board images, the Google Maps screenshot, the carved screen photo | Yes |

## Master scene rules

1. **Units = meters.** Set in Blender: `Scene Properties > Units > Unit System: Metric, Unit Scale: 1.0`.
2. **Up = +Z in Blender (default).** The exporter converts to +Y for glTF automatically.
3. **One scene per file.** `source/rooms/teahouse.blend` contains exactly one Blender scene.
4. **Apply transforms before export** (Object > Apply > All Transforms). The export script does this for meshes, but armatures need it manual.
5. **PBR metalness-roughness materials only.** No proprietary shaders. Use the **Principled BSDF** node only. Custom shaders won't survive glTF / FBX / USD round-trips.
6. **Textures**: PNG for albedo + alpha, packed normal/roughness/metalness when possible. Resolutions: 2K for hero props, 4K only for the room shell, 1K for filler.
7. **No driver expressions, no Geometry Nodes for runtime geometry.** Apply / bake to mesh first.

## Portable object naming convention

Every interactive element is recognized by **object name prefix**. The export pipeline copies any custom properties you set on these objects into glTF `extras`, where every runtime can read them.

| Prefix | Example name | Object type | Custom properties | What it becomes |
|---|---|---|---|---|
| `collider_` | `collider_walls` | Mesh | `kind: static\|dynamic` | Invisible physics proxy. Rendered hidden. |
| `spawn_` | `spawn_entrance` | Empty (Plain Axes) | `priority: int` (default 1) | Player spawn point. Empty's +Y rotation = facing direction. |
| `sit_` | `sit_couch_left` | Empty (Single Arrow, +Y forward) | `kind: chair\|couch\|floor\|stool\|bench` | Snap-to-seat point. |
| `interactable_` | `interactable_teacup_1` | Mesh | `kind: pickup\|toggle\|button\|door`, `event: <id>`, `respawnAfter: float` | Clickable / pickup-able. |
| `light_` | `light_lantern_main` | Light (Point/Spot/Sun/Area) | preserved automatically (color, intensity, distance) | Native glTF light via `KHR_lights_punctual`. |
| `audio_` | `audio_rain_outside` | Empty | `src: <relative path>`, `volume: 0..1`, `loop: bool`, `radius: float` | Positional or global sound. |
| `portal_` | `portal_courtyard` | Empty | `to: <room id>` | Future: doorway to another room. |
| `cam_` | `cam_hero_1` | Empty | `kind: hero\|orbit` | Suggested camera angle. |

### How to set custom properties in Blender

1. Select the object.
2. Properties Editor > **Object Properties tab** (orange square icon).
3. Scroll to **Custom Properties** panel at the bottom.
4. Click **New**, give it a name (e.g. `kind`) and value (e.g. `couch`).
5. Click the gear icon next to it > **Edit Property** to change the type if needed (string / int / float / bool).

### Why this works portably

- glTF 2.0 spec defines `extras` on every node — preserved by every glTF importer.
- Mozilla Hubs uses an identical pattern via `MOZ_hubs_components`.
- Our spec-driven runtimes read both `spec/teahouse.room.json` (canonical) **and** the glb extras (in-context), so authors can edit either side.

## Texture and material rules

- **Albedo**: sRGB color space, alpha for cutouts (e.g. the carved screen).
- **Normal**: Non-Color, +Y up convention (glTF / Unity / Unreal all agree on this).
- **Roughness + Metalness**: Non-Color, packed into a single image as G=roughness, B=metalness if you want one less texture. The exporter handles this.
- **Emissive**: sRGB color, used for lanterns, candles, screens.
- **No baked-in lighting in albedo.** The export-time lights handle illumination per runtime.

## Carved-screen specific recipe

The hand-carved screen in [`source/references/carved-screen-reference.png`](references/carved-screen-reference.png) is our hero prop. Photogrammetry will fail on the lattice cutouts. Recipe:

1. In `source/props/carved-screen.blend`, model **flat planes** (one per panel) with the correct silhouette only.
2. Take a high-res orthographic photo of the screen lit from behind (so you can see the cutouts as silhouette).
3. In an image editor, mask out the wood vs cutout to get a clean **alpha matte**.
4. Use the original colored photo as albedo, the alpha matte as alpha channel.
5. Bake a normal map from a high-poly version of one panel (or use **CrazyBump** / **Materialize** to derive a normal from the photo).
6. Apply with Principled BSDF: alpha clip mode = "Hashed" or "Clipped".
7. Object name: `interactable_carved_screen` if you want it clickable, otherwise just `carved_screen`.

## Versioning

- Bump `spec/teahouse.room.json` `version` field on every meaningful change (semver).
- Tag git commits when you produce an exports/ snapshot worth deploying.
- Keep a `CHANGELOG.md` if multiple humans will edit the master scene.
