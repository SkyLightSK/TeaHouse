/**
 * Loads and exposes the canonical room descriptor.
 * Imports the JSON directly at build-time so the spec ships with the bundle.
 */
import type { RoomSpec } from "@teahouse/shared";
import roomJson from "../../../../../spec/teahouse.room.json";

export const room = roomJson as unknown as RoomSpec;
