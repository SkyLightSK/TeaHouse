import { useState } from "react";
import type { RoomSpec } from "@teahouse/shared";
import { useNetwork } from "../net/networkContext.js";

interface Props {
  spec: RoomSpec;
}

/**
 * Renders a small visual marker at every sit point and lets the local player
 * click to request a sit/stand. The actual avatar snap happens in
 * LocalPlayer once the server confirms.
 */
export function SitPoints({ spec }: Props) {
  const network = useNetwork();
  const [hover, setHover] = useState<string | null>(null);

  return (
    <>
      {spec.sitPoints?.map((s) => (
        <mesh
          key={s.id}
          position={[s.position[0], s.position[1] + 0.02, s.position[2]]}
          rotation={[-Math.PI / 2, 0, 0]}
          onPointerOver={(e) => {
            e.stopPropagation();
            setHover(s.id);
            document.body.style.cursor = "pointer";
          }}
          onPointerOut={() => {
            setHover(null);
            document.body.style.cursor = "auto";
          }}
          onClick={(e) => {
            e.stopPropagation();
            network?.sit(s.id);
          }}
        >
          <ringGeometry args={[0.25, 0.32, 24]} />
          <meshBasicMaterial
            color={hover === s.id ? "#ffd28a" : "#996644"}
            transparent
            opacity={0.6}
          />
        </mesh>
      ))}
    </>
  );
}
