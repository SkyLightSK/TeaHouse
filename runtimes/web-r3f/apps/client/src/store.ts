import { create } from "zustand";
import type { PlayerStateView } from "@teahouse/shared";

export interface AppState {
  joined: boolean;
  myName: string;
  myAvatarUrl: string;
  mySessionId: string | null;
  players: Map<string, PlayerStateView>;
  voiceConnected: boolean;
  voiceUrl: string;
  voiceToken: string;

  setJoined: (joined: boolean) => void;
  setIdentity: (name: string, avatarUrl: string) => void;
  setSessionId: (id: string | null) => void;
  upsertPlayer: (p: PlayerStateView) => void;
  removePlayer: (sessionId: string) => void;
  setPlayers: (list: PlayerStateView[]) => void;
  setVoice: (url: string, token: string) => void;
  setVoiceConnected: (v: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  joined: false,
  myName: "",
  myAvatarUrl: "",
  mySessionId: null,
  players: new Map(),
  voiceConnected: false,
  voiceUrl: "",
  voiceToken: "",

  setJoined: (joined) => set({ joined }),
  setIdentity: (myName, myAvatarUrl) => set({ myName, myAvatarUrl }),
  setSessionId: (mySessionId) => set({ mySessionId }),
  upsertPlayer: (p) =>
    set((s) => {
      const next = new Map(s.players);
      next.set(p.sessionId, p);
      return { players: next };
    }),
  removePlayer: (sessionId) =>
    set((s) => {
      const next = new Map(s.players);
      next.delete(sessionId);
      return { players: next };
    }),
  setPlayers: (list) => set({ players: new Map(list.map((p) => [p.sessionId, p])) }),
  setVoice: (voiceUrl, voiceToken) => set({ voiceUrl, voiceToken }),
  setVoiceConnected: (voiceConnected) => set({ voiceConnected }),
}));
