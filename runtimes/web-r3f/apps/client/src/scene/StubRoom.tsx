import { useMemo } from "react";
import * as THREE from "three";
import { useTexture } from "@react-three/drei";
import { RigidBody } from "@react-three/rapier";
import type {
  RoomSpec,
  Room as RoomDef,
  Doorway,
  Vec2,
} from "@teahouse/shared";

import carvedScreenUrl from "../../../../../../source/references/carved-screen-reference.png";

interface Props {
  spec: RoomSpec;
}

const WALL_THICK = 0.12;
const DEFAULT_CEILING = 2.8;
const DEFAULT_DOOR_HEIGHT = 2.0;
const STEP_DEFAULT_RISE = 0.15;
const STEP_DEFAULT_TREAD = 0.30;

const DEFAULT_FLOOR_COLOR = "#5a3a26";
const DEFAULT_WALL_COLOR = "#d8c2a3";
const DEFAULT_CEILING_COLOR = "#3b2a1d";

const KIND_FLOOR_COLOR: Record<string, string> = {
  tearoom: "#5a3a26",
  teabar: "#5a3a26",
  store: "#6a4a32",
  corridor: "#4a3520",
  toilet: "#7a8a8a",
  hall: "#6a4a32",
  entrance: "#5a3a26",
  lecture_hall: "#7a5a3a",
  other: DEFAULT_FLOOR_COLOR,
};

/**
 * Multi-room stub renderer.
 *
 * Reads spec.rooms[] and spec.doorways[] and boxes out each room with floor,
 * ceiling, and walls split where doorways pass through them. Step transitions
 * are rendered between rooms whose floorY values differ.
 *
 * When the master Blender scene exports exports/web/teahouse.glb, swap this
 * for a GlbRoom component that uses useGLTF — the runtime adapter is the only
 * code change needed.
 */
export function StubRoom({ spec }: Props) {
  const screenTex = useTexture(carvedScreenUrl);
  screenTex.colorSpace = THREE.SRGBColorSpace;

  // Fallback to single-room behavior when no rooms[] are defined.
  if (!spec.rooms || spec.rooms.length === 0) {
    return <SingleRoomStub spec={spec} screenTex={screenTex} />;
  }

  return (
    <group>
      {spec.rooms.map((r) => (
        <RoomGeometry
          key={r.id}
          room={r}
          doorways={spec.doorways ?? []}
          allRooms={spec.rooms!}
          screenTex={r.kind === "tearoom" ? screenTex : null}
        />
      ))}
      {(spec.doorways ?? []).map((d) => (
        <DoorwaySteps key={d.id} doorway={d} rooms={spec.rooms!} />
      ))}
    </group>
  );
}

