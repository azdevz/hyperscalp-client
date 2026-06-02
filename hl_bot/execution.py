"""
hl_bot/execution.py — Order placement, monitoring, and exit logic for Hyperliquid perps.

Handles:
  - Placing limit entry orders (maker, reduce fees)
  - Monitoring TP1 / TP2 / Trailing / Hard SL / Time Stop
  - Writing trade records to DB
  - Alerts on close
"""

import logging
import time
from datetime import datetime, timezone
import math
from typing import Optional

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants
import eth_account

import config
import db
import alerts

logger = logging.getLogger(__name__)

# ── Hyperliquid client singletons ─────────────────────────────────────────────
_exchange: Optional[Exchange] = None
_info:     Optional[Info]     = None
_current_network: Optional[str] = None  # Tracks 'demo' | 'live' in memory


def _get_clients() -> tuple[Exchange, Info]:
    global _exchange, _info, _current_network
    
    # Query database for current network regime (demo or live)
    try:
        db_regime = db.get_bot_state("hl_network_regime") or "demo"
    except Exception as exc:
        logger.debug(f"Network regime DB lookup failed: {exc}")
        db_regime = "demo"

    # Re-initialize clients if singletons are empty OR the network regime has changed
    if _exchange is None or _info is None or _current_network != db_regime:
        # Resolve dynamic credentials based on active regime
        if db_regime == "live":
            base_url = constants.MAINNET_API_URL
            private_key = config.HL_MAINNET_PRIVATE_KEY or config.HL_PRIVATE_KEY
        else:
            base_url = constants.TESTNET_API_URL
            private_key = config.HL_TESTNET_PRIVATE_KEY or config.HL_PRIVATE_KEY

        if not private_key:
            raise ValueError(f"No private key configured for Hyperliquid {db_regime.upper()} mode.")

        account = eth_account.Account.from_key(private_key)
        _exchange = Exchange(account, base_url, account_address=config.HL_ACCOUNT or account.address)
        _info = Info(base_url, skip_ws=True)
        _current_network = db_regime
        logger.info(f"HL clients initialised and routed to {db_regime.upper()} ({base_url}).")

    return _exchange, _info


def get_account_balance() -> float:
    """Returns USDT account value (unrealised PnL included)."""
    try:
        _, info = _get_clients()
        state = info.user_state(config.HL_ACCOUNT or _get_clients()[0].wallet.address)
        return float(state.get("marginSummary", {}).get("accountValue", 0))
    except Exception as exc:
        logger.error(f"Balance fetch failed: {exc}")
        return 0.0


def get_spot_balance() -> float:
    """Returns total USDC spot balance."""
    try:
        _, info = _get_clients()
        spot_state = info.spot_user_state(config.HL_ACCOUNT or _get_clients()[0].wallet.address)
        usdc_balance = 0.0
        for b in spot_state.get("balances", []):
            if b.get("coin") == "USDC":
                usdc_balance += float(b.get("total", 0))
        return usdc_balance
    except Exception as exc:
        logger.error(f"Spot balance fetch failed: {exc}")
        return 0.0


def get_open_positions() -> list[dict]:
    """Returns current open positions from HL account state."""
    try:
        _, info = _get_clients()
        addr = config.HL_ACCOUNT
        state = info.user_state(addr)
        positions = []
        for pos in state.get("assetPositions", []):
            p = pos.get("position", {})
            szi = float(p.get("szi", 0))
            if szi == 0:
                continue
            entry = float(p.get("entryPx", 0))
            pnl   = float(p.get("unrealizedPnl", 0))
            positions.append({
                "symbol":      p.get("coin", ""),
                "direction":   "long" if szi > 0 else "short",
                "size":        abs(szi),
                "entry_price": entry,
                "unrealized_pnl": pnl,
                "leverage":    p.get("leverage", {}).get("value", 1),
                "margin":      float(p.get("marginUsed", 0)),
                "liquidation_px": float(p.get("liquidationPx", 0)) if p.get("liquidationPx") else None,
                "position_value": float(p.get("positionValue", 0)),
                "roe":         float(p.get("returnOnEquity", 0)),
            })
        return positions
    except Exception as exc:
        logger.error(f"Positions fetch failed: {exc}")
        return []


