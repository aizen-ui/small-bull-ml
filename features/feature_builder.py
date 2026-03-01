"""
Combines all feature sources into a single ML-ready feature matrix.
Pulls from: daily_prices, technical_indicators, sentiment_scores,
analyst_data, market_context, RSS news, Nifty index, industry peers,
and company fundamentals (xlsx).
"""

from __future__ import annotations
import logging
from datetime import date, timedelta
import pandas as pd
import numpy as np
from data import supabase_client as db
from features.technical_indicators import compute_ml_features
from features.fundamentals_features import (
    get_fundamentals_for_stock,
    FUNDAMENTAL_FEATURE_COLS,
)
from config.settings import NEUTRAL_THRESHOLD

logger = logging.getLogger(__name__)


def _get_stock_info(stock_id: int) -> dict:
    """Get stock symbol, sector, company_name from stocks table."""
    rows = db.query("stocks", filters={"id": stock_id}, limit=1)
    if rows:
        return rows[0]
    return {}


def _get_industry_peers_avg(stock_id: int, sector: str, days: int) -> pd.DataFrame:
    """
    Compute average daily returns of industry peers (same sector).
    Returns DataFrame with columns: date, industry_avg_return, industry_volatility.
    """
    # Get all stock IDs in the same sector
    all_stocks = db.query("stocks", filters={"is_active": True}, limit=200)
    peer_ids = [s["id"] for s in all_stocks
                if s.get("sector") == sector and s["id"] != stock_id]

    if not peer_ids:
        return pd.DataFrame(columns=["date", "industry_avg_return", "industry_volatility"])

    # Collect daily returns for peers (sample up to 10 to keep it fast)
    peer_ids_sample = peer_ids[:10]
    peer_returns = []
    for pid in peer_ids_sample:
        prices = db.get_daily_prices(pid, days=days)
        if len(prices) < 20:
            continue
        pdf = pd.DataFrame(prices)
        pdf["date"] = pd.to_datetime(pdf["date"]).dt.date
        pdf = pdf.sort_values("date")
        pdf["ret"] = pdf["close"].pct_change()
        peer_returns.append(pdf[["date", "ret"]].rename(columns={"ret": f"ret_{pid}"}))

    if not peer_returns:
        return pd.DataFrame(columns=["date", "industry_avg_return", "industry_volatility"])

    # Merge all peer returns on date
    merged = peer_returns[0]
    for pr in peer_returns[1:]:
        merged = merged.merge(pr, on="date", how="outer")
    merged = merged.sort_values("date")

    ret_cols = [c for c in merged.columns if c.startswith("ret_")]
    merged["industry_avg_return"] = merged[ret_cols].mean(axis=1)
    merged["industry_volatility"] = merged[ret_cols].std(axis=1)
    merged = merged[["date", "industry_avg_return", "industry_volatility"]]

    return merged


def _get_nifty_features(days: int) -> pd.DataFrame:
    """
    Build Nifty 50 index features: daily return, 5d/20d momentum, volatility.
    Uses ^NSEI daily prices stored during nightly pipeline.
    """
    # Nifty index is stored as a stock with symbol "^NSEI" or we can query market_context
    # Use market_context which has nifty50_change_pct
    rows = db.query("market_context", order="-date", limit=days)
    if not rows:
        return pd.DataFrame(columns=[
            "date", "nifty_daily_return", "nifty_5d_momentum",
            "nifty_20d_momentum", "nifty_volatility_20d"
        ])

    ndf = pd.DataFrame(rows)
    ndf["date"] = pd.to_datetime(ndf["date"]).dt.date
    ndf = ndf.sort_values("date").reset_index(drop=True)

    # nifty50_change_pct is already daily return
    ndf["nifty_daily_return"] = pd.to_numeric(ndf["nifty50_change_pct"], errors="coerce").fillna(0)

    # Compute rolling features from the daily return
    ndf["nifty_5d_momentum"] = ndf["nifty_daily_return"].rolling(5).sum()
    ndf["nifty_20d_momentum"] = ndf["nifty_daily_return"].rolling(20).sum()
    ndf["nifty_volatility_20d"] = ndf["nifty_daily_return"].rolling(20).std()

    return ndf[["date", "nifty_daily_return", "nifty_5d_momentum",
                "nifty_20d_momentum", "nifty_volatility_20d"]]


