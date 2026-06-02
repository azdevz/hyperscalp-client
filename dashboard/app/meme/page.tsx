// dashboard/app/meme/page.tsx — Meme Bot Panel
"use client";

import { useState, useEffect, useCallback } from "react";
import { api, Pair } from "@/lib/api";

function PairRow({ pair }: { pair: Pair }) {
  return (
    <tr key={pair.id}>
      <td style={{ fontWeight: 700 }}>{pair.symbol}</td>
      <td>
        <span
          className="mono"
          style={{ fontSize: "11px", color: "var(--text-muted)" }}
          title={pair.contract}
        >
          {pair.contract ? `${pair.contract.slice(0, 6)}…${pair.contract.slice(-4)}` : "—"}
        </span>
      </td>
      <td>
        <span className={`badge ${pair.active ? "badge-green" : "badge-gray"}`}>
          {pair.active ? "● Active" : "○ Paused"}
        </span>
      </td>
      <td className="mono" style={{ fontSize: "12px" }}>
        +{pair.custom_tp_pct}% / -{pair.custom_sl_pct}%
      </td>
      <td style={{ color: "var(--text-muted)", fontSize: "12px" }}>
        {pair.max_hold_min}m
      </td>
      <td style={{ fontSize: "12px", color: "var(--text-secondary)", maxWidth: "180px" }}>
        {pair.note || "—"}
      </td>
    </tr>
  );
}

