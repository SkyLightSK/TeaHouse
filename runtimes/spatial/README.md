# Spatial.io Runtime

Zero-code deployment to [Spatial.io](https://spatial.io). They handle the multiplayer, voice, avatars, browser + VR. We just upload our `.glb` and translate the spec into their editor's spawn/sit primitives.

## Prerequisites

- A free Spatial account at [spatial.io](https://spatial.io)
- `exports/web/teahouse.glb` built from `source/rooms/teahouse.blend` (run `tools/export-all.sh`)

## Steps

1. Sign in at [spatial.io](https://spatial.io)
2. Click **Create Space** → **Custom Space** → **Upload your own environment**
3. Drag `exports/web/teahouse.glb` into the upload zone (max 250 MB)
4. After it processes, click **Edit Space**
5. Translate `spec/teahouse.room.json` into Spatial primitives:
   - For each `spawnPoints[i]` → drop a **Spawn Point** at the matching XYZ, set rotation to `rotationY` degrees on Y axis
   - For each `sitPoints[i]` → drop a **Sit Point** (Tools > Interactive > Sit Point), match `kind` to closest available preset
   - For each `interactables[i]` with `kind: "pickup"` → drop a **Pickup** anchor or use Spatial's Item Spawner
   - Skip `lights[]` if your `.glb` already bakes lighting (it does once Blender export is done with `export_lights=True`)
6. Set **Privacy** to **Private** → invite friends via email or generate a link
7. Click **Save & Publish**

## Sharing the link

Spatial gives you a `https://spatial.io/s/<your-id>` link. Friends visit it in a browser (mobile, desktop, or VR via Quest browser) and walk in. No install needed.

## Limits to know

- **250 MB** glb upload limit (web runtime is well under this — typically 10–30 MB after gltfpack)
- **50 simultaneous users** in a private room (free tier)
- **No custom scripting** — only Spatial's built-in interactive primitives
- Gaussian splat (`.ksplat`) is **not supported** — Spatial uses the mesh shell only

## When to use this runtime

Best when:
- You want friends to join from any browser, any device, no install
- You don't need custom interaction logic beyond sit / pickup / portals
- You want the fastest path from "have a glb" to "we're meeting in the room"

Skip in favor of `runtimes/web-r3f/` when you need:
- Custom interactions (drawing on whiteboards, custom games, real-time data)
- Branding / custom UI / custom landing page
- Gaussian splat photoreal rendering
- Self-hosted, no third-party dependency
