"""
meme_bot/execution.py — Jupiter v6 API swap execution for Solana meme tokens.

Uses Jupiter Aggregator REST API v6 directly (most reliable, best routing).
Handles:
  - Quote → price impact check → swap
  - Liquidity-based position sizing (brain.md §13.4)
  - Active position monitoring (TP/SL/trailing/time/liquidity stop)
  - Blacklist management (4h after SL)
"""

import base64
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

import config
import db
import alerts
from meme_bot import birdeye

logger = logging.getLogger(__name__)

JUPITER_URL = "https://quote-api.jup.ag/v6"
SOL_MINT    = "So11111111111111111111111111111111111111112"
USDC_MINT   = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# ── Token blacklist (contract → unblacklist_at UTC) ───────────────────────────
_blacklist: dict[str, datetime] = {}


def is_blacklisted(contract: str) -> bool:
    if contract in _blacklist:
        if datetime.now(timezone.utc) < _blacklist[contract]:
            return True
        else:
            del _blacklist[contract]
    return False


def blacklist(contract: str) -> None:
    _blacklist[contract] = datetime.now(timezone.utc) + timedelta(hours=config.MEME_BLACKLIST_H)
    logger.info(f"Blacklisted {contract[:8]}… for {config.MEME_BLACKLIST_H}h")


# ── Jupiter API ───────────────────────────────────────────────────────────────

def get_jupiter_quote(
    input_mint:  str,
    output_mint: str,
    amount_usd:  float,
    price:       float,
) -> Optional[dict]:
    """Get Jupiter quote. Returns quote dict with priceImpactPct."""
    if price <= 0:
        return None
    # Amount in USDC lamports (6 decimals)
    amount_lamports = int(amount_usd * 1_000_000)
    try:
        resp = httpx.get(
            f"{JUPITER_URL}/quote",
            params={
                "inputMint":            USDC_MINT,
                "outputMint":           output_mint,
                "amount":               amount_lamports,
                "slippageBps":          int(config.MEME_MIN_SLIPPAGE * 10_000),
                "onlyDirectRoutes":     False,
                "asLegacyTransaction":  False,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning(f"Jupiter quote failed: {exc}")
        return None


def execute_swap(quote: dict, wallet_key: str) -> Optional[str]:
    """
    Execute a Jupiter swap.
    Returns transaction signature or None on failure.
    Note: Requires solders for transaction signing.
    """
    try:
        from solders.keypair import Keypair  # type: ignore
        from solders.transaction import VersionedTransaction  # type: ignore
        import base58

        # Get swap transaction from Jupiter
        resp = httpx.post(
            f"{JUPITER_URL}/swap",
            json={
                "quoteResponse":               quote,
                "userPublicKey":               str(Keypair.from_base58_string(wallet_key).pubkey()),
                "wrapAndUnwrapSol":            True,
                "dynamicComputeUnitLimit":     True,
                "prioritizationFeeLamports":   "auto",
            },
            timeout=15,
        )
        resp.raise_for_status()
        swap_data = resp.json()
        tx_bytes  = base64.b64decode(swap_data["swapTransaction"])

        # Sign and send
        keypair = Keypair.from_base58_string(wallet_key)
        tx = VersionedTransaction.from_bytes(tx_bytes)
        tx.sign([keypair])

        # Send via Solana RPC
        rpc_resp = httpx.post(
            "https://api.mainnet-beta.solana.com",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [
                    base64.b64encode(bytes(tx)).decode(),
                    {"encoding": "base64", "skipPreflight": False, "maxRetries": 3},
                ],
            },
            timeout=20,
        )
        result = rpc_resp.json()
        sig = result.get("result")
        if sig:
            logger.info(f"Swap executed: {sig}")
            return sig
        else:
            logger.error(f"Swap failed: {result.get('error')}")
            return None
    except Exception as exc:
        logger.error(f"Swap execution error: {exc}")
        return None


def calculate_meme_size(contract: str, meme_allocation: float, current_price: float) -> float:
    """
    brain.md §13.4 position sizing based on Jupiter price impact.
    """
    test_size = meme_allocation * 0.05
    quote = get_jupiter_quote(USDC_MINT, contract, test_size, current_price)

    if not quote:
        return 0.0

    price_impact = abs(float(quote.get("priceImpactPct", 1.0)))

    if price_impact <= 0.005:
        return meme_allocation * 0.05     # 5%
    elif price_impact <= 0.010:
        return meme_allocation * 0.03     # 3%
    elif price_impact <= config.MEME_MAX_IMPACT:
        return meme_allocation * 0.02     # 2%
    elif price_impact > config.MEME_SKIP_IMPACT:
        logger.info(f"Price impact {price_impact:.2%} > 3% — skipping trade")
        return 0.0
    return 0.0


# ── Active Meme Trade ─────────────────────────────────────────────────────────

class ActiveMemeTrade:
    """Tracks an open meme position lifecycle."""

    def __init__(
        self,
        trade_id:    int,
        symbol:      str,
        contract:    str,
        direction:   str,
        entry_price: float,
        size_usd:    float,
        tp_pct:      float,
        sl_pct:      float,
        max_hold_min: int,
        opened_at:   datetime,
    ):
        self.trade_id     = trade_id
        self.symbol       = symbol
        self.contract     = contract
        self.direction    = direction
        self.entry_price  = entry_price
        self.size_usd     = size_usd
        self.tp_pct       = tp_pct / 100
        self.sl_pct       = sl_pct / 100
        self.max_hold_min = max_hold_min
        self.opened_at    = opened_at
        self.peak_price   = entry_price
        self.partial_hit  = False   # partial TP at +12%
        self.closed       = False

    def check_exit(self, current_price: float, liquidity: float) -> Optional[str]:
        if self.closed:
            return None

        pct_move = (current_price - self.entry_price) / self.entry_price
        self.peak_price = max(self.peak_price, current_price)

        # Liquidity stop
        if liquidity > 0 and liquidity < config.MEME_MIN_LIQ:
            return "liquidity"

        # Hard stop loss
        if pct_move <= -self.sl_pct:
            return "sl"

        # Partial TP at +12%
        if not self.partial_hit and pct_move >= 0.12:
            return "partial_tp"

        # Trailing stop after partial TP
        if self.partial_hit:
            trail_from_peak = (self.peak_price - current_price) / self.peak_price
            if trail_from_peak >= config.MEME_TRAIL_PCT:
                return "trailing"

        # Full TP
        if pct_move >= self.tp_pct:
            return "tp"

        # Time stop
        elapsed = (datetime.now(timezone.utc) - self.opened_at).total_seconds() / 60
        if elapsed >= self.max_hold_min:
            return "time"

        return None

    def on_partial_tp(self, current_price: float) -> None:
        self.partial_hit = True
        logger.info(f"MEME PARTIAL TP {self.symbol} @ {current_price:.6f} (+12%) — close 60%")

    def on_close(self, exit_reason: str, current_price: float) -> None:
        if self.closed:
            return
        self.closed = True
        pnl_pct = (current_price - self.entry_price) / self.entry_price
        pnl_usd = pnl_pct * self.size_usd

        if exit_reason == "sl":
            blacklist(self.contract)

        db.close_trade(self.trade_id, current_price, pnl_usd, pnl_pct, exit_reason)
        alerts.trade_closed_alert(self.symbol, pnl_usd, exit_reason)

        logger.info(
            f"MEME CLOSED {self.symbol} | reason={exit_reason} | "
            f"pnl=${pnl_usd:+.2f} ({pnl_pct:+.1%})"
        )
