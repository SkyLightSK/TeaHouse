/**
 * TypeScript types for spec/room.schema.json.
 * Mirror this whenever the schema changes (or generate via json-schema-to-typescript later).
 */

export type Vec3 = [number, number, number];

export type ScaleUnit = "meters" | "centimeters" | "feet";
export type UpAxis = "+Y" | "+Z";

export type AssetFormat =
  | "glb"
  | "gltf"
  | "fbx"
  | "usdz"
  | "splat"
  | "ksplat"
  | "ply";

export interface AssetRef {
  src: string;
  format: AssetFormat;
  size?: number;
}

export interface SpawnPoint {
  id: string;
  position: Vec3;
  rotationY: number;
  priority?: number;
  roomId?: string;
}

export type SitKind = "chair" | "couch" | "floor" | "stool" | "bench";

export interface SitPoint {
  id: string;
  position: Vec3;
  rotationY: number;
  kind: SitKind;
  roomId?: string;
}

export type InteractableKind =
  | "pickup"
  | "toggle"
  | "button"
  | "door"
  | "pour";

export interface Interactable {
  id: string;
  asset?: AssetRef;
  position: Vec3;
  rotationY?: number;
  kind: InteractableKind;
  event?: string;
  respawnAfter?: number;
  roomId?: string;
}

export type LightKind = "point" | "spot" | "directional" | "area";

export interface Light {
  id: string;
  position: Vec3;
  kind: LightKind;
  color?: string;
  intensity?: number;
  distance?: number;
  decay?: number;
  castShadow?: boolean;
  roomId?: string;
}

export type RoomKind =
  | "tearoom"
  | "teabar"
  | "store"
  | "corridor"
  | "toilet"
  | "hall"
  | "entrance"
  | "spawn"
  | "lecture_hall"
  | "other";

export type Vec2 = [number, number];

export interface Room {
  id: string;
  name: string;
  kind?: RoomKind;
  center: Vec2;
  size: Vec2;
  floorY: number;
  ceilingHeight?: number;
  wallColor?: string;
  floorColor?: string;
}

export interface DoorwaySteps {
  count: number;
  rise?: number;
  /** Per-step depth along the travel direction. */
  tread?: number;
  /**
   * Optional unit vector (dx, dz) pointing FROM the lower room toward the
   * higher room. When set, the staircase runs in this direction (used for
   * 45° / diagonal staircases). When omitted, the renderer derives an
   * axis-aligned direction from the doorway wall.
   */
  direction?: Vec2;
}

export interface Doorway {
  id: string;
  between: [string, string];
  position: Vec2;
  width: number;
  height?: number;
  steps?: DoorwaySteps;
}

export interface AmbientAudio {
  id: string;
  src: string;
  volume?: number;
  loop?: boolean;
  global?: boolean;
  position?: Vec3;
  radius?: number;
}

export interface Portal {
  id: string;
  position: Vec3;
  rotationY?: number;
  to: string;
}

export interface RoomDimensions {
  width: number;
  length: number;
  height: number;
}

export interface RoomSpec {
  $schema?: string;
  version: string;
  id: string;
  name: string;
  scale: ScaleUnit;
  up: UpAxis;
  dimensions?: RoomDimensions;
  geometry: {
    shell: AssetRef;
    splat?: AssetRef;
  };
  spawnPoints: SpawnPoint[];
  sitPoints?: SitPoint[];
  interactables?: Interactable[];
  lights?: Light[];
  ambientAudio?: AmbientAudio[];
  portals?: Portal[];
  rooms?: Room[];
  doorways?: Doorway[];
  metadata?: Record<string, unknown>;
}
