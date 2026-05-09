# Mozilla Hubs CE Runtime

Self-hosted, open-source, browser-based. Closest to "VRChat in a browser" with full source available.

Mozilla Hubs was originally a Mozilla project; since 2024 it lives on as **Hubs Community Edition** maintained by the community. This folder is a thin deployment wrapper.

## Prerequisites

- Docker + docker-compose
- A small VPS (Hetzner, Linode, DigitalOcean — $10/mo is plenty for friends-only)
- A domain with DNS pointed at the VPS (TLS is required for Hubs)
- `exports/web/teahouse.glb` produced by `tools/export-all.sh`

## Quick start (local dev)

```bash
cd runtimes/hubs
git clone https://github.com/Hubs-Foundation/hubs-compose.git compose
cd compose
cp .env.example .env
# Edit .env to set your domain (use https://localhost.localdomain for local-only)
docker-compose up -d
```

Open the Hubs URL, sign in (email magic link), open **Spoke** (the scene editor), and import `exports/web/teahouse.glb`.

## Translating the spec to Hubs

Hubs uses a glTF extension called `MOZ_hubs_components` for interactivity. To make our spec portable to Hubs, the export pipeline can inject this extension during glb packing. To enable:

1. Install the [Hubs Blender Add-on](https://github.com/Hubs-Foundation/hubs-blender-exporter)
2. Open `source/rooms/teahouse.blend`
3. Add Hubs components to objects:
   - `sit_*` empties → **waypoint** component, set `canBeOccupied: true`, `canBeSpawnPoint: true` (for some)
   - `interactable_*` meshes → **interactable** component
   - `audio_*` empties → **audio-source** component
4. Re-export via Blender's glTF exporter (the Hubs add-on plugs into it)

Result: the same `teahouse.glb` works in Spatial (which ignores the extension) AND lights up with full interactivity in Hubs.

## Using the room

1. In Hubs Spoke, **Save** → **Publish**
2. Click **Create Room from this Scene**
3. Share the room URL with friends — they join in any browser, no account needed (just a name)

## Production deployment

Follow the [Hubs CE deployment guide](https://github.com/Hubs-Foundation/community-edition). For friends-only, a single 2GB-RAM VPS with the docker-compose stack is sufficient.

## When to use this runtime

Best when:
- You want a fully self-hosted, no-third-party, open-source stack
- You're comfortable running a VPS and DNS
- You want Hubs' built-in goodies: media frames, drawing, file sharing, video chat

Skip when:
- You don't want to run servers — use Spatial.io instead
- You need custom interactions beyond Hubs' component system — use `runtimes/web-r3f/`