function RoomGeometry({
  room,
  doorways,
  allRooms,
  screenTex,
}: {
  room: RoomDef;
  doorways: Doorway[];
  allRooms: RoomDef[];
  screenTex: THREE.Texture | null;
}) {
  const ceilingHeight = room.ceilingHeight ?? DEFAULT_CEILING;
  const floorY = room.floorY;
  const ceilingY = floorY + ceilingHeight;
  const [cx, cz] = room.center;
  const [w, d] = room.size;

  const halfW = w / 2;
  const halfD = d / 2;

  const wallColor = room.wallColor ?? DEFAULT_WALL_COLOR;
  const floorColor =
    room.floorColor ?? KIND_FLOOR_COLOR[room.kind ?? "other"] ?? DEFAULT_FLOOR_COLOR;

  const floorMat = useMemo(
    () => new THREE.MeshStandardMaterial({ color: floorColor, roughness: 0.85 }),
    [floorColor],
  );
  const wallMat = useMemo(
    () => new THREE.MeshStandardMaterial({ color: wallColor, roughness: 0.95 }),
    [wallColor],
  );
  const ceilingMat = useMemo(
    () => new THREE.MeshStandardMaterial({ color: DEFAULT_CEILING_COLOR, roughness: 0.9 }),
    [],
  );

  // For each of the 4 walls, find doorways that pierce it and compute the
  // wall-segment ranges between them. Each wall is a vertical slab of thickness
  // WALL_THICK aligned along one axis.
  const walls = useMemo(() => buildWallSegments(room, doorways), [room, doorways]);

  const stairwellData = useMemo(() => {
    const results: {
      cutout: { cx: number; cz: number; w: number; d: number };
      lowerFloorY: number;
      holeCorners: [number, number][];
    }[] = [];
    for (const dw of doorways) {
      if (!dw.steps?.direction) continue;
      if (!dw.between.includes(room.id)) continue;
      const r1 = allRooms.find((r) => r.id === dw.between[0]);
      const r2 = allRooms.find((r) => r.id === dw.between[1]);
      if (!r1 || !r2) continue;
      const isHigher = room.floorY >= Math.max(r1.floorY, r2.floorY);
      if (!isHigher) continue;
      const lower = r1.floorY < r2.floorY ? r1 : r2;
      const [dx, dz] = dw.position;
      const [vx, vz] = dw.steps.direction;
      const nrm = Math.hypot(vx, vz) || 1;
      const dirX = vx / nrm;
      const dirZ = vz / nrm;
      const perpX = -dirZ;
      const perpZ = dirX;
      const tread = dw.steps.tread ?? STEP_DEFAULT_TREAD;
      const totalRun = dw.steps.count * tread;
      const sCxAuto = dx + dirX * totalRun / 2;
      const sCzAuto = dz + dirZ * totalRun / 2;
      // ── Stairwell cutout: position & size (tweak these) ──
      const cutOffsetX = 0.67;    // shift cutout in world X (+ = east)
      const cutOffsetZ = 0.67;    // shift cutout in world Z (+ = south)
      const sCx = sCxAuto + cutOffsetX;
      const sCz = sCzAuto + cutOffsetZ;
      const halfLen = totalRun / 2 + 1.5;   // half-length along stair direction (large so SE side reaches room edge)
      const halfWid = dw.width / 2 + 0.1;   // half-width perpendicular to stair
      // sCx, sCz = center of the staircase footprint in world coords
      // dirX, dirZ = unit vector pointing NW (up the stairs)
      // perpX, perpZ = unit vector perpendicular to stairs
      const rL = room.center[0] - room.size[0] / 2;
      const rR = room.center[0] + room.size[0] / 2;
      const rT = room.center[1] - room.size[1] / 2;
      const rB = room.center[1] + room.size[1] / 2;
      const clamp = (x: number, z: number): [number, number] => [
        Math.max(rL, Math.min(rR, x)),
        Math.max(rT, Math.min(rB, z)),
      ];
      const holeCorners: [number, number][] = [
        clamp(sCx - dirX * halfLen + perpX * halfWid, sCz - dirZ * halfLen + perpZ * halfWid),
        clamp(sCx + dirX * halfLen + perpX * halfWid, sCz + dirZ * halfLen + perpZ * halfWid),
        clamp(sCx + dirX * halfLen - perpX * halfWid, sCz + dirZ * halfLen - perpZ * halfWid),
        clamp(sCx - dirX * halfLen - perpX * halfWid, sCz - dirZ * halfLen - perpZ * halfWid),
      ];
      let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
      for (const [hx, hz] of holeCorners) {
        minX = Math.min(minX, hx); maxX = Math.max(maxX, hx);
        minZ = Math.min(minZ, hz); maxZ = Math.max(maxZ, hz);
      }
      results.push({
        cutout: {
          cx: (minX + maxX) / 2,
          cz: (minZ + maxZ) / 2,
          w: maxX - minX + 0.02,
          d: maxZ - minZ + 0.02,
        },
        lowerFloorY: lower.floorY,
        holeCorners,
      });
    }
    return results;
  }, [room, doorways, allRooms]);

  const floorCutouts = useMemo(
    () => stairwellData.map((s) => s.cutout),
    [stairwellData],
  );

  const floorSegments = useMemo(() => {
    if (floorCutouts.length === 0) {
      return [{ px: cx, pz: cz, sw: w, sd: d }];
    }
    const segs: { px: number; pz: number; sw: number; sd: number }[] = [];
    for (const cut of floorCutouts) {
      const cutLeft = cut.cx - cut.w / 2;
      const cutRight = cut.cx + cut.w / 2;
      const cutTop = cut.cz - cut.d / 2;
      const cutBot = cut.cz + cut.d / 2;
      const roomLeft = cx - w / 2;
      const roomRight = cx + w / 2;
      const roomTop = cz - d / 2;
      const roomBot = cz + d / 2;
      const leftW = cutLeft - roomLeft;
      if (leftW > 0.01) segs.push({ px: roomLeft + leftW / 2, pz: cz, sw: leftW, sd: d });
      const rightW = roomRight - cutRight;
      if (rightW > 0.01) segs.push({ px: roomRight - rightW / 2, pz: cz, sw: rightW, sd: d });
      const midLeft = Math.max(roomLeft, cutLeft);
      const midRight = Math.min(roomRight, cutRight);
      const midW = midRight - midLeft;
      if (midW > 0.01) {
        const topD = cutTop - roomTop;
        if (topD > 0.01) segs.push({ px: (midLeft + midRight) / 2, pz: roomTop + topD / 2, sw: midW, sd: topD });
        const botD = roomBot - cutBot;
        if (botD > 0.01) segs.push({ px: (midLeft + midRight) / 2, pz: roomBot - botD / 2, sw: midW, sd: botD });
      }
    }
    return segs.length > 0 ? segs : [{ px: cx, pz: cz, sw: w, sd: d }];
  }, [cx, cz, w, d, floorCutouts]);

  const floorHoleGeo = useMemo(() => {
    if (stairwellData.length === 0) return null;

    // Shape is defined in XY plane; after rotateX(-PI/2), shapeY maps to -Z.
    // So we negate Z offsets: shapeY = -(worldZ - cz) to get correct world Z.
    const shape = new THREE.Shape();
    shape.moveTo(-halfW, halfD);
    shape.lineTo(halfW, halfD);
    shape.lineTo(halfW, -halfD);
    shape.lineTo(-halfW, -halfD);
    shape.closePath();

    for (const sw of stairwellData) {
      if (!sw.holeCorners || sw.holeCorners.length < 4) continue;
      const hole = new THREE.Path();
      hole.moveTo(sw.holeCorners[0][0] - cx, -(sw.holeCorners[0][1] - cz));
      for (let j = 1; j < sw.holeCorners.length; j++) {
        hole.lineTo(sw.holeCorners[j][0] - cx, -(sw.holeCorners[j][1] - cz));
      }
      hole.closePath();
      shape.holes.push(hole);
    }

    const geo = new THREE.ExtrudeGeometry(shape, { depth: 0.1, bevelEnabled: false });
    geo.rotateX(-Math.PI / 2);
    return geo;
  }, [halfW, halfD, cx, cz, stairwellData]);

  return (
    <group>
      {/* Floor — with rotated 45° hole if stairwell exists, otherwise simple box */}
      {floorHoleGeo ? (
        <RigidBody type="fixed" colliders="trimesh">
          <mesh receiveShadow position={[cx, floorY - 0.1, cz]}>
            <primitive object={floorHoleGeo} attach="geometry" />
            <primitive object={floorMat} attach="material" />
          </mesh>
        </RigidBody>
      ) : (
        <RigidBody type="fixed" colliders="cuboid">
          <mesh receiveShadow position={[cx, floorY - 0.05, cz]}>
            <boxGeometry args={[w, 0.1, d]} />
            <primitive object={floorMat} attach="material" />
          </mesh>
        </RigidBody>
      )}
      {/* Stairwell: corridor-level floor under the steps + pit walls */}
      {stairwellData.map((sw, i) => {
        const pitDepth = floorY - sw.lowerFloorY;
        return (
          <group key={`stairwell-${i}`}>
            <RigidBody type="fixed" colliders="cuboid">
              <mesh receiveShadow position={[sw.cutout.cx, sw.lowerFloorY - 0.05, sw.cutout.cz]}>
                <boxGeometry args={[sw.cutout.w, 0.1, sw.cutout.d]} />
                <meshStandardMaterial color="#4a3520" roughness={0.85} />
              </mesh>
            </RigidBody>
            <mesh position={[sw.cutout.cx, floorY - pitDepth / 2, sw.cutout.cz]}>
              <boxGeometry args={[sw.cutout.w, pitDepth, sw.cutout.d]} />
              <meshStandardMaterial color="#3b2a1d" roughness={0.9} side={THREE.BackSide} />
            </mesh>
          </group>
        );
      })}

      {/* Ceiling */}
      <mesh position={[cx, ceilingY, cz]}>
        <boxGeometry args={[w, 0.05, d]} />
        <primitive object={ceilingMat} attach="material" />
      </mesh>

      {/* Walls (each segment becomes a separate cuboid + collider) */}
      {walls.map((seg, i) => (
        <RigidBody key={i} type="fixed" colliders="cuboid">
          <mesh
            position={[seg.cx, floorY + seg.height / 2, seg.cz]}
            rotation={[0, seg.rotY, 0]}
          >
            <boxGeometry args={[seg.length, seg.height, WALL_THICK]} />
            <primitive object={wallMat} attach="material" />
          </mesh>
        </RigidBody>
      ))}

      {/* Lintels above doorways (kept short — purely visual continuity) */}
      {walls.flatMap((seg) =>
        seg.lintels.map((lt, j) => (
          <mesh
            key={`${seg.id}-lt-${j}`}
            position={[lt.cx, floorY + lt.bottom + lt.height / 2, lt.cz]}
            rotation={[0, seg.rotY, 0]}
          >
            <boxGeometry args={[lt.length, lt.height, WALL_THICK]} />
            <primitive object={wallMat} attach="material" />
          </mesh>
        )),
      )}

      {/* Tearoom hero prop: the carved-screen reference photo as an alpha plane */}
      {screenTex && (
        <mesh
          position={[cx + halfW - 0.3, floorY + 1.0, cz]}
          rotation={[0, -Math.PI / 2, 0]}
          castShadow
        >
          <planeGeometry args={[1.2, 2.0]} />
          <meshStandardMaterial
            map={screenTex}
            transparent
            alphaTest={0.4}
            side={THREE.DoubleSide}
            roughness={0.7}
          />
        </mesh>
      )}

      {/* Tearoom decoration: stand-in turquoise couch */}
      {room.kind === "tearoom" && (
        <RigidBody type="fixed" colliders="cuboid">
          <mesh position={[cx - halfW + 0.5, floorY + 0.3, cz]} castShadow receiveShadow>
            <boxGeometry args={[0.7, 0.6, 1.6]} />
            <meshStandardMaterial color="#2c8a8a" roughness={0.7} />
          </mesh>
        </RigidBody>
      )}

      {/* Tearoom decoration: low table where the cups sit */}
      {room.kind === "tearoom" && (
        <mesh position={[cx, floorY + 0.25, cz]} castShadow>
          <boxGeometry args={[0.6, 0.5, 1.2]} />
          <meshStandardMaterial color="#3b2a1d" roughness={0.9} />
        </mesh>
      )}

      {/* Teabar decoration: bar counter along the east wall (vertical orientation) */}
      {room.kind === "teabar" && (
        <RigidBody type="fixed" colliders="cuboid">
          <mesh position={[cx + halfW - 0.4, floorY + 0.5, cz]} castShadow>
            <boxGeometry args={[0.5, 1.0, d - 1.0]} />
            <meshStandardMaterial color="#6a4a32" roughness={0.7} />
          </mesh>
        </RigidBody>
      )}

      {/* Tiny floating room label — useful while we navigate the stub */}
      <mesh position={[cx, ceilingY - 0.05, cz]}>
        <boxGeometry args={[0.001, 0.001, 0.001]} />
        <meshBasicMaterial transparent opacity={0} />
      </mesh>
    </group>
  );
}

