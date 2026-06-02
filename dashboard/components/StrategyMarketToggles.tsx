"use client";

import { useState } from "react";
import { Strategy } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";
const API_SECRET = process.env.NEXT_PUBLIC_API_SECRET || "";

interface Props {
  strategy: Strategy;
}

export default function StrategyMarketToggles({ strategy }: Props) {
  const [perp, setPerp] = useState(strategy.apply_perp);
  const [meme, setMeme] = useState(strategy.apply_meme);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);

  async function save(newPerp: boolean, newMeme: boolean) {
    setLoading(true);
    setSaved(false);
    try {
      await fetch(`${API_BASE}/api/strategies/${strategy.id}/markets`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${API_SECRET}`,
        },
        body: JSON.stringify({ apply_perp: newPerp, apply_spot: false, apply_meme: newMeme }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setLoading(false);
    }
  }

  function toggle(market: "perp" | "meme") {
    const newPerp = market === "perp" ? !perp : perp;
    const newMeme = market === "meme" ? !meme : meme;
    if (market === "perp") setPerp(newPerp);
    if (market === "meme") setMeme(newMeme);
    save(newPerp, newMeme);
  }

  const pillBase: React.CSSProperties = {
    display: "inline-flex", alignItems: "center", gap: "6px",
    padding: "7px 14px", borderRadius: "8px", fontWeight: 600,
    fontSize: "13px", cursor: "pointer", border: "1.5px solid",
    transition: "all 0.2s", userSelect: "none",
  };

  const activePill: React.CSSProperties = {
    ...pillBase,
    background: "rgba(34,197,94,0.15)", borderColor: "rgba(34,197,94,0.5)",
    color: "#4ade80",
  };

  const inactivePill: React.CSSProperties = {
    ...pillBase,
    background: "rgba(255,255,255,0.04)", borderColor: "rgba(255,255,255,0.1)",
    color: "var(--text-muted)",
  };

  const disabledPill: React.CSSProperties = {
    ...pillBase,
    background: "rgba(255,255,255,0.02)", borderColor: "rgba(255,255,255,0.06)",
    color: "var(--text-muted)", cursor: "not-allowed", opacity: 0.5,
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      <div style={{ fontSize: "11px", color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
        Apply Strategy To
      </div>
      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
        {/* Perp Toggle */}
        <div
          style={perp ? activePill : inactivePill}
          onClick={() => !loading && toggle("perp")}
          title="Toggle HL Perp trading"
        >
          <span>{perp ? "✓" : "○"}</span>
          ⚡ Perp
        </div>

        {/* Spot — Coming Soon */}
        <div style={disabledPill} title="Spot trading coming soon">
          <span>○</span>
          🪙 Spot
          <span style={{ fontSize: "10px", background: "rgba(251,191,36,0.2)", color: "#fbbf24", padding: "1px 5px", borderRadius: "4px", marginLeft: "2px" }}>
            Soon
          </span>
        </div>

        {/* Meme Toggle */}
        <div
          style={meme ? activePill : inactivePill}
          onClick={() => !loading && toggle("meme")}
          title="Toggle Meme bot trading"
        >
          <span>{meme ? "✓" : "○"}</span>
          🚀 Meme
        </div>

        {loading && (
          <span style={{ fontSize: "12px", color: "var(--text-muted)", alignSelf: "center" }}>Saving…</span>
        )}
        {saved && (
          <span style={{ fontSize: "12px", color: "#4ade80", alignSelf: "center" }}>✓ Saved</span>
        )}
      </div>
    </div>
  );
}
