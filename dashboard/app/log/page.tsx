// dashboard/app/log/page.tsx — Trade History
import { api, getErrorLogs, Trade } from "@/lib/api";
export const dynamic = 'force-dynamic';
export const revalidate = 0;


async function getData(source?: string) {
  try {
    const [tradesRes, summaryRes, errorsRes, stateRes] = await Promise.allSettled([
      api.getTrades({ limit: 500 }),
      api.getPnLSummary(),
      getErrorLogs(),
      api.getState(),
    ]);
    return {
      trades:  tradesRes.status === "fulfilled"  ? tradesRes.value.trades   : [],
      summary: summaryRes.status === "fulfilled" ? summaryRes.value : null,
      errors:  errorsRes.status === "fulfilled"  ? errorsRes.value : [],
      state:   stateRes.status === "fulfilled"   ? stateRes.value : null,
    };
  } catch {
    return { trades: [], summary: null, errors: [], state: null };
  }
}

function pnlColor(val: number | null) {
  if (val === null || val === 0) return "var(--text-muted)";
  return val > 0 ? "var(--accent-green)" : "var(--accent-red)";
}

function exitReasonBadge(reason: string | null) {
  if (!reason) return <span className="badge badge-gray">open</span>;
  const map: Record<string, string> = {
    tp1: "badge-green", tp2: "badge-blue", tp: "badge-green",
    trailing: "badge-cyan", partial_tp: "badge-cyan",
    sl: "badge-red", time: "badge-amber", liquidity: "badge-purple",
  };
  const cls = map[reason] || "badge-gray";
  return <span className={`badge ${cls}`}>{reason}</span>;
}

