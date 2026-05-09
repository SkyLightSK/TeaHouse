# TeaHouse — Goals & Context

The single source of truth for **where we are** and **what we're building next**. Update this file every time the focus shifts. All other docs (`README.md`, `TASKS-FOR-YOU.md`, plan file) link back here.

## North star

Recreate a real tea house in 3D so a small group of friends can meet inside a browser-accessible virtual space, **walk around, sit down, and drink tea together**. Everything else (multiplayer, voice, VR) is in service of that experience.

Drinking tea is the gesture that turns "we're walking around the same model" into "we're actually hanging out".

## Current state (as of this commit)


| Layer                    | Status                                                                                                        |
| ------------------------ | ------------------------------------------------------------------------------------------------------------- |
| Repo skeleton            | Done — portable assets, runtime adapters, build pipeline                                                      |
| Spec & schema            | Done — `spec/teahouse.room.json` validates against `spec/room.schema.json`                                    |
| Custom web runtime (R3F) | Done end-to-end — Vite client + Colyseus server boot, real player joins succeed                               |
| Stub geometry            | Working placeholder — primitive room + carved screen plane from reference photo                               |
| First-person controls    | Working — WASD, mouse, jump, sprint, Rapier collision                                                         |
| Multiplayer presence     | Working — capsule avatars + nameplates, position sync at 15 Hz                                                |
| Spatial voice (LiveKit)  | Wired up — disabled until `LIVEKIT_`* env vars are set                                                        |
| Sit / stand mechanic     | Working — click sit-rings, server-authoritative seat occupancy                                                |
| **Interact-with-cup**    | **Skeleton only — kind=`pickup`, event=`drink` defined in spec, server toggles `heldBy`, no actual drinking** |
| Real 3D assets           | Not yet — Phase 0 capture pending                                                                             |
| Public deployment        | Not yet — VPS chosen, deploy scripts pending                                                                  |


## Immediate goal — interactive tea cups, drink tea

Concretely, after this goal is shipped, this sequence works in the room with a friend:

1. Walk up to a cup on the low table
2. The cup highlights (subtle warm glow) when you're in interaction range
3. Click → cup attaches to your hand, animation plays of you holding it
4. Press **E** (or click again) → "drink" — cup tilts to your mouth, liquid level drops, faint sound
5. Steam particles diminish as the cup empties
6. Empty cup → place it back on a coaster (snap point) or pour more from the teapot
7. **Your friend sees all of this** — your avatar tilts the cup, their cup is independent, two people can drink simultaneously

### Definition of done

- At least 2 cups exist as separate entities in the spec
- Each cup has server-authoritative state: `level: 0..1`, `heldBy: sessionId | null`, `lastDrinkAt: ms`
- Drinking decreases `level` by ~0.2 per sip with a 1-second cooldown
- Steam particle intensity tracks `level` (none at 0, full at 1)
- Cups respawn / refill after `respawnAfter` (already in spec) seconds when `level === 0` and untouched
- Drinking animation visible to all players in the room
- Drinking event also emits a `clientMessage` "drink" so future runtimes (Spatial, VRChat) can subscribe
- At least one **teapot** in the room you can pick up and "pour" onto a held cup → cup `level` goes to 1
- Cup in-range affordance: outline / glow when within 1.5 m of player camera
- Audio: gentle "sip" sound on drink (positional, attached to drinking player)

## Why this is the right next thing

- It's **small**: scopable in days, not weeks. We can ship it before real photoreal assets exist.
- It's **gestural**: the moment you and a friend can both drink tea while looking at each other, the room feels real.
- It **exercises every layer of the stack**: server-authoritative state, schema, multiplayer sync, animations, particles, audio, input — all in one feature.
- It **stays portable**: the cup behavior is encoded as state + events in the spec / Colyseus schema, so when we add the VRChat or Spatial runtime, we already know what to wire up there.
- It **scales to more interactions later**: pour, drink, refill is the same skeleton as eat, light, blow out, write — every future tea-house gesture inherits this pattern.

## How this maps to the existing codebase


