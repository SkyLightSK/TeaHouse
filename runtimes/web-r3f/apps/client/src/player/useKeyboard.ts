import { useEffect, useRef } from "react";

export interface KeyState {
  forward: boolean;
  back: boolean;
  left: boolean;
  right: boolean;
  jump: boolean;
  sprint: boolean;
}

export function useKeyboard(): React.MutableRefObject<KeyState> {
  const ref = useRef<KeyState>({
    forward: false,
    back: false,
    left: false,
    right: false,
    jump: false,
    sprint: false,
  });

  useEffect(() => {
    const map: Record<string, keyof KeyState> = {
      KeyW: "forward",
      ArrowUp: "forward",
      KeyS: "back",
      ArrowDown: "back",
      KeyA: "left",
      ArrowLeft: "left",
      KeyD: "right",
      ArrowRight: "right",
      Space: "jump",
      ShiftLeft: "sprint",
      ShiftRight: "sprint",
    };
    const down = (e: KeyboardEvent) => {
      const k = map[e.code];
      if (k) ref.current[k] = true;
    };
    const up = (e: KeyboardEvent) => {
      const k = map[e.code];
      if (k) ref.current[k] = false;
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, []);

  return ref;
}
