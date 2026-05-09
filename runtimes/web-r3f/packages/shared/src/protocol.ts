/**
 * Network protocol types shared between Colyseus client and server.
 * Mirrors the Colyseus Schema definitions on the server.
 */

export interface PlayerStateView {
  sessionId: string;
  name: string;
  avatarUrl: string;
  position: { x: number; y: number; z: number };
  rotationY: number;
  animationState: AnimationState;
  sittingOn?: string;
  holdingPropId?: string;
}

export type AnimationState = "idle" | "walking" | "running" | "sitting" | "wave";

export interface PoseUpdate {
  position: { x: number; y: number; z: number };
  rotationY: number;
  animationState: AnimationState;
}

export interface JoinOptions {
  name: string;
  avatarUrl: string;
}

export interface SitRequest {
  sitPointId: string;
}

export interface InteractRequest {
  interactableId: string;
}

export type ClientMessage =
  | { type: "pose"; payload: PoseUpdate }
  | { type: "sit"; payload: SitRequest }
  | { type: "stand" }
  | { type: "interact"; payload: InteractRequest };

export const ROOM_NAME = "teahouse" as const;
export const POSE_HZ = 15;
