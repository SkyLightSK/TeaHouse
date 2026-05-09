# VRChat Runtime (Unity)

Best-in-class VR experience. Friends install VRChat (free, PC or Quest), accept your invite, and walk into the world. Worldwide community of avatars and worlds to draw from.

## Prerequisites

- Windows or macOS (VRChat SDK doesn't support Linux for builds)
- Unity Hub + **Unity 2022.3 LTS** (the version VRChat SDK3 requires — check [VRChat's compat page](https://creators.vrchat.com/sdk/upgrade) for current required version)
- VRChat account at [vrchat.com](https://vrchat.com), bumped to **New User+** trust rank (a few hours of public-world time)
- `exports/unity/teahouse.fbx` built by `tools/export-all.sh`

## Project setup

1. Open Unity Hub → **New Project** → **3D (URP)** template → save inside `runtimes/vrchat-unity/`
2. Import the [VRChat Worlds SDK](https://creators.vrchat.com/sdk/) via the VCC (VRChat Creator Companion)
3. Drag `exports/unity/teahouse.fbx` into `Assets/`
4. Drag the imported prefab into the scene
5. Add a **VRC_SceneDescriptor** component to the root (VRChat SDK requirement)
6. Run our spec importer: `Tools > TeaHouse > Import Spec` (see `Editor/SpecImporter.cs`). This reads `spec/teahouse.room.json` and instantiates VRChat-specific game objects:
   - Each `spawnPoints[i]` becomes a **VRC_SceneDescriptor.spawns[]** entry
   - Each `sitPoints[i]` becomes a **VRC_Station** with the appropriate seat orientation
   - Each `interactables[i].kind === "pickup"` becomes a **VRC_Pickup** + Rigidbody

## Build & publish

1. **VRChat SDK > Build & Publish for Windows** (and again for **Android** if you want Quest support)
2. Set world to **Private** until you're ready to share
3. Right-click in your VRChat client → **Invite friends** to the world

## Asset budget reminders

- **Tris**: under 70k for PC-good rating, under 25k for Quest-good
- **Materials**: under 20 unique for PC-good
- **Textures**: 250 MB world for PC, 100 MB world for Quest
- Run **VRChat SDK > Build > Build & Test** locally first to see the world's "Performance Rank"

## When to use this runtime

Best when:
- You want **the best VR experience** — full body tracking, hand tracking, finger tracking, jaw tracking
- Some friends already use VRChat and have avatars they love

Skip when:
- Friends won't install VRChat (use `runtimes/spatial/` or `runtimes/web-r3f/` instead)
- You want browser access
- You need custom non-VRChat interactivity

## Spec importer

A starter Unity Editor script lives at [`Editor/SpecImporter.cs`](Editor/SpecImporter.cs). It reads our portable `spec/teahouse.room.json` and wires up VRChat-specific components, so re-importing whenever the spec changes only takes a click.
