// dashboard/components/PnLChart.tsx
"use client";

import {
  ComposedChart,
  Area,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { PnLPoint } from "@/lib/api";

interface ChartDataPoint {
  date:       string;
  hl_cum:     number;
  meme_cum:   number;
  total_cum:  number;
  daily_pnl:  number;
}

function buildChartData(series: PnLPoint[], hlOffset: number): ChartDataPoint[] {
  const byDate: Record<string, { hl: number; meme: number }> = {};
  for (const pt of series) {
    if (!byDate[pt.date]) byDate[pt.date] = { hl: 0, meme: 0 };
    if (pt.source === "hyperliquid") byDate[pt.date].hl += Number(pt.daily_pnl);
    if (pt.source === "meme")        byDate[pt.date].meme += Number(pt.daily_pnl);
  }
  // Rebuild cumulative from daily, then apply offset to last point
  const entries = Object.entries(byDate).sort(([a], [b]) => a.localeCompare(b));
  let hlRunning = 0;
  let memeRunning = 0;
  const result: ChartDataPoint[] = entries.map(([date, { hl, meme }]) => {
    hlRunning += hl;
    memeRunning += meme;
    return {
      date: date.slice(5),
      hl_cum: Math.round(hlRunning * 100) / 100,
      meme_cum: Math.round(memeRunning * 100) / 100,
      total_cum: Math.round((hlRunning + memeRunning) * 100) / 100,
      daily_pnl: 0,
    };
  });
  // Apply offset to align final HL value with real balance
  if (result.length > 0 && hlOffset !== 0) {
    const lastHl = result[result.length - 1].hl_cum;
    const diff = hlOffset - lastHl;
    return result.map((pt, i) => ({
      ...pt,
      hl_cum: Math.round((pt.hl_cum + (diff * (i + 1) / result.length)) * 100) / 100,
      total_cum: Math.round((pt.hl_cum + diff * (i + 1) / result.length + pt.meme_cum) * 100) / 100,
    }));
  }
  return result;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border-bright)",
        borderRadius: "8px",
        padding: "10px 14px",
        fontSize: "12px",
      }}
    >
      <div style={{ marginBottom: "6px", color: "var(--text-muted)", fontWeight: 600 }}>{label}</div>
      {payload.map((p: any) => (
        <div
          key={p.name}
          style={{ color: p.color, display: "flex", justifyContent: "space-between", gap: "16px" }}
        >
          <span>{p.name}</span>
          <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
            ${p.value > 0 ? "+" : ""}{p.value.toFixed(2)}
          </span>
        </div>
      ))}
    </div>
  );
};

export default function PnLChart({ series, hlTruePnL }: { series: PnLPoint[]; hlTruePnL?: number }) {
  const data = buildChartData(series, hlTruePnL ?? 0);

  if (!data.length) {
    return (
      <div
        style={{
          height: "280px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-muted)",
          fontSize: "13px",
        }}
      >
        No closed trades yet — PnL chart will appear here.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={data} margin={{ top: 5, right: 10, left: 5, bottom: 5 }}>
        <defs>
          <linearGradient id="hlGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="memeGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#8b5cf6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,179,237,0.07)" />
        <XAxis
          dataKey="date"
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${v}`}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }}
        />
        <ReferenceLine y={0} stroke="rgba(255,255,255,0.1)" strokeDasharray="4 4" />
        <Area
          type="monotone"
          dataKey="hl_cum"
          name="HL Perps"
          stroke="#3b82f6"
          strokeWidth={2}
          fill="url(#hlGrad)"
          dot={false}
        />
        <Area
          type="monotone"
          dataKey="meme_cum"
          name="Meme Bot"
          stroke="#8b5cf6"
          strokeWidth={2}
          fill="url(#memeGrad)"
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
