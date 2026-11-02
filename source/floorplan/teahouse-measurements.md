# Tea House — Floor Plan & Measurements

> **Reference update (2026-11-01):** a 23-view November 2017 panorama tour is now available. See [the photo comparison](panorama-comparison.md) for confirmed connections, contradictions, and unverified areas. The numeric dimensions below remain estimates.

Source plan: [`teahouse-plan.png`](teahouse-plan.png) (editable Photoshop source: [`teahouse-plan.psd`](teahouse-plan.psd))

Real-world reference: [Google Maps](https://maps.app.goo.gl/uGfxcrumW2HSkJD68)

> **Note:** measurements below are approximate (~10–20% accuracy). They define the topology and proportions; refine with on-site tape readings later. The 3D runtime adapts automatically when these values change because the spec is the single source of truth.

## Coordinate system

- **Origin:** center of the **spawn** room (entrance threshold)
- **+X:** east (right side of plan)
- **+Z:** south (toward the outside / exit door)
- **−Z:** north (deeper into the building)
- **+Y:** up

Player initially faces **−Z** (looking into the building from the entrance).

## Levels (elevation, +Y in meters)

The building has **three floor levels** because of the recessed corridor:

| Level | Y | Rooms |
|---|---|---|
| Entrance level | **0.00** | spawn, toilet, books_hall, lecture_hall_entrance |
| **Recessed corridor** | **−0.30** | corridor (the one with stairs) |
| Upper level | **+0.15** | corridor_2, accessories_store, teabar, **tearoom** |

### Step transitions (per the user's note)

- **Spawn → corridor**: 2 steps DOWN (Δy = −0.30 m, ~0.15 m per step)
- **Corridor → accessories_store**: 3 steps UP (Δy = +0.45 m, ~0.15 m per step)
- All other doorways are flat (no level change)

## Rooms (top-down, approximate)

All positions are room **centers** in world coords. Sizes are `[width along X, depth along Z]`. Ceiling height is 2.8 m unless noted.

| ID | Name | Center (x, z) | Size (w, d) | Floor Y | Notes |
|---|---|---|---|---|---|
| `spawn` | Spawn / Entrance threshold | (0, 0) | (3.0, 1.5) | 0.00 | Main entrance from outside is on the south wall (+Z). |
| `toilet` | Toilet | (0, −2.4) | (3.0, 2.5) | 0.00 | North of spawn. |
| `books_hall` | Books store hall | (5.5, −1.5) | (8.0, 5.0) | 0.00 | The big central room. |
| `lecture_hall_entrance` | Entrance to the Lecture Hall | (10.5, −1.5) | (3.0, 5.0) | 0.00 | Far east. |
| `corridor` | Corridor (recessed, with stairs) | (−3.5, 0.0) | (4.0, 1.5) | **−0.30** | Recessed; west of spawn. |
| `corridor_2` | Corridor 2 | (−3.5, −2.6) | (4.0, 1.5) | **+0.15** | Connects upper-level rooms. |
| `accessories_store` | Accessories store | (−7.5, −2.4) | (4.5, 4.5) | **+0.15** | West of corridor_2; reached via stairs from `corridor`. |
| `teabar` | Teabar | (−6.0, −7.0) | (3.0, 4.0) | **+0.15** | North of accessories_store. **Interaction-rich**. |
| `tearoom` | Tearoom | (−9.5, −7.0) | (3.5, 4.0) | **+0.15** | West of teabar. **Interaction-rich** — the cups and table live here. |

## Doorways (visible in plan)

Each doorway connects two rooms; world position is the doorway center; `width` is the opening size in meters; `height` is the opening top above floor (default 2.0 m).

| ID | Between | Position (x, z) | Width | Steps |
|---|---|---|---|---|
| `door_outside_to_spawn` | outside → spawn | (0, 0.75) | 1.2 | — |
| `door_spawn_to_toilet` | spawn ↔ toilet | (0.7, −0.75) | 0.9 | — |
| `door_spawn_to_corridor` | spawn ↔ corridor | (−1.5, 0) | 1.0 | **2 down** |
| `door_corridor_to_accessories` | corridor ↔ accessories_store | (−5.0, 0) | 1.2 | **3 up** |
| `door_corridor2_to_teabar` | corridor_2 ↔ teabar | (−6.0, −5.0) | 1.0 | — |
| `door_corridor2_to_accessories` | corridor_2 ↔ accessories_store | (−5.5, −2.6) | 1.0 | — |
| `door_corridor2_to_toilet` | corridor_2 ↔ toilet | (−1.5, −2.6) | 0.9 | — (assumed flat — TODO confirm; if there's a step here it's between +0.15 and 0.00) |
| `door_tearoom_to_teabar` | tearoom ↔ teabar | (−7.5, −7.0) | 1.2 | — |
| `door_books_to_spawn` | books_hall ↔ spawn | (1.5, −1.0) | 1.4 | — |
| `door_books_to_lecture` | books_hall ↔ lecture_hall_entrance | (9.5, −1.5) | 1.4 | — |

## Where interactions live

> **Tearoom + Teabar** are the interaction hotspots. The teacups and teapot from the [drink-tea goal](../../GOALS.md) all live in the **tearoom**.

Other rooms (toilet, books_hall, lecture_hall, accessories_store) currently have no scripted interactions — they exist for spatial richness and so future content can land there without rebuilding the map.

## Things still to confirm on-site

- [ ] All measured wall lengths in meters (currently ±20% guesses)
- [ ] Ceiling height (currently 2.8 m assumed throughout)
- [ ] Whether `door_corridor2_to_toilet` actually has a step (it would have to, per the elevation arithmetic, since corridor_2 is at +0.15 and toilet is at 0.00)
- [ ] Door widths (currently 0.9 m for interior, 1.2 m for room-to-room, 1.4 m for hall openings)
- [ ] The exact location and number of stair-step indicators (currently inferred from the user's note)
- [ ] Whether the carved screen is in the tearoom or accessories store

## How this gets used

This document is a **human-readable companion** to [`spec/teahouse.room.json`](../../spec/teahouse.room.json). The spec is the canonical machine-readable form that the runtime reads. Whenever you edit one, update the other to match.

The spec extends [`spec/room.schema.json`](../../spec/room.schema.json) with `rooms[]` and `doorways[]` arrays so multi-room layouts validate.
