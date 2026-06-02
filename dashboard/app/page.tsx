// dashboard/app/page.tsx — Overview Page
import { api, PnLSummary } from "@/lib/api";
export const dynamic = 'force-dynamic';
export const revalidate = 0;

import PnLChart from "@/components/PnLChart";

import MilestoneBar from "@/components/MilestoneBar";

import BotControlsWrapper from "@/components/BotControlsWrapper";


async function getData() {
  try {
    const [stateRes, summaryRes, seriesRes, positionsRes] = await Promise.allSettled([
      api.getState(),
      api.getPnLSummary(),
      api.getPnLSeries(),
      api.getPositions(),
    ]);
    return {
      state:     stateRes.status === "fulfilled"     ? stateRes.value     : null,
      summary:   summaryRes.status === "fulfilled"   ? summaryRes.value   : null,
      series:    seriesRes.status === "fulfilled"    ? seriesRes.value.series : [],
      positions: positionsRes.status === "fulfilled" ? positionsRes.value : { hyperliquid: [], meme: [] },
    };
  } catch {
    return { state: null, summary: null, series: [], positions: { hyperliquid: [], meme: [] } };
  }
}

function pnlColor(val: number) {
  if (val > 0) return "var(--accent-green)";
  if (val < 0) return "var(--accent-red)";
  return "var(--text-muted)";
}

export default async function OverviewPage() {
  const { state, summary, series, positions } = await getData();

  const hlStats   = summary?.hyperliquid;
  const memeStats = summary?.meme;

  const openMemePnL = positions?.meme?.reduce((sum, p) => sum + (p.pnl_usd || 0), 0) || 0;
  
  // Actual balances from state
  const perpBalance = state?.perp_balance ?? 0;
  const spotBalance = state?.spot_balance ?? 0;
  const totalBalance = perpBalance + spotBalance;

  // HL True PnL = Current Balance - Starting Capital (330)
  // We only calculate this if we have a valid perp balance, otherwise fallback to 0
  const hlTruePnL = perpBalance > 0 ? (perpBalance - 330) : 0;
  
  const memeTotalPnL = (memeStats?.total_pnl ?? 0) + openMemePnL;
  const totalPnL  = hlTruePnL + memeTotalPnL;
  
  const totalWins = (hlStats?.wins ?? 0) + (memeStats?.wins ?? 0);
  const totalTrades = (hlStats?.total ?? 0) + (memeStats?.total ?? 0);
  const totalWinRate = totalTrades ? ((totalWins / totalTrades) * 100).toFixed(1) : "—";

  return (
    <div>
      <div className="page-header">
        <div className="page-title">📊 Overview</div>
        <div className="page-subtitle">Real-time performance dashboard — all figures in USDC</div>
      </div>

      {/* KPI Cards */}
      <div className="grid-4 section">
        <div className="card fade-in">
          <div className="card-title">💰 Total PnL</div>
          <div className="card-value" style={{ color: pnlColor(totalPnL) }}>
            {totalPnL >= 0 ? "+" : ""}${totalPnL.toFixed(2)}
          </div>
          <div className="card-sub">Since inception</div>
        </div>

        <div className="card fade-in">
          <div className="card-title">🎯 Win Rate</div>
          <div className="card-value">{totalWinRate}%</div>
          <div className="card-sub">{totalWins}W / {(totalTrades - totalWins)}L ({totalTrades} total)</div>
        </div>

        <div className="card fade-in">
          <div className="card-title">📈 HL Profit Factor</div>
          <div className="card-value">
            {hlStats?.profit_factor === Infinity ? "∞" : hlStats?.profit_factor?.toFixed(2) ?? "—"}
          </div>
          <div className="card-sub">{hlStats?.total ?? 0} HL trades</div>
        </div>

        <div className="card fade-in">
          <div className="card-title">🚀 Meme PnL</div>
          <div className="card-value" style={{ color: pnlColor(memeTotalPnL) }}>
            {memeTotalPnL >= 0 ? "+" : ""}${memeTotalPnL.toFixed(2)}
          </div>
          <div className="card-sub">{memeStats?.total ?? 0} meme trades</div>
        </div>

        <div className="card fade-in">
          <div className="card-title">🏦 Perp Balance</div>
          <div className="card-value">${perpBalance.toFixed(2)}</div>
          <div className="card-sub">Live Hyperliquid Margin</div>
        </div>

        <div className="card fade-in">
          <div className="card-title">💵 Spot Balance</div>
          <div className="card-value">${spotBalance.toFixed(2)}</div>
          <div className="card-sub">Live USDC Balance</div>
        </div>
      </div>

      {/* Main grid */}
      <div className="grid-2 section">
        {/* PnL Chart */}
        <div className="card" style={{ gridColumn: "1 / -1" }}>
          <div className="card-title">📊 Cumulative PnL — HL Perps + Meme Combined</div>
          <PnLChart series={series} hlTruePnL={hlTruePnL} />
        </div>

        {/* Milestone bar */}
        <MilestoneBar balance={totalBalance > 0 ? totalBalance : 100 + totalPnL} />

        {/* Bot controls — self-fetching client component */}
        <BotControlsWrapper />
      </div>

      {/* AI Risk State */}
      <div className="section">
        <div className="section-title">🧠 AI Risk State</div>
        <div className="grid-3">
          <div className="card fade-in">
            <div className="card-title">Volatility Regime</div>
            <div className="card-value" style={{ fontSize: "20px" }}>
              {hlStats ? "LIVE" : "IDLE"}
            </div>
            <div className="card-sub">Based on ATR% — auto-adjusts leverage</div>
          </div>

          <div className="card fade-in">
            <div className="card-title">Max Risk / Trade</div>
            <div className="card-value" style={{ fontSize: "20px" }}>2.0%</div>
            <div className="card-sub">Adjusts with win/loss streak</div>
          </div>

          <div className="card fade-in">
            <div className="card-title">Leverage Range</div>
            <div className="card-value" style={{ fontSize: "20px" }}>5×–15×</div>
            <div className="card-sub">ATR-dynamic, never exceeds 15×</div>
          </div>
        </div>
      </div>

      {/* Quick stats row */}
      <div className="section">
        <div className="section-title">📋 Strategy Stats</div>
        <div className="grid-auto">
          {[
            { label: "HL Win Rate",     value: hlStats ? `${hlStats.win_rate}%` : "—" },
            { label: "Meme Win Rate",   value: memeStats ? `${memeStats.win_rate}%` : "—" },
            { label: "HL Avg PnL/Trade", value: hlStats ? `${(hlStats.avg_pnl_pct * 100).toFixed(2)}%` : "—" },
            { label: "Meme Avg PnL/Trade", value: memeStats ? `${(memeStats.avg_pnl_pct * 100).toFixed(2)}%` : "—" },
            { label: "Max Leverage",    value: "15×" },
            { label: "Max Positions",   value: "3 HL + 3 Meme" },
          ].map((item) => (
            <div key={item.label} className="card fade-in">
              <div className="card-title">{item.label}</div>
              <div className="card-value" style={{ fontSize: "20px" }}>{item.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
