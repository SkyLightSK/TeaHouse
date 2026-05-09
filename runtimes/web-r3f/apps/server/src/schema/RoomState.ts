import { MapSchema, Schema, type } from "@colyseus/schema";
import { Player } from "./Player.js";

export class PropState extends Schema {
  @type("string") id = "";
  @type("number") x = 0;
  @type("number") y = 0;
  @type("number") z = 0;
  @type("number") rotationY = 0;
  @type("string") heldBy = "";
}

export class RoomState extends Schema {
  @type({ map: Player }) players = new MapSchema<Player>();
  @type({ map: PropState }) props = new MapSchema<PropState>();
  @type({ map: "string" }) seatOccupancy = new MapSchema<string>();
}
