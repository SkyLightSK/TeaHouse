import { Room, Client } from "@colyseus/core";
import { AccessToken } from "livekit-server-sdk";
import type {
  JoinOptions,
  PoseUpdate,
  SitRequest,
  InteractRequest,
} from "@teahouse/shared";
import { RoomState, PropState } from "../schema/RoomState.js";
import { Player } from "../schema/Player.js";

const LIVEKIT_API_KEY = process.env.LIVEKIT_API_KEY ?? "";
const LIVEKIT_API_SECRET = process.env.LIVEKIT_API_SECRET ?? "";
const LIVEKIT_URL = process.env.LIVEKIT_URL ?? "";

export class TeaHouseRoom extends Room<RoomState> {
  state = new RoomState();
  maxClients = 16;

  override onCreate(): void {
    this.setPatchRate(1000 / 20);

    this.onMessage("pose", (client, payload: PoseUpdate) => {
      const p = this.state.players.get(client.sessionId);
      if (!p || p.sittingOn) return;
      p.position.x = payload.position.x;
      p.position.y = payload.position.y;
      p.position.z = payload.position.z;
      p.rotationY = payload.rotationY;
      p.animationState = payload.animationState;
    });

    this.onMessage("sit", (client, payload: SitRequest) => {
      const p = this.state.players.get(client.sessionId);
      if (!p) return;
      const occupant = this.state.seatOccupancy.get(payload.sitPointId);
      if (occupant && occupant !== client.sessionId) return;
      if (p.sittingOn) {
        this.state.seatOccupancy.delete(p.sittingOn);
      }
      p.sittingOn = payload.sitPointId;
      p.animationState = "sitting";
      this.state.seatOccupancy.set(payload.sitPointId, client.sessionId);
    });

    this.onMessage("stand", (client) => {
      const p = this.state.players.get(client.sessionId);
      if (!p) return;
      if (p.sittingOn) {
        this.state.seatOccupancy.delete(p.sittingOn);
        p.sittingOn = "";
      }
      p.animationState = "idle";
    });

    this.onMessage("interact", (client, payload: InteractRequest) => {
      const p = this.state.players.get(client.sessionId);
      if (!p) return;
      let prop = this.state.props.get(payload.interactableId);
      if (!prop) {
        prop = new PropState();
        prop.id = payload.interactableId;
        this.state.props.set(prop.id, prop);
      }
      if (prop.heldBy && prop.heldBy !== client.sessionId) return;
      if (prop.heldBy === client.sessionId) {
        prop.heldBy = "";
        p.holdingPropId = "";
      } else {
        prop.heldBy = client.sessionId;
        p.holdingPropId = prop.id;
      }
    });
  }

  override onJoin(client: Client, options: JoinOptions): void {
    const p = new Player();
    p.sessionId = client.sessionId;
    p.name = (options?.name || "guest").slice(0, 32);
    p.avatarUrl = options?.avatarUrl ?? "";
    p.position.x = 0;
    p.position.y = 0;
    p.position.z = 3.5;
    p.rotationY = 180;
    p.joinedAt = Date.now();
    this.state.players.set(client.sessionId, p);
    console.log(`[teahouse] +join ${p.name} (${client.sessionId}) — total ${this.state.players.size}`);

    if (LIVEKIT_API_KEY && LIVEKIT_API_SECRET && LIVEKIT_URL) {
      void this.issueLiveKitToken(client, p.name).catch((e) =>
        console.warn("[teahouse] livekit token failed", e),
      );
    }
  }

  private async issueLiveKitToken(client: Client, identity: string): Promise<void> {
    const at = new AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET, {
      identity,
      ttl: 60 * 60,
    });
    at.addGrant({
      room: "teahouse",
      roomJoin: true,
      canPublish: true,
      canSubscribe: true,
    });
    const token = await at.toJwt();
    client.send("livekit-token", { url: LIVEKIT_URL, token, room: "teahouse" });
  }

  override onLeave(client: Client): void {
    const p = this.state.players.get(client.sessionId);
    if (p?.sittingOn) {
      this.state.seatOccupancy.delete(p.sittingOn);
    }
    if (p?.holdingPropId) {
      const prop = this.state.props.get(p.holdingPropId);
      if (prop) prop.heldBy = "";
    }
    this.state.players.delete(client.sessionId);
    console.log(`[teahouse] -leave (${client.sessionId}) — total ${this.state.players.size}`);
  }

  override onDispose(): void {
    console.log("[teahouse] room disposed");
  }
}
