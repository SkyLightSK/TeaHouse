import { useState } from "react";
import { useAppStore } from "../store.js";
import { config } from "../config.js";

interface Props {
  onJoin: (name: string, avatarUrl: string) => Promise<void>;
}

export function JoinScreen({ onJoin }: Props) {
  const [name, setName] = useState(localStorage.getItem("teahouse:name") ?? "");
  const [avatarUrl, setAvatarUrl] = useState(
    localStorage.getItem("teahouse:avatar") ?? config.defaultAvatarUrl,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Please enter a name");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      localStorage.setItem("teahouse:name", name);
      localStorage.setItem("teahouse:avatar", avatarUrl);
      useAppStore.getState().setIdentity(name, avatarUrl);
      await onJoin(name, avatarUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        display: "grid",
        placeItems: "center",
        background:
          "radial-gradient(ellipse at center, rgba(82, 50, 28, 0.4) 0%, #1a1410 70%)",
        zIndex: 10,
      }}
    >
      <form
        onSubmit={submit}
        style={{
          background: "rgba(28, 20, 14, 0.94)",
          padding: "32px 40px",
          borderRadius: 12,
          border: "1px solid rgba(232, 217, 192, 0.15)",
          boxShadow: "0 24px 60px rgba(0, 0, 0, 0.6)",
          width: 380,
          maxWidth: "90vw",
        }}
      >
        <h1 style={{ margin: 0, fontSize: 28, fontWeight: 500 }}>The Tea House</h1>
        <p style={{ marginTop: 8, marginBottom: 24, color: "#a89886", fontSize: 13, lineHeight: 1.5 }}>
          A 3D recreation of a real place. Walk around, sit on the couch, meet your friends.
        </p>

        <Field label="Your name">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={32}
            autoFocus
            style={inputStyle}
          />
        </Field>

        <Field label="Avatar GLB URL (Ready Player Me)">
          <input
            type="url"
            value={avatarUrl}
            onChange={(e) => setAvatarUrl(e.target.value)}
            placeholder="https://models.readyplayer.me/...glb"
            style={inputStyle}
          />
          <a
            href="https://readyplayer.me/avatar"
            target="_blank"
            rel="noreferrer"
            style={{ color: "#c9a877", fontSize: 12, marginTop: 4, display: "inline-block" }}
          >
            Create one at readyplayer.me &rarr;
          </a>
        </Field>

        {error && (
          <div
            style={{
              background: "rgba(180, 60, 60, 0.2)",
              border: "1px solid rgba(180, 60, 60, 0.5)",
              padding: 8,
              borderRadius: 6,
              fontSize: 13,
              marginBottom: 12,
              color: "#f0c0c0",
            }}
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          style={{
            width: "100%",
            padding: "12px 20px",
            background: busy ? "#5a4030" : "#a16a3a",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: busy ? "wait" : "pointer",
            fontSize: 15,
            fontWeight: 500,
            marginTop: 8,
            transition: "background 0.15s",
          }}
        >
          {busy ? "Joining..." : "Enter the room"}
        </button>

        <p
          style={{
            marginTop: 16,
            fontSize: 11,
            color: "#7a6a58",
            lineHeight: 1.5,
          }}
        >
          Controls: <b>WASD</b> move, <b>mouse</b> look, <b>space</b> jump, <b>shift</b> sprint, click sit-rings to sit, <b>esc</b> release cursor.
        </p>
      </form>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "10px 12px",
  background: "rgba(0, 0, 0, 0.3)",
  border: "1px solid rgba(232, 217, 192, 0.2)",
  borderRadius: 6,
  color: "#e8d9c0",
  fontSize: 14,
  fontFamily: "inherit",
  boxSizing: "border-box",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "block", marginBottom: 16 }}>
      <div style={{ fontSize: 12, color: "#a89886", marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5 }}>
        {label}
      </div>
      {children}
    </label>
  );
}
