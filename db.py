"""
db.py — PostgreSQL connection pool and all DB helper functions.
Uses psycopg2 connection pool. Thread-safe for APScheduler workers.
"""

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor

import config

logger = logging.getLogger(__name__)

# ── Connection pool (initialised at startup) ──────────────────────────────────
_pool: Optional[pg_pool.ThreadedConnectionPool] = None


def init_pool() -> None:
    """Call once at startup (main.py)."""
    global _pool
    _pool = pg_pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=config.DATABASE_URL,
        cursor_factory=RealDictCursor,
    )
    logger.info("DB pool initialised (min=1 max=10).")


@contextmanager
def get_conn():
    """Context manager — gets a connection from pool, returns it after use."""
    global _pool
    if _pool is None:
        raise RuntimeError("DB pool not initialised — call init_pool() first.")
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def execute(sql: str, params: tuple = ()) -> list[dict]:
    """Run any SQL, return list of dicts (empty for non-SELECT)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description:
                return [dict(r) for r in cur.fetchall()]
            return []


# ── bot_state helpers ─────────────────────────────────────────────────────────

def get_bot_state(key: str) -> Optional[str]:
    rows = execute("SELECT value FROM bot_state WHERE key = %s", (key,))
    return rows[0]["value"] if rows else None


def set_bot_state(key: str, value: str) -> None:
    execute(
        "INSERT INTO bot_state (key, value) VALUES (%s, %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        (key, value),
    )


def is_emergency_stopped() -> bool:
    return get_bot_state("emergency_stop") == "true"


def is_hl_active() -> bool:
    if is_emergency_stopped():
        return False
    v = get_bot_state("hl_bot_active")
    if v != "true":
        return False
    until = get_bot_state("hl_paused_until") or ""
    if until:
        try:
            pause_until = datetime.fromisoformat(until)
            if datetime.now(timezone.utc) < pause_until:
                return False
            else:
                set_bot_state("hl_paused_until", "")
        except ValueError:
            pass
    return True


def is_meme_active() -> bool:
    if is_emergency_stopped():
        return False
    v = get_bot_state("meme_bot_active")
    if v != "true":
        return False
    until = get_bot_state("meme_paused_until") or ""
    if until:
        try:
            pause_until = datetime.fromisoformat(until)
            if datetime.now(timezone.utc) < pause_until:
                return False
            else:
                set_bot_state("meme_paused_until", "")
        except ValueError:
            pass
    return True


def get_active_strategy() -> dict:
    """Returns the full active strategy row as a dict."""
    rows = execute("SELECT * FROM strategies WHERE is_active = true LIMIT 1")
    if rows:
        return dict(rows[0])
    return {"id": 0, "name": "Unknown", "description": "", "apply_perp": True, "apply_spot": False, "apply_meme": False}


def get_all_strategies() -> list[dict]:
    return execute("SELECT * FROM strategies ORDER BY created_at ASC")


def update_strategy_markets(strategy_id: int, apply_perp: bool, apply_spot: bool, apply_meme: bool) -> None:
    execute(
        "UPDATE strategies SET apply_perp=%s, apply_spot=%s, apply_meme=%s WHERE id=%s",
        (apply_perp, apply_spot, apply_meme, strategy_id),
    )


# ── Trade helpers ─────────────────────────────────────────────────────────────

def insert_trade(
    source: str,
    symbol: str,
    direction: str,
    entry_price: float,
    size_usd: float,
    opened_at: Optional[datetime] = None,
) -> int:
    """Insert an open trade (no exit yet). Returns trade ID."""
    regime = get_bot_state("hl_network_regime") or "demo"
    coin_size = size_usd / entry_price if entry_price > 0 else 0.0
    rows = execute(
        """
        INSERT INTO trades (exchange, symbol, direction, entry_price, size_usd, coin_size, network, opened_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (source, symbol, direction, entry_price, size_usd, coin_size, regime,
         opened_at or datetime.now(timezone.utc)),
    )
    return rows[0]["id"]


def close_trade(
    trade_id: int,
    exit_price: float,
    pnl_usd: float,
    pnl_pct: float,
    exit_reason: str,
) -> None:
    execute(
        """
        UPDATE trades
        SET exit_price = %s,
            pnl_usd    = %s,
            pnl_pct    = %s,
            exit_reason = %s,
            closed_at  = %s
        WHERE id = %s
        """,
        (exit_price, pnl_usd, pnl_pct, exit_reason,
         datetime.now(timezone.utc), trade_id),
    )


