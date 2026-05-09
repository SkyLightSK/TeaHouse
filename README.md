# TeaHouse — Portable 3D Multiplayer Metaverse

> **Current focus:** interactive tea cups — you and your friends should be able to walk in, sit down, and drink tea together. See [`GOALS.md`](GOALS.md) for the north-star context, definition of done, and what's queued next.

A 3D recreation of a real-world tea house, built as a **portable asset bundle** in open formats and deployable to multiple multiplayer runtimes:

- **Custom web (R3F)** — full control, browser link, no install
- **Spatial.io** — fastest path, browser-based
- **Mozilla Hubs CE** — open source, self-hosted
- **VRChat** — best VR experience (requires VRChat client)
- *Future: Unreal Engine, Apple Vision Pro, Godot, PlayCanvas*

## Core principle

Build the room **once** in open formats. Deploy it **anywhere**.

```
source/  →  spec/  →  exports/  →  runtimes/
```

- `source/` — authoritative Blender files + raw photo/video captures
- `spec/teahouse.room.json` — runtime-agnostic descriptor (spawn points, sit points, interactables, lights)
- `exports/` — auto-generated distribution formats (`.glb`, `.fbx`, `.usdz`, `.ksplat`)
- `runtimes/` — thin adapters that consume the bundle (R3F, Spatial, Hubs, VRChat)

## Quick start (custom web runtime, no real assets needed)

The custom R3F runtime ships with **placeholder geometry** so you can walk around a stub tea house immediately.

> **Heads up:** if your project lives on a filesystem that doesn't support symlinks (exFAT, FAT32, NTFS-without-admin), `pnpm install` will fail because workspaces require symlinks. Run [`tools/setup-dev.sh`](tools/setup-dev.sh) first — it mirrors the project to `~/TeaHouse-dev/` (ext4) and you develop from there. See [`TASKS-FOR-YOU.md`](TASKS-FOR-YOU.md) § "Tier 0".

On a Linux filesystem (or after running `setup-dev.sh`):

```bash
pnpm install
pnpm dev
```

Open [http://localhost:5173](http://localhost:5173). You'll spawn in a primitive box-shape of the room with the carved screen as a textured plane (using the reference photo). Open it again in a second window to test multiplayer.

## What's where

| Folder | Purpose | Edit by hand? |
|---|---|---|
| [`source/`](source/) | Master Blender scenes, photo/video captures, reference images | Yes |
| [`spec/`](spec/) | Cross-runtime room descriptor + JSON Schema | Yes |
| [`exports/`](exports/) | Auto-generated `.glb` / `.fbx` / `.usdz` / `.ksplat` (gitignored) | No |
| [`tools/`](tools/) | Build pipeline (Blender export, packing, validation) | Yes |
| [`runtimes/web-r3f/`](runtimes/web-r3f/) | Custom React Three Fiber app + Colyseus server | Yes |
| [`runtimes/spatial/`](runtimes/spatial/) | Spatial.io upload guide | Yes (docs only) |
| [`runtimes/hubs/`](runtimes/hubs/) | Mozilla Hubs CE deployment | Yes |
| [`runtimes/vrchat-unity/`](runtimes/vrchat-unity/) | Unity project + spec importer | Yes |

## What you (the human) need to do

See [`TASKS-FOR-YOU.md`](TASKS-FOR-YOU.md) for the phased checklist of tasks only you can do (physical capture, account creation, API keys, artistic decisions).

## What we're building right now

See [`GOALS.md`](GOALS.md). It captures the immediate goal, the definition of done, and the next features queued behind it. Update that file whenever priorities shift — it's the single source of truth for "where we are".

## How the real 3D assets get made

See [`source/ASSETS-PLAN.md`](source/ASSETS-PLAN.md). Floor plan (reverse-engineered from photos), Google Maps 360 photosphere, photos, plus Hunyuan 3D + Tripo 3D for props. Composed in Blender. The runtime adapter doesn't care which tool produced what — it just consumes `exports/web/teahouse.glb` + `spec/teahouse.room.json`.

## Naming conventions

The portable spec relies on **prefix-based object naming** in the master Blender scene. See [`source/CONVENTIONS.md`](source/CONVENTIONS.md).

## License

Code: MIT. 3D assets and captured photos: CC-BY-NC-4.0 (non-commercial — this is a personal recreation of a real establishment).
