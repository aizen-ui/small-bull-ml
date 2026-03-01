"""
Professional stock prediction model with:
- Stacking ensemble (LightGBM + XGBoost + RandomForest)
- Purged walk-forward cross-validation
- Confidence-based prediction filtering
- F1-macro optimized hyperparameter tuning
"""

from __future__ import annotations
import logging
import pickle
from datetime import date
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    mean_absolute_error, mean_squared_error,
)
import optuna

logger = logging.getLogger(__name__)

optuna.logging.set_verbosity(optuna.logging.WARNING)

# Minimum confidence to issue a directional prediction
DEFAULT_CONFIDENCE_THRESHOLD = 0.45


class StockPredictor:
    """
    Stacking ensemble: LightGBM + XGBoost + RandomForest base learners,
    LogisticRegression meta-learner. Plus a separate regression model for magnitude.
    """

    def __init__(self):
        self.clf_model = None
        self.reg_model: lgb.LGBMRegressor | None = None
        self.label_encoder = LabelEncoder()
        self.feature_names: list[str] = []
        self.version: str = ""
        self.confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD

    def _build_ensemble(self, params: dict | None = None):
        """Build the stacking ensemble classifier."""
        clf_params = params or {
            "n_estimators": 500,
            "learning_rate": 0.05,
            "max_depth": 6,
            "num_leaves": 31,
            "min_child_samples": 20,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": 0.1,
            "reg_lambda": 0.1,
            "random_state": 42,
            "verbose": -1,
        }

        lgbm_base = lgb.LGBMClassifier(**clf_params)

        # Try to use XGBoost if available
        try:
            import xgboost as xgb
            xgb_params = {
                "n_estimators": clf_params.get("n_estimators", 500),
                "learning_rate": clf_params.get("learning_rate", 0.05),
                "max_depth": clf_params.get("max_depth", 6),
                "subsample": clf_params.get("subsample", 0.8),
                "colsample_bytree": clf_params.get("colsample_bytree", 0.8),
                "reg_alpha": clf_params.get("reg_alpha", 0.1),
                "reg_lambda": clf_params.get("reg_lambda", 0.1),
                "random_state": 42,
                "verbosity": 0,
                "eval_metric": "mlogloss",
            }
            xgb_base = xgb.XGBClassifier(**xgb_params)
            estimators = [
                ("lgbm", lgbm_base),
                ("xgb", xgb_base),
                ("rf", RandomForestClassifier(
                    n_estimators=300, max_depth=8, min_samples_leaf=20,
                    max_features="sqrt", random_state=42, n_jobs=-1,
                )),
            ]
        except ImportError:
            logger.info("XGBoost not available, using LightGBM + RF ensemble")
            estimators = [
                ("lgbm", lgbm_base),
                ("rf", RandomForestClassifier(
                    n_estimators=300, max_depth=8, min_samples_leaf=20,
                    max_features="sqrt", random_state=42, n_jobs=-1,
                )),
            ]

        # Meta-learner: regularized logistic regression
        ensemble = StackingClassifier(
            estimators=estimators,
            final_estimator=LogisticRegression(
                C=0.1, max_iter=1000, random_state=42,
            ),
            cv=3,  # internal CV for generating meta-features
            stack_method="predict_proba",
            passthrough=False,
            n_jobs=-1,
        )
        return ensemble

    def train(self, X_train: pd.DataFrame, y_dir_train: pd.Series,
              y_pct_train: pd.Series, params: dict | None = None) -> dict:
        """Train stacking ensemble + regression model."""
        self.feature_names = list(X_train.columns)

        y_encoded = self.label_encoder.fit_transform(y_dir_train)

        # Build and train ensemble classifier
        logger.info("Training stacking ensemble classifier...")
        self.clf_model = self._build_ensemble(params)
        self.clf_model.fit(X_train, y_encoded)

        # Train regression model for magnitude
        reg_params = (params or {}).copy()
        reg_params.pop("verbose", None)
        reg_params.setdefault("n_estimators", 500)
        reg_params.setdefault("learning_rate", 0.05)
        reg_params.setdefault("max_depth", 6)
        reg_params.setdefault("random_state", 42)
        reg_params["verbose"] = -1

        logger.info("Training regression model...")
        self.reg_model = lgb.LGBMRegressor(**reg_params)
        self.reg_model.fit(X_train, y_pct_train)

        # Training metrics
        y_pred = self.clf_model.predict(X_train)
        train_acc = accuracy_score(y_encoded, y_pred)
        train_f1 = f1_score(y_encoded, y_pred, average="macro", zero_division=0)
        logger.info(f"Training accuracy: {train_acc:.4f}, F1-macro: {train_f1:.4f}")

        return {"train_accuracy": train_acc, "train_f1_macro": train_f1}

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Make predictions with confidence filtering.
        Low-confidence predictions are labeled 'hold'.
        """
        if self.clf_model is None:
            raise ValueError("Model not trained")

        proba = self.clf_model.predict_proba(X)
        pred_encoded = np.argmax(proba, axis=1)
        pred_direction = self.label_encoder.inverse_transform(pred_encoded)
        confidence = np.max(proba, axis=1)

        # Regression prediction
        pred_pct = self.reg_model.predict(X)

        # Apply confidence threshold — low confidence = "hold"
        final_direction = np.where(
            confidence >= self.confidence_threshold,
            pred_direction,
            "hold"
        )

        return pd.DataFrame({
            "predicted_direction": final_direction,
            "raw_direction": pred_direction,
            "predicted_pct_change": np.round(pred_pct, 4),
            "confidence_score": np.round(confidence, 4),
        })

    def evaluate(self, X_test: pd.DataFrame, y_dir_test: pd.Series,
                 y_pct_test: pd.Series) -> dict:
        """Evaluate model on test set with comprehensive metrics."""
        y_encoded = self.label_encoder.transform(y_dir_test)
        y_pred = self.clf_model.predict(X_test)
        y_pred_dir = self.label_encoder.inverse_transform(y_pred)
        y_pred_pct = self.reg_model.predict(X_test)

        # Overall classification metrics
        accuracy = accuracy_score(y_encoded, y_pred)
        f1_macro = f1_score(y_encoded, y_pred, average="macro", zero_division=0)

        # Binary direction accuracy (ignoring neutral)
        mask = y_dir_test.isin(["up", "down"])
        if mask.sum() > 0:
            dir_acc = accuracy_score(
                y_dir_test[mask] == "up",
                pd.Series(y_pred_dir)[mask.values] == "up"
            )
        else:
            dir_acc = 0.0

        precision_w = precision_score(y_encoded, y_pred, average="weighted", zero_division=0)
        recall_w = recall_score(y_encoded, y_pred, average="weighted", zero_division=0)
        f1_w = f1_score(y_encoded, y_pred, average="weighted", zero_division=0)

        # High-confidence precision (predictions above threshold)
        proba = self.clf_model.predict_proba(X_test)
        confidence = np.max(proba, axis=1)
        high_conf_mask = confidence >= self.confidence_threshold
        if high_conf_mask.sum() > 0:
            hc_acc = accuracy_score(y_encoded[high_conf_mask], y_pred[high_conf_mask])
            hc_precision = precision_score(
                y_encoded[high_conf_mask], y_pred[high_conf_mask],
                average="weighted", zero_division=0
            )
            hc_coverage = high_conf_mask.sum() / len(y_encoded)
        else:
            hc_acc = 0.0
            hc_precision = 0.0
            hc_coverage = 0.0

        # Regression metrics
        mae = mean_absolute_error(y_pct_test, y_pred_pct)
        rmse = np.sqrt(mean_squared_error(y_pct_test, y_pred_pct))

        metrics = {
            "accuracy": round(accuracy, 4),
            "directional_accuracy": round(dir_acc, 4),
            "f1_macro": round(f1_macro, 4),
            "precision_up": round(precision_w, 4),
            "recall_up": round(recall_w, 4),
            "f1_up": round(f1_w, 4),
            "high_conf_accuracy": round(hc_acc, 4),
            "high_conf_precision": round(hc_precision, 4),
            "high_conf_coverage": round(hc_coverage, 4),
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
        }
        logger.info(f"Test metrics: {metrics}")
        return metrics

    def backtest(self, X: pd.DataFrame, y_dir: pd.Series,
                 y_pct: pd.Series, dates: pd.Series | None = None) -> pd.DataFrame:
        """
        Run model predictions on every row of X and compare to actuals.
        Returns DataFrame with: date, predicted_direction, actual_direction,
        predicted_pct, actual_pct, confidence, was_correct, error.
        Used for model-vs-actual chart and error feedback features.
        """
        preds = self.predict(X)
        results = pd.DataFrame({
            "predicted_direction": preds["predicted_direction"].values,
            "raw_direction": preds["raw_direction"].values,
            "actual_direction": y_dir.values,
            "predicted_pct": preds["predicted_pct_change"].values,
            "actual_pct": y_pct.values,
            "confidence": preds["confidence_score"].values,
        })
        if dates is not None:
            results["date"] = dates.values

        results["was_correct"] = (
            results["raw_direction"] == results["actual_direction"]
        )
        results["error"] = results["predicted_pct"] - results["actual_pct"]
        results["abs_error"] = results["error"].abs()

        return results

    def calibrate_threshold(self, bt: pd.DataFrame) -> float:
        """
        Auto-calibrate confidence threshold from backtest results.
        Finds the threshold that maximises (accuracy * coverage).
        """
        best_score = 0
        best_thresh = self.confidence_threshold

        for thresh in np.arange(0.30, 0.70, 0.02):
            mask = bt["confidence"] >= thresh
            if mask.sum() < 10:
                continue
            acc = bt.loc[mask, "was_correct"].mean()
            coverage = mask.mean()
            score = acc * coverage  # balance accuracy with coverage
            if score > best_score:
                best_score = score
                best_thresh = round(float(thresh), 2)

        logger.info(
            f"Calibrated threshold: {self.confidence_threshold} -> {best_thresh} "
            f"(score={best_score:.4f})"
        )
        self.confidence_threshold = best_thresh
        return best_thresh

    def get_feature_importance(self, top_n: int = 20) -> list[dict]:
        """Get top N most important features from the LightGBM base learner."""
        if self.clf_model is None:
            return []
        try:
            lgbm = self.clf_model.named_estimators_["lgbm"]
            importances = lgbm.feature_importances_
        except (AttributeError, KeyError):
            return []
        indices = np.argsort(importances)[::-1][:top_n]
        return [
            {"feature": self.feature_names[i], "importance": int(importances[i])}
            for i in indices if i < len(self.feature_names)
        ]

    def to_bytes(self) -> bytes:
        """Serialize model to bytes for storage."""
        return pickle.dumps({
            "clf_model": self.clf_model,
            "reg_model": self.reg_model,
            "label_encoder": self.label_encoder,
            "feature_names": self.feature_names,
            "version": self.version,
            "confidence_threshold": self.confidence_threshold,
        })

    @classmethod
    def from_bytes(cls, data: bytes) -> StockPredictor:
        """Deserialize model from bytes."""
        obj = pickle.loads(data)
        predictor = cls()
        predictor.clf_model = obj["clf_model"]
        predictor.reg_model = obj["reg_model"]
        predictor.label_encoder = obj["label_encoder"]
        predictor.feature_names = obj["feature_names"]
        predictor.version = obj.get("version", "unknown")
        predictor.confidence_threshold = obj.get(
            "confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD
        )
        return predictor


def purged_walk_forward_cv(X: pd.DataFrame, y: pd.Series,
                            n_splits: int = 5, purge_days: int = 10,
                            params: dict | None = None) -> list[float]:
    """
    Purged walk-forward cross-validation (Marcos López de Prado).
    Removes rows near test boundary from training to prevent label overlap.
    Returns list of f1_macro scores per fold.
    """
    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    n = len(X)
    fold_size = n // (n_splits + 1)

    scores = []
    for i in range(n_splits):
        test_start = fold_size * (i + 1)
        test_end = min(fold_size * (i + 2), n)

        train_end = max(0, test_start - purge_days)
        if train_end < 100:
            continue

        X_tr = X.iloc[:train_end]
        y_tr = y_enc[:train_end]
        X_te = X.iloc[test_start:test_end]
        y_te = y_enc[test_start:test_end]

        if len(X_te) == 0:
            continue

        clf_params = params or {
            "n_estimators": 300, "learning_rate": 0.05, "max_depth": 6,
            "num_leaves": 31, "verbose": -1, "random_state": 42,
        }
        model = lgb.LGBMClassifier(**clf_params)
        model.fit(X_tr, y_tr)
        y_pred = model.predict(X_te)
        score = f1_score(y_te, y_pred, average="macro", zero_division=0)
        scores.append(score)

    return scores


def tune_hyperparameters(X: pd.DataFrame, y_dir: pd.Series,
                         y_pct: pd.Series, n_trials: int = 30) -> dict:
    """
    Optuna hyperparameter tuning with purged walk-forward validation.
    Optimizes f1_macro (not accuracy) for better precision/recall balance.
    """
    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 200, 800),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "num_leaves": trial.suggest_int("num_leaves", 15, 63),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 50),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            "verbose": -1,
            "random_state": 42,
        }
        scores = purged_walk_forward_cv(X, y_dir, n_splits=4, purge_days=10,
                                         params=params)
        return np.mean(scores) if scores else 0.0

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best_params = study.best_params
    best_params["verbose"] = -1
    best_params["random_state"] = 42
    logger.info(f"Best params (f1_macro={study.best_value:.4f}): {best_params}")
    return best_params


def generate_version() -> str:
    """Generate a model version string."""
    return f"v{date.today().isoformat()}"
