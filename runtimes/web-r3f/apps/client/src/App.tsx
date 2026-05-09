import { useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Scene } from "./scene/Scene.js";
import { JoinScreen } from "./ui/JoinScreen.js";
import { Hud } from "./ui/Hud.js";
import { NetworkContext, type NetworkApi } from "./net/networkContext.js";
import { connect } from "./net/colyseus.js";
import { connectVoice } from "./net/livekit.js";
import { useAppStore } from "./store.js";

export function App() {
  const joined = useAppStore((s) => s.joined);
  const voiceUrl = useAppStore((s) => s.voiceUrl);
  const voiceToken = useAppStore((s) => s.voiceToken);
  const [network, setNetwork] = useState<NetworkApi | null>(null);

  const handleJoin = async (name: string, avatarUrl: string) => {
    const api = await connect({ name, avatarUrl });
    setNetwork(api);
    useAppStore.getState().setJoined(true);
  };

  useEffect(() => {
    if (joined && voiceUrl && voiceToken) {
      connectVoice(voiceUrl, voiceToken).catch((e) =>
        console.warn("voice connect failed", e),
      );
    }
  }, [joined, voiceUrl, voiceToken]);

  return (
    <NetworkContext.Provider value={network}>
      {!joined && <JoinScreen onJoin={handleJoin} />}
      {joined && <Hud />}
      <Canvas
        shadows
        gl={{ antialias: true, powerPreference: "high-performance" }}
        camera={{ fov: 70, near: 0.05, far: 100, position: [0, 1.6, 3.5] }}
        style={{ position: "fixed", inset: 0 }}
      >
        <Scene />
      </Canvas>
    </NetworkContext.Provider>
  );
}
