import { Room, RoomEvent, type RemoteParticipant, Track } from "livekit-client";
import { useAppStore } from "../store.js";

let room: Room | null = null;

export async function connectVoice(url: string, token: string): Promise<Room> {
  if (room) return room;
  room = new Room({
    adaptiveStream: true,
    dynacast: true,
    audioCaptureDefaults: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });

  room.on(RoomEvent.TrackSubscribed, (track, _publication, participant) => {
    if (track.kind === Track.Kind.Audio) {
      attachSpatialAudio(track, participant);
    }
  });

  await room.connect(url, token);
  await room.localParticipant.setMicrophoneEnabled(true);
  useAppStore.getState().setVoiceConnected(true);
  return room;
}

export function disconnectVoice(): void {
  room?.disconnect();
  room = null;
  useAppStore.getState().setVoiceConnected(false);
}

/**
 * Updates per-frame: positions every remote audio source at its avatar's
 * world position so distance-based attenuation feels right.
 */
export function updateSpatialPositions(
  listenerPos: { x: number; y: number; z: number },
  listenerForward: { x: number; y: number; z: number },
  participantPositions: Map<string, { x: number; y: number; z: number }>,
): void {
  if (!room) return;
  const ctx = audioContext();
  if (!ctx) return;
  const listener = ctx.listener;
  if (listener.positionX) {
    listener.positionX.value = listenerPos.x;
    listener.positionY.value = listenerPos.y;
    listener.positionZ.value = listenerPos.z;
    listener.forwardX.value = listenerForward.x;
    listener.forwardY.value = listenerForward.y;
    listener.forwardZ.value = listenerForward.z;
    listener.upX.value = 0;
    listener.upY.value = 1;
    listener.upZ.value = 0;
  }
  for (const [identity, pos] of participantPositions) {
    const node = panners.get(identity);
    if (node?.positionX) {
      node.positionX.value = pos.x;
      node.positionY.value = pos.y;
      node.positionZ.value = pos.z;
    }
  }
}

const panners = new Map<string, PannerNode>();

function audioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { __teahouseAudioCtx?: AudioContext };
  if (!w.__teahouseAudioCtx) {
    try {
      w.__teahouseAudioCtx = new AudioContext();
    } catch {
      return null;
    }
  }
  return w.__teahouseAudioCtx ?? null;
}

function attachSpatialAudio(track: any, participant: RemoteParticipant): void {
  const ctx = audioContext();
  if (!ctx) return;
  const stream: MediaStream | undefined = track.mediaStream;
  if (!stream) return;
  const src = ctx.createMediaStreamSource(stream);
  const panner = new PannerNode(ctx, {
    panningModel: "HRTF",
    distanceModel: "inverse",
    refDistance: 1,
    rolloffFactor: 1.2,
    maxDistance: 20,
  });
  src.connect(panner);
  panner.connect(ctx.destination);
  panners.set(participant.identity, panner);
}