def _get_rss_sentiment(stock_name: str, symbol: str, sector: str) -> dict:
    """
    Fetch RSS news and score sentiment for stock + industry + market.
    Returns dict with sentiment features.
    """
    try:
        from data.rss_fetcher import fetch_all_news_for_stock
        from features.sentiment_scorer import score_news_batch

        news = fetch_all_news_for_stock(stock_name, symbol, sector, max_age_days=2)

        stock_scores = score_news_batch(news.get("stock", []))
        industry_scores = score_news_batch(news.get("industry", []))
        market_scores = score_news_batch(news.get("market", []))

        return {
            "rss_stock_sentiment": stock_scores["weighted_sentiment"],
            "rss_stock_news_count": stock_scores["news_count"],
            "rss_industry_sentiment": industry_scores["weighted_sentiment"],
            "rss_industry_news_count": industry_scores["news_count"],
            "rss_market_sentiment": market_scores["weighted_sentiment"],
            "rss_market_news_count": market_scores["news_count"],
        }
    except Exception as e:
        logger.debug(f"RSS sentiment fetch failed: {e}")
        return {
            "rss_stock_sentiment": 0, "rss_stock_news_count": 0,
            "rss_industry_sentiment": 0, "rss_industry_news_count": 0,
            "rss_market_sentiment": 0, "rss_market_news_count": 0,
        }


