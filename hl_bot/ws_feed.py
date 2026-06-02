"""
hl_bot/ws_feed.py — Hyperliquid WebSocket feed manager.

Streams L2 order book data for multiple symbols and exposes:
  - get_ob_ratio(symbol) → float  (bid_vol / ask_vol)
  - get_last_trades(symbol) → list[dict]

Runs in a daemon thread started by main.py at boot.
Auto-reconnects with exponential backoff on disconnect.
"""

import json
import logging
import threading
import time
from collections import defaultdict, deque
from typing import Optional

import websocket  # websocket-client library

import config

logger = logging.getLogger(__name__)

# ── Shared state (thread-safe via GIL for simple reads) ──────────────────────
_ob_bids:   dict[str, dict[float, float]] = defaultdict(dict)  # price → size
_ob_asks:   dict[str, dict[float, float]] = defaultdict(dict)
_last_trades: dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
_connected = False
_ws_app: Optional[websocket.WebSocketApp] = None

# ── Public accessors ──────────────────────────────────────────────────────────

def get_ob_ratio(symbol: str) -> float:
    """Returns bid volume / ask volume. >1 = bullish pressure, <1 = bearish."""
    bids = _ob_bids.get(symbol, {})
    asks = _ob_asks.get(symbol, {})
    bid_vol = sum(bids.values())
    ask_vol = sum(asks.values())
    if ask_vol == 0:
        return 1.0
    return round(bid_vol / ask_vol, 4)


def get_last_trades(symbol: str) -> list[dict]:
    return list(_last_trades.get(symbol, []))


def is_connected() -> bool:
    return _connected


# ── WebSocket callbacks ───────────────────────────────────────────────────────

def _on_open(ws):
    global _connected
    _connected = True
    logger.info("HL WebSocket connected.")
    symbols = config.HL_PRIMARY_PAIRS + config.HL_SECONDARY_PAIRS
    # Subscribe to L2 book for each symbol
    for sym in symbols:
        coin = f"{sym}-PERP" if not sym.endswith("-PERP") else sym
        ws.send(json.dumps({
            "method": "subscribe",
            "subscription": {"type": "l2Book", "coin": sym}
        }))
        ws.send(json.dumps({
            "method": "subscribe",
            "subscription": {"type": "trades", "coin": sym}
        }))
    logger.info(f"Subscribed to L2 book + trades for: {symbols}")


def _on_message(ws, message: str):
    try:
        data = json.loads(message)
        channel = data.get("channel", "")
        d = data.get("data", {})

        if channel == "l2Book":
            coin = d.get("coin", "")
            # Snapshot or update
            levels = d.get("levels", [[], []])
            if len(levels) >= 2:
                bids_raw, asks_raw = levels[0], levels[1]
                _ob_bids[coin] = {
                    float(b["px"]): float(b["sz"]) for b in bids_raw
                }
                _ob_asks[coin] = {
                    float(a["px"]): float(a["sz"]) for a in asks_raw
                }

        elif channel == "trades":
            coin = d[0].get("coin", "") if isinstance(d, list) and d else ""
            if coin:
                for trade in (d if isinstance(d, list) else [d]):
                    _last_trades[coin].append({
                        "price": float(trade.get("px", 0)),
                        "size":  float(trade.get("sz", 0)),
                        "side":  trade.get("side", ""),
                        "time":  trade.get("time", 0),
                    })
    except Exception as exc:
        logger.debug(f"WS parse error: {exc}")


def _on_error(ws, error):
    logger.warning(f"HL WebSocket error: {error}")


def _on_close(ws, close_status_code, close_msg):
    global _connected
    _connected = False
    logger.warning(f"HL WebSocket closed ({close_status_code}): {close_msg}")


# ── Connection loop with exponential backoff ──────────────────────────────────

def _run_forever():
    global _ws_app
    backoff = 1
    while True:
        try:
            ws_url = (
                "wss://api.hyperliquid-testnet.xyz/ws"
                if config.IS_TESTNET
                else "wss://api.hyperliquid.xyz/ws"
            )
            _ws_app = websocket.WebSocketApp(
                ws_url,
                on_open=_on_open,
                on_message=_on_message,
                on_error=_on_error,
                on_close=_on_close,
            )
            _ws_app.run_forever(ping_interval=20, ping_timeout=10)
        except Exception as exc:
            logger.error(f"WS loop exception: {exc}")
        logger.info(f"Reconnecting in {backoff}s…")
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)


def start_ws_thread() -> None:
    """Launch WS in a daemon thread. Call once from main.py."""
    t = threading.Thread(target=_run_forever, daemon=True, name="hl-ws-feed")
    t.start()
    logger.info("HL WebSocket thread started.")
