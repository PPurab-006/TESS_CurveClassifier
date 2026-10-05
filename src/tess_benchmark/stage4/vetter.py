"""
Stage 4 Candidate Vetter Module.

Implements the CandidateVetter classification pipeline:
- Handles missingness / NaNs cleanly (native support for HistGradientBoosting; median imputation for RF/LR)
- Executes 5-fold Star-Group Cross-Validation on synthetic candidates
- Deterministic decision-threshold calibration rule:
  1. Maximize synthetic OOF F1 score
  2. Subject to synthetic OOF Recall >= 0.92
  3. If tied, maximize Recall
  4. If still tied, choose the highest threshold
- Serializes the frozen, immutable vetter for out-of-sample evaluation
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier

from ..evaluation.metrics import compute_metrics, EvaluationReport
from ..evaluation.splitting import StarGroupSplitter
from .features import STAGE4_FEATURE_NAMES, BASELINE_FEATURE_NAMES, STAGE4_FEATURE_GROUPS


@dataclass
class ThresholdCalibrationResult:
    """Result of deterministic decision-threshold calibration on synthetic OOF predictions."""
    selected_threshold: float
    best_f1: float
    recall_at_selected: float
    specificity_at_selected: float
    precision_at_selected: float
    calibration_table: pd.DataFrame
    rule_description: str = (
        "Maximize synthetic OOF F1 subject to Recall >= 0.92; "
        "tie-break: maximize Recall; further tie-break: highest threshold"
    )


def calibrate_decision_threshold(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    min_recall: float = 0.92,
    threshold_grid: Optional[np.ndarray] = None
) -> ThresholdCalibrationResult:
    """
    Deterministic decision-threshold selection on out-of-fold validation probabilities.

    Constraints:
    1. Maximize F1 score
    2. Subject to Recall >= min_recall (default 0.92)
    3. Tie-break: maximize Recall
    4. Second tie-break: highest threshold
    """
    if threshold_grid is None:
        threshold_grid = np.round(np.linspace(0.05, 0.95, 91), 4)

    rows: List[Dict[str, float]] = []

    for t in threshold_grid:
        y_pred = (y_proba >= t).astype(int)
        tp = np.sum((y_true == 1) & (y_pred == 1))
        fp = np.sum((y_true == 0) & (y_pred == 1))
        fn = np.sum((y_true == 1) & (y_pred == 0))
        tn = np.sum((y_true == 0) & (y_pred == 0))

        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        f1 = (2.0 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        rows.append({
            "threshold": float(t),
            "f1": float(f1),
            "recall": float(rec),
            "specificity": float(spec),
            "precision": float(prec),
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "tn": int(tn),
        })

    df_calib = pd.DataFrame(rows)

    # Filter by min_recall constraint
    valid_candidates = df_calib[df_calib["recall"] >= min_recall]
    if len(valid_candidates) == 0:
        # Fallback: if no threshold satisfies min_recall, pick threshold with max recall
        sorted_candidates = df_calib.sort_values(by=["recall", "f1", "threshold"], ascending=[False, False, False])
        selected_row = sorted_candidates.iloc[0]
    else:
        # Sort by: F1 (descending), Recall (descending), Threshold (descending)
        sorted_candidates = valid_candidates.sort_values(
            by=["f1", "recall", "threshold"],
            ascending=[False, False, False]
        )
        selected_row = sorted_candidates.iloc[0]

    return ThresholdCalibrationResult(
        selected_threshold=float(selected_row["threshold"]),
        best_f1=float(selected_row["f1"]),
        recall_at_selected=float(selected_row["recall"]),
        specificity_at_selected=float(selected_row["specificity"]),
        precision_at_selected=float(selected_row["precision"]),
        calibration_table=df_calib
    )


class CandidateVetter:
    """
    Standardized, serialized candidate vetting pipeline.

    Wraps:
    - Preprocessing / imputation pipeline
    - Supervised classical estimator
    - Exact ordered feature schema
    - Calibrated frozen decision threshold
    """

    def __init__(
        self,
        model_name: str = "RandomForest",
        feature_names: Optional[List[str]] = None,
        decision_threshold: float = 0.50,
        seed: int = 42,
        estimator: Optional[BaseEstimator] = None
    ):
        self.model_name = model_name
        self.feature_names = list(feature_names) if feature_names is not None else list(STAGE4_FEATURE_NAMES)
        self.decision_threshold = float(decision_threshold)
        self.seed = int(seed)
        self.estimator = estimator or self._build_estimator(model_name, seed)
        self.is_fitted: bool = False
        self.training_metadata: Dict[str, Any] = {}

    def _build_estimator(self, model_name: str, seed: int) -> BaseEstimator:
        if model_name == "HistGradientBoosting":
            return HistGradientBoostingClassifier(
                max_iter=100,
                max_depth=5,
                min_samples_leaf=5,
                class_weight="balanced",
                random_state=seed
            )
        elif model_name == "RandomForest":
            return Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("clf", RandomForestClassifier(
                    n_estimators=150,
                    max_depth=8,
                    min_samples_leaf=4,
                    class_weight="balanced",
                    random_state=seed,
                    n_jobs=-1
                ))
            ])
        elif model_name == "LogisticRegression":
            return Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(
                    max_iter=1000,
                    C=1.0,
                    class_weight="balanced",
                    random_state=seed
                ))
            ])
        else:
            raise ValueError(f"Unsupported model_name: {model_name}")

    def fit(self, X: np.ndarray, y: np.ndarray) -> "CandidateVetter":
        """Fit estimator on training data."""
        self.estimator.fit(X, y)
        self.is_fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return 1D array of positive transit probabilities."""
        if not self.is_fitted:
            raise RuntimeError("CandidateVetter must be fitted before predict_proba.")
        proba = self.estimator.predict_proba(X)
        if proba.shape[1] > 1:
            return proba[:, 1]
        return proba[:, 0]

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Classify candidate as retained (1) or rejected (0) using frozen threshold."""
        proba = self.predict_proba(X)
        return (proba >= self.decision_threshold).astype(int)

    def save(self, filepath: Path | str) -> Path:
        """Serialize complete frozen vetter pipeline to disk."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, p)
        return p

    @classmethod
    def load(cls, filepath: Path | str) -> "CandidateVetter":
        """Load frozen vetter pipeline from disk."""
        p = Path(filepath)
        if not p.exists():
            raise FileNotFoundError(f"Vetter artifact not found: {p}")
        return joblib.load(p)


