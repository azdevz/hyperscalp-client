// dashboard/app/signals/page.tsx — Signal Monitor
import { api, Signal, Strategy } from "@/lib/api";

export const dynamic = 'force-dynamic';
export const revalidate = 0;


async function getData() {
  try {
    const [signalsRes, stateRes] = await Promise.allSettled([
      api.getSignals(100),
      api.getState(),
    ]);
    const raw = stateRes.status === "fulfilled" ? stateRes.value.active_strategy : null;
    // Handle both old string response and new Strategy object
    const activeStrategy: Strategy | null =
      raw && typeof raw === "object" ? (raw as Strategy) : null;
    return {
      signals: signalsRes.status === "fulfilled" ? signalsRes.value.signals : [],
      activeStrategy,
    };
  } catch {
    return { signals: [], activeStrategy: null };
  }
}

function SignalBar({ count, direction }: { count?: number | null; direction?: string | null }) {
  if (count == null) count = 0;
  const pipColor = direction === "short" ? "active-short" : direction === "long" ? "active-long" : "";

  return (
    <div className="signal-bar">
      <div className={`signal-pip ${count >= 1 ? pipColor : ""}`} title="Signal 1" />
      <div className={`signal-pip ${count >= 2 ? pipColor : ""}`} title="Signal 2" />
      <div className={`signal-pip ${count >= 3 ? pipColor : ""}`} title="Signal 3" />
      <span style={{ marginLeft: "6px", fontSize: "11px", color: "var(--text-muted)" }}>
        {count}/3
      </span>
    </div>
  );
}

function rsiColor(val: number | null) {
  if (val === null) return "var(--text-muted)";
  if (val < 30)  return "var(--accent-green)";
  if (val > 70)  return "var(--accent-red)";
  return "var(--text-primary)";
}

function adxColor(val: number | null) {
  if (val === null) return "var(--text-muted)";
  if (val >= 25)   return "var(--accent-green)";
  return "var(--text-secondary)";
}

