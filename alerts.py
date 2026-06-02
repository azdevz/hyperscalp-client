"""
alerts.py — Telegram alert helper. Fire-and-forget async sends.
All alerts are optional — bot continues if Telegram not configured.
"""

import logging
import httpx
import config

logger = logging.getLogger(__name__)

TELE_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send(message: str) -> None:
    """Send a Telegram message. Non-blocking — errors are logged, not raised."""
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    try:
        url = TELE_URL.format(token=config.TELEGRAM_TOKEN)
        httpx.post(
            url,
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=5,
        )
    except Exception as exc:
        logger.warning(f"Telegram alert failed: {exc}")


def kill_switch_alert(reason: str, hours: int) -> None:
    send(f"🛑 <b>KILL SWITCH</b>\n{reason}\nBot paused {hours}h.")


def milestone_alert(phase: str, capital: float) -> None:
    send(f"🏆 <b>MILESTONE REACHED</b>\nPhase: {phase}\nCapital: ${capital:,.2f}")


def trade_closed_alert(symbol: str, pnl: float, reason: str) -> None:
    emoji = "✅" if pnl > 0 else "❌"
    send(f"{emoji} <b>{symbol}</b> closed | PnL: ${pnl:+.2f} | Reason: {reason}")