def evaluate_synthetic_cross_validation(
    df_synthetic: pd.DataFrame,
    model_name: str,
    feature_names: List[str],
    n_splits: int = 5,
    seed: int = 42
) -> Tuple[EvaluationReport, np.ndarray, np.ndarray]:
    """
    Perform 5-fold Star-Group Cross-Validation strictly on synthetic candidate dataset.

    Returns:
    (EvaluationReport at default 0.5 threshold, out_of_fold_probabilities, y_true_array)
    """
    X = df_synthetic[feature_names].values
    y = df_synthetic["label"].values.astype(int)
    star_ids = df_synthetic["target_id"].values

    splitter = StarGroupSplitter(n_splits=n_splits, seed=seed)
    oof_proba = np.zeros(len(y), dtype=float)

    for train_idx, val_idx in splitter.kfold_split(X, y, star_ids):
        X_tr, y_tr = X[train_idx], y[train_idx]
        X_val = X[val_idx]

        vetter = CandidateVetter(model_name=model_name, feature_names=feature_names, seed=seed)
        vetter.fit(X_tr, y_tr)
        oof_proba[val_idx] = vetter.predict_proba(X_val)

    y_pred_05 = (oof_proba >= 0.50).astype(int)
    report = compute_metrics(
        y_true=y,
        y_pred=y_pred_05,
        y_proba=oof_proba,
        model_name=f"{model_name}_SyntheticCV"
    )
    return report, oof_proba, y


def train_and_calibrate_candidate_vetter(
    df_synthetic: pd.DataFrame,
    model_name: str,
    feature_names: List[str],
    min_recall: float = 0.92,
    seed: int = 42
) -> Tuple[CandidateVetter, ThresholdCalibrationResult, EvaluationReport]:
    """
    Full synthetic training and deterministic decision-threshold calibration protocol.

    1. Executes 5-fold CV to collect out-of-fold probabilities.
    2. Calibrates decision-threshold using deterministic tie-break rules.
    3. Fits champion vetter on full synthetic training dataset.
    4. Sets frozen decision threshold on the champion vetter.
    """
    # 1. 5-fold CV on synthetic dataset
    report_cv, oof_proba, y_true = evaluate_synthetic_cross_validation(
        df_synthetic=df_synthetic,
        model_name=model_name,
        feature_names=feature_names,
        seed=seed
    )

    # 2. Deterministic threshold calibration on synthetic OOF predictions
    calib_result = calibrate_decision_threshold(
        y_true=y_true,
        y_proba=oof_proba,
        min_recall=min_recall
    )

    # 3. Fit on full synthetic dataset
    X_full = df_synthetic[feature_names].values
    y_full = df_synthetic["label"].values.astype(int)

    champion_vetter = CandidateVetter(
        model_name=model_name,
        feature_names=feature_names,
        decision_threshold=calib_result.selected_threshold,
        seed=seed
    )
    champion_vetter.fit(X_full, y_full)
    champion_vetter.training_metadata = {
        "model_name": model_name,
        "n_samples": len(df_synthetic),
        "n_transits": int(np.sum(y_full == 1)),
        "n_confounders": int(np.sum(y_full == 0)),
        "feature_count": len(feature_names),
        "selected_threshold": calib_result.selected_threshold,
        "cv_f1_at_selected": calib_result.best_f1,
        "cv_recall_at_selected": calib_result.recall_at_selected,
        "cv_pr_auc": report_cv.pr_auc,
        "cv_roc_auc": report_cv.roc_auc,
        "seed": seed
    }

    return champion_vetter, calib_result, report_cv
