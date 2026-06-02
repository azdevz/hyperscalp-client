"""
meme_bot/signals.py — Volume spike + price breakout detector for Solana meme tokens.

Entry requires ALL 3 conditions (brain.md §13.3):
  1. Volume spike: 5m vol > 3x 1h average  OR  24h vol +40% in 30min
  2. Price breakout: above 15m high, candle body >2%, above VWAP
  3. Liquidity depth: price impact < 1.5% (checked in execution)
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

import config
from meme_bot import birdeye

logger = logging.getLogger(__name__)


@dataclass
class MemeSignalResult:
    symbol:        str
    contract:      str
    entry_allowed: bool = False
    vol_spike:     bool = False
    breakout:      bool = False
    vol_ratio:     float = 0.0
    current_price: float = 0.0
    liquidity:     float = 0.0
    reason:        str = ""


def compute_meme_signals(pair: dict) -> MemeSignalResult:
    """
    Evaluate entry conditions for a meme pair.
    pair: row from pairs DB table (symbol, contract, custom_tp_pct, ...)
    """
    symbol   = pair["symbol"]
    contract = pair.get("contract", "")
    result   = MemeSignalResult(symbol=symbol, contract=contract)

    if not contract:
        result.reason = "No contract address"
        return result

    # ── Check token age guard (added < 30 min ago → skip) ────────────────────
    from datetime import datetime, timezone
    added_at = pair.get("added_at")
    if added_at:
        if isinstance(added_at, str):
            try:
                added_at = datetime.fromisoformat(added_at.replace("Z", "+00:00"))
            except ValueError:
                added_at = None
        if added_at:
            age_min = (datetime.now(timezone.utc) - added_at).total_seconds() / 60
            if age_min < config.MEME_MIN_AGE_MIN:
                result.reason = f"Token age {age_min:.0f}min < {config.MEME_MIN_AGE_MIN}min gate"
                return result

    # ── Fetch overview ────────────────────────────────────────────────────────
    overview = birdeye.get_token_overview(contract)
    if not overview:
        result.reason = "Birdeye overview unavailable"
        return result

    result.current_price = float(overview.get("price", 0))
    result.liquidity     = float(overview.get("liquidity", 0))

    # Liquidity floor
    if result.liquidity < config.MEME_MIN_LIQ:
        result.reason = f"Liquidity ${result.liquidity:,.0f} < ${config.MEME_MIN_LIQ:,.0f}"
        return result

    # mcap filter
    mcap = float(overview.get("mcap", 0))
    if mcap > config.MEME_MAX_MCAP:
        result.reason = f"Mcap ${mcap:,.0f} > ${config.MEME_MAX_MCAP:,.0f} cap"
        return result

    # ── Condition 1: Volume spike ─────────────────────────────────────────────
    vols_5m = birdeye.get_5m_volumes_1h(contract)
    if len(vols_5m) >= 2:
        current_5m_vol = vols_5m[-1]
        avg_5m_vol = float(np.mean(vols_5m[:-1])) if len(vols_5m) > 1 else 0
        result.vol_ratio = round(current_5m_vol / avg_5m_vol, 3) if avg_5m_vol > 0 else 0
        if result.vol_ratio >= config.MEME_VOL_SPIKE_X:
            result.vol_spike = True
            logger.debug(f"{symbol}: Vol spike {result.vol_ratio:.1f}x ✓")

    # Fallback: 24h volume increase check
    if not result.vol_spike:
        v24h = float(overview.get("volume_24h", 0))
        v1h  = float(overview.get("volume_1h", 0))
        if v1h > 0 and v24h > 0:
            # Annualise 1h volume to estimate 30min run rate
            vol_30m_pct_increase = (v1h * 2) / v24h - 1
            if vol_30m_pct_increase >= config.MEME_VOL_24H_INC:
                result.vol_spike = True
                logger.debug(f"{symbol}: 24h vol +{vol_30m_pct_increase:.0%} ✓")

    if not result.vol_spike:
        result.reason = f"No vol spike (ratio={result.vol_ratio:.1f}x)"
        result.entry_allowed = False
        return result

    # ── Condition 2: Price breakout ───────────────────────────────────────────
    df_5m = birdeye.get_ohlcv(contract, "5m", limit=20)
    if df_5m.empty or len(df_5m) < 4:
        result.reason = "Insufficient OHLCV data"
        return result

    close_now = float(df_5m["close"].iloc[-1])
    open_now  = float(df_5m["open"].iloc[-1])
    high_15m  = float(df_5m["high"].iloc[-4:-1].max())  # highest close last 15m (3 × 5m bars)

    # Price above 15m high
    above_high = close_now > high_15m

    # Candle body > 2%
    candle_body_pct = abs(close_now - open_now) / open_now if open_now > 0 else 0
    strong_body = candle_body_pct >= config.MEME_BREAKOUT_MIN

    # VWAP: volume-weighted average price over last 1h (12 × 5m bars)
    if len(df_5m) >= 12:
        vwap_df = df_5m.tail(12)
        typical_price = (vwap_df["high"] + vwap_df["low"] + vwap_df["close"]) / 3
        vwap = float((typical_price * vwap_df["volume"]).sum() / vwap_df["volume"].sum()) \
               if vwap_df["volume"].sum() > 0 else 0
        above_vwap = close_now > vwap if vwap > 0 else True
    else:
        above_vwap = True

    result.breakout = above_high and strong_body and above_vwap

    if not result.breakout:
        result.reason = (
            f"Breakout fail: above_high={above_high} "
            f"body={candle_body_pct:.1%} above_vwap={above_vwap}"
        )
        return result

    # ── All conditions met ────────────────────────────────────────────────────
    result.entry_allowed = True
    result.reason = f"Vol spike {result.vol_ratio:.1f}x + breakout above {high_15m:.6f}"
    logger.info(f"MEME SIGNAL: {symbol} ({contract[:8]}…) → ENTRY ✅")
    return result
