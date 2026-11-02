# Tea House — Canonical ASCII Floor Map (DRAFT)

> **Reference update (2026-11-01):** see [the panorama comparison](panorama-comparison.md) before revising this draft. Its coordinate table, doorway table, drawing, and current JSON spec disagree in places; the new photographs verify some connections but do not establish metric dimensions.

> **Status:** DRAFT — needs review and corrections from the user. Once this is
> agreed upon, `spec/teahouse.room.json` and the runtime layout are regenerated
> from it. Treat this file as the single source of truth for the building's
> topology while the real Blender model is still in progress.

## Coordinate convention

* Origin `(0,0)` ≈ middle of the **Corridor (lower)**. Spawn is at `(4, -1.5)`.
* `+X` points **east**, `-X` points **west**.
* `+Z` points **south** (toward the entrance door / outside), `-Z` points **north**.
* `Y` (vertical) levels in this building:
  - `y = 0.00 m` — entrance level (spawn, toilet, books store hall, lecture halls)
  - `y = -0.30 m` — recessed corridor (lower), with 2 steps up east into spawn
  - `y = +0.15 m` — upper level (accessories store, teabar, tearoom, both arms of corridor 2)
* All sizes are `(width along X) × (depth along Z)` in meters.
* All measurements are placeholders. **Refine with real tape readings later.**

## Legend (mark conventions)

```
  ────  /  ────     solid wall (drawn on the side that the wall belongs to)
  ║    /  │         solid wall (vertical)
  ╔ ╗ ╝ ╚            wall corner
  · · · ·            doorway / opening (a gap in the wall — pass-through)
  >>  /  <<          axis-aligned step run, arrow points UP-the-stairs
  v v v / ^ ^ ^      same, vertical step run, arrow points UP-the-stairs
  / / /              DIAGONAL stair run (45°), each "/" = one tread,
                     arrow direction implicit from context (annotated below)
  [LABEL]            room interior label
  (X.X, Y.Y)         (x-coordinate, z-coordinate) anchor in meters
  D1, D2, …          doorway IDs, defined in the doorway table below
  S1, S2, …          step transitions (a doorway with steps), defined in steps table
```

## Rooms (v0.4 coordinates — matches spec/teahouse.room.json)

| ID                    | Label                  | Center (x, z)   | Size (w × d) | Floor Y | Notes                                       |
|-----------------------|------------------------|-----------------|--------------|---------|---------------------------------------------|
| `spawn`               | Spawn / Entrance       | ( 4.0, -1.5)    | 2.0 × 1.0   |  0.00   | Small vestibule; D0 south, D1 east, S1 west |
| `toilet`              | Toilet                 | ( 4.0, -3.0)    | 2.0 × 2.0   |  0.00   | North of spawn                               |
| `books_hall`          | Books Store Hall       | ( 9.5, -3.0)    | 9.0 × 4.0   |  0.00   | Largest room; east of spawn/toilet           |
| `lecture_hall`        | Lecture Hall (north)   | (15.5, -4.0)    | 3.0 × 2.0   |  0.00   | North vestibule of actual lecture hall       |
| `lecture_hall_entry`  | Lecture Hall Entry (south) | (15.5, -2.0) | 3.0 × 2.0   |  0.00   | South foyer, connected to books_hall via D8 |
| `corridor`            | Corridor (lower)       | ( 0.0, -1.5)    | 6.0 × 1.0   | -0.30   | Recessed, runs east-west                     |
| `accessories_store`   | Accessories Store      | (-7.0, -3.0)    | 8.0 × 2.0   | +0.15   | West of corridor; reached via diagonal S2    |
| `corridor_2_north`    | Corridor 2 (north arm) | (-2.0, -7.0)   | 2.0 × 4.0   | +0.15   | Vertical arm of L, east of teabar            |
| `corridor_2_east`     | Corridor 2 (east arm)  | ( 1.0, -4.5)   | 8.0 × 1.0   | +0.15   | Horizontal arm running east toward toilet/books |
| `teabar`              | Teabar                 | (-5.0, -6.5)    | 4.0 × 5.0   | +0.15   | Bar room                                     |
| `tearoom`             | Tearoom                | (-9.0, -6.5)    | 4.0 × 5.0   | +0.15   | Carved screen + cups + couch                 |

