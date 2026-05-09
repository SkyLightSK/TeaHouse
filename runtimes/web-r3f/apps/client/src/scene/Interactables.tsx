import type { RoomSpec } from "@teahouse/shared";
import { useNetwork } from "../net/networkContext.js";

interface Props {
  spec: RoomSpec;
}

export function Interactables({ spec }: Props) {
  const network = useNetwork();
  return (
    <>
      {spec.interactables?.map((it) => (
        <mesh
          key={it.id}
          position={it.position}
          rotation={[0, ((it.rotationY ?? 0) * Math.PI) / 180, 0]}
          castShadow
          onClick={(e) => {
            e.stopPropagation();
            network?.interact(it.id);
          }}
        >
          {it.kind === "pickup" ? (
            <cylinderGeometry args={[0.04, 0.05, 0.06, 16]} />
          ) : (
            <boxGeometry args={[0.1, 0.1, 0.1]} />
          )}
          <meshStandardMaterial color="#e8d9c0" roughness={0.4} />
        </mesh>
      ))}
    </>
  );
}
