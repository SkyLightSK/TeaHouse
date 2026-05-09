import { Client, Room, getStateCallbacks } from "colyseus.js";
import {
  ROOM_NAME,
  type JoinOptions,
  type PlayerStateView,
  type PoseUpdate,
} from "@teahouse/shared";
import { config } from "../config.js";
import { useAppStore } from "../store.js";
import type { NetworkApi } from "./networkContext.js";

let activeRoom: Room | null = null;

export async function connect(options: JoinOptions): Promise<NetworkApi> {
  const client = new Client(config.serverUrl);
  const room = await client.joinOrCreate(ROOM_NAME, options);
  activeRoom = room;

  const store = useAppStore.getState();
  store.setSessionId(room.sessionId);

  // Colyseus Schema 3.x callback API: callbacks are accessed via getStateCallbacks(room)
  // rather than directly on the schema instances.
  const $ = getStateCallbacks(room);

  $(room.state).players.onAdd((player: any, sessionId: string) => {
    useAppStore.getState().upsertPlayer(mapPlayer(sessionId, player));
    $(player).onChange(() => {
      useAppStore.getState().upsertPlayer(mapPlayer(sessionId, player));
    });
    if (player.position) {
      $(player.position).onChange(() => {
        useAppStore.getState().upsertPlayer(mapPlayer(sessionId, player));
      });
    }
  });

  $(room.state).players.onRemove((_player: any, sessionId: string) => {
    useAppStore.getState().removePlayer(sessionId);
  });

  room.onMessage("livekit-token", (msg: { url: string; token: string }) => {
    useAppStore.getState().setVoice(msg.url, msg.token);
  });

  room.onLeave(() => {
    useAppStore.getState().setSessionId(null);
    useAppStore.getState().setJoined(false);
    activeRoom = null;
  });

  return {
    sendPose: (pose: PoseUpdate) => {
      room.send("pose", pose);
    },
    sit: (sitPointId: string) => {
      room.send("sit", { sitPointId });
    },
    stand: () => {
      room.send("stand");
    },
    interact: (interactableId: string) => {
      room.send("interact", { interactableId });
    },
    leave: () => {
      room.leave();
    },
  };
}

export function disconnect(): void {
  activeRoom?.leave();
  activeRoom = null;
}

function mapPlayer(sessionId: string, p: any): PlayerStateView {
  return {
    sessionId,
    name: p.name ?? "",
    avatarUrl: p.avatarUrl ?? "",
    position: { x: p.position?.x ?? 0, y: p.position?.y ?? 0, z: p.position?.z ?? 0 },
    rotationY: p.rotationY ?? 0,
    animationState: (p.animationState as PlayerStateView["animationState"]) ?? "idle",
    sittingOn: p.sittingOn || undefined,
    holdingPropId: p.holdingPropId || undefined,
  };
}