function AddPairModal({ onClose, onAdd }: { onClose: () => void; onAdd: () => void }) {
  const [form, setForm] = useState({
    symbol: "", contract: "", pool: "", note: "",
    custom_tp_pct: 20, custom_sl_pct: 8, max_hold_min: 20,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!form.symbol || !form.contract) {
      setError("Symbol and contract address are required.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await api.createPair({ ...form, active: true, source: "meme" });
      onAdd();
      onClose();
    } catch (e: any) {
      setError(e.message || "Failed to add pair.");
    } finally {
      setLoading(false);
    }
  };

  const f = (k: string) => (e: any) =>
    setForm((p) => ({ ...p, [k]: e.target.value }));

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">➕ Add Meme Pair</div>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div className="form-group">
            <label className="form-label">Token Symbol *</label>
            <input placeholder="e.g. BONK" value={form.symbol} onChange={f("symbol")} />
          </div>
          <div className="form-group">
            <label className="form-label">Solana Contract Address *</label>
            <input
              placeholder="e.g. DezXAZ8z7PnrnRJjz3..."
              value={form.contract}
              onChange={f("contract")}
              style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Raydium Pool Address (optional)</label>
            <input placeholder="Pool address" value={form.pool} onChange={f("pool")} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px" }}>
            <div className="form-group">
              <label className="form-label">TP %</label>
              <input type="number" value={form.custom_tp_pct} onChange={f("custom_tp_pct")} min={5} max={100} />
            </div>
            <div className="form-group">
              <label className="form-label">SL %</label>
              <input type="number" value={form.custom_sl_pct} onChange={f("custom_sl_pct")} min={2} max={20} />
            </div>
            <div className="form-group">
              <label className="form-label">Max Hold (min)</label>
              <input type="number" value={form.max_hold_min} onChange={f("max_hold_min")} min={5} max={60} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Note (catalyst / why you're adding)</label>
            <textarea
              rows={2}
              placeholder="e.g. Volume spike on DexScreener, LP locked, mint renounced..."
              value={form.note}
              onChange={f("note")}
            />
          </div>

          <div className="info-box">
            ✅ Confirm LP locked (Rugcheck.xyz) • Mint authority renounced (Solscan) •
            Top 10 wallets &lt;40% supply (Birdeye) • Token age &gt;30 min
          </div>

          {error && (
            <div style={{ color: "var(--accent-red)", fontSize: "12px" }}>{error}</div>
          )}

          <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", paddingTop: "4px" }}>
            <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" onClick={submit} disabled={loading}>
              {loading ? "Adding…" : "Add Pair"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function MemePage() {
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const loadPairs = useCallback(async () => {
    try {
      const res = await api.getPairs(!showAll);
      setPairs(res.pairs);
    } catch { /* offline */ } finally {
      setLoading(false);
    }
  }, [showAll]);

  useEffect(() => { loadPairs(); }, [loadPairs]);

  const handleToggle = async (id: number, active: boolean) => {
    await api.togglePair(id, active);
    loadPairs();
  };

  const handleDelete = async (id: number) => {
    await api.deletePair(id);
    loadPairs();
  };

  const activePairs = pairs.filter((p) => p.active);

  return (
    <div>
      <div className="page-header">
        <div className="page-title">🚀 Meme Bot Panel</div>
        <div className="page-subtitle">
          {activePairs.length}/5 active pairs • Bot scans every 30s via Birdeye
        </div>
      </div>

      {/* Stats */}
      <div className="grid-4 section">
        <div className="card fade-in">
          <div className="card-title">Active Pairs</div>
          <div className="card-value">{activePairs.length}<span style={{ fontSize: "16px", color: "var(--text-muted)" }}>/5</span></div>
        </div>
        <div className="card fade-in">
          <div className="card-title">Max Positions</div>
          <div className="card-value">3</div>
          <div className="card-sub">Simultaneous meme trades</div>
        </div>
        <div className="card fade-in">
          <div className="card-title">Capital Allocation</div>
          <div className="card-value">30%</div>
          <div className="card-sub">Of total account</div>
        </div>
        <div className="card fade-in">
          <div className="card-title">Default Exit</div>
          <div className="card-value" style={{ fontSize: "18px" }}>+20% / -8%</div>
          <div className="card-sub">TP / SL (per-pair overridable)</div>
        </div>
      </div>

      {/* Pairs table */}
      <div className="section">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
          <div className="section-title" style={{ marginBottom: 0 }}>
            📁 Watchlist ({pairs.length} pairs)
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowAll((p) => !p)}>
              {showAll ? "Active only" : "Show all"}
            </button>
          </div>
        </div>

        {loading ? (
          <div className="skeleton" style={{ height: "120px" }} />
        ) : pairs.length === 0 ? (
          <div className="card" style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
            No pairs yet. Add your first meme token to start.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Contract</th>
                  <th>Status</th>
                  <th>TP / SL</th>
                  <th>Max Hold</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {pairs.map((pair) => (
                  <PairRow
                    key={pair.id}
                    pair={pair}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Entry signal logic reminder */}
      <div className="section">
        <div className="section-title">⚡ Entry Signal Requirements</div>
        <div className="grid-3">
          {[
            { icon: "📊", title: "Volume Spike", desc: "5m volume > 3× its own 1h average, OR 24h vol +40% in 30min" },
            { icon: "🚀", title: "Price Breakout", desc: "Above 15m high • Candle body >2% • Price above 1h VWAP" },
            { icon: "💧", title: "Liquidity Gate", desc: "Jupiter price impact <1.5% to enter • Skip if >3% impact" },
          ].map((item) => (
            <div key={item.title} className="card fade-in">
              <div className="card-title">{item.icon} {item.title}</div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.6" }}>
                {item.desc}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Scout tools */}
      <div className="section">
        <div className="section-title">🔍 Scout Tools</div>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {[
            { label: "DexScreener", href: "https://dexscreener.com/solana" },
            { label: "Birdeye",     href: "https://birdeye.so" },
            { label: "Pump.fun",    href: "https://pump.fun" },
            { label: "Rugcheck",    href: "https://rugcheck.xyz" },
            { label: "Solscan",     href: "https://solscan.io" },
          ].map((t) => (
            <a
              key={t.label}
              href={t.href}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-ghost btn-sm"
            >
              {t.label} ↗
            </a>
          ))}
        </div>
      </div>

      {showModal && (
        <AddPairModal onClose={() => setShowModal(false)} onAdd={loadPairs} />
      )}
    </div>
  );
}
