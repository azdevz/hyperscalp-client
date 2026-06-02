"""
hl_bot/signals.py — Quantitative Scalping Engine (LLM-Simulator)

This engine mathematically mimics the output of a High-Frequency Trading LLM
by analyzing Order Book Imbalance (OBI), Cumulative Volume Delta (CVD) divergence,
and Open Interest (OI) spikes. It returns a strict JSON string payload.

v2: Added 5m EMA trend filter, LIMIT_IOC fills, wider TPs, reduced leverage.
"""

import logging
import json
import time
import math
import pandas as pd
import numpy as np
from typing import Optional

from hl_bot import execution, ws_feed
import httpx
import config
import db

logger = logging.getLogger(__name__)

CANDLE_URL = "{base}/info"

# Stateful tracker for Open Interest and Price velocity (to detect squeezes)
_STATE = {}

def _fetch_candles(symbol: str, interval: str, n: int = 5) -> pd.DataFrame:
    ms_map = {"1m": 60000, "5m": 300000}
    end_time = int(time.time() * 1000)
    start_time = end_time - ms_map.get(interval, 60000) * n
    
    body = {
        "type": "candleSnapshot",
        "req": {"coin": symbol, "interval": interval, "startTime": start_time, "endTime": end_time},
    }
    try:
        resp = httpx.post(CANDLE_URL.format(base=config.HL_BASE_URL), json=body, timeout=5)
        resp.raise_for_status()
        raw = resp.json()
        if not raw:
            return pd.DataFrame()
        df = pd.DataFrame(raw)
        df = df.rename(columns={"t": "timestamp", "o": "open", "h": "high",
                                  "l": "low",   "c": "close",  "v": "volume"})
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.sort_values("timestamp").reset_index(drop=True).tail(n)
    except Exception as exc:
        logger.warning(f"Candle fetch failed {symbol} {interval}: {exc}")
        return pd.DataFrame()


def _get_obi(symbol: str, current_price: float) -> tuple[float, float]:
    """Calculates Bid and Ask volume within 0.5% of mid price."""
    l2 = execution.get_l2_book(symbol)
    if not l2:
        return 0.0, 0.0
        
    levels = l2.get("levels", [[], []])
    if len(levels) < 2:
        return 0.0, 0.0
        
    bids, asks = levels[0], levels[1]
    
    bid_vol = 0.0
    for b in bids:
        px = float(b.get("px", 0))
        sz = float(b.get("sz", 0))
        if px >= current_price * 0.995:
            bid_vol += sz * px
            
    ask_vol = 0.0
    for a in asks:
        px = float(a.get("px", 0))
        sz = float(a.get("sz", 0))
        if px <= current_price * 1.005:
            ask_vol += sz * px
            
    return bid_vol, ask_vol


def _get_cvd_divergence(symbol: str, df_1m: pd.DataFrame) -> str:
    """Calculates CVD Divergence using 1m candle volume proxy over last 5m."""
    if df_1m.empty or len(df_1m) < 5:
        return "NONE"
        
    df_cvd = df_1m.tail(5)
    buy_vol = 0.0
    sell_vol = 0.0
    
    for _, row in df_cvd.iterrows():
        if row["close"] > row["open"]:
            buy_vol += float(row["volume"])
        elif row["close"] < row["open"]:
            sell_vol += float(row["volume"])
            
    c_close = float(df_cvd["close"].iloc[-1])
    c_open_5m = float(df_cvd["open"].iloc[0])
    price_delta_pct = (c_close - c_open_5m) / c_open_5m if c_open_5m > 0 else 0
    
    # Bearish Absorption: Price flat/down, STRONG net buying (1.5x ratio)
    # Aggressive buying met by passive sellers. Price will drop.
    if -0.003 <= price_delta_pct <= 0.001 and buy_vol > (sell_vol * 1.5):
        return "BEARISH"
    
    # Bullish Absorption: Price flat/up, net volume is aggressive selling
    # Aggressive selling met by passive buyers. Price will bounce.
    if -0.001 <= price_delta_pct <= 0.003 and sell_vol > (buy_vol * 1.2):
        return "BULLISH"
        
    return "NONE"


