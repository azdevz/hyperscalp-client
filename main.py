"""
main.py — HYPER-SCALP-AI entry point.

Boots:
  1. DB connection pool
  2. Hyperliquid WebSocket feed (daemon thread)
  3. APScheduler: HL bot (1s), Meme bot (30s), Pairs reload (60s)
  4. FastAPI (uvicorn) on PORT

Run:  python main.py
Railway start command in Procfile: web: python main.py
"""

import logging
import sys

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
import db
from api.routes import router
from hl_bot import ws_feed
from hl_bot.bot import bot_tick as hl_tick
from hl_bot.auto_tuner import run_auto_tuner
from meme_bot.bot import bot_tick as meme_tick

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="HYPER-SCALP-AI",
    description="Autonomous perps + meme scalping bot API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Dashboard on Vercel — restrict to vercel domain in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    logger.info("=" * 60)
    logger.info("  HYPER-SCALP-AI starting up")
    logger.info(f"  Mode: {config.HL_MODE.upper()}")
    logger.info(f"  HL URL: {config.HL_BASE_URL}")
    logger.info("=" * 60)

    # 1. DB
    if config.DATABASE_URL:
        try:
            db.init_pool()
        except Exception as exc:
            logger.error(f"DB init failed: {exc}")
            logger.warning("Running without DB — dashboard will not work.")
    else:
        logger.warning("DATABASE_URL not set — DB disabled.")

    # 2. WebSocket feed
    ws_feed.start_ws_thread()

    # 3. Scheduler
    scheduler = BackgroundScheduler(timezone="UTC")

    # HL bot: every 1 second
    if config.HL_PRIVATE_KEY:
        scheduler.add_job(
            hl_tick,
            trigger=IntervalTrigger(seconds=config.HL_LOOP_INTERVAL_S),
            id="hl_bot",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=5,
        )
        logger.info("HL bot scheduler registered (1s interval).")
        
        # Auto-tuner: every 30 minutes
        scheduler.add_job(
            run_auto_tuner,
            trigger=IntervalTrigger(minutes=30),
            id="hl_auto_tuner",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
        logger.info("Auto-tuner scheduler registered (30m interval).")

        # OTA Tuner Strategy Sync: every 30 minutes
        from hl_bot.ota_tuner import run_ota_sync
        scheduler.add_job(
            run_ota_sync,
            trigger=IntervalTrigger(minutes=30),
            id="hl_ota_tuner",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
        logger.info("OTA Strategy sync registered (30m interval).")
    else:
        logger.warning("HL_PRIVATE_KEY not set — HL bot disabled.")

    # Meme bot: every 30 seconds
    if config.BIRDEYE_API_KEY:
        scheduler.add_job(
            meme_tick,
            trigger=IntervalTrigger(seconds=config.MEME_LOOP_INTERVAL_S),
            id="meme_bot",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=15,
        )
        logger.info("Meme bot scheduler registered (30s interval).")
    else:
        logger.warning("BIRDEYE_API_KEY not set — Meme bot disabled.")

    scheduler.start()
    logger.info("Scheduler started.")


@app.on_event("shutdown")
async def shutdown():
    logger.info("HYPER-SCALP-AI shutting down.")


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=False,
    )