interface WallSegment {
  id: string;
  cx: number;
  cz: number;
  rotY: number;
  length: number;
  height: number;
  lintels: { cx: number; cz: number; length: number; bottom: number; height: number }[];
}

function buildWallSegments(room: RoomDef, doorways: Doorway[]): WallSegment[] {
  const ceilingHeight = room.ceilingHeight ?? DEFAULT_CEILING;
  const [cx, cz] = room.center;
  const [w, d] = room.size;
  const halfW = w / 2;
  const halfD = d / 2;

  const segments: WallSegment[] = [];

  // Each wall is parameterized by:
  //   - axis: "x" (wall runs along X, fixed Z) or "z" (wall runs along Z, fixed X)
  //   - fixed: the constant coordinate
  //   - from, to: range along the axis
  //   - rotY: rotation of the wall around Y so its long side aligns with axis
  //   - id: which side ("south", "north", "west", "east")
  type WallSpec = {
    id: "south" | "north" | "west" | "east";
    axis: "x" | "z";
    fixed: number;
    from: number;
    to: number;
    rotY: number;
  };

  const wallSpecs: WallSpec[] = [
    { id: "south", axis: "x", fixed: cz + halfD, from: cx - halfW, to: cx + halfW, rotY: 0 },
    { id: "north", axis: "x", fixed: cz - halfD, from: cx - halfW, to: cx + halfW, rotY: 0 },
    { id: "west", axis: "z", fixed: cx - halfW, from: cz - halfD, to: cz + halfD, rotY: Math.PI / 2 },
    { id: "east", axis: "z", fixed: cx + halfW, from: cz - halfD, to: cz + halfD, rotY: Math.PI / 2 },
  ];

  for (const wallSpec of wallSpecs) {
    // Find doorways that lie on this wall.
    const cuts: { center: number; width: number; height: number }[] = [];
    for (const door of doorways) {
      if (!doorTouchesRoom(door, room.id)) continue;

      const [dx, dz] = door.position as Vec2;
      const widthOnAxis = door.width;
      const tol = 0.15; // generous tolerance for hand-authored coords

      if (wallSpec.axis === "x" && Math.abs(dz - wallSpec.fixed) <= tol) {
        cuts.push({ center: dx, width: widthOnAxis, height: door.height ?? DEFAULT_DOOR_HEIGHT });
      } else if (wallSpec.axis === "z" && Math.abs(dx - wallSpec.fixed) <= tol) {
        cuts.push({ center: dz, width: widthOnAxis, height: door.height ?? DEFAULT_DOOR_HEIGHT });
      }
    }
    cuts.sort((a, b) => a.center - b.center);

    // Build wall segments between cuts.
    const ranges: { from: number; to: number }[] = [];
    let cursor = wallSpec.from;
    for (const cut of cuts) {
      const cutFrom = cut.center - cut.width / 2;
      const cutTo = cut.center + cut.width / 2;
      if (cutFrom > cursor) ranges.push({ from: cursor, to: Math.min(cutFrom, wallSpec.to) });
      cursor = Math.max(cursor, cutTo);
    }
    if (cursor < wallSpec.to) ranges.push({ from: cursor, to: wallSpec.to });

    // Lintels — short walls above each doorway.
    const lintels: WallSegment["lintels"] = cuts.map((cut) => ({
      cx: wallSpec.axis === "x" ? cut.center : wallSpec.fixed,
      cz: wallSpec.axis === "x" ? wallSpec.fixed : cut.center,
      length: cut.width,
      bottom: cut.height,
      height: Math.max(0.001, ceilingHeight - cut.height),
    }));

    for (const rng of ranges) {
      const length = rng.to - rng.from;
      if (length <= 0.01) continue;
      const center = (rng.from + rng.to) / 2;
      segments.push({
        id: `${room.id}-${wallSpec.id}-${center.toFixed(2)}`,
        cx: wallSpec.axis === "x" ? center : wallSpec.fixed,
        cz: wallSpec.axis === "x" ? wallSpec.fixed : center,
        rotY: wallSpec.rotY,
        length,
        height: ceilingHeight,
        lintels: [],
      });
    }

    // Attach lintels to a synthetic wall segment so they share the rotation.
    if (lintels.length > 0) {
      segments.push({
        id: `${room.id}-${wallSpec.id}-lintels`,
        cx: cx,
        cz: cz,
        rotY: wallSpec.rotY,
        length: 0,
        height: 0,
        lintels,
      });
    }
  }

  return segments;
}

