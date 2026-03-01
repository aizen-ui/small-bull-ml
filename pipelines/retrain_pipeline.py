"""
Weekly retrain pipeline: runs every Saturday.
Rebuilds features from all historical data, tunes hyperparameters, trains new model.
"""

from __future__ import annotations
import logging
import sys

from data import supabase_client as db
from features.feature_builder import build_training_dataset, get_temporal_split
from models.trainer import StockPredictor, tune_hyperparameters, generate_version
from models.model_registry import save_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


def run(skip_tuning: bool = False):
    """
    Full retrain pipeline.
    Args:
        skip_tuning: If True, skip Optuna tuning (faster, for testing).
    """
    run_id = db.log_pipeline_start("retrain")

    try:
        # Step 1: Build training dataset
        logger.info("=== Step 1: Building training dataset ===")
        X, y_direction, y_pct_change = build_training_dataset(days=500)
        logger.info(f"Dataset: {X.shape[0]} samples, {X.shape[1]} features")

        # Step 2: Temporal split
        logger.info("=== Step 2: Temporal train/test split ===")
        X_train, X_test, y_dir_train, y_dir_test = get_temporal_split(X, y_direction)
        _, _, y_pct_train, y_pct_test = get_temporal_split(X, y_pct_change)

        logger.info(f"Train: {len(X_train)}, Test: {len(X_test)}")

        # Step 3: Hyperparameter tuning (optional)
        best_params = None
        if not skip_tuning:
            logger.info("=== Step 3: Hyperparameter tuning ===")
            best_params = tune_hyperparameters(
                X_train, y_dir_train, y_pct_train, n_trials=30
            )
        else:
            logger.info("=== Step 3: Skipping tuning ===")

        # Step 4: Train model
        logger.info("=== Step 4: Training model ===")
        model = StockPredictor()
        model.version = generate_version()
        model.train(X_train, y_dir_train, y_pct_train, params=best_params)

        # Step 5: Evaluate
        logger.info("=== Step 5: Evaluating model ===")
        metrics = model.evaluate(X_test, y_dir_test, y_pct_test)

        # Step 6: Save
        logger.info("=== Step 6: Saving model ===")
        version = save_model(model, metrics)

        db.log_pipeline_end(run_id, "success", details={
            "model_version": version,
            "metrics": metrics,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
        })
        logger.info(f"Retrain complete. Model {version}: {metrics}")

    except Exception as e:
        logger.error(f"Retrain pipeline failed: {e}", exc_info=True)
        db.log_pipeline_end(run_id, "failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tuning", action="store_true",
                        help="Skip Optuna hyperparameter tuning")
    args = parser.parse_args()
    run(skip_tuning=args.skip_tuning)