def _get_5m_trend(df_5m: pd.DataFrame) -> str:
    """
    Determines the 5-minute trend direction using EMA-20 slope.
    Returns 'UP', 'DOWN', or 'FLAT'.
    This is the KEY filter that prevents counter-trend entries.
    """
    if df_5m.empty or len(df_5m) < 10:
        return "FLAT"

    ema_20 = df_5m["close"].ewm(span=20, adjust=False).mean()
    
    # Check slope of last 3 EMA values
    if len(ema_20) < 3:
        return "FLAT"
    
    slope_recent = float(ema_20.iloc[-1]) - float(ema_20.iloc[-3])
    ema_val = float(ema_20.iloc[-1])
    
    # Normalize slope as percentage of price
    slope_pct = slope_recent / ema_val if ema_val > 0 else 0
    
    # Require a meaningful slope (>0.05% over 3 bars = 15min)
    if slope_pct > 0.0005:
        return "UP"
    elif slope_pct < -0.0005:
        return "DOWN"
    return "FLAT"


def compute_signals(symbol: str) -> str:
    """
    Outputs the strict JSON string payload.
    v2: No auto-tuner blocking. Uses 5m trend filter instead.
    """
    default_resp = {
      "action": "NO_TRADE",
      "asset": symbol,
      "reasoning_code": "NONE",
      "entry_limit_price": 0.0,
      "take_profit": 0.0,
      "stop_loss": 0.0,
      "leverage": 1,
      "execution_type": "LIMIT_IOC"
    }

    # ── Funding rate entry guard ──────────────────────────────────────────────
    # HL settles funding every hour. Never open a new trade at :57-:00.
    # A bad entry near the hour boundary risks an immediate funding spike.
    from datetime import datetime as _dt, timezone as _tz
    _now_min = _dt.now(_tz.utc).minute
    if _now_min >= 57 or _now_min == 0:
        return json.dumps(default_resp)



    # Data Fetching (1m and 5m payloads)
    df_1m = _fetch_candles(symbol, "1m", n=150) # Need 150 for EMA-50 to avoid initialization bias
    df_5m = _fetch_candles(symbol, "5m", n=30)  # Need 30 for EMA-20 on 5m
    
    if df_1m.empty or df_5m.empty:
        return json.dumps(default_resp)
        
    c_close = float(df_1m["close"].iloc[-1])
    ema_50 = float(df_1m["close"].ewm(span=50, adjust=False).mean().iloc[-1])
    
    # ── 5-MINUTE TREND FILTER (the most important change) ─────────────────────
    trend_5m = _get_5m_trend(df_5m)
    
    # RSI-14 calculation for overbought/oversold filter
    delta = df_1m['close'].diff()
    gain = delta.where(delta > 0, 0.0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
    
    # ATR Calculation
    prev_close = df_1m['close'].shift(1)
    tr1 = df_1m['high'] - df_1m['low']
    tr2 = (df_1m['high'] - prev_close).abs()
    tr3 = (df_1m['low'] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = float(tr.ewm(alpha=1/14, adjust=False).mean().iloc[-1])
    
    # Bollinger Bands Calculation
    sma_20_series = df_1m['close'].rolling(window=20).mean()
    std_20_series = df_1m['close'].rolling(window=20).std()
    upper_bb_series = sma_20_series + 2 * std_20_series
    lower_bb_series = sma_20_series - 2 * std_20_series
    
    sma_20 = float(sma_20_series.iloc[-1])
    upper_bb = float(upper_bb_series.iloc[-1])
    lower_bb = float(lower_bb_series.iloc[-1])
    
    # Regime Detection
    # If bb_width > 0.003 (0.3%), it's trending. Otherwise, sideways.
    bb_width = (upper_bb - lower_bb) / sma_20 if sma_20 > 0 else 0
    is_trending = bb_width > 0.003

    
    # Track OI internally for squeezes
    current_oi = execution.get_open_interest(symbol)
    now = time.time()
    
    oi_spike_bullish = False
    oi_spike_bearish = False
    
    if symbol not in _STATE:
        _STATE[symbol] = {"oi": current_oi, "px": c_close, "ts": now, "sq_bull": 0, "sq_bear": 0}
    else:
        state = _STATE[symbol]
        dt = now - state["ts"]
        
        # Evaluate over 60 second buckets
        if dt >= 60:
            oi_change = (current_oi - state["oi"]) / state["oi"] if state["oi"] > 0 else 0
            px_change = (c_close - state["px"]) / state["px"] if state["px"] > 0 else 0
            
            # Momentum Spike: OI spiked > 0.1%, price moved > 0.1%
            if oi_change > 0.001:
                if px_change > 0.001:  # Strong Long Momentum
                    state["sq_bull"] = now + 120 # valid for 2 mins
                elif px_change < -0.001: # Strong Short Momentum
                    state["sq_bear"] = now + 120 # valid for 2 mins
                    
            state["oi"] = current_oi
            state["px"] = c_close
            state["ts"] = now
            
        if now < state.get("sq_bull", 0):
            oi_spike_bullish = True
        if now < state.get("sq_bear", 0):
            oi_spike_bearish = True

    # Alpha 1: Order Book Imbalance (OBI) — 2.0x ratio
    # Bids represent support but also liquidity magnets (draw price down).
    # Asks represent resistance but also liquidity magnets (draw price up).
    if ws_feed.is_connected():
        ob_ratio = ws_feed.get_ob_ratio(symbol)
        obi_bullish = ob_ratio < 0.5 and ob_ratio > 0
        obi_bearish = ob_ratio > 2.0
    else:
        bid_vol, ask_vol = _get_obi(symbol, c_close)
        obi_bullish = ask_vol > (bid_vol * 2.0) and bid_vol > 0
        obi_bearish = bid_vol > (ask_vol * 2.0) and ask_vol > 0
    
    # Alpha 2: CVD Divergence
    cvd_div = _get_cvd_divergence(symbol, df_1m)
    cvd_bullish = cvd_div == "BULLISH"
    cvd_bearish = cvd_div == "BEARISH"
    
    # RSI filter: reject overbought longs (RSI > 65) and oversold shorts (RSI < 35)
    rsi_allows_long = current_rsi < 65
    rsi_allows_short = current_rsi > 35
    
    # Additional confluences
    rsi_oversold = current_rsi < 35
    rsi_overbought = current_rsi > 65
    
    vol_mean = df_1m["volume"].rolling(20).mean().iloc[-1]
    vol_spike = float(df_1m["volume"].iloc[-1]) > (vol_mean * 1.5) if vol_mean > 0 else False

    # Signal scores
    bullish_score = int(sum([bool(obi_bullish), bool(cvd_bullish), bool(oi_spike_bullish), bool(rsi_oversold), bool(vol_spike)]))
    bearish_score = int(sum([bool(obi_bearish), bool(cvd_bearish), bool(oi_spike_bearish), bool(rsi_overbought), bool(vol_spike)]))
    
    # Auto-tuner can adjust min_score thresholds (but never BLOCK)
    try:
        req_sym = int(db.get_bot_state(f"tuner_sym_{symbol}_min_score") or 2)
        bull_threshold = max(2, req_sym)
        bear_threshold = max(2, req_sym)
    except Exception:
        bull_threshold = 2
        bear_threshold = 2

    action = "NO_TRADE"
    reason = "NONE"

    # ── LONG TRADES ───────────────────────────────────────────────────────────
    if bullish_score >= bull_threshold and rsi_allows_long:
        if trend_5m == "UP":
            if is_trending:
                if c_close > ema_50:  # Price above 1m EMA-50 confirms short-term strength
                    action = "EXECUTE_LONG"
                    if oi_spike_bullish: reason = "TREND_MOMENTUM_SPIKE"
                    elif cvd_bullish: reason = "TREND_CVD_DIVERGENCE"
                    else: reason = "TREND_BREAKOUT"
            else:
                # Sideways + upward bias: Mean reversion long at lower BB
                if c_close <= lower_bb * 1.005:
                    action = "EXECUTE_LONG"
                    reason = "MEAN_REVERSION_SUPPORT"
        elif trend_5m == "FLAT":
            # Flat trend: Mean reversion long at lower BB
            if c_close <= lower_bb * 1.005:
                action = "EXECUTE_LONG"
                reason = "MEAN_REVERSION_SUPPORT"
            
    # ── SHORT TRADES ──────────────────────────────────────────────────────────
    elif bearish_score >= bear_threshold and rsi_allows_short:
        if trend_5m == "DOWN":
            if is_trending:
                if c_close < ema_50:  # Price below 1m EMA-50 confirms short-term weakness
                    action = "EXECUTE_SHORT"
                    if oi_spike_bearish: reason = "TREND_MOMENTUM_SPIKE"
                    elif cvd_bearish: reason = "TREND_CVD_DIVERGENCE"
                    else: reason = "TREND_BREAKOUT"
            else:
                # Sideways + downward bias: Mean Reversion short at upper BB
                if c_close >= upper_bb * 0.995:
                    action = "EXECUTE_SHORT"
                    reason = "MEAN_REVERSION_RESISTANCE"
        elif trend_5m == "FLAT":
            # Flat trend: Mean reversion short at upper BB
            if c_close >= upper_bb * 0.995:
                action = "EXECUTE_SHORT"
                reason = "MEAN_REVERSION_RESISTANCE"
        
    # Leverage mapping — REDUCED to widen effective stops
    leverage_map = {"BTC": 7, "ETH": 5, "SOL": 3}
    lev = leverage_map.get(symbol, 3)
    
    # Dynamic Risk-to-Reward optimized for 70-80% Win Rate (Tight TP, Wider SL)
    atr_pct = atr / c_close if c_close > 0 else 0
    if is_trending:
        sl_pct = max(0.003, min(0.004, atr_pct * 1.0))  # Tight stop capped at 0.4%
    else:
        sl_pct = max(0.003, min(0.004, atr_pct * 0.8))  # Tight stop capped at 0.4%
    
    tp_pct = 0.006  # Fixed Take Profit at 0.6%
    
    is_long = action == "EXECUTE_LONG"
    
    sl_px = c_close * (1 - sl_pct) if is_long else c_close * (1 + sl_pct)
    tp_px = c_close * (1 + tp_pct) if is_long else c_close * (1 - tp_pct)
    
    # All orders use LIMIT_IOC — guarantees fill or nothing (no stale POST_ONLY)
    exec_type = "LIMIT_IOC"

    resp = {
      "action": action,
      "asset": symbol,
      "reasoning_code": reason,
      "entry_limit_price": float(round(c_close, 5)),
      "take_profit": float(round(tp_px, 5)),
      "stop_loss": float(round(sl_px, 5)),
      "leverage": lev,
      "execution_type": exec_type,
      "cvd_bullish": 100 if bool(cvd_bullish) else 50,
      "cvd_bearish": 100 if bool(cvd_bearish) else 50,
      "oi_spike": 100 if bool(oi_spike_bullish or oi_spike_bearish) else 0,
      "obi_bullish": 3.0 if bool(obi_bullish) else 1.0,
      "obi_bearish": 0.5 if bool(obi_bearish) else 1.0,
      "score": int(max(bullish_score, bearish_score)),
      "trend_5m": trend_5m,
    }
    
    if action != "NO_TRADE":
        logger.info(f"AI ENGINE [{symbol}]: {action} | Reason: {reason} | Score: B={bullish_score}/S={bearish_score} | Trend5m: {trend_5m}")
    
    return json.dumps(resp)
