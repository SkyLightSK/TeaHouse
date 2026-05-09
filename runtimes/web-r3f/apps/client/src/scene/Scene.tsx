import { Suspense } from "react";
import { Environment } from "@react-three/drei";
import { Physics } from "@react-three/rapier";
import { Bloom, EffectComposer, ToneMapping } from "@react-three/postprocessing";
import { ToneMappingMode } from "postprocessing";
import { room } from "../spec.js";
import { StubRoom } from "./StubRoom.js";
import { SpecLights } from "./SpecLights.js";
import { SitPoints } from "./SitPoints.js";
import { Interactables } from "./Interactables.js";
import { LocalPlayer } from "../player/LocalPlayer.js";
import { RemotePlayers } from "../player/RemotePlayers.js";

export function Scene() {
  return (
    <Suspense fallback={null}>
      <color attach="background" args={["#1a1410"]} />
      <fog attach="fog" args={["#1a1410", 8, 30]} />

      <Environment preset="warehouse" environmentIntensity={0.35} />
      <SpecLights spec={room} />

      <Physics gravity={[0, -9.81, 0]} timeStep={1 / 60}>
        <StubRoom spec={room} />
        <SitPoints spec={room} />
        <Interactables spec={room} />
        <LocalPlayer spec={room} />
        <RemotePlayers />
      </Physics>

      <EffectComposer>
        <Bloom mipmapBlur intensity={0.4} luminanceThreshold={0.85} />
        <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
      </EffectComposer>
    </Suspense>
  );
}