function formatTime(ts: string) {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default async function SignalsPage() {
  const { signals, activeStrategy } = await getData();

  // Latest signal per symbol (HL)
  const latestBySymbol: Record<string, Signal> = {};
  for (const s of signals) {
    if (s.source === "hyperliquid") {
      if (!latestBySymbol[s.symbol] || s.logged_at > latestBySymbol[s.symbol].logged_at) {
        latestBySymbol[s.symbol] = s;
      }
    }
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-title">📡 Signal Monitor</div>
        <div className="page-subtitle">
          Live Order Book Imbalance, CVD Divergence, and Open Interest Squeeze readings — requires ≥2/3 to enter
        </div>
      </div>

      {/* Strategy Card */}
      {activeStrategy && (
        <div className="section">
          <div className="card fade-in" style={{
            background: "linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.06))",
            border: "1px solid rgba(99,102,241,0.3)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "20px" }}>
              {/* Strategy name + description */}
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                  <span style={{ fontSize: "20px" }}>🧠</span>
                  <div>
                    <div style={{ fontSize: "10px", color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Active Strategy</div>
                    <div style={{ fontWeight: 800, fontSize: "18px", color: "#818cf8", fontFamily: "var(--font-mono)" }}>
                      {activeStrategy.name}
                    </div>
                  </div>
                </div>
                {activeStrategy.description && (
                  <div style={{ fontSize: "13px", color: "var(--text-secondary)", marginLeft: "30px" }}>
                    {activeStrategy.description}
                  </div>
                )}
              </div>

              {/* Static market pills — read-only, admin panel coming soon */}
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Markets</div>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  {/* Perp — always enabled by default */}
                  <span style={{
                    display: "inline-flex", alignItems: "center", gap: "5px",
                    padding: "6px 13px", borderRadius: "8px", fontWeight: 600, fontSize: "13px",
                    background: "rgba(34,197,94,0.15)", border: "1.5px solid rgba(34,197,94,0.45)", color: "#4ade80",
                  }}>
                    ✓ ⚡ Perp
                  </span>
                  {/* Spot — coming soon */}
                  <span style={{
                    display: "inline-flex", alignItems: "center", gap: "5px",
                    padding: "6px 13px", borderRadius: "8px", fontWeight: 600, fontSize: "13px",
                    background: "rgba(255,255,255,0.03)", border: "1.5px solid rgba(255,255,255,0.08)", color: "var(--text-muted)", opacity: 0.5,
                  }}>
                    ○ 🪙 Spot
                    <span style={{ fontSize: "10px", background: "rgba(251,191,36,0.2)", color: "#fbbf24", padding: "1px 5px", borderRadius: "4px" }}>Soon</span>
                  </span>
                  {/* Meme */}
                  <span style={{
                    display: "inline-flex", alignItems: "center", gap: "5px",
                    padding: "6px 13px", borderRadius: "8px", fontWeight: 600, fontSize: "13px",
                    background: activeStrategy.apply_meme ? "rgba(34,197,94,0.15)" : "rgba(255,255,255,0.04)",
                    border: `1.5px solid ${activeStrategy.apply_meme ? "rgba(34,197,94,0.45)" : "rgba(255,255,255,0.1)"}`,
                    color: activeStrategy.apply_meme ? "#4ade80" : "var(--text-muted)",
                  }}>
                    {activeStrategy.apply_meme ? "✓" : "○"} 🚀 Meme
                  </span>
                </div>
                <div style={{ fontSize: "10px", color: "var(--text-muted)", fontStyle: "italic" }}>
                  Manage in Admin Panel
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Live readings per pair */}
      <div className="section">
        <div className="section-title">⚡ HL Perps — Latest Readings</div>
        {Object.keys(latestBySymbol).length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: "32px", color: "var(--text-muted)" }}>
            No signal data yet — readings appear after the bot starts scanning.
          </div>
        ) : (
          <div className="grid-2">
            {Object.entries(latestBySymbol).map(([symbol, s]) => (
              <div key={symbol} className="card fade-in">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "14px" }}>
                  <div>
                    <div style={{ fontWeight: 800, fontSize: "16px" }}>{symbol}-PERP</div>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                      {formatTime(s.logged_at)}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    {s.signal_hit && (
                      <span className="badge badge-green">🎯 TRADE FIRED</span>
                    )}
                    {s.direction && !s.signal_hit && (
                      <span className={`badge ${s.direction === "long" ? "badge-green" : "badge-red"}`}>
                        {s.direction === "long" ? "▲ LONG bias" : "▼ SHORT bias"}
                      </span>
                    )}
                  </div>
                </div>

                <SignalBar count={s.signal_count} direction={s.direction} />

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginTop: "14px" }}>
                  <div>
                    <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "2px" }}>CVD Long</div>
                    <div
                      className="mono"
                      style={{ fontSize: "15px", fontWeight: 700, color: (s.rsi_1m ?? 0) > 50 ? "var(--accent-green)" : "var(--text-muted)" }}
                    >
                      {(s.rsi_1m ?? 0) > 50 ? "Yes" : "No"}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "2px" }}>CVD Short</div>
                    <div
                      className="mono"
                      style={{ fontSize: "15px", fontWeight: 700, color: (s.rsi_5m ?? 0) > 50 ? "var(--accent-red)" : "var(--text-muted)" }}
                    >
                      {(s.rsi_5m ?? 0) > 50 ? "Yes" : "No"}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "2px" }}>OI Squeeze</div>
                    <div
                      className="mono"
                      style={{ fontSize: "15px", fontWeight: 700, color: (s.adx ?? 0) > 50 ? "var(--accent-green)" : "var(--text-muted)" }}
                    >
                      {(s.adx ?? 0) > 50 ? "Spike" : "None"}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "2px" }}>OBI Long</div>
                    <div
                      className="mono"
                      style={{
                        fontSize: "15px", fontWeight: 700,
                        color: (s.vol_ratio ?? 0) > 2 ? "var(--accent-green)" : "var(--text-primary)",
                      }}
                    >
                      {(s.vol_ratio ?? 0) > 2 ? "High" : "Low"}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "2px" }}>OBI Short</div>
                    <div
                      className="mono"
                      style={{
                        fontSize: "15px", fontWeight: 700,
                        color: (s.ob_ratio ?? 1) < 0.67
                          ? "var(--accent-red)"
                          : "var(--text-primary)",
                      }}
                    >
                      {(s.ob_ratio ?? 1) < 0.67 ? "High" : "Low"}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: "10px", color: "var(--text-muted)", marginBottom: "2px" }}>Score</div>
                    <div style={{ fontSize: "15px", fontWeight: 700 }}>
                      <span style={{ color: (s.signal_count ?? 0) >= 2 ? "var(--accent-green)" : "var(--text-muted)" }}>
                        {s.signal_count ?? 0}/3
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Signal thresholds reference */}
      <div className="section">
        <div className="section-title">📋 Quant Strategy Reference</div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Alpha Trigger</th>
                <th>Description</th>
                <th>Long Condition</th>
                <th>Short Condition</th>
                <th>Weight</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Order Book Imbalance", "L2 bid/ask skew within 0.5% of mid", "Bid volume > 3x Ask volume", "Ask volume > 3x Bid volume", "1/3"],
                ["CVD Divergence", "Buy vs Sell market order delta vs Price", "Price flat/down, CVD aggressively up", "Price flat/up, CVD aggressively down", "1/3"],
                ["OI Squeeze", "Sudden Open Interest spike + Price velocity", "+1% OI surge into local lows", "+1% OI surge into local highs", "1/3"],
              ].map(([sig, desc, long, short, wt]) => (
                <tr key={sig as string}>
                  <td style={{ fontWeight: 600 }}>{sig}</td>
                  <td style={{ color: "var(--text-muted)", fontSize: "12px" }}>{desc}</td>
                  <td style={{ color: "var(--accent-green)", fontSize: "12px" }}>{long}</td>
                  <td style={{ color: "var(--accent-red)", fontSize: "12px" }}>{short}</td>
                  <td>
                    <span className="badge badge-blue">{wt}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="info-box" style={{ marginTop: "10px" }}>
          ≥ <strong>2 out of 3 signals</strong> must align in the same direction to trigger a scalp. Hard limits: Max 3% margin allocation per trade, 15m max duration, 3m stall exit.
        </div>
      </div>

      {/* Recent signal log */}
      <div className="section">
        <div className="section-title">📜 Recent Signal Log</div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>Confluence</th>
                <th>Direction</th>
                <th>CVD L</th>
                <th>CVD S</th>
                <th>OI Spike</th>
                <th>OBI L</th>
                <th>OBI S</th>
                <th>Trade</th>
              </tr>
            </thead>
            <tbody>
              {signals.slice(0, 50).map((s) => (
                <tr key={s.id}>
                  <td style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                    {formatTime(s.logged_at)}
                  </td>
                  <td style={{ fontWeight: 600 }}>{s.symbol}</td>
                  <td><SignalBar count={s.signal_count} direction={s.direction} /></td>
                  <td>
                    {s.direction && s.direction !== "none" ? (
                      <span className={`badge badge-sm ${s.direction === "long" ? "badge-green" : "badge-red"}`}>
                        {s.direction}
                      </span>
                    ) : <span style={{ color: "var(--text-muted)" }}>—</span>}
                  </td>
                  <td className="mono" style={{ fontSize: "11px", color: (s.rsi_1m ?? 0) > 50 ? "var(--accent-green)" : "inherit" }}>
                    {(s.rsi_1m ?? 0) > 50 ? "Yes" : "No"}
                  </td>
                  <td className="mono" style={{ fontSize: "11px", color: (s.rsi_5m ?? 0) > 50 ? "var(--accent-red)" : "inherit" }}>
                    {(s.rsi_5m ?? 0) > 50 ? "Yes" : "No"}
                  </td>
                  <td className="mono" style={{ fontSize: "11px", color: (s.adx ?? 0) > 50 ? "var(--accent-green)" : "inherit" }}>
                    {(s.adx ?? 0) > 50 ? "Spike" : "—"}
                  </td>
                  <td className="mono" style={{ fontSize: "11px", color: (s.vol_ratio ?? 0) > 2 ? "var(--accent-green)" : "inherit" }}>
                    {(s.vol_ratio ?? 0) > 2 ? "High" : "Low"}
                  </td>
                  <td className="mono" style={{ fontSize: "11px", color: (s.ob_ratio ?? 1) < 0.67 ? "var(--accent-red)" : "inherit" }}>
                    {(s.ob_ratio ?? 1) < 0.67 ? "High" : "Low"}
                  </td>
                  <td>
                    {s.signal_hit
                      ? <span className="badge badge-green">✓ Fired</span>
                      : <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
