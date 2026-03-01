"""
ML Stock — CLI entry point for manual operations.
Usage:
    python app.py seed          # Seed stocks table from stock_universe
    python app.py add SYMBOL    # Add a stock + backfill (e.g. python app.py add ZOMATO)
    python app.py backfill      # Backfill 2 years of daily prices
    python app.py train         # Train initial model (skip tuning)
    python app.py train --tune  # Train with Optuna hyperparameter tuning
    python app.py nightly       # Run nightly pipeline manually
    python app.py live          # Start minute-by-minute predictions (loop)
    python app.py retrain       # Run weekly retrain manually
    python app.py status        # Check API budget and pipeline status
    python app.py upload FILE   # Upload xlsx to uploads/ and extract fundamentals
    python app.py serve         # Start local API server for dashboard uploads
"""

import argparse
import logging
import math
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("app")


def cmd_seed():
    """Seed the stocks table."""
    from config.stock_universe import STOCK_UNIVERSE
    from data.supabase_client import seed_stocks
    logger.info(f"Seeding {len(STOCK_UNIVERSE)} stocks...")
    seed_stocks(STOCK_UNIVERSE)
    logger.info("Done.")


def cmd_add(symbol: str):
    """Add a single stock and backfill its historical data."""
    from config.settings import YFINANCE_HISTORY_YEARS
    from data.supabase_client import upsert, get_stock_id, upsert_daily_prices
    from data.yfinance_fetcher import fetch_daily

    # Normalize symbol
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        symbol = symbol.upper() + ".NS"
    else:
        symbol = symbol.upper()

    # Check if stock already exists
    existing_id = get_stock_id(symbol)
    if existing_id:
        logger.info(f"{symbol} already exists (id={existing_id}), skipping insert — will backfill.")
    else:
        # Fetch basic info from yfinance
        import yfinance as yf
        logger.info(f"Fetching info for {symbol}...")
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        row = {
            "symbol": symbol,
            "company_name": info.get("longName") or info.get("shortName") or symbol,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap_category": _market_cap_category(info.get("marketCap")),
            "is_nifty50": False,
            "is_active": True,
        }
        upsert("stocks", [row], on_conflict="symbol")
        logger.info(f"Added {symbol} ({row['company_name']})")

    # Backfill
    stock_id = get_stock_id(symbol)
    logger.info(f"Backfilling {YFINANCE_HISTORY_YEARS}y of data for {symbol}...")
    data = fetch_daily([symbol], period=f"{YFINANCE_HISTORY_YEARS}y")
    if symbol in data:
        rows = data[symbol].to_dict("records")
        upsert_daily_prices(stock_id, rows)
        logger.info(f"Done — {len(rows)} daily price rows inserted.")
    else:
        logger.error(f"No data returned for {symbol}. Check if the symbol is valid.")


def _market_cap_category(market_cap) -> str | None:
    if market_cap is None:
        return None
    if market_cap >= 20_000_00_00_000:  # 20,000 Cr
        return "largecap"
    elif market_cap >= 5_000_00_00_000:  # 5,000 Cr
        return "midcap"
    return "smallcap"


def cmd_backfill():
    """Backfill historical daily prices via yfinance."""
    from config.stock_universe import get_symbols
    from config.settings import YFINANCE_HISTORY_YEARS
    from data.supabase_client import get_all_stock_ids, upsert_daily_prices
    from data.yfinance_fetcher import fetch_daily

    symbols = get_symbols()
    stock_ids = get_all_stock_ids()

    logger.info(f"Backfilling {YFINANCE_HISTORY_YEARS}y of data for {len(symbols)} stocks...")
    data = fetch_daily(symbols, period=f"{YFINANCE_HISTORY_YEARS}y")

    for symbol, df in data.items():
        sid = stock_ids.get(symbol)
        if sid is None:
            logger.warning(f"No stock_id for {symbol}, run 'seed' first")
            continue
        rows = df.to_dict("records")
        upsert_daily_prices(sid, rows)
        logger.info(f"  {symbol}: {len(rows)} rows")

    logger.info(f"Backfill complete for {len(data)} stocks.")


