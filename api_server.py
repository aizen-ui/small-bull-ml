"""
Lightweight API server for the ML Stock dashboard.
Handles xlsx file uploads and triggers training/fundamentals extraction.
Run via: python app.py serve
"""

import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}

app = Flask(__name__)
CORS(app)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/upload", methods=["POST"])
def upload_xlsx():
    """
    Upload an xlsx file for a stock.
    Expects multipart form with 'file' field.
    Optional 'symbol' field to associate with a stock.
    Returns extracted fundamental features.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Invalid file type: {ext}. Use .xlsx or .xls"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOADS_DIR, filename)
    file.save(filepath)

    # Extract fundamental features
    from features.fundamentals_features import extract_fundamentals_features
    features = extract_fundamentals_features(filepath)

    symbol = request.form.get("symbol", "")

    return jsonify({
        "message": f"Uploaded {filename} successfully",
        "symbol": symbol,
        "filename": filename,
        "features_extracted": len(features),
        "features": {k: (v if v == v else None) for k, v in features.items()},  # NaN -> null
    })


@app.route("/api/uploads", methods=["GET"])
def list_uploads():
    """List all uploaded xlsx files."""
    files = []
    for fname in os.listdir(UPLOADS_DIR):
        if fname.endswith((".xlsx", ".xls")):
            fpath = os.path.join(UPLOADS_DIR, fname)
            files.append({
                "filename": fname,
                "size_kb": round(os.path.getsize(fpath) / 1024, 1),
            })
    return jsonify({"files": files})


@app.route("/api/uploads/<filename>", methods=["DELETE"])
def delete_upload(filename):
    """Delete an uploaded xlsx file."""
    filepath = os.path.join(UPLOADS_DIR, secure_filename(filename))
    if os.path.isfile(filepath):
        os.remove(filepath)
        return jsonify({"message": f"Deleted {filename}"})
    return jsonify({"error": "File not found"}), 404


import threading
import time
import uuid

# In-memory store for training job status
_train_jobs: dict = {}


@app.route("/api/train", methods=["POST"])
def trigger_training():
    """
    Start model training in a background thread.
    Returns a job_id immediately; poll /api/train/<job_id> for status.
    """
    body = request.get_json(silent=True) or {}
    tune = body.get("tune", False)

    job_id = str(uuid.uuid4())[:8]
    _train_jobs[job_id] = {"status": "running", "started": time.time()}

    def _run_training():
        try:
            from features.feature_builder import build_training_dataset, get_temporal_split
            from models.trainer import StockPredictor, tune_hyperparameters, generate_version
            from models.model_registry import save_model

            X, y_dir, y_pct = build_training_dataset(days=500)
            X_train, X_test, y_dir_train, y_dir_test = get_temporal_split(X, y_dir)
            _, _, y_pct_train, y_pct_test = get_temporal_split(X, y_pct)

            params = None
            if tune:
                params = tune_hyperparameters(X_train, y_dir_train, y_pct_train, n_trials=30)

            model = StockPredictor()
            model.version = generate_version()
            model.train(X_train, y_dir_train, y_pct_train, params=params)

            metrics = model.evaluate(X_test, y_dir_test, y_pct_test)
            version = save_model(model, metrics)

            _train_jobs[job_id] = {
                "status": "completed",
                "message": f"Model {version} trained successfully",
                "version": version,
                "metrics": metrics,
                "samples": {"train": len(X_train), "test": len(X_test)},
                "features": X.shape[1],
                "elapsed": round(time.time() - _train_jobs[job_id]["started"], 1),
            }
        except Exception as e:
            logger.exception("Training failed")
            _train_jobs[job_id] = {
                "status": "failed",
                "error": str(e),
                "elapsed": round(time.time() - _train_jobs[job_id]["started"], 1),
            }

    t = threading.Thread(target=_run_training, daemon=True)
    t.start()

    return jsonify({"job_id": job_id, "status": "running"})


@app.route("/api/train/<job_id>", methods=["GET"])
def get_training_status(job_id):
    """Poll training job status."""
    job = _train_jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/api/prices/<symbol>", methods=["GET"])
def get_prices(symbol):
    """Get recent daily price history + past predictions for charting."""
    try:
        from data.supabase_client import get_stock_id, query

        sym = symbol.upper()
        if not sym.endswith(".NS") and not sym.endswith(".BO"):
            sym += ".NS"

        sid = get_stock_id(sym)
        if sid is None:
            return jsonify({"error": f"Stock {sym} not found in DB"}), 404

        days = int(request.args.get("days", 180))
        rows = query("daily_prices", select="date,open,high,low,close,volume",
                      filters={"stock_id": sid}, order="-date", limit=days)
        rows.reverse()

        # Past predictions for model performance overlay
        preds = query("predictions", filters={"stock_id": sid},
                       order="-prediction_timestamp", limit=100)
        price_by_date = {r["date"]: float(r["close"]) for r in rows}
        sorted_dates = sorted(price_by_date.keys())
        pred_points = []
        for p in reversed(preds):
            ts = p.get("prediction_timestamp", "")
            pred_date = ts[:10] if ts else ""
            base = price_by_date.get(pred_date)
            if base is None:
                for d in reversed(sorted_dates):
                    if d <= pred_date:
                        base = price_by_date[d]
                        break
            if base:
                projected = base * (1 + float(p.get("predicted_pct_change", 0)))
                actual_pct = p.get("actual_pct_change")
                actual_price = base * (1 + float(actual_pct)) if actual_pct is not None else None
                pred_points.append({
                    "date": pred_date,
                    "predicted_price": round(projected, 2),
                    "actual_price": round(actual_price, 2) if actual_price else None,
                    "direction": p.get("predicted_direction"),
                    "confidence": float(p.get("confidence_score", 0)),
                    "was_correct": p.get("was_correct"),
                    "type": p.get("prediction_type"),
                })

        return jsonify({"symbol": sym, "prices": rows, "past_predictions": pred_points})

    except Exception as e:
        logger.exception(f"Failed to get prices for {symbol}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/predict/<symbol>", methods=["GET"])
def predict_stock(symbol):
    """Run prediction for a single stock. Returns prediction + backtest for chart."""
    try:
        from data.supabase_client import get_stock_id, query
        from features.feature_builder import build_features_for_stock
        from models.predictor import load_model, predict_for_stock
        import numpy as np
        import pandas as pd

        # Normalize symbol
        sym = symbol.upper()
        if not sym.endswith(".NS") and not sym.endswith(".BO"):
            sym += ".NS"

        sid = get_stock_id(sym)
        if sid is None:
            return jsonify({"error": f"Stock {sym} not found in DB"}), 404

        model = load_model()
        features = build_features_for_stock(sid, days=200)

        if features is None or len(features) == 0:
            return jsonify({"error": f"No features available for {sym}"}), 400

        # Current prediction (latest row)
        result = predict_for_stock(model, features)
        if result is None:
            return jsonify({"error": "Prediction failed"}), 500

        result["symbol"] = sym

        # Recent prices for chart
        rows = query("daily_prices", select="date,open,high,low,close,volume",
                      filters={"stock_id": sid}, order="-date", limit=180)
        rows.reverse()
        result["prices"] = rows

        # ── Predicted price vs actual price for chart ──
        # The model now predicts DETRENDED residual change (not raw returns).
        # To reconstruct predicted price:
        #   trend = EMA(20) of close
        #   residual_now = close / trend - 1
        #   predicted_residual_change = model output
        #   predicted_price = trend * (1 + residual_now + predicted_residual_change)
        #
        # This removes the lag because the trend component is handled
        # separately from the mean-reverting residual the model predicts.
        FORWARD_DAYS = 5
        TREND_WINDOW = 20
        # Use ALL feature rows including recent ones without targets —
        # so the orange line extends to the latest date with no gap
        bt_rows = min(120, len(features))
        bt_features = features.iloc[-bt_rows:]

        expected = model.feature_names
        bt_X = bt_features.copy()
        for col in set(expected) - set(bt_X.columns):
            bt_X[col] = 0
        bt_X = bt_X[expected]
        bt_X = bt_X.replace([np.inf, -np.inf], np.nan).fillna(0).clip(-1e9, 1e9)

        bt_preds = model.predict(bt_X)

        price_by_date = {r["date"]: float(r["close"]) for r in rows}
        sorted_dates = sorted(price_by_date.keys())
        date_to_idx = {d: i for i, d in enumerate(sorted_dates)}

        # Compute trend (EMA-20) for price reconstruction
        close_series = pd.Series(
            [price_by_date[d] for d in sorted_dates],
            index=sorted_dates
        )
        trend_series = close_series.ewm(span=TREND_WINDOW, adjust=False).mean()

        # Build prediction date list from features
        bt_dates = []
        for i in range(len(bt_features)):
            d = str(bt_features.iloc[i]["date"]) if "date" in bt_features.columns else ""
            bt_dates.append(d)

        backtest = []
        correct_count = 0
        total_count = 0

        for i, pred_date in enumerate(bt_dates):
            base_price = price_by_date.get(pred_date)
            if base_price is None:
                continue

            pred_row = bt_preds.iloc[i]
            residual_change = float(pred_row["predicted_pct_change"])
            direction = pred_row.get("raw_direction", pred_row["predicted_direction"])
            confidence = float(pred_row["confidence_score"])

            # Align residual sign with classifier direction
            if direction == "down" and residual_change > 0:
                residual_change = -abs(residual_change)
            elif direction == "up" and residual_change < 0:
                residual_change = abs(residual_change)

            # Reconstruct predicted price from detrended residual
            trend_now = trend_series.get(pred_date, base_price)
            residual_now = base_price / trend_now - 1 if trend_now else 0
            predicted_future_residual = residual_now + residual_change
            predicted_price = trend_now * (1 + predicted_future_residual)

            # Track accuracy only where we have actual future prices
            idx = date_to_idx.get(pred_date)
            if idx is not None:
                target_idx = idx + FORWARD_DAYS
                if target_idx < len(sorted_dates):
                    actual_future_price = price_by_date[sorted_dates[target_idx]]
                    actual_dir = "up" if actual_future_price > base_price else "down"
                    if direction in ("up", "down"):
                        total_count += 1
                        if direction == actual_dir:
                            correct_count += 1

            # Plot at prediction date D — extends all the way to latest date
            backtest.append({
                "date": pred_date,
                "actual_price": round(base_price, 2),
                "model_price": round(predicted_price, 2),
                "direction": direction,
                "confidence": round(confidence, 4),
            })

        dir_accuracy = round(correct_count / total_count, 4) if total_count > 0 else 0
        result["backtest"] = backtest
        result["backtest_stats"] = {
            "directional_accuracy": dir_accuracy,
            "total_signals": total_count,
            "correct_signals": correct_count,
        }

        return jsonify(result)

    except Exception as e:
        logger.exception(f"Prediction failed for {symbol}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/train/stock", methods=["POST"])
def train_single_stock():
    """
    Train model for a single stock in a background thread.
    Expects JSON: {"symbol": "RELIANCE", "tune": false}
    """
    body = request.get_json(silent=True) or {}
    symbol = body.get("symbol", "")
    tune = body.get("tune", False)

    if not symbol:
        return jsonify({"error": "symbol is required"}), 400

    sym = symbol.upper()
    if not sym.endswith(".NS") and not sym.endswith(".BO"):
        sym += ".NS"

    job_id = str(uuid.uuid4())[:8]
    _train_jobs[job_id] = {"status": "running", "started": time.time(), "symbol": sym}

    def _run_stock_training():
        try:
            from data.supabase_client import get_stock_id
            from features.feature_builder import (
                build_training_dataset, get_temporal_split,
            )
            from models.trainer import StockPredictor, tune_hyperparameters, generate_version
            from models.model_registry import save_model

            sid = get_stock_id(sym)
            if sid is None:
                raise ValueError(f"Stock {sym} not found in DB")

            X, y_dir, y_pct = build_training_dataset(stock_ids=[sid], days=500)
            X_train, X_test, y_dir_train, y_dir_test = get_temporal_split(X, y_dir)
            _, _, y_pct_train, y_pct_test = get_temporal_split(X, y_pct)

            params = None
            if tune:
                params = tune_hyperparameters(X_train, y_dir_train, y_pct_train, n_trials=30)

            # Train model (no two-pass — avoids data leakage)
            model = StockPredictor()
            model.version = generate_version()
            model.train(X_train, y_dir_train, y_pct_train, params=params)

            # Calibrate confidence threshold on test set
            bt_test = model.backtest(X_test, y_dir_test, y_pct_test)
            model.calibrate_threshold(bt_test)

            metrics = model.evaluate(X_test, y_dir_test, y_pct_test)
            version = save_model(model, metrics)

            _train_jobs[job_id] = {
                "status": "completed",
                "message": f"Model {version} trained on {sym}",
                "version": version,
                "symbol": sym,
                "metrics": metrics,
                "samples": {"train": len(X_train), "test": len(X_test)},
                "features": X.shape[1],
                "elapsed": round(time.time() - _train_jobs[job_id]["started"], 1),
            }
        except Exception as e:
            logger.exception(f"Training failed for {sym}")
            _train_jobs[job_id] = {
                "status": "failed",
                "error": str(e),
                "symbol": sym,
                "elapsed": round(time.time() - _train_jobs[job_id]["started"], 1),
            }

    t = threading.Thread(target=_run_stock_training, daemon=True)
    t.start()

    return jsonify({"job_id": job_id, "status": "running", "symbol": sym})


@app.route("/api/stocks", methods=["GET"])
def list_stocks():
    """List all stocks from DB."""
    try:
        from data.supabase_client import query
        stocks = query("stocks", order="symbol", limit=200)
        return jsonify({"stocks": stocks})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sentiment/<symbol>", methods=["GET"])
def get_sentiment(symbol):
    """
    Get live sentiment for a stock.
    Fetches news via RSS, scores headlines, and returns sentiment analysis.
    On weekdays, also tries IndianAPI for richer data.
    """
    try:
        from data.supabase_client import get_stock_id, query
        from data.rss_fetcher import fetch_all_news_for_stock
        from features.sentiment_scorer import score_headline, score_news_batch
        import datetime as dt

        # Resolve stock
        sym = symbol.upper()
        if not sym.endswith(".NS") and not sym.endswith(".BO"):
            sym += ".NS"

        sid = get_stock_id(sym)
        stock_info = None
        if sid:
            rows = query("stocks", filters={"id": sid}, limit=1)
            stock_info = rows[0] if rows else None

        stock_name = stock_info.get("company_name", sym.replace(".NS", "")) if stock_info else sym.replace(".NS", "")
        sector = stock_info.get("sector", "") if stock_info else ""
        clean_sym = sym.replace(".NS", "").replace(".BO", "")

        # Fetch RSS news
        news = fetch_all_news_for_stock(stock_name, clean_sym, sector, max_age_days=2)

        # Score each category
        stock_scores = score_news_batch(news.get("stock", []))
        industry_scores = score_news_batch(news.get("industry", []))
        market_scores = score_news_batch(news.get("market", []))

        # Score individual headlines for display
        scored_headlines = []
        for category, items in [("stock", news.get("stock", [])),
                                 ("industry", news.get("industry", [])),
                                 ("market", news.get("market", []))]:
            for item in items[:20]:
                title = item.get("title", "")
                score = score_headline(title)
                scored_headlines.append({
                    "title": title,
                    "score": round(score, 4),
                    "category": category,
                    "timestamp": item.get("timestamp", ""),
                    "link": item.get("link", ""),
                })
        scored_headlines.sort(key=lambda x: abs(x["score"]), reverse=True)

        # Try IndianAPI on weekdays for extra news
        indianapi_news = []
        today = dt.date.today()
        is_weekday = today.weekday() < 5
        if is_weekday and stock_info and stock_info.get("indianapi_name"):
            try:
                from data.indianapi_client import get_stock as api_get_stock
                data = api_get_stock(stock_info["indianapi_name"])
                if data and data.get("recentNews"):
                    for n in data["recentNews"][:15]:
                        title = n.get("title", "")
                        score = score_headline(title)
                        indianapi_news.append({
                            "title": title,
                            "score": round(score, 4),
                            "date": n.get("date", ""),
                            "source": "IndianAPI",
                            "link": n.get("link", ""),
                        })
            except Exception as e:
                logger.warning(f"IndianAPI sentiment fetch failed: {e}")

        # Historical sentiment from DB
        history = []
        if sid:
            rows = query("sentiment_scores", filters={"stock_id": sid},
                          order="-date", limit=30)
            history = [{
                "date": r["date"],
                "weighted_sentiment": r.get("score", r.get("weighted_sentiment", 0)),
                "avg_sentiment": r.get("score", r.get("avg_sentiment", 0)),
                "news_count": r.get("news_count", 1),
            } for r in rows]

        # Overall sentiment (combine stock + IndianAPI)
        all_stock_headlines = news.get("stock", [])
        if indianapi_news:
            all_stock_headlines = all_stock_headlines + [
                {"title": n["title"], "timestamp": n.get("date", "")}
                for n in indianapi_news
            ]
        overall = score_news_batch(all_stock_headlines)

        return jsonify({
            "symbol": sym,
            "company_name": stock_name,
            "sector": sector,
            "overall": overall,
            "stock_sentiment": stock_scores,
            "industry_sentiment": industry_scores,
            "market_sentiment": market_scores,
            "headlines": scored_headlines[:30],
            "indianapi_news": indianapi_news,
            "history": history,
            "is_weekday": is_weekday,
        })

    except Exception as e:
        logger.exception(f"Sentiment fetch failed for {symbol}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/sentiment/market", methods=["GET"])
def get_market_sentiment():
    """
    Get overall market / Nifty sentiment.
    Uses market RSS feeds + IndianAPI trending on weekdays.
    """
    try:
        from data.rss_fetcher import fetch_market_news
        from features.sentiment_scorer import score_headline, score_news_batch
        from data.supabase_client import query
        import datetime as dt

        # RSS market news
        market_news = fetch_market_news(max_age_days=3)
        market_scores = score_news_batch(market_news)

        # Score headlines
        scored = []
        for item in market_news[:30]:
            title = item.get("title", "")
            score = score_headline(title)
            scored.append({
                "title": title,
                "score": round(score, 4),
                "timestamp": item.get("timestamp", ""),
                "link": item.get("link", ""),
            })
        scored.sort(key=lambda x: abs(x["score"]), reverse=True)

        # IndianAPI trending / market data on weekdays
        trending_data = None
        today = dt.date.today()
        if today.weekday() < 5:
            try:
                from data.indianapi_client import get_trending
                trending_data = get_trending()
            except Exception as e:
                logger.warning(f"IndianAPI trending fetch failed: {e}")

        # Nifty history from market_context table
        nifty_history = []
        rows = query("market_context", order="-date", limit=30)
        for r in rows:
            nifty_history.append({
                "date": r["date"],
                "nifty50_close": r.get("nifty50_close"),
                "nifty50_change_pct": r.get("nifty50_change_pct"),
                "market_breadth_score": r.get("market_breadth_score"),
            })

        # Overall market sentiment label
        ws = market_scores.get("weighted_sentiment", 0)
        if ws > 0.1:
            label = "Bullish"
        elif ws < -0.1:
            label = "Bearish"
        else:
            label = "Neutral"

        return jsonify({
            "label": label,
            "overall": market_scores,
            "headlines": scored[:20],
            "trending": trending_data,
            "nifty_history": nifty_history,
        })

    except Exception as e:
        logger.exception("Market sentiment fetch failed")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=5000, debug=True)