function formatDate(dt: string | null) {
  if (!dt) return "—";
  const d = new Date(dt);
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

export default async function LogPage() {
  const { trades, summary, errors, state } = await getData();

  const closed = trades.filter((t) => t.closed_at);
  const wins = closed.filter((t) => (t.pnl_usd ?? 0) > 0).length;
  const winRate = closed.length ? ((wins / closed.length) * 100).toFixed(1) : "—";

  const hlData   = summary?.hyperliquid;
  const memeData = summary?.meme;

  // True HL PnL based on balance
  const perpBalance = state?.perp_balance ?? 0;
  const hlTruePnL = perpBalance > 0 ? (perpBalance - 330) : 0;
  const memePnL = memeData?.total_pnl ?? 0;
  const totalPnL = hlTruePnL + memePnL;

  return (
    <div>
      <div className="page-header">
        <div className="page-title">📜 Trade Log</div>
        <div className="page-subtitle">{closed.length} closed trades • All sources combined</div>
      </div>

      {/* Stats row */}
      <div className="grid-4 section">
        <div className="card fade-in">
          <div className="card-title">Total Trades</div>
          <div className="card-value">{closed.length}</div>
          <div className="card-sub">{wins}W / {closed.length - wins}L</div>
        </div>
        <div className="card fade-in">
          <div className="card-title">Win Rate</div>
          <div className="card-value">{winRate}%</div>
        </div>
        <div className="card fade-in">
          <div className="card-title">HL Profit Factor</div>
          <div className="card-value">
            {hlData?.profit_factor === Infinity ? "∞" : hlData?.profit_factor?.toFixed(2) ?? "—"}
          </div>
        </div>
        <div className="card fade-in">
          <div className="card-title">Total Realized PnL</div>
          <div className="card-value" style={{ color: pnlColor(totalPnL) }}>
            {totalPnL >= 0 ? "+" : ""}${totalPnL.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Breakdown by source */}
      <div className="grid-2 section">
        <div className="card fade-in">
          <div className="card-title">⚡ HL Perps Stats</div>
          {hlData ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "13px" }}>
              {[
                ["Trades",         hlData.total],
                ["Win Rate",       `${hlData.win_rate}%`],
                ["Profit Factor",  hlData.profit_factor === Infinity ? "∞" : hlData.profit_factor?.toFixed(2)],
                ["Total PnL",      `$${hlTruePnL.toFixed(2)}`],
                ["Avg PnL/Trade",  `${(hlData.avg_pnl_pct * 100).toFixed(3)}%`],
              ].map(([k, v]) => (
                <div key={k as string} style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>{k}</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{v}</span>
                </div>
              ))}
            </div>
          ) : (
            <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>No HL trades yet</span>
          )}
        </div>
        <div className="card fade-in">
          <div className="card-title">🚀 Meme Bot Stats</div>
          {memeData ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "13px" }}>
              {[
                ["Trades",         memeData.total],
                ["Win Rate",       `${memeData.win_rate}%`],
                ["Profit Factor",  memeData.profit_factor === Infinity ? "∞" : memeData.profit_factor?.toFixed(2)],
                ["Total PnL",      `$${memeData.total_pnl.toFixed(2)}`],
                ["Avg PnL/Trade",  `${(memeData.avg_pnl_pct * 100).toFixed(2)}%`],
              ].map(([k, v]) => (
                <div key={k as string} style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "var(--text-muted)" }}>{k}</span>
                  <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{v}</span>
                </div>
              ))}
            </div>
          ) : (
            <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>No meme trades yet</span>
          )}
        </div>
      </div>

      {/* Trade table */}
      <div className="section">
        <div className="section-title">All Trades</div>
        {closed.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
            No closed trades yet — they will appear here after the bot executes its first trades.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Source</th>
                  <th>Symbol</th>
                  <th>Dir</th>
                  <th>Entry</th>
                  <th>Exit</th>
                  <th>Size</th>
                  <th>PnL $</th>
                  <th>PnL %</th>
                  <th>Reason</th>
                  <th>Opened</th>
                  <th>Closed</th>
                </tr>
              </thead>
              <tbody>
                {closed.map((t) => (
                  <tr key={t.id}>
                    <td style={{ color: "var(--text-muted)", fontSize: "11px" }}>{t.id}</td>
                    <td>
                      <span className={`badge ${t.source === "hyperliquid" ? "badge-blue" : "badge-purple"}`}>
                        {t.source === "hyperliquid" ? "HL" : "MEME"}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600 }}>{t.symbol}</td>
                    <td>
                      {t.direction && (
                        <span className={`badge ${t.direction === "long" || t.direction === "buy" ? "badge-green" : "badge-red"}`}>
                          {t.direction === "long" ? "▲" : t.direction === "buy" ? "↑" : "▼"}
                          {" "}{t.direction}
                        </span>
                      )}
                    </td>
                    <td className="mono" style={{ fontSize: "12px" }}>
                      ${Number(t.entry_price).toFixed(t.source === "meme" ? 6 : 2)}
                    </td>
                    <td className="mono" style={{ fontSize: "12px" }}>
                      {t.exit_price ? `$${Number(t.exit_price).toFixed(t.source === "meme" ? 6 : 2)}` : "—"}
                    </td>
                    <td className="mono" style={{ fontSize: "12px" }}>
                      ${Number(t.size_usd).toFixed(2)}
                    </td>
                    <td
                      className="mono"
                      style={{ color: pnlColor(t.pnl_usd), fontSize: "12px", fontWeight: 700 }}
                    >
                      {t.pnl_usd != null ? `${t.pnl_usd > 0 ? "+" : ""}$${t.pnl_usd.toFixed(2)}` : "—"}
                    </td>
                    <td
                      className="mono"
                      style={{ color: pnlColor(t.pnl_pct), fontSize: "12px" }}
                    >
                      {t.pnl_pct != null ? `${t.pnl_pct > 0 ? "+" : ""}${(t.pnl_pct * 100).toFixed(2)}%` : "—"}
                    </td>
                    <td>{exitReasonBadge(t.exit_reason)}</td>
                    <td style={{ fontSize: "11px", color: "var(--text-muted)" }}>{formatDate(t.opened_at)}</td>
                    <td style={{ fontSize: "11px", color: "var(--text-muted)" }}>{formatDate(t.closed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* System Error Logs */}
      <div className="section" style={{ marginTop: "40px" }}>
        <div className="section-title" style={{ color: "var(--red)" }}>System & HL Errors</div>
        {(!errors || errors.length === 0) ? (
          <div className="card" style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
            No errors logged recently. System is healthy.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Source</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {errors.map((e: any) => (
                  <tr key={e.id}>
                    <td style={{ fontSize: "12px", color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                      {formatDate(e.timestamp)}
                    </td>
                    <td>
                      <span className={`badge ${e.source === "hyperliquid" ? "badge-blue" : "badge-gray"}`}>
                        {e.source.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ fontSize: "13px", color: "var(--red)", fontFamily: "var(--font-mono)", maxWidth: "500px", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {e.message}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