def build_features_for_stock(stock_id: int, days: int = 500) -> pd.DataFrame | None:
    """
    Build complete feature matrix for one stock.
    Returns DataFrame with all features + target columns, one row per trading day.

    Feature groups:
    - Technical indicators (19 features)
    - Sentiment from DB (5 features)
    - Analyst data (3 features)
    - Market context (2 features)
    - Calendar (4 features)
    - Nifty index momentum (4 features)
    - Industry peer performance (2 features)
    - RSS news sentiment (6 features)
    - Company fundamentals from xlsx (20 features, static per stock)
    """
    # 1. Get daily prices
    prices = db.get_daily_prices(stock_id, days=days)
    if len(prices) < 60:
        logger.warning(f"Stock {stock_id}: only {len(prices)} days, need 60+")
        return None

    price_df = pd.DataFrame(prices)
    price_df["date"] = pd.to_datetime(price_df["date"]).dt.date
    price_df = price_df.sort_values("date").reset_index(drop=True)

    # Get stock info for sector/industry features
    stock_info = _get_stock_info(stock_id)
    symbol = stock_info.get("symbol", "")
    sector = stock_info.get("sector", "")
    company_name = stock_info.get("company_name", "")

    # 2. Compute technical features
    tech_features = compute_ml_features(price_df)

    # 3. Get sentiment scores (from DB / indianapi)
    sentiment_rows = db.query(
        "sentiment_scores",
        filters={"stock_id": stock_id},
        order="-date",
        limit=days,
    )
    if sentiment_rows:
        sent_df = pd.DataFrame(sentiment_rows)
        sent_df["date"] = pd.to_datetime(sent_df["date"]).dt.date
        # Live table has single 'score' column — map to feature names
        if "score" in sent_df.columns and "weighted_sentiment" not in sent_df.columns:
            sent_df["weighted_sentiment"] = sent_df["score"]
            sent_df["avg_sentiment"] = sent_df["score"]
            sent_df["max_sentiment"] = sent_df["score"]
            sent_df["min_sentiment"] = sent_df["score"]
            sent_df["news_count"] = 1  # unknown from single-score schema
        sent_df = sent_df[["date", "avg_sentiment", "max_sentiment",
                           "min_sentiment", "weighted_sentiment", "news_count"]]
    else:
        sent_df = pd.DataFrame(columns=["date", "avg_sentiment", "max_sentiment",
                                         "min_sentiment", "weighted_sentiment",
                                         "news_count"])

    # 4. Get analyst data
    analyst_rows = db.query(
        "analyst_data",
        filters={"stock_id": stock_id},
        order="-date",
        limit=days,
    )
    if analyst_rows:
        analyst_df = pd.DataFrame(analyst_rows)
        analyst_df["date"] = pd.to_datetime(analyst_df["date"]).dt.date
        # Encode recommendation
        rec_map = {"Strong Buy": 2, "Buy": 2, "Hold": 1, "Sell": 0,
                    "Strong Sell": 0, "Outperform": 2, "Underperform": 0}
        analyst_df["recommendation_encoded"] = analyst_df["recommendation"].map(
            rec_map
        ).fillna(1)
        # Encode risk meter
        risk_map = {"Low": 0, "Moderate": 1, "High": 2, "Very High": 3}
        analyst_df["risk_meter_encoded"] = analyst_df["risk_meter"].map(
            risk_map
        ).fillna(1)
        analyst_df = analyst_df[["date", "upside_pct", "recommendation_encoded",
                                  "risk_meter_encoded"]]
    else:
        analyst_df = pd.DataFrame(columns=["date", "upside_pct",
                                            "recommendation_encoded",
                                            "risk_meter_encoded"])

    # 5. Get market context
    market_rows = db.query("market_context", order="-date", limit=days)
    if market_rows:
        market_df = pd.DataFrame(market_rows)
        market_df["date"] = pd.to_datetime(market_df["date"]).dt.date
        market_df = market_df[["date", "nifty50_change_pct", "market_breadth_score"]]
    else:
        market_df = pd.DataFrame(columns=["date", "nifty50_change_pct",
                                           "market_breadth_score"])

    # 6. Nifty index features (momentum, volatility)
    nifty_df = _get_nifty_features(days)

    # 7. Industry peer features
    industry_df = _get_industry_peers_avg(stock_id, sector, days) if sector else \
        pd.DataFrame(columns=["date", "industry_avg_return", "industry_volatility"])

    # 8. Merge everything on date
    features = tech_features.copy()
    features["date"] = pd.to_datetime(features["date"]).dt.date if not isinstance(
        features["date"].iloc[0], date) else features["date"]

    for df_to_merge in [sent_df, analyst_df, market_df, nifty_df, industry_df]:
        if not df_to_merge.empty:
            df_to_merge = df_to_merge.copy()
            if len(df_to_merge) > 0:
                if isinstance(df_to_merge["date"].iloc[0], str):
                    df_to_merge["date"] = pd.to_datetime(df_to_merge["date"]).dt.date
            features = features.merge(df_to_merge, on="date", how="left")

    # 9. Forward-fill sparse columns (sentiment/analyst/market refreshed on rotation)
    sparse_cols = ["avg_sentiment", "max_sentiment", "min_sentiment",
                   "weighted_sentiment", "news_count", "upside_pct",
                   "recommendation_encoded", "risk_meter_encoded",
                   "nifty50_change_pct", "market_breadth_score",
                   "nifty_daily_return", "nifty_5d_momentum",
                   "nifty_20d_momentum", "nifty_volatility_20d",
                   "industry_avg_return", "industry_volatility"]
    for col in sparse_cols:
        if col in features.columns:
            features[col] = features[col].ffill().fillna(0)

    # 10. RSS sentiment — only apply to last row (inference), NOT to training history
    # For training rows, RSS sentiment columns will be 0 (no look-ahead bias)
    # RSS is only useful at prediction time, not for historical training
    rss_cols = ["rss_stock_sentiment", "rss_stock_news_count",
                "rss_industry_sentiment", "rss_industry_news_count",
                "rss_market_sentiment", "rss_market_news_count"]
    for col in rss_cols:
        features[col] = 0.0
    # Tag the last row with live RSS (only matters during prediction)
    if len(features) > 0:
        try:
            rss_features = _get_rss_sentiment(company_name, symbol, sector)
            for k, v in rss_features.items():
                features.loc[features.index[-1], k] = v
        except Exception:
            pass

    # 11. Company fundamentals from xlsx (static features per stock)
    fund_features = get_fundamentals_for_stock(symbol)
    for col in FUNDAMENTAL_FEATURE_COLS:
        features[col] = fund_features.get(col, 0) if fund_features else 0

    # 12. Sector encoding (categorical — lets model learn sector-specific patterns)
    sector_map = {
        "Energy": 0, "IT": 1, "Financials": 2, "FMCG": 3, "Automobile": 4,
        "Materials": 5, "Industrials": 6, "Healthcare": 7, "Telecom": 8,
        "Consumer Discretionary": 9, "Real Estate": 10,
    }
    features["sector_encoded"] = sector_map.get(sector, -1)
    features["is_nifty50"] = int(stock_info.get("is_nifty50", False))

    # 13. Market cap category
    cap_map = {"largecap": 2, "midcap": 1, "smallcap": 0}
    features["market_cap_cat"] = cap_map.get(
        stock_info.get("market_cap_category", ""), 1
    )

    # 14. Calendar features
    date_series = pd.to_datetime(features["date"])
    features["day_of_week"] = date_series.dt.dayofweek
    features["month"] = date_series.dt.month
    features["is_month_end"] = (
        date_series.dt.is_month_end |
        ((date_series + pd.Timedelta(days=1)).dt.is_month_end) |
        ((date_series + pd.Timedelta(days=2)).dt.is_month_end)
    ).astype(int)

    # F&O expiry week (last Thursday of month)
    def is_expiry_week(d):
        from calendar import monthrange
        last_day = monthrange(d.year, d.month)[1]
        last_date = date(d.year, d.month, last_day)
        while last_date.weekday() != 3:
            last_date -= timedelta(days=1)
        expiry_week_start = last_date - timedelta(days=last_date.weekday())
        return expiry_week_start <= d <= last_date

    features["is_expiry_week"] = date_series.apply(
        lambda x: int(is_expiry_week(x.date()))
    )

    # 15. Market regime (bull/bear/high-vol)
    if "nifty_volatility_20d" in features.columns and "nifty_20d_momentum" in features.columns:
        vol_75 = features["nifty_volatility_20d"].quantile(0.75)
        features["market_regime"] = np.where(
            features["nifty_volatility_20d"] > vol_75, 2,  # high-vol
            np.where(features["nifty_20d_momentum"] > 0, 0, 1)  # bull / bear
        )
    else:
        features["market_regime"] = 0

    # 16. Build target: DETRENDED 5-day forward residual return
    #
    # Raw forward returns cause tree models to lag because they learn to
    # extrapolate recent trends. Instead we:
    #   1. Compute a 20-day EMA trend for the stock
    #   2. Compute residual = close / trend - 1 (deviation from trend)
    #   3. Target = residual(D+5) - residual(D)  (change in deviation)
    #
    # This is stationary and mean-reverting — tree models can predict it
    # without producing the characteristic "echo lag".
    # We also store the raw forward return for reference.
    FORWARD_DAYS = 5
    TREND_WINDOW = 20
    DIRECTION_THRESHOLD = 0.005  # 0.5% residual threshold

    close = price_df["close"]
    trend = close.ewm(span=TREND_WINDOW, adjust=False).mean()
    residual = close / trend - 1  # % deviation from trend

    # Detrended target: change in residual over FORWARD_DAYS
    features["target_pct_change"] = residual.shift(-FORWARD_DAYS) - residual

    # Also store raw forward return (for price reconstruction in backtest)
    features["_raw_forward_return"] = (
        close.shift(-FORWARD_DAYS) - close
    ) / close

    # Store current trend value (needed to reconstruct predicted price)
    features["_trend"] = trend
    features["_close"] = close

    features["target_direction"] = np.where(
        features["target_pct_change"] > DIRECTION_THRESHOLD, "up",
        np.where(features["target_pct_change"] < -DIRECTION_THRESHOLD, "down", "neutral")
    )

    # Drop initial warmup rows (need 52-week indicators to be valid)
    features = features.iloc[60:]

    # For rows without a target (last FORWARD_DAYS rows), fill target with NaN
    # but KEEP them — the latest row is needed for live inference.
    # Training code will handle dropping NaN targets.

    return features.reset_index(drop=True)


