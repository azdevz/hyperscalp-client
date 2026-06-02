// dashboard/app/positions/page.tsx — Live Positions
import { api, Trade } from "@/lib/api";
export const dynamic = 'force-dynamic';
export const revalidate = 0;


async function getData() {
  try {
    return await api.getPositions();
  } catch {
    return { hyperliquid: [], meme: [] };
  }
}

function pnlStyle(pnl: number | null) {
  if (!pnl) return { color: "var(--text-muted)" };
  return { color: pnl > 0 ? "var(--accent-green)" : "var(--accent-red)", fontFamily: "var(--font-mono)" };
}

function directionBadge(dir: string | null) {
  if (!dir) return null;
  const isLong = dir === "long" || dir === "buy";
  return (
    <span className={`badge ${isLong ? "badge-green" : "badge-red"}`}>
      {isLong ? "▲ LONG" : "▼ SHORT"}
    </span>
  );
}

function elapsed(openedAt: string) {
  const diff = (Date.now() - new Date(openedAt).getTime()) / 1000;
  if (diff < 60)   return `${Math.floor(diff)}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m`;
}

export default async function PositionsPage() {
  const { hyperliquid, meme } = await getData();

  const totalOpen = hyperliquid.length + meme.length;

  return (
    <div>
      <div className="page-header">
        <div className="page-title">📋 Live Positions</div>
        <div className="page-subtitle">
          {totalOpen} open position{totalOpen !== 1 ? "s" : ""} — updates on page refresh
        </div>
      </div>

      {/* HL Positions */}
      <div className="section">
        <div className="section-title">⚡ Hyperliquid Perps</div>
        {hyperliquid.length === 0 ? (
          <div className="card" style={{ color: "var(--text-muted)", textAlign: "center", padding: "32px" }}>
            No open HL positions
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Coin</th>
                  <th>Size</th>
                  <th>Position Value</th>
                  <th>Entry Price</th>
                  <th>Mark Price</th>
                  <th>PNL (ROE %)</th>
                  <th>Liq. Price</th>
                  <th>Margin</th>
                </tr>
              </thead>
              <tbody>
                {hyperliquid.map((pos) => {
                  const ep = pos.entry_price ?? 0;
                  const roe = pos.roe ? pos.roe * 100 : 0;
                  return (
                    <tr key={pos.symbol}>
                      <td style={{ fontWeight: 700 }}>
                        <span style={{ color: pos.direction === "long" ? "var(--accent-green)" : "var(--accent-red)", marginRight: '6px' }}>
                          {pos.symbol}
                        </span>
                        <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>
                          {pos.leverage}x
                        </span>
                      </td>
                      <td className="mono" style={{ color: pos.direction === "long" ? "var(--accent-green)" : "var(--accent-red)" }}>
                        {pos.size} {pos.symbol}
                      </td>
                      <td className="mono">{pos.position_value != null ? `${pos.position_value.toFixed(2)} USDC` : "—"}</td>
                      <td className="mono">{ep.toFixed(ep < 1 ? 5 : 1)}</td>
                      <td className="mono">{pos.current_price != null ? pos.current_price.toFixed(ep < 1 ? 5 : 1) : "—"}</td>
                      <td style={pnlStyle(pos.pnl_usd)}>
                        {pos.pnl_usd != null ? `${pos.pnl_usd > 0 ? "+$" : "-$"}${Math.abs(pos.pnl_usd).toFixed(2)} (${roe > 0 ? "+" : ""}${roe.toFixed(1)}%)` : "—"}
                      </td>
                      <td className="mono">{pos.liquidation_px ? pos.liquidation_px.toFixed(ep < 1 ? 5 : 1) : "—"}</td>
                      <td className="mono">
                        {pos.margin != null ? `$${pos.margin.toFixed(2)} (Isolated)` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Meme Positions */}
      <div className="section">
        <div className="section-title">🚀 Meme Bot Positions</div>
        {meme.length === 0 ? (
          <div className="card" style={{ color: "var(--text-muted)", textAlign: "center", padding: "32px" }}>
            No open meme positions
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Token</th>
                  <th>Entry Price</th>
                  <th>Current Price</th>
                  <th>Size</th>
                  <th>Unrealized PnL</th>
                  <th>Time Held</th>
                  <th>TP Target</th>
                  <th>SL Trigger</th>
                </tr>
              </thead>
              <tbody>
                {meme.map((pos) => {
                  const ep = pos.entry_price ?? 0;
                  return (
                    <tr key={pos.id}>
                      <td style={{ fontWeight: 700 }}>{pos.symbol}</td>
                      <td className="mono">${ep.toFixed(8)}</td>
                      <td className="mono">{pos.current_price != null ? `$${pos.current_price.toFixed(8)}` : "—"}</td>
                      <td className="mono">${pos.size_usd?.toFixed(2)}</td>
                      <td style={pnlStyle(pos.pnl_usd)}>
                        {pos.pnl_usd != null ? `${pos.pnl_usd > 0 ? "+" : ""}$${pos.pnl_usd.toFixed(2)}` : "—"}
                      </td>
                      <td style={{ color: "var(--text-muted)" }}>{elapsed(pos.opened_at)}</td>
                      <td className="mono" style={{ color: "var(--accent-green)", fontSize: "12px" }}>
                        +20%
                      </td>
                      <td className="mono" style={{ color: "var(--accent-red)", fontSize: "12px" }}>
                        -8%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Risk summary */}
      <div className="info-box" style={{ marginTop: "8px" }}>
        <strong>Risk rules enforced:</strong> Max 3 HL + 3 Meme open simultaneously • Max 2% account per trade •
        Max 6% total HL exposure • Daily -10% kill switch • Weekly -20% kill switch
      </div>
    </div>
  );
}