def get_mid_price(symbol: str) -> float:
    """Get current mid price for a symbol."""
    try:
        _, info = _get_clients()
        mids = info.all_mids()
        return float(mids.get(symbol, 0))
    except Exception as exc:
        logger.debug(f"Mid price fetch failed {symbol}: {exc}")
        return 0.0


def get_funding_rate(symbol: str) -> float:
    """Get current funding rate."""
    try:
        _, info = _get_clients()
        meta = info.meta()
        for asset in meta.get("universe", []):
            if asset.get("name") == symbol:
                return float(asset.get("funding", 0))
        return 0.0
    except Exception:
        return 0.0


def get_sz_decimals(symbol: str) -> int:
    """Get size decimals for a coin."""
    try:
        _, info = _get_clients()
        meta = info.meta()
        for asset in meta.get("universe", []):
            if asset.get("name") == symbol:
                return int(asset.get("szDecimals", 0))
        return 0
    except Exception:
        return 0


def get_l2_book(symbol: str) -> dict:
    """Get L2 order book snapshot."""
    try:
        _, info = _get_clients()
        return info.l2_snapshot(symbol)
    except Exception as exc:
        logger.debug(f"L2 book fetch failed {symbol}: {exc}")
        return {}


def get_recent_trades(symbol: str) -> list:
    """Get recent trades for CVD calculation."""
    try:
        # Note: info client might not have a direct helper, fallback to raw post if needed
        # The python SDK info client usually has info.post("l2Book", {"coin": symbol}) but l2_snapshot works.
        # For trades, we can try info.post("trades", {"coin": symbol}) or info.user_history if generic.
        # Actually, info.post("trades", {"coin": symbol}) works on HL API.
        _, info = _get_clients()
        return info.post("trades", {"coin": symbol})
    except Exception as exc:
        logger.debug(f"Trades fetch failed {symbol}: {exc}")
        return []


def get_open_interest(symbol: str) -> float:
    """Get current Open Interest for an asset."""
    try:
        _, info = _get_clients()
        # info.meta_and_asset_ctxs() returns [universe, contexts]
        ctxs = info.meta_and_asset_ctxs()[1]
        meta = info.meta()
        for idx, asset in enumerate(meta.get("universe", [])):
            if asset.get("name") == symbol:
                return float(ctxs[idx].get("openInterest", 0))
        return 0.0
    except Exception as exc:
        logger.debug(f"OI fetch failed {symbol}: {exc}")
        return 0.0


def set_leverage(symbol: str, leverage: int) -> bool:
    try:
        exchange, _ = _get_clients()
        exchange.update_leverage(leverage, symbol, is_cross=False)
        return True
    except Exception as exc:
        logger.warning(f"Set leverage failed {symbol} {leverage}x: {exc}")
        return False


