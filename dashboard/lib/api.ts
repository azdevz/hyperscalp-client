// dashboard/lib/api.ts
// Typed API client for all bot backend calls
// All requests attach Bearer token from env var

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";
const API_SECRET = process.env.NEXT_PUBLIC_API_SECRET || "";

const headers = () => ({
  "Content-Type": "application/json",
  Authorization: `Bearer ${API_SECRET}`,
});

async function req<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers(), ...(options?.headers || {}) },
    next: { revalidate: 0 }, // always fresh
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${path}: ${text}`);
  }
  return res.json();
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Trade {
  id:          number;
  source:      "hyperliquid" | "meme";
  symbol:      string;
  direction:   string;
  entry_price: number;
  current_price?: number | null;
  exit_price:  number | null;
  size_usd:    number;
  pnl_usd:     number | null;
  pnl_pct:     number | null;
  exit_reason: string | null;
  opened_at:   string;
  closed_at:   string | null;
  roe?:        number;
  leverage?:   number | string;
  margin?:     number;
  position_value?: number;
  liquidation_px?: number | null;
  size?:       number;
}

export interface Pair {
  id:            number;
  source:        string;
  symbol:        string;
  contract:      string;
  pool:          string;
  active:        boolean;
  custom_tp_pct: number;
  custom_sl_pct: number;
  max_hold_min:  number;
  note:          string;
  added_at:      string;
}

export interface Strategy {
  id:          number;
  name:        string;
  description: string;
  is_active:   boolean;
  apply_perp:  boolean;
  apply_spot:  boolean;
  apply_meme:  boolean;
}

export interface BotState {
  hl_bot_active:    string;
  meme_bot_active:  string;
  emergency_stop:   string;
  hl_paused_until:  string;
  meme_paused_until: string;
  hl_active:        boolean;
  meme_active:      boolean;
  mode:             string;
  perp_balance:     number;
  spot_balance:     number;
  active_strategy:  Strategy;
}

export interface Signal {
  id:           number;
  source:       string;
  symbol:       string;
  rsi_1m:       number | null;
  rsi_5m:       number | null;
  macd:         number | null;
  adx:          number | null;
  vol_ratio:    number | null;
  bb_signal:    boolean;
  ob_ratio:     number | null;
  signal_count: number;
  direction:    string | null;
  signal_hit:   boolean;
  logged_at:    string;
}

export interface PnLSummary {
  [source: string]: {
    wins:          number;
    losses:        number;
    total:         number;
    win_rate:      number;
    total_pnl:     number;
    avg_pnl_pct:   number;
    profit_factor: number;
  };
}

export interface Milestone {
  id:          number;
  phase:       string;
  capital_usd: number;
  reached_at:  string;
}

export interface PnLPoint {
  date:           string;
  daily_pnl:      number;
  cumulative_pnl: number;
  source:         string;
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const api = {
  // Health
  health: () => req<{ status: string; mode: string }>("/api/health"),

  // State
  getState:      () => req<BotState>("/api/state"),
  pauseHL:       (hours = 24) => req<{ ok: boolean }>(`/api/state/pause-hl?hours=${hours}`, { method: "POST" }),
  resumeHL:      () => req<{ ok: boolean }>("/api/state/resume-hl", { method: "POST" }),
  pauseMeme:     (hours = 24) => req<{ ok: boolean }>(`/api/state/pause-meme?hours=${hours}`, { method: "POST" }),
  resumeMeme:    () => req<{ ok: boolean }>("/api/state/resume-meme", { method: "POST" }),
  emergencyStop: () => req<{ ok: boolean }>("/api/state/emergency-stop", { method: "POST" }),
  emergencyResume: () => req<{ ok: boolean }>("/api/state/emergency-resume", { method: "POST" }),

  // Trades
  getTrades: (params?: { source?: string; symbol?: string; exit_reason?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.source) qs.set("source", params.source);
    if (params?.symbol) qs.set("symbol", params.symbol);
    if (params?.exit_reason) qs.set("exit_reason", params.exit_reason);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    return req<{ trades: Trade[]; count: number }>(`/api/trades?${qs}`);
  },
  getPositions: () => req<{ hyperliquid: Trade[]; meme: Trade[] }>("/api/positions"),

  // PnL
  getPnLSummary: () => req<PnLSummary>("/api/pnl/summary"),
  getPnLSeries:  () => req<{ series: PnLPoint[] }>("/api/pnl/series"),

  // Milestones
  getMilestones: () => req<{ milestones: Milestone[] }>("/api/milestones"),

  // Pairs
  getPairs:    (activeOnly = true) => req<{ pairs: Pair[] }>(`/api/pairs?active_only=${activeOnly}`),
  createPair:  (data: Partial<Pair>) => req<{ ok: boolean; pair: Pair }>("/api/pairs", { method: "POST", body: JSON.stringify(data) }),
  togglePair:  (id: number, active: boolean) => req<{ ok: boolean }>(`/api/pairs/${id}/toggle?active=${active}`, { method: "PATCH" }),
  deletePair:  (id: number) => req<{ ok: boolean }>(`/api/pairs/${id}`, { method: "DELETE" }),

  // Signals
  getSignals: (limit = 50) => req<{ signals: Signal[] }>(`/api/signals?limit=${limit}`),

  // Strategies
  getStrategies: () => req<{ strategies: Strategy[] }>("/api/strategies"),
  updateStrategyMarkets: (id: number, flags: { apply_perp: boolean; apply_spot: boolean; apply_meme: boolean }) =>
    req<{ ok: boolean }>(`/api/strategies/${id}/markets`, { method: "PATCH", body: JSON.stringify(flags) }),
};

export interface ErrorLog {
  id: number;
  timestamp: string;
  source: string;
  message: string;
}

export async function getErrorLogs(): Promise<ErrorLog[]> {
  const res = await fetch(`${API_BASE}/api/errors`, {
    headers: { Authorization: `Bearer ${API_SECRET}` },
    next: { revalidate: 0 },
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.errors || [];
}
