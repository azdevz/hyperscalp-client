"""
hl_bot/bot.py — Main Hyperliquid perps scalping loop.

Called every 1 second by APScheduler.
Sequence per tick:
  1. Check kill switches (DB + drawdown)
  2. Monitor & exit any active trades
  3. If capacity for new trade: run signal engine
  4. If signal ≥3/6: run risk engine → size → enter
  5. Log signals to DB
  6. Check milestones
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import config
import db
import alerts
from hl_bot import signals, risk, execution

logger = logging.getLogger(__name__)

# ── In-memory active trade registry ──────────────────────────────────────────
# Maps trade_id → ActiveTrade object
_active_trades: dict[int, execution.ActiveTrade] = {}
_last_sync_time = 0

# ── Streak tracking ───────────────────────────────────────────────────────────
_recent_pnls: list[float] = []  # last 20 PnLs (usd), most-recent last


def _check_milestones(balance: float) -> None:
    """Log milestone if new phase reached."""
    for ms in config.MILESTONES:
        if ms["min"] <= balance < ms["max"]:
            phase = ms["phase"]
            existing = db.get_milestones()
            if not existing or existing[0].get("phase") != phase:
                db.log_milestone(phase, balance)
                alerts.milestone_alert(phase, balance)
            break


def _sync_active_trades() -> None:
    """Synchronize in-memory trades with Hyperliquid open positions to handle bot restarts."""
    global _last_sync_time
    now = time.time()
    if now - _last_sync_time < 30:  # Sync every 30 seconds
        return
    _last_sync_time = now

    try:
        open_positions = execution.get_open_positions()
        hl_symbols = {pos["symbol"] for pos in open_positions}

        # Fetch DB open trades FIRST
        db_open_trades = db.get_open_trades("hyperliquid")
        db_open_by_symbol = {t["symbol"]: t for t in db_open_trades}

        # 1. Adopt orphaned HL positions
        for pos in open_positions:
            symbol = pos["symbol"]
            if not any(t.symbol == symbol for t in _active_trades.values()):
                if symbol in db_open_by_symbol:
                    logger.info(f"Restoring trade for {symbol} from DB.")
                    db_trade = db_open_by_symbol[symbol]
                    trade_id = db_trade["id"]
                    entry_price = float(db_trade["entry_price"])
                    size_usd = float(db_trade["size_usd"])
                    opened_at = db_trade["opened_at"]
                else:
                    logger.info(f"Orphaned position found for {symbol}, adopting it.")
                    trade_id = db.insert_trade(
                        source="hyperliquid",
                        symbol=symbol,
                        direction=pos["direction"],
                        entry_price=pos["entry_price"],
                        size_usd=pos["size"] * pos["entry_price"],
                        opened_at=datetime.now(timezone.utc),
                    )
                    entry_price = pos["entry_price"]
                    size_usd = pos["size"] * pos["entry_price"]
                    opened_at = datetime.now(timezone.utc)

                active = execution.ActiveTrade(
                    trade_id=trade_id,
                    symbol=symbol,
                    direction=pos["direction"],
                    entry_price=entry_price,
                    size_usd=size_usd,
                    coin_size=pos["size"],
                    opened_at=opened_at,
                    sl_pct=0.10,  # Safety default
                    tp_pct=0.10,  # Safety default
                    stop_type="TRAILING",
                )
                _active_trades[trade_id] = active
            else:
                # Update exact entry price for existing trades
                for trade in _active_trades.values():
                    if trade.symbol == symbol:
                        # Update exact entry price from HL
                        if abs(trade.entry_price - pos["entry_price"]) > 1e-6:
                            logger.info(f"Sync exact entry price {symbol}: {trade.entry_price} -> {pos['entry_price']}")
                            trade.entry_price = pos["entry_price"]
                            db.execute("UPDATE trades SET entry_price = %s WHERE id = %s", (pos["entry_price"], trade.trade_id))

        # 2. Close trades in DB that are not on HL
        for db_trade in db_open_trades:
            if db_trade["symbol"] not in hl_symbols:
                sym = db_trade["symbol"]
                logger.info(f"Trade {db_trade['id']} for {sym} not found on HL, sync-closing in DB.")
                
                # Fetch actual close fill from user history
                fill = execution.get_actual_close_fill(sym)
                if fill:
                    exit_price = fill["price"]
                    pnl_usd = fill["pnl"]
                    pnl_pct = pnl_usd / float(db_trade["size_usd"])
                    exit_reason = "manual_exit"
                    logger.info(f"Synced exit price/PnL for orphaned trade {sym}: {exit_price} | PnL: ${pnl_usd:+.2f}")
                else:
                    exit_price = float(db_trade["entry_price"])
                    pnl_usd = 0.0
                    pnl_pct = 0.0
                    exit_reason = "sync_closed"
                
                db.close_trade(
                    trade_id=db_trade["id"],
                    exit_price=exit_price,
                    pnl_usd=pnl_usd,
                    pnl_pct=pnl_pct,
                    exit_reason=exit_reason
                )
                _active_trades.pop(db_trade["id"], None)
    except Exception as exc:
        logger.error(f"Sync active trades failed: {exc}")


def _monitor_active_trades() -> None:
    """Check all active trades for exit conditions."""
    closed_ids = []
    for trade_id, trade in _active_trades.items():
        current_price = execution.get_mid_price(trade.symbol)
        if current_price == 0:
            continue

        exit_reason = trade.check_exit(current_price)
        if exit_reason == "tp1":
            trade.on_tp1(current_price)
            continue
        elif exit_reason:
            trade.on_close(exit_reason, current_price)
            closed_ids.append(trade_id)
            # Update streak
            pnl = (1 if trade.direction == "long" else -1) * \
                  (current_price - trade.entry_price) / trade.entry_price * trade.size_usd
            _recent_pnls.append(pnl)
            if len(_recent_pnls) > 20:
                _recent_pnls.pop(0)

    for tid in closed_ids:
        _active_trades.pop(tid, None)


def _can_enter_new_trade() -> bool:
    """Check capacity and cooldown for a new trade."""
    if len(_active_trades) >= config.MAX_OPEN_POSITIONS:
        return False

    # Check cooldown period after last closed trade
    try:
        trades = db.get_trades(source="hyperliquid", limit=1)
        if trades:
            last_closed = trades[0]["closed_at"]
            if last_closed:
                elapsed = (datetime.now(timezone.utc) - last_closed).total_seconds() / 60
                if elapsed < config.TRADE_COOLDOWN_MINUTES:
                    logger.debug(f"In cooldown period ({config.TRADE_COOLDOWN_MINUTES}m). {config.TRADE_COOLDOWN_MINUTES - elapsed:.1f}m remaining.")
                    return False
    except Exception as exc:
        logger.error(f"Cooldown check failed: {exc}")

    return True


def _enter_trade(symbol: str, sig: dict, decision: risk.RiskDecision, balance: float) -> None:
    """Place order and register active trade from JSON signal."""
    current_price = execution.get_mid_price(symbol)
    if current_price == 0:
        logger.warning(f"No price for {symbol}, skipping entry.")
        return

    milestone_max = risk.get_milestone_max(balance)
    
    # sig["stop_loss"] is absolute price. We need pct for sizing.
    sl_px = float(sig["stop_loss"])
    direction = "long" if sig["action"] == "EXECUTE_LONG" else "short"
    stop_pct = abs(current_price - sl_px) / current_price
    
    size_usd = risk.compute_position_size(
        account_balance=balance,
        risk_pct=decision.risk_pct,
        entry_price=current_price,
        stop_pct=stop_pct,
        milestone_max=milestone_max,
    )

    if size_usd < 1:
        logger.warning(f"Size too small (${size_usd:.2f}), skipping.")
        return

    order_result = execution.place_limit_order(
        symbol    = symbol,
        direction = direction,
        size_usd  = size_usd,
        price     = current_price,
        leverage  = decision.leverage,
        execution_type = sig["execution_type"]
    )

    if not order_result or order_result.get("status") == "err":
        msg = f"Order failed for {symbol}: {order_result}"
        logger.error(msg)
        return

    response_data = order_result.get("response", {})
    if isinstance(response_data, dict):
        status = response_data.get("data", {}).get("statuses", [{}])
        if not status or "error" in str(status[0]).lower():
            msg = f"Order not filled {symbol}: {status}"
            logger.error(msg)
            return

    coin_size = round(size_usd / current_price, 6)
    opened_at = datetime.now(timezone.utc)
    trade_id = db.insert_trade(
        source="hyperliquid",
        symbol=symbol,
        direction=direction,
        entry_price=current_price,
        size_usd=size_usd,
        opened_at=opened_at,
    )

    tp_pct = abs(float(sig["take_profit"]) - current_price) / current_price

    active = execution.ActiveTrade(
        trade_id=trade_id,
        symbol=symbol,
        direction=direction,
        entry_price=current_price,
        size_usd=size_usd,
        coin_size=coin_size,
        opened_at=opened_at,
        sl_pct=stop_pct,
        tp_pct=tp_pct,
        stop_type="TRAILING",
    )
    _active_trades[trade_id] = active
    logger.info(
        f"ENTERED {symbol} {direction.upper()} @ {current_price:.4f} | "
        f"${size_usd:.2f} | {decision.leverage}x | strat={sig['reasoning_code']}"
    )


# ── Main bot tick ─────────────────────────────────────────────────────────────

def bot_tick() -> None:
    """Called every 1 second by APScheduler."""
    try:
        # 1. Kill switches
        if not db.is_hl_active():
            return

        # 2. Strategy market gate — only trade perps if strategy allows it
        strategy = db.get_active_strategy()
        if not strategy.get("apply_perp", True):
            logger.debug("HL Perp trading disabled by active strategy.")
            return

        _sync_active_trades()

        balance = execution.get_account_balance()
        if balance <= 0:
            logger.warning("Balance is 0 or unavailable. Skipping tick.")
            return

        daily_pnl_pct  = db.get_daily_pnl_pct(balance)
        weekly_pnl_pct = db.get_weekly_pnl_pct(balance)

        # Drawdown kill switch enforcement
        if daily_pnl_pct <= -config.DAILY_DRAWDOWN_KILL:
            from datetime import timedelta
            pause_until = datetime.now(timezone.utc) + timedelta(hours=24)
            db.set_bot_state("hl_paused_until", pause_until.isoformat())
            db.set_bot_state("hl_bot_active", "true")
            alerts.kill_switch_alert(f"Daily drawdown {daily_pnl_pct:.1%}", 24)
            logger.warning("Daily drawdown kill switch triggered — pausing 24h.")
            return

        if weekly_pnl_pct <= -config.WEEKLY_DRAWDOWN_KILL:
            from datetime import timedelta
            pause_until = datetime.now(timezone.utc) + timedelta(hours=72)
            db.set_bot_state("hl_paused_until", pause_until.isoformat())
            alerts.kill_switch_alert(f"Weekly drawdown {weekly_pnl_pct:.1%}", 72)
            logger.warning("Weekly drawdown kill switch triggered — pausing 72h.")
            return

        # 2. Monitor existing trades
        _monitor_active_trades()

        # 3. Try entering new trades
        if not _can_enter_new_trade():
            return


        for symbol in config.HL_PRIMARY_PAIRS + config.HL_SECONDARY_PAIRS:
            if not _can_enter_new_trade():
                break

            # Skip if already have position in this symbol
            if any(t.symbol == symbol for t in _active_trades.values()):
                continue

            # Compute signals (JSON String)
            import json
            sig_str = signals.compute_signals(symbol)
            try:
                sig = json.loads(sig_str)
            except Exception:
                continue

            # Log signal ALWAYS so UI stays alive
            db.log_signal({
                "source":       "hyperliquid",
                "symbol":       symbol,
                "rsi_1m":       sig.get("cvd_bullish", 0), # Mapped for UI
                "rsi_5m":       sig.get("cvd_bearish", 0), # Mapped for UI
                "macd":         0,
                "adx":          sig.get("oi_spike", 0),    # Mapped for UI
                "vol_ratio":    sig.get("obi_bullish", 0), # Mapped for UI
                "bb_signal":    False,
                "ob_ratio":     sig.get("obi_bearish", 0), # Mapped for UI
                "signal_count": sig.get("score", 0),
                "direction":    sig.get("action", "").replace("EXECUTE_", "").replace("NO_TRADE", "none").lower(),
                "signal_hit":   sig.get("action") != "NO_TRADE",
            })

            if sig.get("action") == "NO_TRADE":
                continue

            # Run risk engine
            open_count = len(_active_trades)
            decision = risk.compute_risk(
                symbol=symbol,
                leverage_request=sig.get("leverage", 5),
                daily_pnl_pct=daily_pnl_pct,
                weekly_pnl_pct=weekly_pnl_pct,
                open_positions_count=open_count,
            )

            if decision.trade_allowed:
                _enter_trade(symbol, sig, decision, balance)

        # 4. Milestone check
        _check_milestones(balance)

    except Exception as exc:
        logger.error(f"HL bot_tick error: {exc}", exc_info=True)
