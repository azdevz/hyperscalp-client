"""
hl_bot/auto_tuner.py — Adaptive Strategy Tuner (v2: No Blocking)

Runs every 30 minutes via APScheduler.
Analyzes the last 50 closed trades and writes tuning parameters to bot_state.

v2 Changes:
  - NEVER blocks symbols or directions (was causing death spiral)
  - Only adjusts position sizing multipliers
  - Removed streak cooldown (drawdown kill switch handles this)
  - Still logs reports for dashboard visibility

Tuning parameters:
  - tuner_sym_{SYM}_min_score    → "2"/"3" — raise entry threshold
  - tuner_sym_{SYM}_size_mult    → "0.5"/"0.75"/"1.0"/"1.25" — position sizing
  - tuner_last_run               → ISO timestamp
  - tuner_last_report            → JSON summary of decisions
"""
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import db

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
MIN_TRADES_FOR_DECISION = 5      # Need at least 5 trades to make a call
POOR_WIN_RATE = 0.25             # Reduce sizing if win rate < 25%
RESTRICT_WIN_RATE = 0.35         # Raise min_score if win rate < 35%
BOOST_WIN_RATE = 0.55            # Increase sizing if win rate > 55%


def run_auto_tuner() -> None:
    """Analyze last 50 trades and set tuning parameters (sizing only, no blocking)."""
    try:
        trades = db.get_trades(source="hyperliquid", limit=50)
        
        # Filter trades by reset time if available
        reset_time_str = db.get_bot_state("tuner_reset_time")
        if reset_time_str:
            try:
                reset_time = datetime.fromisoformat(reset_time_str)
                trades = [t for t in trades if t.get("closed_at") and t["closed_at"] > reset_time]
            except Exception as e:
                logger.warning(f"Failed to parse tuner_reset_time: {e}")

        if len(trades) < MIN_TRADES_FOR_DECISION:
            logger.info(f"Auto-tuner: only {len(trades)} valid trades, need {MIN_TRADES_FOR_DECISION}. Skipping.")
            return

        report = {"timestamp": datetime.now(timezone.utc).isoformat(), "decisions": []}

        # ── 1. Per-Symbol Analysis (sizing only, NO blocking) ─────────────────
        symbols = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0.0, "trades": []})
        for t in trades:
            sym = t["symbol"]
            pnl = float(t["pnl_usd"] or 0)
            bucket = "wins" if pnl > 0 else "losses"
            symbols[sym][bucket] += 1
            symbols[sym]["pnl"] += pnl
            symbols[sym]["trades"].append(t)

        for sym, data in symbols.items():
            w, l = data["wins"], data["losses"]
            total = w + l
            wr = w / total if total > 0 else 0

            if total >= MIN_TRADES_FOR_DECISION and wr < POOR_WIN_RATE:
                # Poor performance → reduce size, raise score threshold
                db.set_bot_state(f"tuner_sym_{sym}_min_score", "3")
                db.set_bot_state(f"tuner_sym_{sym}_size_mult", "0.5")
                decision = f"REDUCED {sym}: {wr:.0%} WR on {total} trades, PnL ${data['pnl']:.2f} → size×0.5, score=3"
                report["decisions"].append(decision)
                logger.warning(f"Auto-tuner: {decision}")

            elif total >= MIN_TRADES_FOR_DECISION and wr < RESTRICT_WIN_RATE:
                # Below average → smaller size, higher score
                db.set_bot_state(f"tuner_sym_{sym}_min_score", "3")
                db.set_bot_state(f"tuner_sym_{sym}_size_mult", "0.75")
                decision = f"CAUTIOUS {sym}: {wr:.0%} WR on {total} trades → score=3, size×0.75"
                report["decisions"].append(decision)
                logger.info(f"Auto-tuner: {decision}")

            elif total >= MIN_TRADES_FOR_DECISION and wr >= BOOST_WIN_RATE:
                # Strong performance → boost sizing
                db.set_bot_state(f"tuner_sym_{sym}_min_score", "2")
                db.set_bot_state(f"tuner_sym_{sym}_size_mult", "1.25")
                decision = f"BOOSTED {sym}: {wr:.0%} WR on {total} trades → size×1.25"
                report["decisions"].append(decision)
                logger.info(f"Auto-tuner: {decision}")

            else:
                # Normal — reset to defaults
                db.set_bot_state(f"tuner_sym_{sym}_min_score", "2")
                db.set_bot_state(f"tuner_sym_{sym}_size_mult", "1.0")
                decision = f"NORMAL {sym}: {wr:.0%} WR on {total} trades"
                report["decisions"].append(decision)

        # ── 2. Exit Reason Analysis (informational only) ──────────────────────
        reasons = defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0})
        for t in trades:
            r = t.get("exit_reason", "unknown")
            reasons[r]["count"] += 1
            pnl = float(t["pnl_usd"] or 0)
            reasons[r]["pnl"] += pnl
            if pnl > 0:
                reasons[r]["wins"] += 1

        for r, data in reasons.items():
            wr = data["wins"] / data["count"] if data["count"] > 0 else 0
            report["decisions"].append(
                f"EXIT '{r}': {data['count']} trades, WR={wr:.0%}, PnL=${data['pnl']:.2f}"
            )

        # ── 3. Save report ────────────────────────────────────────────────────
        db.set_bot_state("tuner_last_run", datetime.now(timezone.utc).isoformat())
        db.set_bot_state("tuner_last_report", json.dumps(report, default=str))

        # Log to error_logs for dashboard visibility
        try:
            summary_lines = [d for d in report["decisions"] if any(k in d for k in ["REDUCED", "CAUTIOUS", "BOOSTED"])]
            if summary_lines:
                db.log_error("auto_tuner", " | ".join(summary_lines))
        except Exception:
            pass

        logger.info(f"Auto-tuner completed: {len(report['decisions'])} decisions on {len(trades)} trades.")

    except Exception as exc:
        logger.error(f"Auto-tuner failed: {exc}", exc_info=True)


if __name__ == "__main__":
    db.init_pool()
    run_auto_tuner()
