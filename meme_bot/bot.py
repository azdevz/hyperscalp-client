"""
meme_bot/bot.py — Solana meme bot main loop.

Called every 30 seconds by APScheduler.
Reads active pairs from DB → evaluates signals → executes swaps → monitors exits.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import config
import db
import alerts
from meme_bot import signals, execution, birdeye

logger = logging.getLogger(__name__)

# ── Active meme trade registry ────────────────────────────────────────────────
_active_trades: dict[int, execution.ActiveMemeTrade] = {}

# ── Daily meme PnL tracking ───────────────────────────────────────────────────
_meme_daily_pnl: float = 0.0
_meme_day_start: Optional[datetime] = None


def _get_meme_allocation(balance: float) -> float:
    """30% of total account balance for meme bot."""
    return balance * config.MEME_CAPITAL_PCT


def _monitor_active_trades() -> None:
    global _meme_daily_pnl
    closed_ids = []

    for trade_id, trade in _active_trades.items():
        overview = birdeye.get_token_overview(trade.contract)
        if not overview:
            continue

        current_price = float(overview.get("price", 0))
        liquidity     = float(overview.get("liquidity", 0))

        if current_price == 0:
            continue

        exit_reason = trade.check_exit(current_price, liquidity)

        if exit_reason == "partial_tp":
            trade.on_partial_tp(current_price)
            continue
        elif exit_reason:
            trade.on_close(exit_reason, current_price)
            pnl = (current_price - trade.entry_price) / trade.entry_price * trade.size_usd
            _meme_daily_pnl += pnl
            closed_ids.append(trade_id)

    for tid in closed_ids:
        _active_trades.pop(tid, None)


def _can_enter_new_trade() -> bool:
    return len(_active_trades) < 3  # max 3 meme positions


def bot_tick() -> None:
    """Called every 30 seconds by APScheduler."""
    global _meme_daily_pnl, _meme_day_start

    try:
        if not db.is_meme_active():
            return

        if not config.BIRDEYE_API_KEY:
            logger.debug("Birdeye API key not set — meme bot idle.")
            return

        # Reset daily PnL tracker at midnight UTC
        now = datetime.now(timezone.utc)
        if _meme_day_start is None or now.date() > _meme_day_start.date():
            _meme_daily_pnl = 0.0
            _meme_day_start = now

        # Daily meme drawdown kill switch
        # TODO: get meme_allocation dynamically
        meme_alloc_approx = 30.0  # approximate — real value requires balance fetch
        if meme_alloc_approx > 0 and _meme_daily_pnl / meme_alloc_approx <= -config.MEME_DAILY_KILL:
            pause_until = now + timedelta(hours=24)
            db.set_bot_state("meme_paused_until", pause_until.isoformat())
            alerts.kill_switch_alert("Meme bot daily drawdown -15%", 24)
            logger.warning("Meme daily kill switch triggered — pausing 24h.")
            return

        # Monitor existing positions
        _monitor_active_trades()

        if not _can_enter_new_trade():
            return

        # Load active pairs
        pairs = db.get_pairs(active_only=True)
        if not pairs:
            logger.debug("No active meme pairs.")
            return

        for pair in pairs:
            if not _can_enter_new_trade():
                break

            contract = pair.get("contract", "")
            if not contract:
                continue

            # Skip if already have position in this token
            if any(t.contract == contract for t in _active_trades.values()):
                continue

            # Blacklist check
            if execution.is_blacklisted(contract):
                logger.debug(f"{pair['symbol']}: blacklisted, skipping.")
                continue

            # Evaluate entry signals
            sig = signals.compute_meme_signals(pair)

            if not sig.entry_allowed:
                logger.debug(f"{pair['symbol']}: no signal ({sig.reason})")
                continue

            # Liquidity depth + position sizing
            meme_alloc = 30.0  # USD (TODO: from real balance)
            size_usd = execution.calculate_meme_size(contract, meme_alloc, sig.current_price)

            if size_usd <= 0:
                logger.info(f"{pair['symbol']}: too illiquid, skipping.")
                continue

            # Execute swap
            quote = execution.get_jupiter_quote(
                execution.USDC_MINT, contract, size_usd, sig.current_price
            )
            if not quote:
                continue

            # Real execution only if Solana key is set
            if config.SOL_PRIVATE_KEY:
                sig_hash = execution.execute_swap(quote, config.SOL_PRIVATE_KEY)
                if not sig_hash:
                    continue
            else:
                logger.info(f"[PAPER] Would swap ${size_usd:.2f} USDC → {pair['symbol']}")

            # Record trade
            opened_at = datetime.now(timezone.utc)
            trade_id = db.insert_trade(
                source="meme",
                symbol=pair["symbol"],
                direction="buy",
                entry_price=sig.current_price,
                size_usd=size_usd,
                opened_at=opened_at,
            )

            active = execution.ActiveMemeTrade(
                trade_id=trade_id,
                symbol=pair["symbol"],
                contract=contract,
                direction="buy",
                entry_price=sig.current_price,
                size_usd=size_usd,
                tp_pct=float(pair.get("custom_tp_pct", 20)),
                sl_pct=float(pair.get("custom_sl_pct", 8)),
                max_hold_min=int(pair.get("max_hold_min", 20)),
                opened_at=opened_at,
            )
            _active_trades[trade_id] = active

            logger.info(
                f"MEME ENTERED {pair['symbol']} @ {sig.current_price:.6f} | "
                f"${size_usd:.2f} | TP={pair.get('custom_tp_pct')}% SL={pair.get('custom_sl_pct')}%"
            )

    except Exception as exc:
        logger.error(f"Meme bot_tick error: {exc}", exc_info=True)
