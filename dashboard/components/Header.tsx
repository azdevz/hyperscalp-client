// dashboard/components/Header.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { api, BotState } from "@/lib/api";

export default function Header() {
  const [state, setState] = useState<BotState | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  // Fetch bot state
  const refresh = useCallback(async () => {
    try {
      const s = await api.getState();
      setState(s);
    } catch { /* offline */ }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 8000); // poll every 8s
    return () => clearInterval(interval);
  }, [refresh]);

  // Handle switching testnet / mainnet
  const handleToggleMode = async (targetMode: "demo" | "live") => {
    if (loading || !state) return;
    const currentMode = state.mode ?? "demo";
    if (currentMode === targetMode) return;

    setLoading(true);
    try {
      await api.updateState("hl_network_regime", targetMode);
      // Force instant route refresh and reload to update tables on the active page
      router.refresh();
      window.location.reload();
    } catch (e) {
      console.error("Failed to toggle network mode:", e);
    } finally {
      setLoading(false);
    }
  };

  // Convert pathname to descriptive page title
  const getPageTitle = () => {
    switch (pathname) {
      case "/": return "📊 Overview";
      case "/positions": return "📋 Live Positions";
      case "/meme": return "🚀 Meme Bot Watchlist";
      case "/log": return "📜 Trade Log History";
      case "/signals": return "📡 Signal Monitor";
      default: return "⚡ Scaling Terminal";
    }
  };

  const currentMode = state?.mode ?? "demo";
  const hlActive = state?.hl_active;
  const memeActive = state?.meme_active;
  const isRunning = hlActive || memeActive;
  const isEmergency = state?.emergency_stop === "true";

  return (
    <header style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      padding: "12px 24px",
      background: "rgba(12, 18, 32, 0.5)",
      backdropFilter: "blur(12px)",
      WebkitBackdropFilter: "blur(12px)",
      borderBottom: "1px solid var(--border)",
      marginBottom: "24px",
      borderRadius: "12px",
      gap: "16px",
      boxShadow: "0 4px 20px rgba(0, 0, 0, 0.15)",
    }}>
      {/* Left side: Dynamic active page indicator */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <div style={{ fontSize: "16px", fontWeight: 800, color: "var(--text-primary)", letterSpacing: "0.02em" }}>
          {getPageTitle()}
        </div>
        
        {/* Connection status indicator */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          background: "rgba(255, 255, 255, 0.03)",
          padding: "4px 8px",
          borderRadius: "6px",
          border: "1px solid var(--border)",
          fontSize: "11px",
        }}>
          <span className={`status-dot ${isEmergency ? "stopped" : isRunning ? "live" : "paused"}`} />
          <span style={{ color: "var(--text-secondary)", fontWeight: 600 }}>
            {isEmergency ? "STOPPED" : isRunning ? "BOT LIVE" : "BOT IDLE"}
          </span>
        </div>
      </div>

      {/* Right side: Interactive universal toggle switch */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Network Regime:
        </span>
        
        <div style={{
          display: "flex",
          background: "rgba(0, 0, 0, 0.3)",
          border: "1.5px solid var(--border-bright)",
          borderRadius: "20px",
          padding: "2px",
          width: "200px",
          position: "relative",
          boxShadow: "inset 0 2px 4px rgba(0,0,0,0.5)",
        }}>
          {/* Testnet pill */}
          <button
            type="button"
            disabled={loading}
            onClick={() => handleToggleMode("demo")}
            style={{
              flex: 1,
              padding: "5px 10px",
              borderRadius: "16px",
              fontSize: "10px",
              fontWeight: 800,
              cursor: loading ? "not-allowed" : "pointer",
              border: "none",
              transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
              zIndex: 2,
              background: currentMode === "demo" ? "var(--accent-amber)" : "transparent",
              color: currentMode === "demo" ? "#000000" : "var(--text-secondary)",
              boxShadow: currentMode === "demo" ? "0 0 10px rgba(245, 158, 11, 0.4)" : "none",
            }}
          >
            🟡 TESTNET
          </button>
          
          {/* Mainnet pill */}
          <button
            type="button"
            disabled={loading}
            onClick={() => handleToggleMode("live")}
            style={{
              flex: 1,
              padding: "5px 10px",
              borderRadius: "16px",
              fontSize: "10px",
              fontWeight: 800,
              cursor: loading ? "not-allowed" : "pointer",
              border: "none",
              transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
              zIndex: 2,
              background: currentMode === "live" ? "var(--accent-green)" : "transparent",
              color: currentMode === "live" ? "#000000" : "var(--text-secondary)",
              boxShadow: currentMode === "live" ? "0 0 10px rgba(16, 185, 129, 0.4)" : "none",
            }}
          >
            🟢 MAINNET
          </button>
        </div>
      </div>
    </header>
  );
}