Corridor 2 is L-shaped, modeled as two rectangles (`_north` and `_east`) joined
by a 2 m full-height opening (`d_corr2_join`) at their shared edge (z = -5).

## Doorways (v0.4)

| Spec ID              | Map ID | Between                                        | Position (x, z) | Width | Notes                                         |
|----------------------|--------|-------------------------------------------------|-----------------|-------|-----------------------------------------------|
| `d_spawn_outside`    | D0     | `spawn` ↔ outside                               | ( 4.0, -1.0)    | 1.0   | Main entrance, south wall of spawn            |
| `d_spawn_books`      | D1     | `spawn` ↔ `books_hall`                           | ( 5.0, -1.5)    | 0.9   | East wall of spawn                            |
| `d_corridor_spawn`   | S1     | `corridor` ↔ `spawn`                             | ( 3.0, -1.5)    | 1.0   | West wall of spawn; 2 axis-aligned steps (up into spawn from corridor) |
| `d_diag_corner`      | S2a    | `corridor` ↔ `accessories_store`                 | (-3.0, -2.0)    | 1.0   | Corner notch at shared NW/SE corner           |
| `d_diag_stairs`      | S2b    | `corridor` ↔ `accessories_store`                 | (-3.4, -2.4)    | 1.0   | 3 diagonal steps (45°) inside corner gap      |
| `d_toilet_corr2e`    | D2     | `toilet` ↔ `corridor_2_east`                     | ( 4.0, -4.0)    | 0.8   | North wall of toilet; 1 step up north         |
| `d_corr2e_books`     | D3     | `corridor_2_east` ↔ `books_hall`                 | ( 5.0, -4.5)    | 0.6   | East wall of corr2_east; 1 step up west       |
| `d_corr2_join`       | —      | `corridor_2_north` ↔ `corridor_2_east`           | (-2.0, -5.0)    | 2.0   | Internal L joint; full-height open passageway |
| `d_teabar_corr2e`    | D4     | `teabar` ↔ `corridor_2_east`                     | (-3.0, -4.5)    | 0.6   | East wall of teabar                           |
| `d_teabar_accessories` | D5   | `teabar` ↔ `accessories_store`                   | (-5.0, -4.0)    | 1.0   | South wall of teabar; flat (same y)           |
| `d_tearoom_accessories`| D6   | `tearoom` ↔ `accessories_store`                  | (-9.0, -4.0)    | 1.0   | South wall of tearoom; flat (same y)          |
| `d_tearoom_teabar`   | D7     | `tearoom` ↔ `teabar`                             | (-7.0, -8.5)    | 1.0   | Shared east/west wall between the two         |
| `d_books_lectent`    | D8     | `books_hall` ↔ `lecture_hall_entry`               | (14.0, -2.0)    | 1.2   | East wall of books hall                       |
| `d_lect_lectent`     | D9     | `lecture_hall` ↔ `lecture_hall_entry`             | (15.5, -3.0)    | 1.0   | Interior wall between the two lecture rooms   |

## Step transitions (v0.4)

| Spec ID            | Map ID | Between                          | Style            | Steps | Rise / Tread | Direction (lower → higher) |
|--------------------|--------|----------------------------------|------------------|-------|--------------|----------------------------|
| `d_corridor_spawn` | S1     | `corridor` ↔ `spawn`             | axis-aligned     | 2     | 0.15 / 0.30  | Step UP eastward from corridor (y=-0.30) into spawn (y=0.00) |
| `d_diag_stairs`    | S2     | `corridor` ↔ `accessories_store` | **45° diagonal** | 3     | 0.15 / 0.70  | Step UP north-west from corridor (y=-0.30) into accessories (y=+0.15) |
| `d_toilet_corr2e`  | D2     | `toilet` ↔ `corridor_2_east`     | axis-aligned     | 1     | 0.15 / 0.30  | Step UP northward from toilet (y=0.00) into corr2_east (y=+0.15) |
| `d_corr2e_books`   | D3     | `corridor_2_east` ↔ `books_hall` | axis-aligned     | 1     | 0.15 / 0.30  | Step DOWN eastward from corr2_east (y=+0.15) into books (y=0.00) |

