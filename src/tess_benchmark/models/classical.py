"""
Supervised Classical Machine Learning Models for Transit Detection.

Wraps scikit-learn models (Logistic Regression, Random Forest, Gradient Boosting, SVM)
with standardized interfaces, latency profiling, and probability calibration.
"""
import time
from typing import Dict, Any, Optional, Tuple
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.svm import SVC


class ModelWrapper:
    """
    Standardized wrapper around a scikit-learn estimator providing timing benchmarks.
    """

    def __init__(self, name: str, estimator: Any):
        self.name = name
        self.estimator = estimator
        self.train_time_sec: float = 0.0
        self.last_inference_latency_ms: float = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> "ModelWrapper":
        """Fit estimator and measure wall-clock training time."""
        t0 = time.perf_counter()
        self.estimator.fit(X, y)
        self.train_time_sec = float(time.perf_counter() - t0)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict binary class labels."""
        return self.estimator.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class probabilities and measure inference latency per sample.
        """
        t0 = time.perf_counter()
        proba = self.estimator.predict_proba(X)
        elapsed = time.perf_counter() - t0
        self.last_inference_latency_ms = float((elapsed / max(1, len(X))) * 1000.0)
        return proba

    def score_probability(self, X: np.ndarray) -> np.ndarray:
        """Return 1D array of positive class probabilities."""
        proba = self.predict_proba(X)
        if proba.shape[1] > 1:
            return proba[:, 1]
        return proba[:, 0]


def build_classical_models(seed: int = 42) -> Dict[str, ModelWrapper]:
    """
    Construct the benchmark suite of classical supervised classifiers.

    Parameters
    ----------
    seed : int
        Reproducible random seed.

    Returns
    -------
    Dict[str, ModelWrapper]
        Dictionary of initialized model wrappers.
    """
    models = {
        "LogisticRegression": ModelWrapper(
            name="LogisticRegression",
            estimator=Pipeline([
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(
                    max_iter=1000,
                    C=1.0,
                    class_weight="balanced",
                    random_state=seed
                ))
            ])
        ),
        "RandomForest": ModelWrapper(
            name="RandomForest",
            estimator=RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                min_samples_split=4,
                class_weight="balanced",
                random_state=seed,
                n_jobs=-1
            )
        ),
        "GradientBoosting": ModelWrapper(
            name="GradientBoosting",
            estimator=HistGradientBoostingClassifier(
                max_iter=100,
                max_depth=5,
                min_samples_leaf=5,
                class_weight="balanced",
                random_state=seed
            )
        ),
        "SVM": ModelWrapper(
            name="SVM",
            estimator=Pipeline([
                ("scaler", StandardScaler()),
                ("clf", CalibratedClassifierCV(
                    SVC(
                        kernel="rbf",
                        C=1.0,
                        class_weight="balanced",
                        random_state=seed
                    ),
                    ensemble=False
                ))
            ])
        )
    }
    return models
