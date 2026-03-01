"""
Nightly pipeline: runs Mon-Fri at 11:30 PM IST via GitHub Actions.
Fetches daily data, computes indicators, calls IndianAPI (budget-controlled),
scores sentiment, evaluates yesterday's predictions, generates tonight's predictions.
"""

from __future__ import annotations
import json
import logging
import sys
from datetime import date, datetime

from config.stock_universe import STOCK_UNIVERSE, get_symbols, get_indianapi_name
from config.settings import MARKET_HOLIDAYS
from data import supabase_client as db
from data import yfinance_fetcher as yf
from data import indianapi_client as api
from features.technical_indicators import compute_all
from features.sentiment_scorer import score_news_batch
from features.feature_builder import build_features_for_stock
from models.predictor import load_model, predict_for_stock
from pipelines.api_budget_manager import (
    get_budget_status, select_stocks_for_today, is_weekly_run_day,
    get_stocks_for_weekly_targets,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


def is_trading_day() -> bool:
    today = date.today()
    if today.weekday() >= 5:
        return False
    if today.isoformat() in MARKET_HOLIDAYS:
        return False
    return True


def step_fetch_daily_prices():
    """Step 1: Fetch daily prices via yfinance (free, unlimited)."""
    logger.info("=== Step 1: Fetching daily prices ===")
    symbols = get_symbols()
    stock_ids = db.get_all_stock_ids()

    data = yf.fetch_daily_latest(symbols)
    for symbol, df in data.items():
        sid = stock_ids.get(symbol)
        if sid is None:
            continue
        rows = df.to_dict("records")
        db.upsert_daily_prices(sid, rows)

    logger.info(f"Upserted daily prices for {len(data)} stocks")

    # Also fetch Nifty 50 index
    nifty = yf.fetch_nifty50_index()
    return nifty


def step_compute_indicators():
    """Step 2: Compute technical indicators for all stocks."""
    logger.info("=== Step 2: Computing technical indicators ===")
    stock_ids = db.get_all_stock_ids()
    count = 0

    for symbol, sid in stock_ids.items():
        prices = db.get_daily_prices(sid, days=60)
        if len(prices) < 30:
            continue

        import pandas as pd
        price_df = pd.DataFrame(prices)
        price_df["date"] = pd.to_datetime(price_df["date"]).dt.date
        price_df = price_df.sort_values("date").reset_index(drop=True)

        indicators = compute_all(price_df)
        # Take only the latest row
        latest = indicators.iloc[-1:]
        rows = latest.to_dict("records")
        db.upsert_indicators(sid, rows)
        count += 1

    logger.info(f"Updated indicators for {count} stocks")


def step_fetch_indianapi(nifty_df=None):
    """Step 3: Fetch IndianAPI data (budget-controlled)."""
    logger.info("=== Step 3: Fetching IndianAPI data ===")
    budget = get_budget_status()
    logger.info(f"API budget: {budget}")

    today = date.today()
    stock_ids = db.get_all_stock_ids()
    context = {"date": today.isoformat()}

    # Daily market-level endpoints (5 calls)
    trending = api.get_trending()
    if trending:
        ts = trending.get("trending_stocks", {})
        context["top_gainers"] = ts.get("top_gainers", [])
        context["top_losers"] = ts.get("top_losers", [])
        # Compute market breadth
        n_gainers = len(context["top_gainers"])
        n_losers = len(context["top_losers"])
        total = n_gainers + n_losers
        context["market_breadth_score"] = (
            round(n_gainers / total, 4) if total > 0 else 0.5
        )

    shockers = api.get_price_shockers()
    if shockers:
        context["price_shockers"] = shockers

    active = api.get_nse_most_active()
    if active:
        context["most_active_nse"] = active

    w52 = api.get_52_week_high_low()
    if w52:
        nse_data = w52.get("NSE_52WeekHighLow", {})
        context["week_52_highs"] = nse_data.get("high52Week", [])
        context["week_52_lows"] = nse_data.get("low52Week", [])

    commodities = api.get_commodities()
    if commodities:
        context["commodities"] = commodities

    # Nifty 50 close from yfinance data
    if nifty_df is not None and len(nifty_df) > 0:
        latest_nifty = nifty_df.iloc[-1]
        context["nifty50_close"] = float(latest_nifty["close"])
        if len(nifty_df) > 1:
            prev = nifty_df.iloc[-2]["close"]
            context["nifty50_change_pct"] = round(
                (float(latest_nifty["close"]) - float(prev)) / float(prev), 4
            )

    db.upsert_market_context(context)

    # Per-stock calls (rotated, budget-controlled)
    selected = select_stocks_for_today()
    for stock in selected:
        name = stock["indianapi_name"]
        symbol = stock["symbol"]
        sid = stock_ids.get(symbol)
        if sid is None:
            continue

        data = api.get_stock(name)
        if data is None:
            continue

        # Extract sentiment from recentNews
        news = data.get("recentNews", [])
        if news:
            scores = score_news_batch(news)
            headlines = [
                {"title": n.get("title", ""), "date": n.get("date")}
                for n in news[:20]
            ]
            db.upsert_sentiment(sid, {
                "date": today.isoformat(),
                "score": scores.get("weighted_sentiment", 0.0),
                "source": "indianapi_nightly",
            })

        # Extract analyst data
        analyst_view = data.get("analystView", {})
        risk_meter = data.get("riskMeter", {})
        current_price = data.get("currentPrice", {})
        nse_price = current_price.get("NSE") or current_price.get("BSE")

        if analyst_view or risk_meter:
            db.upsert_analyst(sid, {
                "date": today.isoformat(),
                "current_price": nse_price,
                "recommendation": analyst_view.get("recommendation"),
                "risk_meter": risk_meter.get("riskLevel")
                              if isinstance(risk_meter, dict) else str(risk_meter),
            })

    # Weekly calls (Mondays only)
    if is_weekly_run_day():
        logger.info("Monday: running weekly extra calls")
        targets = get_stocks_for_weekly_targets(n=10)
        for stock in targets:
            tp = api.get_stock_target_price(stock.get("indianapi_name", ""))
            if tp and stock_ids.get(stock["symbol"]):
                sid = stock_ids[stock["symbol"]]
                pt = tp.get("priceTarget", {})
                rec = tp.get("recommendation", {})
                db.upsert_analyst(sid, {
                    "date": today.isoformat(),
                    "target_price": pt.get("Mean"),
                    "upside_pct": (
                        round((pt["Mean"] / pt["Low"] - 1) * 100, 2)
                        if pt.get("Mean") and pt.get("Low") else None
                    ),
                    "recommendation": rec.get("Mean"),
                })

    logger.info("IndianAPI fetch complete")


def step_evaluate_predictions():
    """Step 4: Evaluate yesterday's nightly predictions."""
    logger.info("=== Step 4: Evaluating yesterday's predictions ===")
    pending = db.get_pending_predictions("nightly")
    stock_ids = db.get_all_stock_ids()
    id_to_symbol = {v: k for k, v in stock_ids.items()}
    evaluated = 0

    for pred in pending:
        sid = pred["stock_id"]
        # Get today's close price
        prices = db.get_daily_prices(sid, days=2)
        if len(prices) < 2:
            continue

        prices_sorted = sorted(prices, key=lambda x: x["date"])
        prev_close = float(prices_sorted[-2]["close"])
        today_close = float(prices_sorted[-1]["close"])

        actual_pct = (today_close - prev_close) / prev_close
        actual_dir = "up" if actual_pct > 0.001 else ("down" if actual_pct < -0.001 else "neutral")
        was_correct = pred["predicted_direction"] == actual_dir

        db.update_prediction_outcome(pred["id"], actual_dir, round(actual_pct, 4), was_correct)
        evaluated += 1

    logger.info(f"Evaluated {evaluated} pending predictions")


def step_generate_predictions():
    """Step 5: Generate tonight's predictions."""
    logger.info("=== Step 5: Generating predictions ===")

    try:
        model = load_model()
    except Exception as e:
        logger.warning(f"No model available: {e}. Skipping predictions.")
        return

    stock_ids = db.get_all_stock_ids()
    now = datetime.utcnow()
    predictions = []

    for symbol, sid in stock_ids.items():
        features = build_features_for_stock(sid, days=200)
        if features is None or features.empty:
            continue

        result = predict_for_stock(model, features)
        if result is None:
            continue

        predictions.append({
            "stock_id": sid,
            "prediction_timestamp": now.isoformat(),
            "prediction_type": "nightly",
            "model_version": model.version,
            "predicted_direction": result["predicted_direction"],
            "predicted_pct_change": result["predicted_pct_change"],
            "confidence_score": result["confidence_score"],
            "top_features": json.dumps(result["top_features"]),
        })

    if predictions:
        db.insert_predictions(predictions)

    logger.info(f"Generated {len(predictions)} nightly predictions")


def run():
    """Main entry point for nightly pipeline."""
    if not is_trading_day():
        logger.info("Not a trading day. Exiting.")
        return

    run_id = db.log_pipeline_start("nightly")
    try:
        nifty_df = step_fetch_daily_prices()
        step_compute_indicators()
        step_fetch_indianapi(nifty_df)
        step_evaluate_predictions()
        step_generate_predictions()

        budget = get_budget_status()
        db.log_pipeline_end(run_id, "success", details={"api_budget": budget})
        logger.info("Nightly pipeline completed successfully")

    except Exception as e:
        logger.error(f"Nightly pipeline failed: {e}", exc_info=True)
        db.log_pipeline_end(run_id, "failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    run()
