import "dotenv/config";
import http from "node:http";
import express from "express";
import cors from "cors";
import { Server } from "@colyseus/core";
import { WebSocketTransport } from "@colyseus/ws-transport";
import { monitor } from "@colyseus/monitor";
import { ROOM_NAME } from "@teahouse/shared";
import { TeaHouseRoom } from "./rooms/TeaHouseRoom.js";

const PORT = Number(process.env.PORT ?? 2567);

const app = express();
app.use(cors({ origin: true, credentials: true }));
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "teahouse-server" });
});

app.use("/colyseus", monitor());

const server = http.createServer(app);
const gameServer = new Server({
  transport: new WebSocketTransport({ server }),
});

gameServer.define(ROOM_NAME, TeaHouseRoom);

gameServer.listen(PORT).then(() => {
  console.log(`[teahouse] Colyseus listening on :${PORT}`);
  console.log(`[teahouse] monitor at  http://localhost:${PORT}/colyseus`);
  console.log(`[teahouse] health at    http://localhost:${PORT}/health`);
});
