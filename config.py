"""
config.py — Central configuration loader for HYPER-SCALP-AI.
All env vars loaded here. Never import os.environ elsewhere.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Hyperliquid ───────────────────────────────────────────────────────────────
HL_PRIVATE_KEY:    str  = os.environ.get("HL_PRIVATE_KEY", "")
HL_TESTNET_PRIVATE_KEY: str = os.environ.get("HL_TESTNET_PRIVATE_KEY", "")
HL_MAINNET_PRIVATE_KEY: str = os.environ.get("HL_MAINNET_PRIVATE_KEY", "")
HL_ACCOUNT:        str  = os.environ.get("HL_ACCOUNT_ADDRESS", "")
HL_MODE:           str  = os.environ.get("HL_MODE", "testnet")          # testnet | mainnet
HL_BASE_URL:       str  = (
    "https://api.hyperliquid.xyz"
    if HL_MODE == "mainnet"
    else "https://api.hyperliquid-testnet.xyz"
)
IS_TESTNET:        bool = HL_MODE != "mainnet"

# ── Solana / Meme ─────────────────────────────────────────────────────────────
SOL_PRIVATE_KEY:   str  = os.environ.get("SOL_PRIVATE_KEY", "")
BIRDEYE_API_KEY:   str  = os.environ.get("BIRDEYE_API_KEY", "")

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL:      str  = os.environ.get("DATABASE_URL", "")

# ── API Security ──────────────────────────────────────────────────────────────
API_SECRET:        str  = os.environ.get("API_SECRET", "dev-secret-change-me")

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN:    str  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID:  str  = os.environ.get("TELEGRAM_CHAT_ID", "")

# ── App ───────────────────────────────────────────────────────────────────────
PORT:              int  = int(os.environ.get("PORT", "8080"))
LOG_LEVEL:         str  = os.environ.get("LOG_LEVEL", "INFO")

# ── HL Perps — Trading pairs ──────────────────────────────────────────────────
HL_PRIMARY_PAIRS   = ["BTC", "ETH"]          # 48.4% win rate, +$382 — our best asset
HL_SECONDARY_PAIRS = ["ARB", "SOL"]          # ARB 47.3%/+$58 ✓ (Disabled ETH to eliminate massive noise stopouts)

# ── Leverage & risk table (Regime-based) ──────────────────────────────────────
LEVERAGE_UPTREND   = {"BTC": 10, "ETH": 8, "SOL": 10, "ARB": 7}
LEVERAGE_SIDEWAYS  = {"BTC": 6,  "ETH": 5, "SOL": 5,  "ARB": 5}
LEVERAGE_DOWNTREND = {"BTC": 5,  "ETH": 4, "SOL": 4,  "ARB": 3}

RISK_PCT_UPTREND   = 0.015
RISK_PCT_SIDEWAYS  = 0.010
RISK_PCT_DOWNTREND = 0.010

# ── Position limits ───────────────────────────────────────────────────────────
MAX_OPEN_POSITIONS:    int   = 5
MAX_ACCOUNT_RISK_PCT:  float = 0.06   # 6% total exposure
DAILY_DRAWDOWN_KILL:   float = 0.10   # -10% → pause 24h
WEEKLY_DRAWDOWN_KILL:  float = 0.20   # -20% → pause 72h
TRADE_COOLDOWN_MINUTES: int  = 1     # Cooldown period (in minutes) after a trade closes

# Note: Exit levels (TP/SL) are now dynamic per strategy and generated in signals.py

# ── Meme exit levels (defaults; overridable per pair) ────────────────────────
MEME_TP_PCT:       float = 0.20    # +20%
MEME_PARTIAL_PCT:  float = 0.12    # +12% → close 60%
MEME_SL_PCT:       float = 0.08    # -8%
MEME_TRAIL_PCT:    float = 0.05    # 5% trailing after +12%
MEME_TIME_STOP_MIN: int  = 20      # max hold minutes
MEME_LIQ_DROP_PCT: float = 0.30    # liquidity drop → emergency exit
MEME_DAILY_KILL:   float = 0.15    # meme allocation -15% → pause 24h
MEME_BLACKLIST_H:  int   = 4       # hours to blacklist after SL
SOL_GAS_MINIMUM:   float = 0.2     # SOL balance floor

# ── Signal thresholds are now dynamically computed in signals.py ──────────────

# ── Meme signal thresholds ────────────────────────────────────────────────────
MEME_VOL_SPIKE_X:  float = 3.0     # 5m vol > 3x 1h average
MEME_VOL_24H_INC:  float = 0.40    # 24h vol +40% in last 30m
MEME_BREAKOUT_MIN: float = 0.02    # candle body > 2%
MEME_MAX_IMPACT:   float = 0.015   # max price impact (1.5%)
MEME_SKIP_IMPACT:  float = 0.030   # skip trade if impact > 3%
MEME_MIN_LIQ:      float = 50_000  # USD liquidity floor
MEME_MIN_MCAP:     float = 5_000_000
MEME_MAX_MCAP:     float = 50_000_000
MEME_MIN_SLIPPAGE: float = 0.025   # 2.5%
MEME_MIN_AGE_MIN:  int   = 30      # token must be > 30 min old

# ── Compounding milestones ────────────────────────────────────────────────────
MILESTONES = [
    {"phase": "Seed",      "min": 100,   "max": 250,   "max_trade": 50},
    {"phase": "Growth I",  "min": 250,   "max": 500,   "max_trade": 150},
    {"phase": "Growth II", "min": 500,   "max": 1_000, "max_trade": 300},
    {"phase": "Scale I",   "min": 1_000, "max": 2_500, "max_trade": 800},
    {"phase": "Scale II",  "min": 2_500, "max": 5_000, "max_trade": 2000},
    {"phase": "Scale III", "min": 5_000, "max": 10_000,"max_trade": 5000},
]

# ── Capital split ─────────────────────────────────────────────────────────────
HL_CAPITAL_PCT:    float = 0.60    # 60% to HL perps
MEME_CAPITAL_PCT:  float = 0.30    # 30% to meme bot
SOL_RESERVE_PCT:   float = 0.10    # 10% SOL gas reserve

# ── Scheduler intervals ───────────────────────────────────────────────────────
HL_LOOP_INTERVAL_S:   int = 10     # HL bot: every 10 seconds
MEME_LOOP_INTERVAL_S: int = 30     # Meme bot: every 30 seconds
PAIRS_RELOAD_S:       int = 60     # Reload pairs from DB
MILESTONE_CHECK_S:    int = 300    # Check milestones every 5 min
