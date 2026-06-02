// dashboard/components/BotControls.tsx
"use client";

import { useState, useEffect } from "react";
import { api, BotState, Strategy } from "@/lib/api";

export default function BotControls({
  state,
  onRefresh,
}: {
  state: BotState | null;
  onRefresh: () => void;
}) {
  const [loading, setLoading] = useState<string | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Fetch strategies at load
  useEffect(() => {
    async function loadStrategies() {
      try {
        const res = await api.getStrategies();
        setStrategies(res.strategies || []);
      } catch (e) {
        console.error("Failed to load strategies", e);
      }
    }
    loadStrategies();
  }, []);

  const triggerAction = async (fn: () => Promise<unknown>, key: string, successText?: string) => {
    setLoading(key);
    setSuccessMsg(null);
    try {
      await fn();
      onRefresh();
      if (successText) {
        setSuccessMsg(successText);
        setTimeout(() => setSuccessMsg(null), 3000);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(null);
    }
  };

  const hlActive  = state?.hl_active;
  const memeActive = state?.meme_active;
  const emergency  = state?.emergency_stop === "true";
  const currentMode = state?.mode ?? "demo"; // 'demo' (testnet) | 'live' (mainnet)
  const activeStrategyId = state?.active_strategy?.id ?? 1;

  // Toggle network mode between testnet and mainnet
  const toggleMode = async (targetMode: "demo" | "live") => {
    if (currentMode === targetMode) return;
    const modeLabel = targetMode === "live" ? "Mainnet" : "Testnet";
    await triggerAction(
      () => api.updateState("hl_network_regime", targetMode),
      "mode-toggle",
      `Successfully switched to ${modeLabel}!`
    );
  };

  // Toggle HL active state
  const handleToggleHL = async () => {
    if (hlActive) {
      await triggerAction(
        () => api.updateState("hl_bot_active", "false"),
        "hl-toggle",
        "HL Perps Bot paused."
      );
    } else {
      await triggerAction(
        () => api.resumeHL(),
        "hl-toggle",
        "HL Perps Bot resumed."
      );
    }
  };

  // Toggle Meme active state
  const handleToggleMeme = async () => {
    if (memeActive) {
      await triggerAction(
        () => api.updateState("meme_bot_active", "false"),
        "meme-toggle",
        "Meme Bot paused."
      );
    } else {
      await triggerAction(
        () => api.resumeMeme(),
        "meme-toggle",
        "Meme Bot resumed."
      );
    }
  };

  // Change strategy
  const handleSelectStrategy = async (strategyId: number) => {
    const chosen = strategies.find(s => s.id === strategyId);
    await triggerAction(
      () => api.activateStrategy(strategyId),
      "strategy-change",
      `Strategy set to: ${chosen?.name ?? "Custom"}`
    );
  };

  return (
    <div className="card fade-in" style={{ gridColumn: "span 2", display: "flex", flexDirection: "column", gap: "20px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div className="card-title" style={{ margin: 0 }}>⚙️ Bot Terminal Controls</div>
        {loading && <span style={{ fontSize: "11px", color: "var(--accent-blue)", animation: "pulse 1.5s infinite" }}>Updating system...</span>}
      </div>

      {successMsg && (
        <div
          style={{
            background: "rgba(16,185,129,0.12)",
            border: "1px solid rgba(16,185,129,0.3)",
            borderRadius: "8px",
            padding: "8px 12px",
            fontSize: "12px",
            color: "var(--accent-green)",
            fontWeight: 600,
            textAlign: "center",
          }}
        >
          ✓ {successMsg}
        </div>
      )}

      {emergency && (
        <div
          style={{
            background: "rgba(239,68,68,0.12)",
            border: "1px solid rgba(239,68,68,0.4)",
            borderRadius: "8px",
            padding: "10px 14px",
            fontSize: "12px",
            color: "var(--accent-red)",
            fontWeight: 600,
          }}
        >
          🛑 EMERGENCY STOP ACTIVE — all trading bots are globally halted.
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
        {/* Left Column: Network & Strategy */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          
          {/* 1. Network Toggle Segment Controls */}
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Network Mode
            </span>
            <div style={{
              display: "flex",
              background: "rgba(255,255,255,0.03)",
              border: "1px solid var(--border)",
              borderRadius: "8px",
              padding: "3px",
              width: "100%",
            }}>
              <button
                type="button"
                disabled={loading !== null}
                onClick={() => toggleMode("demo")}
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: 700,
                  cursor: loading ? "not-allowed" : "pointer",
                  border: "none",
                  transition: "all 0.2s",
                  background: currentMode === "demo" ? "rgba(245,158,11,0.15)" : "transparent",
                  color: currentMode === "demo" ? "var(--accent-amber)" : "var(--text-secondary)",
                  borderWidth: currentMode === "demo" ? "1px" : "0",
                  borderColor: "rgba(245,158,11,0.3)",
                  boxShadow: currentMode === "demo" ? "0 0 10px rgba(245,158,11,0.05)" : "none",
                }}
              >
                🟡 TESTNET
              </button>
              <button
                type="button"
                disabled={loading !== null}
                onClick={() => toggleMode("live")}
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: 700,
                  cursor: loading ? "not-allowed" : "pointer",
                  border: "none",
                  transition: "all 0.2s",
                  background: currentMode === "live" ? "rgba(16,185,129,0.15)" : "transparent",
                  color: currentMode === "live" ? "var(--accent-green)" : "var(--text-secondary)",
                  borderWidth: currentMode === "live" ? "1px" : "0",
                  borderColor: "rgba(16,185,129,0.3)",
                  boxShadow: currentMode === "live" ? "0 0 10px rgba(16,185,129,0.05)" : "none",
                }}
              >
                🟢 MAINNET
              </button>
            </div>
          </div>

          {/* 2. Active Strategy Selector Dropdown */}
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Select Active Strategy
            </span>
            <select
              value={activeStrategyId}
              disabled={loading !== null}
              onChange={(e) => handleSelectStrategy(Number(e.target.value))}
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                borderRadius: "8px",
                padding: "10px 12px",
                color: "var(--text-primary)",
                fontWeight: 600,
                outline: "none",
                cursor: loading ? "not-allowed" : "pointer",
              }}
            >
              {strategies.map((strat) => (
                <option key={strat.id} value={strat.id}>
                  🎯 {strat.name}
                </option>
              ))}
            </select>
            {strategies.find(s => s.id === activeStrategyId)?.description && (
              <p style={{ fontSize: "11px", color: "var(--text-muted)", margin: 0, paddingLeft: "4px" }}>
                {strategies.find(s => s.id === activeStrategyId)?.description}
              </p>
            )}
          </div>

        </div>

        {/* Right Column: Execution Bot Toggles */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", justifyContent: "center" }}>
          
          <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Start / Stop Algorithmic Workers
          </span>

          {/* HL Perps Bot Control Row */}
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "rgba(255,255,255,0.02)",
            border: "1px solid var(--border)",
            borderRadius: "10px",
            padding: "12px 16px",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span className={`status-dot ${hlActive ? "live" : "paused"}`} />
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: "13px", fontWeight: 700 }}>HL Perps Scalper</span>
                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>10s Loop interval</span>
              </div>
            </div>
            <button
              type="button"
              disabled={loading !== null || emergency}
              onClick={handleToggleHL}
              style={{
                padding: "6px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 700,
                cursor: (loading || emergency) ? "not-allowed" : "pointer",
                border: "none",
                transition: "all 0.18s",
                background: hlActive ? "rgba(239,68,68,0.12)" : "rgba(16,185,129,0.12)",
                color: hlActive ? "var(--accent-red)" : "var(--accent-green)",
                borderWidth: "1px",
                borderColor: hlActive ? "rgba(239,68,68,0.2)" : "rgba(16,185,129,0.2)",
              }}
            >
              {hlActive ? "⏸ Pause" : "▶ Start"}
            </button>
          </div>

          {/* Meme Bot Control Row */}
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "rgba(255,255,255,0.02)",
            border: "1px solid var(--border)",
            borderRadius: "10px",
            padding: "12px 16px",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span className={`status-dot ${memeActive ? "live" : "paused"}`} />
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: "13px", fontWeight: 700 }}>Solana Meme Scalper</span>
                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>30s Loop interval</span>
              </div>
            </div>
            <button
              type="button"
              disabled={loading !== null || emergency}
              onClick={handleToggleMeme}
              style={{
                padding: "6px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 700,
                cursor: (loading || emergency) ? "not-allowed" : "pointer",
                border: "none",
                transition: "all 0.18s",
                background: memeActive ? "rgba(239,68,68,0.12)" : "rgba(16,185,129,0.12)",
                color: memeActive ? "var(--accent-red)" : "var(--accent-green)",
                borderWidth: "1px",
                borderColor: memeActive ? "rgba(239,68,68,0.2)" : "rgba(16,185,129,0.2)",
              }}
            >
              {memeActive ? "⏸ Pause" : "▶ Start"}
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}
