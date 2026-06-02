"""
api/routes.py — FastAPI read/write endpoints for the Vercel dashboard.

All state-mutating endpoints require Bearer token (API_SECRET).
Read endpoints also require Bearer token to prevent public exposure.

Base path: /api
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel

import config
import db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ── Auth dependency ───────────────────────────────────────────────────────────

def require_auth(authorization: str = Header(default="")):
    """Validate Bearer token from Authorization header."""
    token = authorization.removeprefix("Bearer ").strip()
    if token != config.API_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok", "mode": config.HL_MODE, "time": datetime.now(timezone.utc).isoformat()}


# ── Bot state ─────────────────────────────────────────────────────────────────

@router.get("/state", dependencies=[Depends(require_auth)])
def get_state():
    """Return all bot_state flags + active status booleans + live balances."""
    from hl_bot import execution
    strategy = db.get_active_strategy()
    return {
        "hl_bot_active":    db.get_bot_state("hl_bot_active"),
        "meme_bot_active":  db.get_bot_state("meme_bot_active"),
        "emergency_stop":   db.get_bot_state("emergency_stop"),
        "hl_paused_until":  db.get_bot_state("hl_paused_until"),
        "meme_paused_until": db.get_bot_state("meme_paused_until"),
        "hl_active":        db.is_hl_active(),
        "meme_active":      db.is_meme_active(),
        "mode":             db.get_bot_state("hl_network_regime") or "demo",
        "perp_balance":     execution.get_account_balance(),
        "spot_balance":     execution.get_spot_balance(),
        "active_strategy":  strategy,
    }


class StateUpdate(BaseModel):
    key:   str
    value: str


@router.post("/state", dependencies=[Depends(require_auth)])
def update_state(payload: StateUpdate):
    """Update a bot_state flag (pause/resume/stop)."""
    allowed_keys = {
        "hl_bot_active", "meme_bot_active", "emergency_stop",
        "hl_paused_until", "meme_paused_until", "hl_network_regime",
    }
    if payload.key not in allowed_keys:
        raise HTTPException(400, f"Key '{payload.key}' not allowed.")
    db.set_bot_state(payload.key, payload.value)
    return {"ok": True, "key": payload.key, "value": payload.value}


@router.post("/state/pause-hl", dependencies=[Depends(require_auth)])
def pause_hl(hours: int = 24):
    pause_until = datetime.now(timezone.utc) + timedelta(hours=hours)
    db.set_bot_state("hl_paused_until", pause_until.isoformat())
    return {"ok": True, "paused_until": pause_until.isoformat()}


@router.post("/state/pause-meme", dependencies=[Depends(require_auth)])
def pause_meme(hours: int = 24):
    pause_until = datetime.now(timezone.utc) + timedelta(hours=hours)
    db.set_bot_state("meme_paused_until", pause_until.isoformat())
    return {"ok": True, "paused_until": pause_until.isoformat()}


@router.post("/state/resume-hl", dependencies=[Depends(require_auth)])
def resume_hl():
    db.set_bot_state("hl_paused_until", "")
    db.set_bot_state("hl_bot_active", "true")
    return {"ok": True}


@router.post("/state/resume-meme", dependencies=[Depends(require_auth)])
def resume_meme():
    db.set_bot_state("meme_paused_until", "")
    db.set_bot_state("meme_bot_active", "true")
    return {"ok": True}


@router.post("/state/emergency-stop", dependencies=[Depends(require_auth)])
def emergency_stop():
    db.set_bot_state("emergency_stop", "true")
    db.set_bot_state("hl_bot_active", "false")
    db.set_bot_state("meme_bot_active", "false")
    return {"ok": True, "stopped": True}


@router.post("/state/emergency-resume", dependencies=[Depends(require_auth)])
def emergency_resume():
    db.set_bot_state("emergency_stop", "false")
    db.set_bot_state("hl_bot_active", "true")
    db.set_bot_state("meme_bot_active", "true")
    return {"ok": True}


# ── Strategies ───────────────────────────────────────────────────────────────

@router.get("/strategies", dependencies=[Depends(require_auth)])
def get_strategies():
    return {"strategies": db.get_all_strategies()}


class StrategyMarketsUpdate(BaseModel):
    apply_perp: bool
    apply_spot: bool
    apply_meme: bool


@router.patch("/strategies/{strategy_id}/markets", dependencies=[Depends(require_auth)])
def update_strategy_markets(strategy_id: int, payload: StrategyMarketsUpdate):
    db.update_strategy_markets(strategy_id, payload.apply_perp, payload.apply_spot, payload.apply_meme)
    return {"ok": True}


# ── Trades ────────────────────────────────────────────────────────────────────

@router.get("/trades", dependencies=[Depends(require_auth)])
def get_trades(
    source:      Optional[str] = Query(None),
    symbol:      Optional[str] = Query(None),
    exit_reason: Optional[str] = Query(None),
    limit:       int           = Query(100, le=500),
    offset:      int           = Query(0),
):
    trades = db.get_trades(source=source, symbol=symbol, exit_reason=exit_reason,
                           limit=limit, offset=offset)
    return {"trades": trades, "count": len(trades)}


@router.get("/positions", dependencies=[Depends(require_auth)])
def get_positions():
    """Returns currently open trades (not yet closed in DB)."""
    from hl_bot import execution as hl_exec
    # Fetch accurate aggregate positions direct from HL
    hl_open = hl_exec.get_open_positions()
    for t in hl_open:
        price = hl_exec.get_mid_price(t["symbol"])
        if price > 0:
            t["current_price"] = price
        # Dashboard expects pnl_usd and size_usd
        t["pnl_usd"] = t.get("unrealized_pnl", 0)
        t["size_usd"] = t.get("position_value", 0)

    meme_open = db.get_open_trades("meme")

    if meme_open:
        from meme_bot import birdeye
        pairs = {p["symbol"]: p["contract"] for p in db.get_pairs(active_only=False)}
        for t in meme_open:
            contract = pairs.get(t["symbol"])
            if contract:
                overview = birdeye.get_token_overview(contract)
                price = overview.get("price", 0)
                if price > 0:
                    t["current_price"] = price
                    t["pnl_pct"] = (price - float(t["entry_price"])) / float(t["entry_price"])
                    t["pnl_usd"] = float(t["pnl_pct"]) * float(t["size_usd"])

    return {"hyperliquid": hl_open, "meme": meme_open}


# ── PnL & Stats ───────────────────────────────────────────────────────────────

@router.get("/pnl/summary", dependencies=[Depends(require_auth)])
def pnl_summary():
    return db.get_pnl_summary()


@router.get("/pnl/daily_report", dependencies=[Depends(require_auth)])
def daily_report():
    """Daily trading report metrics."""
    return db.get_daily_report_stats()


@router.get("/pnl/series", dependencies=[Depends(require_auth)])
def pnl_series():
    """Daily cumulative PnL series for charting."""
    rows = db.get_cumulative_pnl_series()
    return {"series": rows}


# ── Milestones ────────────────────────────────────────────────────────────────

@router.get("/milestones", dependencies=[Depends(require_auth)])
def get_milestones():
    return {"milestones": db.get_milestones()}


# ── Pairs (meme watchlist editor) ─────────────────────────────────────────────

@router.get("/pairs", dependencies=[Depends(require_auth)])
def get_pairs(active_only: bool = Query(True)):
    return {"pairs": db.get_pairs(active_only=active_only)}


class PairCreate(BaseModel):
    symbol:         str
    contract:       Optional[str] = None
    pool:           Optional[str] = None
    active:         bool          = True
    custom_tp_pct:  float         = 20
    custom_sl_pct:  float         = 8
    max_hold_min:   int           = 20
    note:           Optional[str] = ""
    source:         str           = "meme"


@router.post("/pairs", dependencies=[Depends(require_auth)])
def create_pair(payload: PairCreate):
    row = db.upsert_pair(payload.model_dump())
    return {"ok": True, "pair": row}


@router.patch("/pairs/{pair_id}/toggle", dependencies=[Depends(require_auth)])
def toggle_pair(pair_id: int, active: bool = Query(...)):
    db.set_pair_active(pair_id, active)
    return {"ok": True, "id": pair_id, "active": active}


@router.delete("/pairs/{pair_id}", dependencies=[Depends(require_auth)])
def delete_pair(pair_id: int):
    db.set_pair_active(pair_id, False)
    return {"ok": True, "id": pair_id}


# ── Signals log ───────────────────────────────────────────────────────────────

@router.get("/signals", dependencies=[Depends(require_auth)])
def get_signals(limit: int = Query(50, le=200)):
    return {"signals": db.get_signals(limit=limit)}

# ── Error logs ────────────────────────────────────────────────────────────────

@router.get("/errors", dependencies=[Depends(require_auth)])
def get_errors(limit: int = Query(50, le=200)):
    return {"errors": db.get_error_logs(limit=limit)}


# ── Auto-Tuner ────────────────────────────────────────────────────────────────

@router.get("/tuner", dependencies=[Depends(require_auth)])
def get_tuner_status():
    """Returns the latest auto-tuner report and all tuner keys."""
    import json as _json
    last_run = db.get_bot_state("tuner_last_run") or ""
    report_raw = db.get_bot_state("tuner_last_report") or "{}"
    try:
        report = _json.loads(report_raw)
    except Exception:
        report = {}
    
    # Collect all tuner keys
    tuner_keys = {}
    for key_prefix in ["tuner_sym_", "tuner_dir_", "tuner_streak_"]:
        rows = db.execute(
            "SELECT key, value FROM bot_state WHERE key LIKE %s",
            (f"{key_prefix}%",)
        )
        for row in rows:
            tuner_keys[row["key"]] = row["value"]
    
    return {
        "last_run": last_run,
        "report": report,
        "parameters": tuner_keys,
    }


@router.post("/tuner/run", dependencies=[Depends(require_auth)])
def trigger_tuner():
    """Manually trigger the auto-tuner."""
    from hl_bot.auto_tuner import run_auto_tuner
    run_auto_tuner()
    return {"ok": True, "message": "Auto-tuner executed manually."}
