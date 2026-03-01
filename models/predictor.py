"""
Load trained model and run inference for predictions.
"""

from __future__ import annotations
import logging
import pandas as pd
from data import supabase_client as db
from models.trainer import StockPredictor

logger = logging.getLogger(__name__)

_cached_model: StockPredictor | None = None
_cached_version: str | None = None


def load_model(version: str | None = None) -> StockPredictor:
    """Load model from Supabase Storage. Caches in memory."""
    global _cached_model, _cached_version

    if version is None:
        version = db.get_latest_model_version()
        if version is None:
            raise ValueError("No trained model found in model_performance table")

    if _cached_model is not None and _cached_version == version:
        return _cached_model

    logger.info(f"Loading model version: {version}")
    model_bytes = db.download_model(version)
    model = StockPredictor.from_bytes(model_bytes)
    model.version = version

    _cached_model = model
    _cached_version = version
    return model


def predict_for_stock(model: StockPredictor, features: pd.DataFrame) -> dict | None:
    """
    Run prediction for a single stock given its feature row(s).
    Uses the latest row for prediction.
    Returns prediction dict or None.
    """
    if features.empty:
        return None

    # Use the latest row
    latest = features.iloc[[-1]]

    # Ensure feature columns match model's expected features
    expected = model.feature_names
    missing = set(expected) - set(latest.columns)
    for col in missing:
        latest[col] = 0

    # Reorder to match training order
    latest = latest[expected]

    result = model.predict(latest)
    row = result.iloc[0]

    # Get top features for this prediction
    top_features = model.get_feature_importance(top_n=5)

    return {
        "predicted_direction": row["predicted_direction"],
        "raw_direction": row.get("raw_direction", row["predicted_direction"]),
        "predicted_pct_change": float(row["predicted_pct_change"]),
        "confidence_score": float(row["confidence_score"]),
        "top_features": top_features,
    }


def predict_batch(model: StockPredictor,
                  stock_features: dict[int, pd.DataFrame]) -> list[dict]:
    """
    Run predictions for multiple stocks.
    Args:
        stock_features: {stock_id: features_df}
    Returns list of prediction dicts with stock_id.
    """
    predictions = []
    for stock_id, features in stock_features.items():
        result = predict_for_stock(model, features)
        if result:
            result["stock_id"] = stock_id
            predictions.append(result)

    logger.info(f"Generated {len(predictions)} predictions")
    return predictions
