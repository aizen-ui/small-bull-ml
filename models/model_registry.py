"""
Track model versions, save/load models, record performance.
"""

from __future__ import annotations
import logging
from datetime import date
from models.trainer import StockPredictor, generate_version
from data import supabase_client as db

logger = logging.getLogger(__name__)


def save_model(model: StockPredictor, metrics: dict,
               prediction_type: str = "nightly") -> str:
    """
    Save model to Supabase Storage and record performance metrics.
    Returns the model version string.
    """
    version = model.version or generate_version()
    model.version = version

    # Upload model bytes to Supabase Storage
    logger.info(f"Uploading model {version} to Supabase Storage...")
    model_bytes = model.to_bytes()
    db.upload_model(model_bytes, version)

    # Record performance metrics (only include columns that exist in the DB)
    perf_row = {
        "model_version": version,
        "evaluation_date": date.today().isoformat(),
        "prediction_type": prediction_type,
        "accuracy": metrics.get("accuracy"),
        "directional_accuracy": metrics.get("directional_accuracy"),
    }
    # Optional columns — only include if the DB has them
    optional = {
        "precision_up": metrics.get("precision_up"),
        "recall_up": metrics.get("recall_up"),
        "f1_up": metrics.get("f1_up"),
        "mae": metrics.get("mae"),
        "rmse": metrics.get("rmse"),
    }
    try:
        full_row = {**perf_row, **optional}
        db.upsert_model_performance(full_row)
    except Exception:
        logger.warning("Some metric columns missing in DB, saving core metrics only")
        db.upsert_model_performance(perf_row)

    logger.info(f"Model {version} saved. Metrics: {metrics}")
    return version


def get_model_history() -> list[dict]:
    """Get all model versions and their performance."""
    return db.query("model_performance", order="-evaluation_date")


def get_latest_version() -> str | None:
    """Get the latest model version string."""
    return db.get_latest_model_version()
