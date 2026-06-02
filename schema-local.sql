-- ============================================================
-- HYPER-SCALP-AI Local Database Schema (User Railway Space)
-- ============================================================

-- Local trade logs for dashboard rendering
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(12) NOT NULL,
    direction VARCHAR(6) NOT NULL,
    network VARCHAR(10) DEFAULT 'demo', -- 'demo' (testnet) | 'live' (mainnet)
    exchange VARCHAR(20) DEFAULT 'hyperliquid',
    entry_price NUMERIC(16, 8) NOT NULL,
    exit_price NUMERIC(16, 8),
    size_usd NUMERIC(12, 2) NOT NULL,
    coin_size NUMERIC(16, 8) NOT NULL,
    pnl_usd NUMERIC(12, 2),
    pnl_pct NUMERIC(6, 4),
    status VARCHAR(20) DEFAULT 'open',
    exit_reason VARCHAR(50),
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP WITH TIME ZONE
);

-- Basic bot state configurations
CREATE TABLE IF NOT EXISTS bot_state (
    key VARCHAR(50) PRIMARY KEY,
    value VARCHAR(255) NOT NULL
);

-- Active & historical pairs (meme watchlist)
CREATE TABLE IF NOT EXISTS pairs (
  id              SERIAL PRIMARY KEY,
  source          TEXT NOT NULL DEFAULT 'meme',
  symbol          TEXT NOT NULL,
  contract        TEXT,
  pool            TEXT,
  active          BOOLEAN DEFAULT true,
  custom_tp_pct   NUMERIC DEFAULT 20,
  custom_sl_pct   NUMERIC DEFAULT 8,
  max_hold_min    INTEGER DEFAULT 20,
  note            TEXT,
  added_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Strategies (manage active scalping logic)
CREATE TABLE IF NOT EXISTS strategies (
  id          SERIAL PRIMARY KEY,
  name        TEXT UNIQUE NOT NULL,
  description TEXT,
  is_active   BOOLEAN DEFAULT false,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Signal readings log (for dashboard signal monitor)
CREATE TABLE IF NOT EXISTS signals_log (
  id         SERIAL PRIMARY KEY,
  source     TEXT,                  -- 'hyperliquid' | 'meme'
  symbol     TEXT,
  rsi_1m     NUMERIC,
  rsi_5m     NUMERIC,
  macd       NUMERIC,
  adx        NUMERIC,
  vol_ratio  NUMERIC,
  bb_signal  BOOLEAN,
  ob_ratio   NUMERIC,               -- order book bid/ask ratio
  signal_count INTEGER,             -- 0-6 confluence count
  direction  TEXT,                  -- 'long' | 'short' | null
  signal_hit BOOLEAN,               -- true if trade was entered
  logged_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Seed local bot_state flags
INSERT INTO bot_state (key, value) VALUES ('hl_bot_active',   'true')  ON CONFLICT (key) DO NOTHING;
INSERT INTO bot_state (key, value) VALUES ('meme_bot_active', 'true')  ON CONFLICT (key) DO NOTHING;
INSERT INTO bot_state (key, value) VALUES ('emergency_stop',  'false') ON CONFLICT (key) DO NOTHING;
INSERT INTO bot_state (key, value) VALUES ('hl_paused_until', '')      ON CONFLICT (key) DO NOTHING;
INSERT INTO bot_state (key, value) VALUES ('meme_paused_until', '')    ON CONFLICT (key) DO NOTHING;
INSERT INTO bot_state (key, value) VALUES ('hl_network_regime', 'demo') ON CONFLICT (key) DO NOTHING;

-- Error logging
CREATE TABLE IF NOT EXISTS error_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(50),
    message TEXT
);

-- Indexes for fast client queries
CREATE INDEX IF NOT EXISTS idx_local_trades_closed  ON trades (closed_at DESC);
CREATE INDEX IF NOT EXISTS idx_local_trades_network ON trades (network);
CREATE INDEX IF NOT EXISTS idx_local_signals_logged ON signals_log (logged_at DESC);
