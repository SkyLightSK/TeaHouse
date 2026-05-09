/**
 * Compile-time + runtime configuration.
 * Override via Vite env vars in `.env.local` (prefix VITE_).
 */
export const config = {
  serverUrl: import.meta.env.VITE_SERVER_URL ?? "ws://localhost:2567",
  defaultAvatarUrl:
    import.meta.env.VITE_DEFAULT_AVATAR_URL ??
    "https://models.readyplayer.me/64bfa7b5d1d6e7001e8e1f1a.glb",
  poseHz: 15,
  enableXR: import.meta.env.VITE_ENABLE_XR === "true",
} as const;