def cmd_train(tune: bool = False, stock: str = None):
    """Train model on raw features with proper train/test separation.
    No two-pass backtest feedback (causes data leakage / overfitting).
    Calibrates confidence threshold on held-out test set.
    """
    from features.feature_builder import (
        build_training_dataset, get_temporal_split,
    )
    from models.trainer import StockPredictor, tune_hyperparameters, generate_version
    from models.model_registry import save_model
    from data.supabase_client import get_stock_id

    stock_ids = None
    if stock:
        symbol = stock.upper()
        if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
            symbol += ".NS"
        sid = get_stock_id(symbol)
        if sid is None:
            logger.error(f"Stock {symbol} not found in DB. Run 'add {stock}' first.")
            sys.exit(1)
        stock_ids = [sid]
        logger.info(f"Training on single stock: {symbol} (id={sid})")
    else:
        logger.info("Training on all stocks...")

    logger.info("Building training dataset...")
    X, y_dir, y_pct = build_training_dataset(stock_ids=stock_ids, days=500)

    X_train, X_test, y_dir_train, y_dir_test = get_temporal_split(X, y_dir)
    _, _, y_pct_train, y_pct_test = get_temporal_split(X, y_pct)

    logger.info(f"Train: {len(X_train)} samples, Test: {len(X_test)} samples, Features: {X.shape[1]}")

    # Check class distribution
    train_dist = y_dir_train.value_counts()
    test_dist = y_dir_test.value_counts()
    logger.info(f"Train class dist: {dict(train_dist)}")
    logger.info(f"Test class dist:  {dict(test_dist)}")

    params = None
    if tune:
        logger.info("Tuning hyperparameters (this may take a few minutes)...")
        params = tune_hyperparameters(X_train, y_dir_train, y_pct_train, n_trials=30)

    # Train model
    model = StockPredictor()
    model.version = generate_version()
    train_metrics = model.train(X_train, y_dir_train, y_pct_train, params=params)

    # Evaluate on test set
    test_metrics = model.evaluate(X_test, y_dir_test, y_pct_test)

    # Calibrate confidence threshold on test set backtest
    bt_test = model.backtest(X_test, y_dir_test, y_pct_test)
    model.calibrate_threshold(bt_test)

    # Log overfitting check
    logger.info(f"Train accuracy: {train_metrics['train_accuracy']:.4f}")
    logger.info(f"Test accuracy:  {test_metrics['accuracy']:.4f}")
    gap = train_metrics["train_accuracy"] - test_metrics["accuracy"]
    if gap > 0.15:
        logger.warning(f"OVERFITTING detected! Train-test gap: {gap:.4f}")
    else:
        logger.info(f"Train-test gap: {gap:.4f} (OK)")

    version = save_model(model, test_metrics)
    logger.info(f"Model {version} trained and saved.")
    logger.info(f"Metrics: {test_metrics}")

    top_features = model.get_feature_importance(top_n=15)
    if top_features:
        logger.info("Top features:")
        for f in top_features:
            logger.info(f"  {f['feature']}: {f['importance']}")


def cmd_predict(symbol: str):
    """Run prediction for a specific stock and display results."""
    from data.supabase_client import get_stock_id
    from features.feature_builder import build_features_for_stock
    from models.predictor import load_model, predict_for_stock

    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        symbol = symbol.upper() + ".NS"
    else:
        symbol = symbol.upper()

    sid = get_stock_id(symbol)
    if sid is None:
        logger.error(f"Stock {symbol} not found in DB.")
        sys.exit(1)

    logger.info(f"Loading model and building features for {symbol}...")
    model = load_model()
    features = build_features_for_stock(sid, days=200)

    if features is None or len(features) == 0:
        logger.error(f"No features available for {symbol}")
        sys.exit(1)

    result = predict_for_stock(model, features)
    logger.info(f"\n{'='*50}")
    logger.info(f"PREDICTION for {symbol}")
    logger.info(f"{'='*50}")
    logger.info(f"  Direction:   {result['predicted_direction']}")
    if result.get('raw_direction') and result['raw_direction'] != result['predicted_direction']:
        logger.info(f"  Raw Signal:  {result['raw_direction']} (below confidence threshold)")
    logger.info(f"  Pct Change:  {result['predicted_pct_change']:.2%}")
    logger.info(f"  Confidence:  {result['confidence_score']:.1%}")
    logger.info(f"  Horizon:     5-day forward")

    if "top_features" in result:
        logger.info(f"  Top drivers: {result['top_features']}")


