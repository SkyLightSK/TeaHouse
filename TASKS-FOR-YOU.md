# Tasks for You (the Human)

> **What we're building right now:** see [`GOALS.md`](GOALS.md). The current sharp focus is **interactive tea cups — drinking tea together**. The tasks below stay relevant for that goal and beyond.

Everything in this checklist is something I literally cannot do for you — physical access to the tea house, account creation, payment, or artistic decisions. The repo skeleton, build pipeline, and runtime adapters are already done; the project runs end-to-end with stub geometry today. These tasks make it real.

Tasks are grouped by **when you should do them**. You do not have to do them all upfront — only the "Tier 0" tasks unblock anything.

---

## Tier 0 — Just to run the project right now (5 minutes)

The repo is ready. **No accounts, no API keys, no captures needed at this stage.**

### Important: filesystem check

Your project currently lives on `/media/skylight/2BE3-DD121/...` which is an **exFAT** drive. exFAT does not support symlinks, and Node package managers (npm, pnpm, yarn) all need symlinks to wire workspace packages together. Running `pnpm install` directly there will fail with `EPERM: operation not permitted, symlink ...`.

**The fix is built in.** Run:

```bash
bash tools/setup-dev.sh
```

This mirrors the project (everything except `node_modules` and `exports/`) to `~/TeaHouse-dev/` on your home filesystem (ext4, where symlinks work). You develop from there.

### Then run the project

```bash
cd ~/TeaHouse-dev
pnpm install
pnpm dev
```