function doorTouchesRoom(door: Doorway, roomId: string): boolean {
  return door.between[0] === roomId || door.between[1] === roomId;
}

function DoorwaySteps({ doorway, rooms }: { doorway: Doorway; rooms: RoomDef[] }) {
  if (!doorway.steps) return null;

  const r1 = rooms.find((r) => r.id === doorway.between[0]);
  const r2 = rooms.find((r) => r.id === doorway.between[1]);
  if (!r1 || !r2) return null;

  const lower = r1.floorY < r2.floorY ? r1 : r2;
  const higher = r1.floorY < r2.floorY ? r2 : r1;
  if (higher.floorY - lower.floorY < 0.01) return null;

  const tread = doorway.steps.tread ?? STEP_DEFAULT_TREAD;
  const rise = doorway.steps.rise ?? STEP_DEFAULT_RISE;
  const stepCount = doorway.steps.count;

  // Travel direction: explicit direction wins (used for diagonal stairs);
  // otherwise pick an axis-aligned vector from the lower room toward the door.
  let dirX: number;
  let dirZ: number;
  if (doorway.steps.direction) {
    const [vx, vz] = doorway.steps.direction;
    const len = Math.hypot(vx, vz) || 1;
    dirX = vx / len;
    dirZ = vz / len;
  } else {
    const aligned = axisAlignedDirAwayFromRoom(doorway, lower);
    dirX = aligned.x;
    dirZ = aligned.z;
  }

  // Yaw so the step's local +Z points along the travel direction. Three.js'
  // RY(θ) maps local +Z = (0,0,1) to world (sin θ, 0, cos θ) so we want
  // (sin θ, cos θ) = (dirX, dirZ) ⇒ θ = atan2(dirX, dirZ).
  const yaw = Math.atan2(dirX, dirZ);

  const [dx, dz] = doorway.position;
  const stepWidth = doorway.width;

  const elements: React.ReactElement[] = [];
  for (let i = 0; i < stepCount; i++) {
    const stepTop = lower.floorY + (i + 1) * rise;
    const stepHeight = (i + 1) * rise;
    const distAlongStair = (i + 0.5) * tread;
    const x = dx + dirX * distAlongStair;
    const z = dz + dirZ * distAlongStair;
    elements.push(
      <RigidBody key={`${doorway.id}-step-${i}`} type="fixed" colliders="cuboid">
        <mesh
          position={[x, lower.floorY + stepHeight / 2, z]}
          rotation={[0, yaw, 0]}
          castShadow
          receiveShadow
        >
          <boxGeometry args={[stepWidth, stepHeight, tread]} />
          <meshStandardMaterial color="#8B6914" roughness={0.75} />
        </mesh>
      </RigidBody>,
    );
  }
  return <group>{elements}</group>;
}

