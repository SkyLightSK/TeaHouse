import { Schema, type } from "@colyseus/schema";

export class Vec3 extends Schema {
  @type("number") x = 0;
  @type("number") y = 0;
  @type("number") z = 0;
}

export class Player extends Schema {
  @type("string") sessionId = "";
  @type("string") name = "";
  @type("string") avatarUrl = "";
  @type(Vec3) position = new Vec3();
  @type("number") rotationY = 0;
  @type("string") animationState: "idle" | "walking" | "running" | "sitting" | "wave" = "idle";
  @type("string") sittingOn = "";
  @type("string") holdingPropId = "";
  @type("number") joinedAt = 0;
}
