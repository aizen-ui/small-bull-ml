"""
Minute pipeline: runs every minute during trading hours locally,
or every 5 minutes via GitHub Actions.
Fetches 1-min intraday data via yfinance, runs predictions for each stock.

Usage (local continuous mode):
    python -m pipelines.minute_pipeline --loop

Usage (single run):
    python -m pipelines.minute_pipeline
"""

from __future__ import annotations
import json
import logging
import sys
import time
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
from models.predictor import load_model, predict_for_stock
from features.feature_builder import build_features_for_stock

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def is_market_open() -> bool:
    now_ist = datetime.now(IST)
    today = now_ist.date()
    if today.weekday() >= 5:
        return False
    if today.isoformat() in MARKET_HOLIDAYS:
        return False
    market_open = now_ist.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
    market_close = now_ist.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0)
    return market_open <= now_ist <= market_close


def step_fetch_intraday():
    """Fetch 1-minute intraday data for all stocks."""
    logger.info("Fetching 1m intraday data...")
    symbols = get_symbols()
    stock_ids = db.get_all_stock_ids()

    data = yf.fetch_intraday(symbols, interval="1m")
    for symbol, df in data.items():
        sid = stock_ids.get(symbol)
        if sid is None:
            continue
        rows = df.to_dict("records")
        db.upsert_intraday_prices(sid, rows)

    logger.info(f"Upserted 1m data for {len(data)} stocks")
    return data


def step_generate_minute_predictions(intraday_data: dict):
    """Generate predictions based on latest 1-minute data."""
    logger.info("Generating minute predictions...")

    try:
        model = load_model()
    except Exception as e:
        logger.warning(f"No model available: {e}. Skipping.")
        return 0

    stock_ids = db.get_all_stock_ids()
    now = datetime.utcnow()
    predictions = []

    for symbol, sid in stock_ids.items():
        features = build_features_for_stock(sid, days=100)
        if features is None or features.empty:
            continue

        # Enhance with intraday data
        intraday_df = intraday_data.get(symbol)
        if intraday_df is not None and not intraday_df.empty:
            latest_features = features.iloc[-1:].copy()

            intraday_close = float(intraday_df.iloc[-1]["close"])
            daily_open = float(intraday_df.iloc[0]["open"])

            if daily_open > 0:
                latest_features["pct_change_1d"] = (intraday_close - daily_open) / daily_open

            total_vol = intraday_df["volume"].sum()
            if "volume_ratio" in features.columns:
                avg = features["volume_ratio"].iloc[-1]
                if avg and avg > 0:
                    latest_features["volume_ratio"] = total_vol / avg

            features = latest_features

        result = predict_for_stock(model, features)
        if result is None:
            continue

        predictions.append({
            "stock_id": sid,
            "prediction_timestamp": now.isoformat(),
            "prediction_type": "minute",
            "model_version": model.version,
            "predicted_direction": result["predicted_direction"],
            "predicted_pct_change": result["predicted_pct_change"],
            "confidence_score": result["confidence_score"],
            "top_features": json.dumps(result["top_features"]),
        })

    if predictions:
        db.insert_predictions(predictions)

    logger.info(f"Generated {len(predictions)} minute predictions")
    return len(predictions)


def step_evaluate_previous_minute():
    """Evaluate previous minute predictions against current prices."""
    pending = db.get_pending_predictions("minute")
    stock_ids = db.get_all_stock_ids()
    evaluated = 0

    for pred in pending:
        sid = pred["stock_id"]
        rows = db.query(
            "intraday_prices",
            filters={"stock_id": sid},
            order="-timestamp",
            limit=1,
        )
        if not rows:
            continue

        current_price = float(rows[0]["close"])

        # Get price at prediction time (previous minute)
        earlier = db.query(
            "intraday_prices",
            filters={"stock_id": sid},
            order="-timestamp",
            limit=5,
        )
        if len(earlier) < 2:
            continue

        prev_price = float(earlier[1]["close"])
        actual_pct = (current_price - prev_price) / prev_price if prev_price else 0
        actual_dir = "up" if actual_pct > 0.001 else ("down" if actual_pct < -0.001 else "neutral")
        was_correct = pred["predicted_direction"] == actual_dir

        db.update_prediction_outcome(pred["id"], actual_dir, round(actual_pct, 4), was_correct)
        evaluated += 1

    if evaluated > 0:
        logger.info(f"Evaluated {evaluated} minute predictions")


def run_once():
    """Single run: fetch data, evaluate, predict."""
    intraday_data = step_fetch_intraday()
    step_evaluate_previous_minute()
    count = step_generate_minute_predictions(intraday_data)
    return count


def run_loop(force: bool = False):
    """
    Continuous loop: runs every 60 seconds during market hours.
    Run this locally for live updating.
    Use force=True to run even outside market hours (for testing).
    """
    mode = "FORCE mode (ignoring market hours)" if force else "market hours only"
    logger.info(f"Starting minute prediction loop ({mode}) — Ctrl+C to stop")
    while True:
        try:
            if force or is_market_open():
                count = run_once()
                logger.info(f"Tick complete. {count} predictions. Sleeping 60s...")
            else:
                logger.info("Market closed. Sleeping 60s...")
            time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error in loop: {e}", exc_info=True)
            time.sleep(60)


def run():
    """Entry point."""
    run_once()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true",
                        help="Run continuously every 60 seconds")
    parser.add_argument("--force", action="store_true",
                        help="Run even outside market hours")
    args = parser.parse_args()

    if args.loop:
        run_loop(force=args.force)
    else:
        run()