Open [http://localhost:5173](http://localhost:5173). You'll spawn in a primitive box-shape of the tea house with the carved screen as a textured plane, walk around with WASD + mouse, and see remote players (open another browser tab to test).

### Keeping the two locations in sync

The exFAT path is the source of truth (where you'd commit and back up). The home-dir mirror is the working copy where deps live. Sync between them:

```bash
# repo (exFAT) -> mirror (ext4)
rsync -a --delete --exclude node_modules --exclude exports/ \
  /media/skylight/2BE3-DD121/Projects/TeaHouse/ ~/TeaHouse-dev/

# mirror (ext4) -> repo (exFAT)
rsync -a --delete --exclude node_modules --exclude exports/ \
  ~/TeaHouse-dev/ /media/skylight/2BE3-DD121/Projects/TeaHouse/
```

Or set them as shell aliases (the `setup-dev.sh` script prints the snippet).

### If you'd rather not deal with the mirror

Move the project to a Linux filesystem permanently:

```bash
rsync -a /media/skylight/2BE3-DD121/Projects/TeaHouse/ ~/TeaHouse/
cd ~/TeaHouse && pnpm install && pnpm dev
```

The exFAT drive then just stores backups / heavy assets.

---

## Tier 1 — Make it look like the real place (a weekend or two)

### 1. Capture the room photogrammetrically

**Time:** 30–45 min on site, then ~30 min of upload time.

1. Open the **Luma AI** app on your phone (free, [lumalabs.ai](https://lumalabs.ai)) — or **Polycam** if you prefer (free trial)
2. Inside the tea house with **all lights on, daylight curtains open**, walk slowly in **concentric loops**:
   - Outer perimeter loop (close to walls)
   - Middle loop
   - Inner loop close to props
3. For each loop, point the camera at the center of the room while you walk
4. Aim for **3–5 minutes of footage**
5. Tap **Process** in the app
6. Once done, **export as `.ply`** (Luma calls it "Gaussian Splatting") — drop the file at:
   ```
   source/captures/raw-splats/teahouse.ply
   ```

### 2. Take prop photos

**Time:** 20 min on site.

For each distinctive prop (carved screen, teapot, chairs, lanterns, the turquoise couch):
- ~50 photos taken in a tight grid around the object, ~70% overlap between shots
- Save them under `source/captures/photos/<prop-name>/`

Plus:
- 2–3 **flat orthographic-ish reference shots** of the carved wooden screen (front, side, the lattice in front of a plain background) — these become the alpha-cutout texture

### 3. Measure the room

**Time:** 5 min.

Width × Length × Height in **meters**. Use a tape measure, or use your iPhone's **Measure** app, or estimate from a floor plan.

Then edit [`spec/teahouse.room.json`](spec/teahouse.room.json) and update the `dimensions` block:

```json
"dimensions": { "width": 6, "length": 8, "height": 3 }
```

The stub renderer immediately reflects the new dimensions.

---

## Tier 2 — Author the master Blender scene (1–2 weekends)

This is where the room becomes truly photoreal-but-portable.

### 4. Install Blender

[Blender 4.2 LTS](https://blender.org) (free). On Ubuntu: `sudo apt install blender` is fine for most uses.

### 5. Read the conventions

[`source/CONVENTIONS.md`](source/CONVENTIONS.md) — all the prefix-naming rules. The whole multi-runtime portability magic depends on this. ~10 minutes to read.

### 6. Create the master scene

1. Open Blender, save as `source/rooms/teahouse.blend`
2. Import the photogrammetry mesh OR start fresh and use the Gaussian splat as a visual reference (View > Background Images)
3. Box out the walls, floor, ceiling
4. Hand-model the carved wooden screen using the recipe in `source/CONVENTIONS.md` § "Carved-screen specific recipe"
5. Hand-model or import props per the decision tree in the plan (`.cursor/plans/teahouse_3d_multiplayer_metaverse_*.plan.md` § "Asset creation pipeline")
6. Tag every interactable / spawn / sit / light / collider object with the **portable name prefix** + custom properties
7. Save

### 7. Run the export pipeline

```bash
bash tools/export-all.sh
```

This regenerates `exports/web/teahouse.glb`, `exports/unity/teahouse.fbx`, `exports/apple/teahouse.usdz`, and (if your splat is in place) `exports/web/teahouse.ksplat`.

The R3F runtime automatically swaps from stub geometry to the real glb on next page reload.

---

## Tier 3 — Multiplayer voice (15 minutes)

### 8. Sign up for LiveKit Cloud

1. Go to [cloud.livekit.io](https://cloud.livekit.io) — free tier covers 50 participant-minutes/month
2. Create a project, copy:
   - **URL** (looks like `wss://your-project.livekit.cloud`)
   - **API Key**
   - **API Secret**
3. In the repo:
   ```bash
   cp runtimes/web-r3f/apps/server/.env.example runtimes/web-r3f/apps/server/.env
   ```
4. Edit `.env` and paste the values
5. Restart `pnpm dev`. Each player joins the LiveKit room automatically with HRTF spatial audio.

---

## Tier 4 — Avatars (5 minutes)

### 9. Create a Ready Player Me avatar

1. Visit [readyplayer.me/avatar](https://readyplayer.me/avatar)
2. Take a selfie or pick a preset
3. Customize, then **Get Avatar URL** — copy the `.glb` URL
4. Either:
   - Paste it into the **Avatar GLB URL** field on the join screen (per session), OR
   - Set it as the default in `runtimes/web-r3f/apps/client/.env.local`:
     ```
     VITE_DEFAULT_AVATAR_URL=https://models.readyplayer.me/<your-id>.glb
     ```

---

## Tier 5 — Ship to friends (1 hour)

Pick whichever runtime fits the group:

### Path A — Custom web (full control)

Deploy the R3F runtime:

1. **Client** to Vercel / Netlify / Cloudflare Pages: `pnpm -C runtimes/web-r3f/apps/client build` then upload `dist/`
2. **Server** to Fly.io / Railway: see `runtimes/web-r3f/README.md` § "Build for production"
3. **Heavy assets** (large `.glb`, `.ksplat`) to Cloudflare R2 / Bunny.net — update spec paths to point to the CDN
4. Send friends the URL

### Path B — Spatial.io (zero netcode, browser link)

See [`runtimes/spatial/README.md`](runtimes/spatial/README.md) — upload `exports/web/teahouse.glb`, place spawn/sit points using the spec as a guide, share the Spatial link.

### Path C — VRChat (best VR)

See [`runtimes/vrchat-unity/README.md`](runtimes/vrchat-unity/README.md) — open in Unity 2022.3 LTS, run the spec importer, build & publish via VRChat SDK.

### Path D — Mozilla Hubs CE (self-hosted, open source)

See [`runtimes/hubs/README.md`](runtimes/hubs/README.md) — needs a small VPS and a domain, but no third-party dependency.

---

## Optional / future

- Add ambient audio: rain.ogg, distant chatter.ogg, etc. into `runtimes/web-r3f/apps/client/public/assets/audio/` and point `spec.ambientAudio[].src` at them
- WebXR for Quest browser: set `VITE_ENABLE_XR=true` in client `.env.local` (will scaffold but needs additional XR code)
- Persistent prop state: add Redis behind Colyseus so the teacup stays where you left it across sessions
- Multi-room: add more rooms in `source/rooms/` and `portal_*` empties between them

---

## Cheat sheet — file ownership

| What | Who edits | When |
|---|---|---|
| `spec/teahouse.room.json` | You | Whenever room layout changes |
| `source/rooms/*.blend` | You (in Blender) | Authoring 3D content |
| `source/captures/*` | You (drop in) | After phone capture |
| `runtimes/web-r3f/apps/client/src/**` | Me / you | Adding features |
| `runtimes/web-r3f/apps/server/src/**` | Me / you | Adding network features |
| `runtimes/web-r3f/apps/server/.env` | You | LiveKit + future API keys |
| `runtimes/web-r3f/apps/client/.env.local` | You | Avatar URL, server URL overrides |
| `tools/*.sh` and `tools/*.py` | Me / you | Pipeline tweaks |
| `exports/**` | Pipeline (auto) | Never edit by hand |
