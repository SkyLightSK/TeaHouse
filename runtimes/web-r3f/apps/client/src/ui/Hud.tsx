import { useAppStore } from "../store.js";
import { useNetwork } from "../net/networkContext.js";

export function Hud() {
  const players = useAppStore((s) => s.players);
  const me = useAppStore((s) => s.mySessionId);
  const voiceConnected = useAppStore((s) => s.voiceConnected);
  const network = useNetwork();

  const meSitting = me ? players.get(me)?.sittingOn : undefined;

  return (
    <div
      style={{
        position: "fixed",
        top: 12,
        left: 12,
        right: 12,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        pointerEvents: "none",
        color: "#e8d9c0",
        fontSize: 12,
        zIndex: 5,
      }}
    >
      <div style={panelStyle}>
        <div style={{ fontWeight: 500, marginBottom: 4 }}>The Tea House</div>
        <div style={{ color: "#a89886" }}>
          {players.size} present {voiceConnected ? "voice on" : "voice off"}
        </div>
      </div>

      <div style={{ ...panelStyle, pointerEvents: "auto" }}>
        {meSitting ? (
          <button onClick={() => network?.stand()} style={btnStyle}>
            Stand up
          </button>
        ) : (
          <span style={{ color: "#a89886" }}>WASD + mouse</span>
        )}
      </div>
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  background: "rgba(20, 14, 10, 0.7)",
  border: "1px solid rgba(232, 217, 192, 0.15)",
  padding: "8px 12px",
  borderRadius: 6,
  backdropFilter: "blur(4px)",
};

const btnStyle: React.CSSProperties = {
  background: "#a16a3a",
  color: "#fff",
  border: "none",
  padding: "4px 10px",
  borderRadius: 4,
  cursor: "pointer",
  fontSize: 12,
};
