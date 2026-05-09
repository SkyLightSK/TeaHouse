# Web R3F Runtime

The custom web runtime — React Three Fiber client + Colyseus server + LiveKit spatial voice. Reads the canonical room descriptor from `spec/teahouse.room.json` and (when present) the glb shell from `exports/web/teahouse.glb`. Until then, falls back to placeholder geometry built from `spec.dimensions`.

## Run locally

From the **repo root**:

```bash
pnpm install
pnpm dev
```

This starts:
- Vite dev server at [http://localhost:5173](http://localhost:5173) (the client)
- Colyseus server at `ws://localhost:2567` (with a monitor at [http://localhost:2567/colyseus](http://localhost:2567/colyseus))

## Test multiplayer

1. Open [http://localhost:5173](http://localhost:5173) in your browser
2. Open it again in an incognito/private window or another browser
3. Enter different names, click **Enter the room**
4. You'll see each other walking around as turquoise capsules with nameplates

## Enable spatial voice

1. Sign up at [LiveKit Cloud](https://cloud.livekit.io) (free tier)
2. Create a project, copy the URL, API key, and secret
3. Copy `apps/server/.env.example` to `apps/server/.env` and fill in:
   ```
   LIVEKIT_URL=wss://your-project.livekit.cloud
   LIVEKIT_API_KEY=APIxxxxxxxxxxx
   LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxx
   ```
4. Restart the server. Each player automatically joins the LiveKit room on join, with HRTF-spatialized audio.

## Replacing stub geometry with the real glb

Once `exports/web/teahouse.glb` exists (built by `tools/export-all.sh`):

1. The stub is automatically replaced by a glb loader (see `apps/client/src/scene/StubRoom.tsx` — when `exports/web/teahouse.glb` exists, swap `<StubRoom>` for a `<GlbRoom>` component that uses `useGLTF` from drei).
2. The spec's `geometry.shell.src` path is what the loader fetches.

## Build for production

```bash
pnpm -C apps/client build   # outputs apps/client/dist/
pnpm -C apps/server build   # outputs apps/server/dist/
```

Deploy the client to any static host (Vercel, Netlify, Cloudflare Pages). Deploy the server to Fly.io, Railway, or any Node host with WebSocket support.