def place_limit_order(
    symbol:    str,
    direction: str,       # 'long' | 'short'
    size_usd:  float,
    price:     float,
    leverage:  int,
    execution_type: str = "POST_ONLY"
) -> Optional[dict]:
    """
    Place an order using POST_ONLY (Alo) or LIMIT_IOC (Ioc).
    """
    exchange, _ = _get_clients()
    set_leverage(symbol, leverage)

    mid = get_mid_price(symbol)
    if mid == 0:
        logger.error(f"Cannot place order — no mid price for {symbol}")
        return None

    # Convert USD size to coins and round to correct decimals
    sz_decimals = get_sz_decimals(symbol)
    coin_size = round(size_usd / price, sz_decimals)
    
    if coin_size <= 0:
        logger.error(f"Invalid coin size {coin_size} for {symbol} after rounding")
        return None

    is_buy = direction == "long"

    # Calculate exact tick size based on 5 sig figs
    exponent = math.floor(math.log10(price)) - 4
    tick = 10 ** exponent
    
    # We want to buy at ask (price + tick) or sell at bid (price - tick) for POST_ONLY
    # For LIMIT_IOC, we aggressively price it through the book
    if execution_type == "POST_ONLY":
        raw_limit_px = price - tick if is_buy else price + tick
        tif = "Alo" # Add Liquidity Only (Post Only)
    else: # LIMIT_IOC
        raw_limit_px = price * 1.05 if is_buy else price * 0.95
        tif = "Ioc" # Immediate or Cancel
    
    decimals = max(0, -exponent)
    limit_px = round(raw_limit_px, decimals)
    limit_px = float(limit_px)

    logger.info(
        f"{'BUY' if is_buy else 'SELL'} {symbol} | "
        f"size={coin_size} ({size_usd:.2f}USD) @ {limit_px} | {leverage}x | {tif}"
    )

    try:
        result = exchange.order(
            symbol,
            is_buy,
            coin_size,
            limit_px,
            {"limit": {"tif": tif}},
        )
        return result
    except Exception as exc:
        logger.error(f"Order placement failed {symbol}: {exc}")
        return None


def close_position(symbol: str, direction: str, size: float) -> Optional[dict]:
    """Market close entire position."""
    exchange, _ = _get_clients()
    try:
        # SDK's market_close automatically determines side (reduce-only)
        result = exchange.market_close(
            coin=symbol,
            sz=size,
            slippage=0.05, # 5% slippage to guarantee fill
        )
        return result
    except Exception as exc:
        logger.error(f"Close position failed {symbol}: {exc}")
        return None


def partial_close(symbol: str, direction: str, close_fraction: float, position_size: float) -> bool:
    """Close a fraction of the position (e.g., 0.5 for 50%)."""
    close_size = round(position_size * close_fraction, 6)
    exchange, _ = _get_clients()
    try:
        exchange.market_close(
            coin=symbol,
            sz=close_size,
            slippage=0.05,
        )
        return True
    except Exception as exc:
        logger.error(f"Partial close failed {symbol}: {exc}")
        return False


def get_actual_close_fill(symbol: str) -> Optional[dict]:
    """Fetch the latest historical fill for a symbol from Hyperliquid."""
    try:
        _, info = _get_clients()
        addr = config.HL_ACCOUNT or _get_clients()[0].wallet.address
        fills = info.user_fills(addr)
        for fill in fills:
            if fill.get("coin") == symbol and "Close" in fill.get("dir", ""):
                return {
                    "price": float(fill.get("px", 0)),
                    "pnl": float(fill.get("closedPnl", 0)),
                    "fee": float(fill.get("fee", 0)),
                }
        return None
    except Exception as exc:
        logger.error(f"Failed to fetch actual close fill for {symbol}: {exc}")
        return None


# ── Active trade monitoring ───────────────────────────────────────────────────