function axisAlignedDirAwayFromRoom(
  door: Doorway,
  room: RoomDef,
): { x: number; z: number } {
  // The unit vector from the room center toward the doorway, snapped to ±X or ±Z.
  const [rx, rz] = room.center;
  const [dx, dz] = door.position;
  const vx = dx - rx;
  const vz = dz - rz;
  if (Math.abs(vx) > Math.abs(vz)) {
    return { x: Math.sign(vx) || 1, z: 0 };
  }
  return { x: 0, z: Math.sign(vz) || 1 };
}

/** Legacy single-room fallback (kept so older spec versions still render). */
function SingleRoomStub({ spec, screenTex }: { spec: RoomSpec; screenTex: THREE.Texture }) {
  const w = spec.dimensions?.width ?? 6;
  const l = spec.dimensions?.length ?? 8;
  const h = spec.dimensions?.height ?? 3;
  return (
    <group>
      <RigidBody type="fixed" colliders="cuboid">
        <mesh receiveShadow position={[0, -0.05, 0]}>
          <boxGeometry args={[w, 0.1, l]} />
          <meshStandardMaterial color={DEFAULT_FLOOR_COLOR} roughness={0.85} />
        </mesh>
      </RigidBody>
      <mesh position={[0, h, 0]}>
        <boxGeometry args={[w, 0.1, l]} />
        <meshStandardMaterial color={DEFAULT_CEILING_COLOR} roughness={0.9} />
      </mesh>
      <RigidBody type="fixed" colliders="cuboid">
        <mesh position={[0, h / 2, -l / 2]}>
          <boxGeometry args={[w, h, 0.1]} />
          <meshStandardMaterial color={DEFAULT_WALL_COLOR} roughness={0.95} />
        </mesh>
      </RigidBody>
      <RigidBody type="fixed" colliders="cuboid">
        <mesh position={[0, h / 2, l / 2]}>
          <boxGeometry args={[w, h, 0.1]} />
          <meshStandardMaterial color={DEFAULT_WALL_COLOR} roughness={0.95} />
        </mesh>
      </RigidBody>
      <RigidBody type="fixed" colliders="cuboid">
        <mesh position={[-w / 2, h / 2, 0]}>
          <boxGeometry args={[0.1, h, l]} />
          <meshStandardMaterial color={DEFAULT_WALL_COLOR} roughness={0.95} />
        </mesh>
      </RigidBody>
      <RigidBody type="fixed" colliders="cuboid">
        <mesh position={[w / 2, h / 2, 0]}>
          <boxGeometry args={[0.1, h, l]} />
          <meshStandardMaterial color={DEFAULT_WALL_COLOR} roughness={0.95} />
        </mesh>
      </RigidBody>
      <mesh position={[w / 2 - 0.5, 1.0, -l / 2 + 1.2]} rotation={[0, -Math.PI / 2, 0]}>
        <planeGeometry args={[1.2, 2.0]} />
        <meshStandardMaterial map={screenTex} transparent alphaTest={0.5} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}
