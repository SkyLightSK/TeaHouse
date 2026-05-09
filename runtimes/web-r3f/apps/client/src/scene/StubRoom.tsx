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
  screenTex,
}: {
  room: RoomDef;
  doorways: Doorway[];
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

  return (
    <group>
      {/* Floor with collider */}
      <RigidBody type="fixed" colliders="cuboid">
        <mesh receiveShadow position={[cx, floorY - 0.05, cz]}>
          <boxGeometry args={[w, 0.1, d]} />
          <primitive object={floorMat} attach="material" />
        </mesh>
      </RigidBody>

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
    const stepY = lower.floorY + (i + 0.5) * rise;
    const distAlongStair = (i + 0.5) * tread;
    const x = dx + dirX * distAlongStair;
    const z = dz + dirZ * distAlongStair;
    elements.push(
      <RigidBody key={`${doorway.id}-step-${i}`} type="fixed" colliders="cuboid">
        <mesh
          position={[x, stepY, z]}
          rotation={[0, yaw, 0]}
          castShadow
          receiveShadow
        >
          {/* width = perpendicular to travel; tread = along travel direction */}
          <boxGeometry args={[stepWidth, rise, tread]} />
          <meshStandardMaterial color="#4a3520" roughness={0.85} />
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
