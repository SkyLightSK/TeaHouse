import { createContext, useContext } from "react";
import type { PoseUpdate } from "@teahouse/shared";

export interface NetworkApi {
  sendPose: (pose: PoseUpdate) => void;
  sit: (sitPointId: string) => void;
  stand: () => void;
  interact: (interactableId: string) => void;
  leave: () => void;
}

export const NetworkContext = createContext<NetworkApi | null>(null);

export function useNetwork(): NetworkApi | null {
  return useContext(NetworkContext);
}