### S2 details (the diagonal staircase)

* The staircase sits at the shared corner between **corridor's NW** and
  **accessories_store's SE** around `(-3, -2)`.
* `d_diag_corner` carves a 1 m notch out of both rooms' walls at that corner.
* `d_diag_stairs` sits inside that gap and carries 3 rotated step boxes with
  `direction = [-0.7071, -0.7071]` (northwest).
* Total rise: 0.45 m (from corridor y=-0.30 to accessories y=+0.15).
* The user enters the stairs from the SE side and ascends northwest.

## Open questions / things that look wrong

1. **Lecture hall:** now modeled as two rooms (`lecture_hall` north +
   `lecture_hall_entry` south) connected by D9. The north room represents the
   vestibule of the actual lecture hall building (not fully modeled).
2. **Tearoom-to-accessories door (D6):** included as real based on the user's
   ASCII map. Can be removed if the user says it doesn't exist.
3. **Toilet ↔ spawn:** no direct door in v0.4 — the user's ASCII map doesn't
   show one. Toilet is reached via corridor_2_east (D2) or books_hall.
4. **Real measurements:** every number is approximate. Refine with on-site
   tape readings.

## Top-down ASCII map (north = up, south = down)

> Approximate scale: each character ≈ 0.5 m horizontally, each row ≈ 0.6 m
> vertically. The drawing is schematic; rely on the coordinate tables below for
> actual numbers.

```
                                        x →
        -11   -9   -7   -5   -3   -1    0    1    3    5    7    9   11   12   13   14   15   16   17   18
z=-9    ╔═════════╦═════════╦═════╗
        ║         ·D7       ║     ║ 
        ║ TEAROOM ║ TEABAR  ║     ║
z=-8    ║         ║         ║     ║      
        ║         ║         ║     ║
        ║         ║         ║     ║
z=-7    ║         ║         ║     ║      
        ║         ║         ║     ║
        ║         ║         ║     ║
z=-5    ║         ╠═══·D6═══╣     ╚══════════════╦═══════════════════════════════════╦═════════════╗
        ║         ║  Pre    ║                   ·D3                                  ║             ║
        ║         ║  Teabar ·        CORRIDOR 2  ║                                   ║   LECTURE   ║ 
z=-4    ╠═════════╩═══·D5═══╣═════╦══════════·D2═╣                                   ║     HALL    ║         
        ║                   ║     ║              ║                                   ║     LH      ║ 
        ║                   ║     ║              ║    BOOKS                          ║             ║
z=-3    ║                   ║     ║              ║    STORE                          ║             ║
        ║                   ║     ║              ║    HALL                           ║             ║
        ║ ACCESSORIES STORE ║     ║TOILET        ║     B                             ║             ║
z=-2    ║                 A ║     ║  Tlt         ║                                   ║═════D9·═════║
        ║                   ║     ╚══════════════║                                   ║             ║ 
        ║                   ║             ╔══════╣                                   ║             ║
z=-1    ║                   ║             ║      ║                                   ║             ║
        ║                   ║             ║      ║                                   ║             ║                                     ║                   ║             ║      ║                                   ║   LECTURE   ║
z=0     ║           S2      ╠═════════════╣      D1·                                 D8·  HALL     ║
        ║ (3 diag steps ////  CORRIDOR (lower)   ║                                   ║    ENTRY    ║    
        ║ UP, NW)       ////    y = -0.30  SPAWN ║                                   ║     L       ║         
z=+1    ╚═══════════════════╩════S1═v═v═v═╩══D0══╩═══════════════════════════════════╩═════════════╝
                                                  ↓                         
                                                  D0              
z=+2                                             outside           
                                                                 
                                                                   
                                                                   
                                                                 
                                                                            
                                                                            
```

> **NOTE:** the ASCII drawing is rough and only shows topology. Use it to spot
> "this room is in the wrong place" issues, not to measure distances.
