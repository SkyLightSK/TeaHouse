import type { RoomSpec } from "@teahouse/shared";

interface Props {
  spec: RoomSpec;
}

export function SpecLights({ spec }: Props) {
  return (
    <>
      <ambientLight intensity={0.25} color="#fff1de" />
      {spec.lights?.map((l) => {
        const color = l.color ?? "#ffffff";
        const intensity = l.intensity ?? 1;
        if (l.kind === "point") {
          return (
            <pointLight
              key={l.id}
              position={l.position}
              color={color}
              intensity={intensity}
              distance={l.distance ?? 0}
              decay={l.decay ?? 2}
              castShadow={l.castShadow ?? false}
            />
          );
        }
        if (l.kind === "spot") {
          return (
            <spotLight
              key={l.id}
              position={l.position}
              color={color}
              intensity={intensity}
              distance={l.distance ?? 0}
              decay={l.decay ?? 2}
              castShadow={l.castShadow ?? false}
            />
          );
        }
        if (l.kind === "directional") {
          return (
            <directionalLight
              key={l.id}
              position={l.position}
              color={color}
              intensity={intensity}
              castShadow={l.castShadow ?? false}
            />
          );
        }
        return null;
      })}
    </>
  );
}
