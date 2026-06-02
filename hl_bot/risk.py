"""
hl_bot/risk.py — Adaptive regime-based risk management.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import config
import db
from hl_bot import signals

logger = logging.getLogger(__name__)


@dataclass
class RiskDecision:
    risk_pct:      float
    leverage:      int
    trade_allowed: bool
    reasoning:     str


def compute_risk(
    symbol:               str,
    leverage_request:     int,
    daily_pnl_pct:        float,
    weekly_pnl_pct:       float,
    open_positions_count: int,
) -> RiskDecision:
    if daily_pnl_pct <= -config.DAILY_DRAWDOWN_KILL:
        return RiskDecision(0, 1, False, "Daily drawdown hit kill switch.")
    if weekly_pnl_pct <= -config.WEEKLY_DRAWDOWN_KILL:
        return RiskDecision(0, 1, False, "Weekly drawdown hit kill switch.")
    if open_positions_count >= config.MAX_OPEN_POSITIONS:
        return RiskDecision(0, 1, False, "Max positions open.")

    # Maximum 1.5% of available isolated margin per trade (was 3%)
    base_risk = 0.015
    try:
        sym_mult = float(db.get_bot_state(f"tuner_sym_{symbol}_size_mult") or 1.0)
    except Exception:
        sym_mult = 1.0
        
    risk_pct = base_risk * sym_mult
    
    # Leverage: use hardcoded caps, then apply tuner override (lower only)
    if symbol == "BTC": lev_cap = 15
    elif symbol == "ETH": lev_cap = 10
    else: lev_cap = 5
    
    # Auto-tuner can REDUCE leverage cap (never increase)
    try:
        tuner_lev = int(db.get_bot_state(f"tuner_sym_{symbol}_lev_cap") or lev_cap)
        lev_cap = min(lev_cap, tuner_lev)
    except Exception:
        pass
    
    leverage = min(leverage_request, lev_cap)

    return RiskDecision(
        risk_pct=risk_pct,
        leverage=leverage,
        trade_allowed=True,
        reasoning=f"Risk={risk_pct:.2%} Lev={leverage}x SizeMult={sym_mult}",
    )


def compute_position_size(
    account_balance: float,
    risk_pct:        float,
    entry_price:     float,
    stop_pct:        float,
    milestone_max:   float = None,
) -> float:
    raw_size_usd = (account_balance * risk_pct) / stop_pct
    if milestone_max is not None:
        raw_size_usd = min(raw_size_usd, milestone_max)
    return round(raw_size_usd, 2)


def get_milestone_max(balance: float) -> float:
    for ms in config.MILESTONES:
        if ms["min"] <= balance < ms["max"]:
            return float(ms["max_trade"])
    return 5000.0