def cmd_nightly():
    from pipelines.nightly_pipeline import run
    run()


def cmd_live(force: bool = False):
    """Start live minute-by-minute predictions (runs continuously)."""
    from pipelines.minute_pipeline import run_loop
    run_loop(force=force)


def cmd_retrain():
    from pipelines.retrain_pipeline import run
    run(skip_tuning=False)


def cmd_upload(filepath: str):
    """Upload an xlsx file and extract fundamental features."""
    import shutil
    import os
    from features.fundamentals_features import extract_fundamentals_features, UPLOADS_DIR

    os.makedirs(UPLOADS_DIR, exist_ok=True)

    if not os.path.isfile(filepath):
        logger.error(f"File not found: {filepath}")
        sys.exit(1)

    basename = os.path.basename(filepath)
    dest = os.path.join(UPLOADS_DIR, basename)
    shutil.copy2(filepath, dest)
    logger.info(f"Copied {basename} to uploads/")

    # Extract and display fundamentals
    features = extract_fundamentals_features(dest)
    if features:
        logger.info(f"Extracted {len(features)} fundamental features:")
        for k, v in features.items():
            logger.info(f"  {k}: {v:.4f}" if isinstance(v, float) and not math.isnan(v) else f"  {k}: N/A")
    else:
        logger.warning("No features could be extracted from the file.")

    logger.info("Fundamentals will be included in next training run.")


def cmd_sentiment_backfill(symbol: str, days: int = 500):
    """Backfill historical sentiment scores for a stock.
    For each trading day, fetches Google News RSS with date filters,
    scores headlines, and stores in sentiment_scores table.
    """
    import time
    from data.supabase_client import get_stock_id, get_daily_prices, query, client as db_client
    from data.rss_fetcher import fetch_stock_news_for_date
    from features.sentiment_scorer import score_news_batch

    def _upsert_sentiment(stock_id, row):
        """Insert sentiment row, update if already exists."""
        full_row = {"stock_id": stock_id, **row}
        try:
            db_client().table("sentiment_scores").insert(full_row).execute()
        except Exception:
            # Row might already exist — try update
            try:
                db_client().table("sentiment_scores").update(row).eq(
                    "stock_id", stock_id
                ).eq("date", row["date"]).execute()
            except Exception as e2:
                logger.debug(f"Sentiment upsert failed for {row['date']}: {e2}")

    sym = symbol.upper()
    if not sym.endswith(".NS") and not sym.endswith(".BO"):
        sym += ".NS"

    sid = get_stock_id(sym)
    if sid is None:
        logger.error(f"Stock {sym} not found in DB. Run 'add {symbol}' first.")
        sys.exit(1)

    # Get stock info
    rows = query("stocks", filters={"id": sid}, limit=1)
    stock_info = rows[0] if rows else {}
    company_name = stock_info.get("company_name", sym.replace(".NS", ""))
    clean_sym = sym.replace(".NS", "").replace(".BO", "")

    # Get existing sentiment dates to skip
    existing = query("sentiment_scores", filters={"stock_id": sid}, order="-date", limit=5000)
    existing_dates = {r["date"] for r in existing}
    logger.info(f"Already have sentiment for {len(existing_dates)} dates")

    # Get all trading dates from daily_prices
    prices = get_daily_prices(sid, days=days)
    if not prices:
        logger.error(f"No price data for {sym}")
        sys.exit(1)

    trading_dates = sorted(set(p["date"] for p in prices))
    to_backfill = [d for d in trading_dates if d not in existing_dates]
    logger.info(f"Backfilling sentiment for {len(to_backfill)} / {len(trading_dates)} dates for {sym}")

    filled = 0
    skipped = 0
    for i, d in enumerate(to_backfill):
        try:
            news = fetch_stock_news_for_date(company_name, clean_sym, d)
            scores = score_news_batch(news)

            # Live table schema: (id, stock_id, date, score, source)
            # Store weighted_sentiment as the single score column
            _upsert_sentiment(sid, {
                "date": d,
                "score": scores["weighted_sentiment"],
                "source": "rss_backfill",
            })
            filled += 1

            if (i + 1) % 20 == 0:
                logger.info(f"  Progress: {i+1}/{len(to_backfill)} — {filled} filled, {skipped} no news")

            # Rate limit: ~1 request per second to be nice to Google
            time.sleep(1.0)

        except Exception as e:
            logger.debug(f"  Failed for {d}: {e}")
            skipped += 1
            time.sleep(0.5)

    logger.info(f"Done. Filled {filled} dates, skipped {skipped}.")


