"""
Hourly pipeline: runs every hour during trading hours (9:15 AM - 3:30 PM IST).
Fetches intraday data via yfinance, computes intraday features, runs predictions.
"""

from __future__ import annotations
import json
import logging
import sys
from datetime import date, datetime, timezone, timedelta

import numpy as np
import pandas as pd

from config.stock_universe import get_symbols
from config.settings import (
    MARKET_HOLIDAYS, MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
    MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE,
)
from data import supabase_client as db
from data import yfinance_fetcher as yf
from features.technical_indicators import compute_all
from models.predictor import load_model, predict_for_stock
from features.feature_builder import build_features_for_stock

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def is_market_open() -> bool:
    """Check if Indian market is currently open."""
    now_ist = datetime.now(IST)
    today = now_ist.date()

    if today.weekday() >= 5:
        return False
    if today.isoformat() in MARKET_HOLIDAYS:
        return False

    market_open = now_ist.replace(
        hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0
    )
    market_close = now_ist.replace(
        hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0
    )
    return market_open <= now_ist <= market_close


def step_fetch_intraday():
    """Fetch intraday 15-min data for all stocks."""
    logger.info("=== Fetching intraday data ===")
    symbols = get_symbols()
    stock_ids = db.get_all_stock_ids()

    data = yf.fetch_intraday(symbols)
    for symbol, df in data.items():
        sid = stock_ids.get(symbol)
        if sid is None:
            continue
        rows = df.to_dict("records")
        db.upsert_intraday_prices(sid, rows)

    logger.info(f"Upserted intraday data for {len(data)} stocks")
    return data


def step_generate_hourly_predictions(intraday_data: dict):
    """Generate hourly predictions using latest intraday data."""
    logger.info("=== Generating hourly predictions ===")

    try:
        model = load_model()
    except Exception as e:
        logger.warning(f"No model available: {e}. Skipping.")
        return

    stock_ids = db.get_all_stock_ids()
    now = datetime.utcnow()
    predictions = []

    for symbol, sid in stock_ids.items():
        # Build features from daily data (historical context)
        features = build_features_for_stock(sid, days=100)
        if features is None or features.empty:
            continue

        # Enhance with intraday data if available
        intraday_df = intraday_data.get(symbol)
        if intraday_df is not None and not intraday_df.empty:
            latest_intraday = intraday_df.iloc[-1]
            latest_features = features.iloc[-1:].copy()

            # Override daily features with intraday values
            if "close" in intraday_df.columns:
                intraday_close = float(latest_intraday["close"])
                daily_open = float(intraday_df.iloc[0]["open"])

                # Intraday return
                if daily_open > 0:
                    latest_features["pct_change_1d"] = (
                        (intraday_close - daily_open) / daily_open
                    )

                # Intraday volume ratio
                total_vol = intraday_df["volume"].sum()
                avg_daily_vol = features["volume_ratio"].iloc[-1] if "volume_ratio" in features.columns else 1
                if avg_daily_vol and avg_daily_vol > 0:
                    latest_features["volume_ratio"] = total_vol / avg_daily_vol

            features = latest_features

        result = predict_for_stock(model, features)
        if result is None:
            continue

        predictions.append({
            "stock_id": sid,
            "prediction_timestamp": now.isoformat(),
            "prediction_type": "hourly",
            "model_version": model.version,
            "predicted_direction": result["predicted_direction"],
            "predicted_pct_change": result["predicted_pct_change"],
            "confidence_score": result["confidence_score"],
            "top_features": json.dumps(result["top_features"]),
        })

    if predictions:
        db.insert_predictions(predictions)

    logger.info(f"Generated {len(predictions)} hourly predictions")


def step_evaluate_previous_hourly():
    """Evaluate the previous hour's predictions."""
    logger.info("=== Evaluating previous hourly predictions ===")
    pending = db.get_pending_predictions("hourly")
    stock_ids = db.get_all_stock_ids()
    evaluated = 0

    for pred in pending:
        sid = pred["stock_id"]
        # Get latest intraday price
        rows = db.query(
            "intraday_prices",
            filters={"stock_id": sid},
            order="-timestamp",
            limit=1,
        )
        if not rows:
            continue

        current_price = float(rows[0]["close"])

        # Get the price at prediction time (approximate)
        pred_ts = pred["prediction_timestamp"]
        earlier_rows = db.query(
            "intraday_prices",
            filters={"stock_id": sid},
            order="-timestamp",
            limit=10,
        )
        if len(earlier_rows) < 2:
            continue

        prev_price = float(earlier_rows[-1]["close"])
        actual_pct = (current_price - prev_price) / prev_price if prev_price else 0
        actual_dir = "up" if actual_pct > 0.001 else ("down" if actual_pct < -0.001 else "neutral")
        was_correct = pred["predicted_direction"] == actual_dir

        db.update_prediction_outcome(pred["id"], actual_dir, round(actual_pct, 4), was_correct)
        evaluated += 1

    logger.info(f"Evaluated {evaluated} hourly predictions")


def run():
    """Main entry point for hourly pipeline."""
    if not is_market_open():
        logger.info("Market is closed. Exiting.")
        return

    run_id = db.log_pipeline_start("hourly")
    try:
        intraday_data = step_fetch_intraday()
        step_evaluate_previous_hourly()
        step_generate_hourly_predictions(intraday_data)

        db.log_pipeline_end(run_id, "success")
        logger.info("Hourly pipeline completed successfully")

    except Exception as e:
        logger.error(f"Hourly pipeline failed: {e}", exc_info=True)
        db.log_pipeline_end(run_id, "failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    run()