def get_trades(
    source: Optional[str] = None,
    symbol: Optional[str] = None,
    exit_reason: Optional[str] = None,
    network: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    if not network:
        network = get_bot_state("hl_network_regime") or "demo"
    wheres = ["closed_at IS NOT NULL", "network = %s"]
    params: list[Any] = [network]
    if source:
        wheres.append("exchange = %s"); params.append(source)
    if symbol:
        wheres.append("symbol ILIKE %s"); params.append(f"%{symbol}%")
    if exit_reason:
        wheres.append("exit_reason = %s"); params.append(exit_reason)
    params += [limit, offset]
    sql = (
        "SELECT id, symbol, direction, network, exchange AS source, entry_price, exit_price, size_usd, coin_size, pnl_usd, pnl_pct, status, exit_reason, opened_at, closed_at FROM trades WHERE " + " AND ".join(wheres)
        + " ORDER BY closed_at DESC LIMIT %s OFFSET %s"
    )
    return execute(sql, tuple(params))


def get_open_trades(source: Optional[str] = None) -> list[dict]:
    regime = get_bot_state("hl_network_regime") or "demo"
    if source:
        return execute(
            "SELECT id, symbol, direction, network, exchange AS source, entry_price, exit_price, size_usd, coin_size, pnl_usd, pnl_pct, status, exit_reason, opened_at, closed_at FROM trades WHERE closed_at IS NULL AND exchange = %s AND network = %s ORDER BY opened_at",
            (source, regime),
        )
    return execute(
        "SELECT id, symbol, direction, network, exchange AS source, entry_price, exit_price, size_usd, coin_size, pnl_usd, pnl_pct, status, exit_reason, opened_at, closed_at FROM trades WHERE closed_at IS NULL AND network = %s ORDER BY opened_at",
        (regime,)
    )


def get_pnl_summary(network: Optional[str] = None) -> dict:
    if not network:
        network = get_bot_state("hl_network_regime") or "demo"
    rows = execute(
        """
        SELECT
            exchange                                           AS source,
            COUNT(*) FILTER (WHERE pnl_usd > 0)               AS wins,
            COUNT(*) FILTER (WHERE pnl_usd <= 0)              AS losses,
            COUNT(*)                                           AS total,
            COALESCE(SUM(pnl_usd), 0)                         AS total_pnl,
            COALESCE(AVG(pnl_pct), 0)                         AS avg_pnl_pct,
            COALESCE(SUM(pnl_usd) FILTER (WHERE pnl_usd > 0), 0) AS gross_profit,
            COALESCE(ABS(SUM(pnl_usd) FILTER (WHERE pnl_usd <= 0)), 0) AS gross_loss
        FROM trades
        WHERE closed_at IS NOT NULL AND network = %s
        GROUP BY exchange
        """,
        (network,)
    )
    summary: dict[str, Any] = {}
    for row in rows:
        src = row["source"]
        gp = float(row["gross_profit"] or 0)
        gl = float(row["gross_loss"] or 0)
        total = int(row["total"] or 0)
        wins  = int(row["wins"] or 0)
        summary[src] = {
            "wins": wins,
            "losses": int(row["losses"] or 0),
            "total": total,
            "win_rate": round(wins / total * 100, 1) if total else 0,
            "total_pnl": round(float(row["total_pnl"] or 0), 4),
            "avg_pnl_pct": round(float(row["avg_pnl_pct"] or 0), 4),
            "profit_factor": round(gp / gl, 3) if gl > 0 else float("inf"),
        }
    return summary


def get_daily_report_stats(network: Optional[str] = None) -> dict:
    """Returns today's PnL, trades count, and all-time total PnL."""
    if not network:
        network = get_bot_state("hl_network_regime") or "demo"
    rows = execute(
        """
        SELECT 
            COUNT(*) as daily_trades_count,
            COALESCE(SUM(pnl_usd), 0) as daily_pnl
        FROM trades
        WHERE closed_at >= (NOW() AT TIME ZONE 'UTC')::DATE
          AND closed_at IS NOT NULL
          AND network = %s
        """,
        (network,)
    )
    daily_trades_count = int(rows[0]["daily_trades_count"]) if rows else 0
    daily_pnl = float(rows[0]["daily_pnl"]) if rows else 0.0

    total_rows = execute(
        """
        SELECT COALESCE(SUM(pnl_usd), 0) as total_pnl
        FROM trades
        WHERE closed_at IS NOT NULL
          AND network = %s
        """,
        (network,)
    )
    total_pnl = float(total_rows[0]["total_pnl"]) if total_rows else 0.0
    
    return {
        "daily_trades_count": daily_trades_count,
        "daily_pnl": daily_pnl,
        "total_pnl": total_pnl
    }


def get_daily_pnl_pct(account_balance: float) -> float:
    """Returns today's PnL as % of account balance (for drawdown kill switch)."""
    regime = get_bot_state("hl_network_regime") or "demo"
    rows = execute(
        """
        SELECT COALESCE(SUM(pnl_usd), 0) AS daily_pnl
        FROM trades
        WHERE closed_at >= (NOW() AT TIME ZONE 'UTC')::DATE
          AND closed_at IS NOT NULL
          AND network = %s
        """,
        (regime,)
    )
    daily_usd = float(rows[0]["daily_pnl"]) if rows else 0.0
    return daily_usd / account_balance if account_balance > 0 else 0.0


def get_weekly_pnl_pct(account_balance: float) -> float:
    regime = get_bot_state("hl_network_regime") or "demo"
    rows = execute(
        """
        SELECT COALESCE(SUM(pnl_usd), 0) AS weekly_pnl
        FROM trades
        WHERE closed_at >= NOW() - INTERVAL '7 days'
          AND closed_at IS NOT NULL
          AND network = %s
        """,
        (regime,)
    )
    weekly_usd = float(rows[0]["weekly_pnl"]) if rows else 0.0
    return weekly_usd / account_balance if account_balance > 0 else 0.0


# ── Pairs helpers ─────────────────────────────────────────────────────────────

def get_pairs(active_only: bool = True) -> list[dict]:
    if active_only:
        return execute("SELECT * FROM pairs WHERE active = true ORDER BY added_at")
    return execute("SELECT * FROM pairs ORDER BY added_at DESC")


def upsert_pair(data: dict) -> dict:
    """Insert new pair or update existing by symbol+source."""
    rows = execute(
        """
        INSERT INTO pairs
          (source, symbol, contract, pool, active, custom_tp_pct, custom_sl_pct, max_hold_min, note)
        VALUES
          (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        RETURNING *
        """,
        (
            data.get("source", "meme"),
            data["symbol"],
            data.get("contract"),
            data.get("pool"),
            data.get("active", True),
            data.get("custom_tp_pct", 20),
            data.get("custom_sl_pct", 8),
            data.get("max_hold_min", 20),
            data.get("note", ""),
        ),
    )
    return rows[0] if rows else {}


def set_pair_active(pair_id: int, active: bool) -> None:
    execute("UPDATE pairs SET active = %s WHERE id = %s", (active, pair_id))


# ── Signal log helpers ────────────────────────────────────────────────────────

def log_signal(data: dict) -> None:
    execute(
        """
        INSERT INTO signals_log
          (source, symbol, rsi_1m, rsi_5m, macd, adx, vol_ratio, bb_signal,
           ob_ratio, signal_count, direction, signal_hit)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            data.get("source"), data.get("symbol"),
            data.get("rsi_1m"), data.get("rsi_5m"),
            data.get("macd"), data.get("adx"),
            data.get("vol_ratio"), data.get("bb_signal"),
            data.get("ob_ratio"), data.get("signal_count"),
            data.get("direction"), data.get("signal_hit", False),
        ),
    )


def get_signals(limit: int = 50) -> list[dict]:
    return execute(
        "SELECT * FROM signals_log ORDER BY logged_at DESC LIMIT %s", (limit,)
    )


# ── Milestone helpers ─────────────────────────────────────────────────────────

def log_milestone(phase: str, capital_usd: float) -> None:
    execute(
        "INSERT INTO milestones (phase, capital_usd) VALUES (%s, %s)",
        (phase, capital_usd),
    )


def get_milestones() -> list[dict]:
    return execute("SELECT * FROM milestones ORDER BY reached_at DESC")


def get_cumulative_pnl_series(network: Optional[str] = None) -> list[dict]:
    """Returns daily cumulative PnL for charting."""
    if not network:
        network = get_bot_state("hl_network_regime") or "demo"
    return execute(
        """
        SELECT
            DATE(closed_at AT TIME ZONE 'UTC') AS date,
            SUM(pnl_usd)                        AS daily_pnl,
            SUM(SUM(pnl_usd)) OVER (ORDER BY DATE(closed_at AT TIME ZONE 'UTC')) AS cumulative_pnl,
            exchange                            AS source
        FROM trades
        WHERE closed_at IS NOT NULL AND network = %s
        GROUP BY DATE(closed_at AT TIME ZONE 'UTC'), exchange
        ORDER BY date ASC
        """,
        (network,)
    )

def log_error(source: str, message: str) -> None:
    execute(
        "INSERT INTO error_logs (source, message) VALUES (%s, %s)",
        (source, message)
    )

def get_error_logs(limit: int = 50) -> list[dict]:
    return execute(
        "SELECT * FROM error_logs ORDER BY timestamp DESC LIMIT %s",
        (limit,)
    )