def build_training_dataset(stock_ids: list[int] | None = None,
                           days: int = 500) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Build full training dataset across all (or selected) stocks.
    Returns (X, y_direction, y_pct_change).
    """
    if stock_ids is None:
        all_ids = db.get_all_stock_ids()
        stock_ids = list(all_ids.values())

    all_features = []
    for sid in stock_ids:
        df = build_features_for_stock(sid, days=days)
        if df is not None and len(df) > 0:
            df["stock_id"] = sid
            all_features.append(df)

    if not all_features:
        raise ValueError("No features could be built for any stock")

    combined = pd.concat(all_features, ignore_index=True)
    # Drop rows without valid targets (needed for training, not inference)
    combined = combined.dropna(subset=["target_pct_change"])
    combined = combined.sort_values("date").reset_index(drop=True)

    # Add cross-sectional rank features (rank within universe on each date)
    rank_cols = ["rsi_14", "momentum_10d", "pct_change_5d",
                 "volume_ratio", "adx_14", "volatility_20d",
                 "sma_20_distance", "pct_change_20d"]
    for col in rank_cols:
        if col in combined.columns:
            combined[f"{col}_rank"] = combined.groupby("date")[col].rank(pct=True)

    # Separate features and targets (exclude internal helper columns)
    target_cols = ["target_pct_change", "target_direction", "date", "stock_id",
                   "_raw_forward_return", "_trend", "_close"]
    feature_cols = [c for c in combined.columns if c not in target_cols]

    X = combined[feature_cols]
    y_direction = combined["target_direction"]
    y_pct_change = combined["target_pct_change"]

    # Replace infinities with NaN, then fill NaNs with median (not 0)
    X = X.replace([np.inf, -np.inf], np.nan)
    for col in X.columns:
        if X[col].isna().any():
            median_val = X[col].median()
            X[col] = X[col].fillna(median_val if pd.notna(median_val) else 0)
    # Clip extreme values to prevent float32 overflow
    X = X.clip(-1e9, 1e9)

    logger.info(
        f"Built training dataset: {X.shape[0]} samples, {X.shape[1]} features, "
        f"stocks={len(all_features)}"
    )

    return X, y_direction, y_pct_change


def add_backtest_error_features(X: pd.DataFrame,
                                 backtest_results: pd.DataFrame) -> pd.DataFrame:
    """
    Add rolling model-error features from backtest results.
    These teach the model about its own systematic biases.

    Features added:
    - bt_rolling_error_5d:  rolling mean prediction error (last 5)
    - bt_rolling_error_20d: rolling mean prediction error (last 20)
    - bt_rolling_bias:      signed bias (positive = model overestimates)
    - bt_rolling_accuracy:  rolling hit rate (last 20)
    - bt_abs_error_trend:   is error growing or shrinking

    Args:
        X: feature matrix (same row count as backtest_results)
        backtest_results: DataFrame from model.backtest()

    Returns:
        X with 5 new columns appended.
    """
    X = X.copy()
    err = backtest_results["error"].values
    correct = backtest_results["was_correct"].astype(float).values
    abs_err = backtest_results["abs_error"].values

    err_s = pd.Series(err)
    correct_s = pd.Series(correct)
    abs_err_s = pd.Series(abs_err)

    X["bt_rolling_error_5d"] = err_s.rolling(5, min_periods=1).mean().values
    X["bt_rolling_error_20d"] = err_s.rolling(20, min_periods=1).mean().values
    X["bt_rolling_bias"] = err_s.rolling(20, min_periods=1).sum().values
    X["bt_rolling_accuracy"] = correct_s.rolling(20, min_periods=1).mean().values
    X["bt_abs_error_trend"] = (
        abs_err_s.rolling(5, min_periods=1).mean().values -
        abs_err_s.rolling(20, min_periods=1).mean().values
    )

    # Fill any NaN from early rows
    for col in ["bt_rolling_error_5d", "bt_rolling_error_20d",
                "bt_rolling_bias", "bt_rolling_accuracy", "bt_abs_error_trend"]:
        X[col] = X[col].fillna(0)

    return X


def get_temporal_split(X: pd.DataFrame, y: pd.Series,
                       train_ratio: float = 0.8,
                       embargo_days: int = 10) -> tuple:
    """
    Temporal train/test split with purge + embargo gap.
    The embargo gap (default 10 trading days = 2 weeks) between train and
    test prevents label leakage from overlapping forward-return windows.
    Without this gap, the last train samples have labels that peek into the
    test period, inflating accuracy and selecting trend-following models.
    """
    split_idx = int(len(X) * train_ratio)
    # Purge: remove the last embargo_days from training set
    train_end = max(0, split_idx - embargo_days)
    return (
        X.iloc[:train_end], X.iloc[split_idx:],
        y.iloc[:train_end], y.iloc[split_idx:]
    )
