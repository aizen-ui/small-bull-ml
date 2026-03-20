-- Migration: Add all missing columns to live Supabase tables
-- Run this in Supabase SQL Editor before deploying code changes
-- Safe to run multiple times (uses IF NOT EXISTS)

-- technical_indicators: add 17 missing columns
ALTER TABLE technical_indicators
  ADD COLUMN IF NOT EXISTS rsi_14 NUMERIC(8,4),
  ADD COLUMN IF NOT EXISTS macd_hist NUMERIC(12,4),
  ADD COLUMN IF NOT EXISTS bb_middle NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS atr_14 NUMERIC(12,4),
  ADD COLUMN IF NOT EXISTS obv BIGINT,
  ADD COLUMN IF NOT EXISTS sma_20 NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS sma_50 NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS ema_12 NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS ema_26 NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS adx_14 NUMERIC(8,4),
  ADD COLUMN IF NOT EXISTS stoch_k NUMERIC(8,4),
  ADD COLUMN IF NOT EXISTS stoch_d NUMERIC(8,4),
  ADD COLUMN IF NOT EXISTS vwap NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS pct_change_1d NUMERIC(8,4),
  ADD COLUMN IF NOT EXISTS pct_change_5d NUMERIC(8,4),
  ADD COLUMN IF NOT EXISTS pct_change_20d NUMERIC(8,4),
  ADD COLUMN IF NOT EXISTS volatility_20d NUMERIC(8,4);

-- sentiment_scores: add 5 missing columns
ALTER TABLE sentiment_scores
  ADD COLUMN IF NOT EXISTS news_count INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS avg_sentiment NUMERIC(6,4),
  ADD COLUMN IF NOT EXISTS max_sentiment NUMERIC(6,4),
  ADD COLUMN IF NOT EXISTS min_sentiment NUMERIC(6,4),
  ADD COLUMN IF NOT EXISTS weighted_sentiment NUMERIC(6,4),
  ADD COLUMN IF NOT EXISTS news_headlines JSONB;

-- market_context: add 3 missing columns
ALTER TABLE market_context
  ADD COLUMN IF NOT EXISTS nifty50_close NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS nifty50_change_pct NUMERIC(8,4),
  ADD COLUMN IF NOT EXISTS market_breadth_score NUMERIC(6,4);

-- analyst_data: add 3 missing columns
ALTER TABLE analyst_data
  ADD COLUMN IF NOT EXISTS current_price NUMERIC(12,2),
  ADD COLUMN IF NOT EXISTS upside_pct NUMERIC(8,4),
  ADD COLUMN IF NOT EXISTS risk_meter TEXT;
