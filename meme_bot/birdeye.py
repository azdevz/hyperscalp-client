"""
meme_bot/birdeye.py — Birdeye API client for Solana token data.

Provides:
  - get_ohlcv(contract, interval, limit) → pd.DataFrame
  - get_token_overview(contract) → dict (mcap, volume, liquidity, price)
  - get_volume_history(contract) → 5-minute volume bars for last 1h
"""

import logging
from typing import Optional

import httpx
import pandas as pd

import config

logger = logging.getLogger(__name__)

BASE_URL = "https://public-api.birdeye.so"

HEADERS = {
    "X-API-KEY": config.BIRDEYE_API_KEY,
    "x-chain": "solana",
}


def _get(endpoint: str, params: dict = None) -> Optional[dict]:
    if not config.BIRDEYE_API_KEY:
        logger.debug("Birdeye API key not set — skipping request.")
        return None
    try:
        resp = httpx.get(
            f"{BASE_URL}{endpoint}",
            headers=HEADERS,
            params=params or {},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning(f"Birdeye request failed {endpoint}: {exc}")
        return None


def get_token_overview(contract: str) -> Optional[dict]:
    """
    Returns token overview: price, mcap, liquidity, volume24h, holders.
    """
    data = _get("/defi/token_overview", {"address": contract})
    if not data or not data.get("success"):
        return None
    d = data.get("data", {})
    return {
        "price":       d.get("price", 0),
        "mcap":        d.get("mc", 0),
        "liquidity":   d.get("liquidity", 0),
        "volume_24h":  d.get("v24hUSD", 0),
        "volume_1h":   d.get("v1hUSD", 0),
        "holders":     d.get("holder", 0),
        "price_change_24h": d.get("priceChange24h", 0),
    }


def get_ohlcv(contract: str, interval: str = "5m", limit: int = 20) -> pd.DataFrame:
    """
    Fetch OHLCV candles from Birdeye.
    interval: '1m' | '5m' | '15m' | '1H'
    """
    # Map to Birdeye interval format
    interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H"}
    be_interval = interval_map.get(interval, "5m")

    data = _get("/defi/ohlcv", {
        "address":  contract,
        "type":     be_interval,
        "limit":    limit,
    })

    if not data or not data.get("success"):
        return pd.DataFrame()

    items = data.get("data", {}).get("items", [])
    if not items:
        return pd.DataFrame()

    df = pd.DataFrame(items)
    df = df.rename(columns={
        "unixTime": "timestamp",
        "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"
    })
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce")
    return df.sort_values("timestamp").reset_index(drop=True)


def get_5m_volumes_1h(contract: str) -> list[float]:
    """Returns last 12 × 5-minute volume bars (1 hour)."""
    df = get_ohlcv(contract, "5m", limit=13)
    if df.empty or "volume" not in df.columns:
        return []
    return df["volume"].tolist()


def get_pool_liquidity(contract: str) -> float:
    """Quick liquidity check via token overview."""
    overview = get_token_overview(contract)
    if overview:
        return float(overview.get("liquidity", 0))
    return 0.0
