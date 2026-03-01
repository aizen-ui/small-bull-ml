-- Run this in Supabase SQL Editor to create all tables

-- 1. Master stock list
CREATE TABLE IF NOT EXISTS stocks (
    id              SERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL UNIQUE,
    indianapi_name  TEXT,
    company_name    TEXT NOT NULL,
    sector          TEXT,
    industry        TEXT,
    market_cap_category TEXT CHECK (market_cap_category IN ('largecap', 'midcap', 'smallcap')),
    is_nifty50      BOOLEAN DEFAULT FALSE,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Daily OHLCV prices
CREATE TABLE IF NOT EXISTS daily_prices (
    id          SERIAL PRIMARY KEY,
    stock_id    INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    date        DATE NOT NULL,
    open        NUMERIC(12,2),
    high        NUMERIC(12,2),
    low         NUMERIC(12,2),
    close       NUMERIC(12,2),
    volume      BIGINT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_id, date)
);
CREATE INDEX IF NOT EXISTS idx_daily_prices_stock_date ON daily_prices(stock_id, date DESC);

-- 3. Intraday 15-min prices
CREATE TABLE IF NOT EXISTS intraday_prices (
    id          SERIAL PRIMARY KEY,
    stock_id    INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    timestamp   TIMESTAMPTZ NOT NULL,
    open        NUMERIC(12,2),
    high        NUMERIC(12,2),
    low         NUMERIC(12,2),
    close       NUMERIC(12,2),
    volume      BIGINT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_id, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_intraday_stock_ts ON intraday_prices(stock_id, timestamp DESC);

-- 4. Technical indicators
CREATE TABLE IF NOT EXISTS technical_indicators (
    id              SERIAL PRIMARY KEY,
    stock_id        INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    rsi_14          NUMERIC(8,4),
    macd            NUMERIC(12,4),
    macd_signal     NUMERIC(12,4),
    macd_hist       NUMERIC(12,4),
    bb_upper        NUMERIC(12,2),
    bb_middle       NUMERIC(12,2),
    bb_lower        NUMERIC(12,2),
    atr_14          NUMERIC(12,4),
    obv             BIGINT,
    sma_20          NUMERIC(12,2),
    sma_50          NUMERIC(12,2),
    ema_12          NUMERIC(12,2),
    ema_26          NUMERIC(12,2),
    adx_14          NUMERIC(8,4),
    stoch_k         NUMERIC(8,4),
    stoch_d         NUMERIC(8,4),
    vwap            NUMERIC(12,2),
    pct_change_1d   NUMERIC(8,4),
    pct_change_5d   NUMERIC(8,4),
    pct_change_20d  NUMERIC(8,4),
    volatility_20d  NUMERIC(8,4),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_id, date)
);

-- 5. Sentiment scores
CREATE TABLE IF NOT EXISTS sentiment_scores (
    id                  SERIAL PRIMARY KEY,
    stock_id            INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    date                DATE NOT NULL,
    news_count          INTEGER DEFAULT 0,
    avg_sentiment       NUMERIC(6,4),
    max_sentiment       NUMERIC(6,4),
    min_sentiment       NUMERIC(6,4),
    weighted_sentiment  NUMERIC(6,4),
    news_headlines      JSONB,
    source              TEXT DEFAULT 'indianapi',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_id, date)
);

-- 6. Analyst data
CREATE TABLE IF NOT EXISTS analyst_data (
    id                  SERIAL PRIMARY KEY,
    stock_id            INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    date                DATE NOT NULL,
    target_price        NUMERIC(12,2),
    current_price       NUMERIC(12,2),
    upside_pct          NUMERIC(8,4),
    recommendation      TEXT,
    risk_meter          TEXT,
    analyst_rating      NUMERIC(4,2),
    source              TEXT DEFAULT 'indianapi',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stock_id, date)
);

-- 7. Market context (one row per trading day)
CREATE TABLE IF NOT EXISTS market_context (
    id                      SERIAL PRIMARY KEY,
    date                    DATE NOT NULL UNIQUE,
    nifty50_close           NUMERIC(12,2),
    nifty50_change_pct      NUMERIC(8,4),
    top_gainers             JSONB,
    top_losers              JSONB,
    price_shockers          JSONB,
    most_active_nse         JSONB,
    week_52_highs           JSONB,
    week_52_lows            JSONB,
    market_breadth_score    NUMERIC(6,4),
    commodities             JSONB,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Predictions
CREATE TABLE IF NOT EXISTS predictions (
    id                      SERIAL PRIMARY KEY,
    stock_id                INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    prediction_timestamp    TIMESTAMPTZ NOT NULL,
    prediction_type         TEXT CHECK (prediction_type IN ('nightly', 'minute')),
    model_version           TEXT NOT NULL,
    predicted_direction     TEXT CHECK (predicted_direction IN ('up', 'down', 'neutral')),
    predicted_pct_change    NUMERIC(8,4),
    confidence_score        NUMERIC(6,4),
    top_features            JSONB,
    actual_direction        TEXT,
    actual_pct_change       NUMERIC(8,4),
    was_correct             BOOLEAN,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_predictions_stock_ts ON predictions(stock_id, prediction_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_type ON predictions(prediction_type, prediction_timestamp DESC);

-- 9. Model performance
CREATE TABLE IF NOT EXISTS model_performance (
    id                  SERIAL PRIMARY KEY,
    model_version       TEXT NOT NULL,
    evaluation_date     DATE NOT NULL,
    prediction_type     TEXT,
    accuracy            NUMERIC(6,4),
    precision_up        NUMERIC(6,4),
    recall_up           NUMERIC(6,4),
    f1_up               NUMERIC(6,4),
    mae                 NUMERIC(8,4),
    rmse                NUMERIC(8,4),
    directional_accuracy NUMERIC(6,4),
    accuracy_7d         NUMERIC(6,4),
    accuracy_30d        NUMERIC(6,4),
    total_predictions   INTEGER,
    correct_predictions INTEGER,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(model_version, evaluation_date, prediction_type)
);

-- 10. API call log
CREATE TABLE IF NOT EXISTS api_call_log (
    id          SERIAL PRIMARY KEY,
    endpoint    TEXT NOT NULL,
    params      JSONB,
    status_code INTEGER,
    called_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_api_calls_month ON api_call_log(called_at);

-- 11. Pipeline runs log
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              SERIAL PRIMARY KEY,
    pipeline_name   TEXT NOT NULL,
    status          TEXT CHECK (status IN ('running', 'success', 'failed')),
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    details         JSONB,
    error_message   TEXT
);