class ActiveTrade:
    """Tracks a single open trade and manages its exit lifecycle."""

    def __init__(
        self,
        trade_id:    int,
        symbol:      str,
        direction:   str,
        entry_price: float,
        size_usd:    float,
        coin_size:   float,
        opened_at:   datetime,
        sl_pct:      float,
        tp_pct:      float,
        stop_type:   str,
    ):
        self.trade_id    = trade_id
        self.symbol      = symbol
        self.direction   = direction
        self.entry_price = entry_price
        self.size_usd    = size_usd
        self.coin_size   = coin_size
        self.opened_at   = opened_at
        self.tp1_hit     = False
        self.peak_price  = entry_price
        self.closed      = False
        self.sl_pct      = sl_pct
        self.tp_pct      = tp_pct
        self.stop_type   = stop_type
        self.breakeven_active = False

    def check_exit(self, current_price: float) -> Optional[str]:
        if self.closed:
            return None

        mult = 1 if self.direction == "long" else -1
        pct_move = mult * (current_price - self.entry_price) / self.entry_price

        if self.direction == "long":
            self.peak_price = max(self.peak_price, current_price)
        else:
            self.peak_price = min(self.peak_price, current_price)

        elapsed_min = (datetime.now(timezone.utc) - self.opened_at).total_seconds() / 60
        now_minute  = datetime.now(timezone.utc).minute

        # ── Funding rate guard: HL settles hourly — exit losers at :58 ───────
        # Avoids being caught by up-to-4%/hr funding spike on a losing trade
        if now_minute >= 58 and pct_move < 0:
            logger.info(f"Funding guard exit {self.symbol} @ {current_price:.4f} (min={now_minute}, pnl={pct_move:+.3%})")
            return "funding_guard"

        # ── Breakeven stop: after 0.3% in our favor, move SL to entry ────────
        # Disabled in Option B setup to allow trades breathing room.
        # if not self.breakeven_active and pct_move >= 0.003:
        #     self.breakeven_active = True
        #     logger.info(f"Breakeven activated {self.symbol} @ {current_price:.4f} (move: {pct_move:+.3%})")
        # 
        # if self.breakeven_active and pct_move <= 0.0001:
        #     return "breakeven"

        # Hard stop loss (0.8% max underlying — see signals.py)
        if pct_move <= -self.sl_pct:
            return "sl"

        if self.stop_type == "TRAILING":
            if not self.tp1_hit and pct_move >= self.tp_pct:
                return "tp1"
            if self.tp1_hit:
                peak_pct = mult * (self.peak_price - self.entry_price) / self.entry_price
                trail_trigger = peak_pct - 0.002
                if pct_move <= trail_trigger:
                    return "trailing"
        else:
            if pct_move >= self.tp_pct:
                return "tp"

        # ── Hard time stop: 45 minutes regardless ────────────────────────────
        if elapsed_min >= 45:
            return "time_45m"

        return None



    def on_tp1(self, current_price: float) -> None:
        """Execute TP1 — close 50% of position."""
        self.tp1_hit = True
        partial_close(self.symbol, self.direction, 0.5, self.coin_size)
        logger.info(f"TP1 hit {self.symbol} @ {current_price:.4f}")

    def on_close(self, exit_reason: str, current_price: float) -> None:
        """Execute full close and record to DB."""
        if self.closed:
            return
        self.closed = True

        res = close_position(self.symbol, self.direction, self.coin_size)
        
        # Check actual fill from user history first to ensure perfect PnL sync
        time.sleep(0.5)  # small delay to let transaction settle on-chain
        fill = get_actual_close_fill(self.symbol)
        if fill:
            exit_price = fill["price"]
            pnl_usd = fill["pnl"]
            pnl_pct = pnl_usd / self.size_usd
            logger.info(f"Synced exit price/PnL from Hyperliquid fills: {exit_price} | PnL: ${pnl_usd:+.2f}")
        else:
            exit_price = current_price
            if res and isinstance(res, dict) and res.get("status") == "ok":
                response_data = res.get("response", {})
                if isinstance(response_data, dict):
                    statuses = response_data.get("data", {}).get("statuses", [])
                    if statuses and isinstance(statuses[0], dict) and "filled" in statuses[0]:
                        filled_data = statuses[0]["filled"]
                        if "avgPx" in filled_data:
                            exit_price = float(filled_data["avgPx"])

            mult = 1 if self.direction == "long" else -1
            # HL Fees: Maker entry = 0.015%, Taker exit = 0.045%
            entry_fee = self.entry_price * self.coin_size * 0.00015
            exit_fee = exit_price * self.coin_size * 0.00045
            
            gross_pnl_usd = (exit_price - self.entry_price) * self.coin_size * mult
            pnl_usd = gross_pnl_usd - entry_fee - exit_fee
            pnl_pct = pnl_usd / self.size_usd

        db.close_trade(self.trade_id, exit_price, pnl_usd, pnl_pct, exit_reason)
        alerts.trade_closed_alert(self.symbol, pnl_usd, exit_reason)

        logger.info(
            f"CLOSED {self.symbol} | reason={exit_reason} | "
            f"pnl=${pnl_usd:+.2f} ({pnl_pct:+.2%}) @ {exit_price}"
        )