def cmd_serve():
    """Start local API server for dashboard xlsx upload."""
    from api_server import app as flask_app
    logger.info("Starting API server on http://localhost:5000")
    flask_app.run(host="0.0.0.0", port=5000, debug=True)


def cmd_status():
    """Print API budget and recent pipeline status."""
    from pipelines.api_budget_manager import get_budget_status
    from data.supabase_client import query

    budget = get_budget_status()
    print(f"\n--- API Budget ---")
    print(f"Used: {budget['used']} / {budget['limit']} ({budget['pct_used']}%)")
    print(f"Remaining: {budget['remaining']}")

    runs = query("pipeline_runs", order="-started_at", limit=5)
    print(f"\n--- Recent Pipeline Runs ---")
    for r in runs:
        status = r["status"]
        icon = {"success": "[OK]", "failed": "[FAIL]", "running": "[...]"}.get(status, "")
        print(f"  {icon} {r['pipeline_name']} — {status} — {r['started_at']}")
        if r.get("error_message"):
            print(f"      Error: {r['error_message']}")

    latest = query("model_performance", order="-evaluation_date", limit=1)
    if latest:
        m = latest[0]
        print(f"\n--- Latest Model ---")
        print(f"Version: {m['model_version']}")
        print(f"Accuracy: {m['accuracy']}")
        print(f"Directional Accuracy: {m['directional_accuracy']}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="ML Stock — Indian Stock Market Prediction System"
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("seed", help="Seed stocks table")

    add_p = sub.add_parser("add", help="Add a stock and backfill its data")
    add_p.add_argument("symbol", help="Stock symbol (e.g. RELIANCE or RELIANCE.NS)")

    sub.add_parser("backfill", help="Backfill historical prices")

    train_p = sub.add_parser("train", help="Train ML model")
    train_p.add_argument("--tune", action="store_true",
                         help="Run Optuna hyperparameter tuning")
    train_p.add_argument("--stock", type=str, default=None,
                         help="Train on a single stock symbol (e.g. RELIANCE)")

    predict_p = sub.add_parser("predict", help="Predict for a stock")
    predict_p.add_argument("symbol", help="Stock symbol (e.g. RELIANCE)")

    sub.add_parser("nightly", help="Run nightly pipeline")
    live_p = sub.add_parser("live", help="Start live minute-by-minute predictions")
    live_p.add_argument("--force", action="store_true",
                        help="Run even outside market hours (for testing)")
    sub.add_parser("retrain", help="Run weekly retrain")
    sub.add_parser("status", help="Check system status")

    upload_p = sub.add_parser("upload", help="Upload xlsx file for fundamentals")
    upload_p.add_argument("file", help="Path to xlsx file")

    sub.add_parser("serve", help="Start local API server for dashboard uploads")

    sent_p = sub.add_parser("sentiment-backfill", help="Backfill historical sentiment for a stock")
    sent_p.add_argument("symbol", help="Stock symbol (e.g. RELIANCE)")
    sent_p.add_argument("--days", type=int, default=500, help="Number of days to backfill (default 500)")

    args = parser.parse_args()

    if args.command == "seed":
        cmd_seed()
    elif args.command == "add":
        cmd_add(args.symbol)
    elif args.command == "backfill":
        cmd_backfill()
    elif args.command == "train":
        cmd_train(tune=args.tune, stock=args.stock)
    elif args.command == "predict":
        cmd_predict(args.symbol)
    elif args.command == "nightly":
        cmd_nightly()
    elif args.command == "live":
        cmd_live(force=args.force)
    elif args.command == "retrain":
        cmd_retrain()
    elif args.command == "status":
        cmd_status()
    elif args.command == "upload":
        cmd_upload(args.file)
    elif args.command == "sentiment-backfill":
        cmd_sentiment_backfill(args.symbol, days=args.days)
    elif args.command == "serve":
        cmd_serve()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
