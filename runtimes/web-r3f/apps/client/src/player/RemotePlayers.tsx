import { useMemo } from "react";
import { Html } from "@react-three/drei";
import { useAppStore } from "../store.js";

/**
 * Renders every remote player as a simple capsule + nameplate placeholder.
 * Replaced by Ready Player Me GLB loader once the user supplies avatar URLs.
 */
export function RemotePlayers() {
  const players = useAppStore((s) => s.players);
  const me = useAppStore((s) => s.mySessionId);

  const list = useMemo(() => {
    const out: { sessionId: string; name: string; pos: [number, number, number]; rotY: number }[] = [];
    players.forEach((p) => {
      if (p.sessionId === me) return;
      out.push({
        sessionId: p.sessionId,
        name: p.name || "guest",
        pos: [p.position.x, p.position.y, p.position.z],
        rotY: p.rotationY,
      });
    });
    return out;
  }, [players, me]);

  return (
    <>
      {list.map((p) => (
        <group key={p.sessionId} position={p.pos} rotation={[0, p.rotY, 0]}>
          <mesh castShadow position={[0, 0.85, 0]}>
            <capsuleGeometry args={[0.3, 1.1, 4, 12]} />
            <meshStandardMaterial color="#a16a3a" roughness={0.6} />
          </mesh>
          <Html
            position={[0, 1.9, 0]}
            center
            distanceFactor={6}
            style={{ pointerEvents: "none", userSelect: "none" }}
          >
            <div
              style={{
                background: "rgba(20, 14, 10, 0.7)",
                color: "#e8d9c0",
                padding: "2px 8px",
                borderRadius: 4,
                fontSize: 12,
                whiteSpace: "nowrap",
                border: "1px solid rgba(232, 217, 192, 0.2)",
              }}
            >
              {p.name}
            </div>
          </Html>
        </group>
      ))}
    </>
  );
}
