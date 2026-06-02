// dashboard/components/BotControls.tsx
"use client";

import { useState } from "react";
import { api, BotState } from "@/lib/api";

export default function BotControls({
  state,
  onRefresh,
}: {
  state: BotState | null;
  onRefresh: () => void;
}) {
  const [loading, setLoading] = useState<string | null>(null);

  const act = async (fn: () => Promise<unknown>, key: string) => {
    setLoading(key);
    try {
      await fn();
      onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(null);
    }
  };

  const hlActive  = state?.hl_active;
  const memeActive = state?.meme_active;
  const emergency  = state?.emergency_stop === "true";

  return (
    <div className="card fade-in">
      <div className="card-title">⚙️ Bot Controls</div>

      {emergency && (
        <div
          style={{
            background: "rgba(239,68,68,0.12)",
            border: "1px solid rgba(239,68,68,0.4)",
            borderRadius: "8px",
            padding: "10px 14px",
            marginBottom: "14px",
            fontSize: "12px",
            color: "var(--accent-red)",
            fontWeight: 600,
          }}
        >
          🛑 EMERGENCY STOP ACTIVE — all bots halted
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        {/* HL Bot — read-only status */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className={`status-dot ${hlActive ? "live" : "paused"}`} />
            <span style={{ fontSize: "13px", fontWeight: 600 }}>HL Perps Bot</span>
          </div>
          <span style={{
            fontSize: "12px", fontWeight: 600, padding: "4px 10px",
            borderRadius: "6px",
            background: hlActive ? "rgba(34,197,94,0.12)" : "rgba(251,191,36,0.12)",
            color: hlActive ? "#4ade80" : "#fbbf24",
            border: `1px solid ${hlActive ? "rgba(34,197,94,0.3)" : "rgba(251,191,36,0.3)"}`,
          }}>
            {hlActive ? "● Running" : "⏸ Paused"}
          </span>
        </div>

        {/* Meme Bot — read-only status */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className={`status-dot ${memeActive ? "live" : "paused"}`} />
            <span style={{ fontSize: "13px", fontWeight: 600 }}>Meme Bot</span>
          </div>
          <span style={{
            fontSize: "12px", fontWeight: 600, padding: "4px 10px",
            borderRadius: "6px",
            background: memeActive ? "rgba(34,197,94,0.12)" : "rgba(251,191,36,0.12)",
            color: memeActive ? "#4ade80" : "#fbbf24",
            border: `1px solid ${memeActive ? "rgba(34,197,94,0.3)" : "rgba(251,191,36,0.3)"}`,
          }}>
            {memeActive ? "● Running" : "⏸ Paused"}
          </span>
        </div>
      </div>
    </div>
  );
}