| Concern           | File(s)                                                                                                              | Change needed                                                                                                                   |
| ----------------- | -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Cup data model    | `[runtimes/web-r3f/apps/server/src/schema/RoomState.ts](runtimes/web-r3f/apps/server/src/schema/RoomState.ts)`       | Add `CupState extends Schema` with `level`, `heldBy`, `lastDrinkAt`, `position`, `rotation` (replaces or extends `PropState`)   |
| Server logic      | `[runtimes/web-r3f/apps/server/src/rooms/TeaHouseRoom.ts](runtimes/web-r3f/apps/server/src/rooms/TeaHouseRoom.ts)`   | Add `pickupCup`, `dropCup`, `drinkSip`, `pourFromTeapot` message handlers + cooldown enforcement + tick-based respawn           |
| Network protocol  | `[runtimes/web-r3f/packages/shared/src/protocol.ts](runtimes/web-r3f/packages/shared/src/protocol.ts)`               | New `ClientMessage` variants: `pickup`, `drop`, `drink`, `pour`. Mirror `CupStateView`                                          |
| Spec              | `[spec/teahouse.room.json](spec/teahouse.room.json)`                                                                 | Add a `teapot_main` interactable with `kind: "pour"` (new kind), and 2-3 cups instead of 1                                      |
| Spec schema       | `[spec/room.schema.json](spec/room.schema.json)`                                                                     | Extend `Interactable.kind` enum to include `"pour"`                                                                             |
| Cup visuals       | New: `runtimes/web-r3f/apps/client/src/scene/Teacup.tsx`                                                             | GLB-loaded (or stub primitive) cup mesh + steam particle emitter + level-driven liquid plane + outline/glow when hover-in-range |
| Teapot visuals    | New: `runtimes/web-r3f/apps/client/src/scene/Teapot.tsx`                                                             | Same idea as cup; "pour" raycast finds nearest held cup                                                                         |
| Hand-attach logic | `[runtimes/web-r3f/apps/client/src/player/LocalPlayer.tsx](runtimes/web-r3f/apps/client/src/player/LocalPlayer.tsx)` | When holding a cup, parent it to a transform attached to the camera (offset for "in hand" feel)                                 |
| Drink input       | `[runtimes/web-r3f/apps/client/src/player/useKeyboard.ts](runtimes/web-r3f/apps/client/src/player/useKeyboard.ts)`   | Add `KeyE` → `drink` action                                                                                                     |
| Audio             | New: `runtimes/web-r3f/apps/client/public/assets/audio/sip.ogg`                                                      | Royalty-free sip sound, played positionally at the drinker's avatar                                                             |
| HUD prompt        | `[runtimes/web-r3f/apps/client/src/ui/Hud.tsx](runtimes/web-r3f/apps/client/src/ui/Hud.tsx)`                         | Show "Press E to drink" when holding a cup with `level > 0`                                                                     |


## What we are explicitly NOT doing in this iteration

- Spilling tea (would require fluid sim or particle juice — defer)
- Custom tea types / flavors / colors (one tea is plenty for the goal)
- Inventory / multiple held items (one item per hand max — defer)
- Persistent cup state across sessions (Redis backing — defer)
- Calorie / hunger / thirst RPG mechanics (out of scope forever)
- Photoreal cup mesh from photogrammetry (use a primitive cylinder + simple GLB until Phase 0 capture is done)

## Definition-of-done checklist (copy when shipping)

When all boxes are checked we move on to the next sharp goal.

- You and a friend simultaneously pick up your own cups
- Both cups visibly tilt toward each player's mouth on drink
- Steam visibly diminishes
- Sip sound is positional (the friend hears yours from your direction)
- Drink event ID is logged on the server
- Cup respawns or refills work
- Spec validates after the changes
- No regressions: walking, sitting, multiplayer presence still work

## Parallel track — asset acquisition

The drink-tea goal works on stub geometry. Replacing the stubs with the real tea house runs in parallel and has its own dedicated roadmap: see [`source/ASSETS-PLAN.md`](source/ASSETS-PLAN.md).

The asset roadmap currently centers on:

- ~~Reverse-engineering a **floor plan** from existing photos + tape measurements (the *skeleton*)~~ — **done**, see [`source/floorplan/`](source/floorplan/)
- Extracting the **Google Maps Street View 360** as an environment map (the *lighting*)
- Generating **props via Hunyuan 3D and Tripo 3D** from photos (the *furniture*)
- Composing everything in Blender → `exports/web/teahouse.glb`

When that lands, swap `<StubRoom>` for `<GlbRoom>` in `Scene.tsx` — one-line change.

## Subsequent goals (queued, not started)

1. **Real geometry** — driven by [`source/ASSETS-PLAN.md`](source/ASSETS-PLAN.md); replace stub room with `teahouse.glb` (+ optional `.ksplat`)
2. **VPS deployment** — Hetzner CX22 + Caddy + systemd; `deploy.sh` from laptop
3. **Spatial voice live** — finish LiveKit Cloud setup, verify HRTF positional audio
4. **Ready Player Me avatars** — replace capsules with real avatars
5. **Second runtime parity** — Spatial.io upload to validate portability of the spec

---

## How to update this doc

When the goal shifts, edit the **"Immediate goal"** and **"Definition of done"** sections. Move the previous goal to the top of "Subsequent goals" if it's deferred, or to the change log below if it's shipped.

### Change log

- **2026-05-09** — Initial goal set: interactive tea cups, drink tea. Repo and stub runtime were green at this point.
- **2026-05-09** — Asset acquisition roadmap drafted at `source/ASSETS-PLAN.md`: floor plan from photos + tape, Google Street View 360 as environment map, Hunyuan 3D + Tripo 3D for props. Parallel track to the drink-tea goal.
- **2026-05-09** — Floor plan acquired ([`source/floorplan/teahouse-plan.png`](source/floorplan/teahouse-plan.png)). Discovered the tea house is a **multi-room building** (tearoom, teabar, accessories store, two corridors at different floor levels, toilet, books store hall, lecture hall entrance) with a recessed corridor (2 steps down from spawn, 3 steps up to accessories store). Schema extended with `rooms[]` and `doorways[]` (with optional `steps`); spec rewritten with all 9 rooms; `StubRoom.tsx` now renders the multi-room layout with walls split by doorways and visible step geometry. Tearoom is the interaction hub — teacups + teapot live there per [`source/floorplan/teahouse-measurements.md`](source/floorplan/teahouse-measurements.md).

