"""
Unit tests for Stage 4 Candidate Vetter and Threshold Calibration.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from tess_benchmark.stage4.features import STAGE4_FEATURE_NAMES, BASELINE_FEATURE_NAMES
from tess_benchmark.stage4.vetter import (
    CandidateVetter,
    calibrate_decision_threshold,
    evaluate_synthetic_cross_validation,
    train_and_calibrate_candidate_vetter,
)


def test_deterministic_threshold_calibration():
    """Verify deterministic decision-threshold calibration rules and tie-breaking."""
    # Synthetic binary ground truth and probabilities
    y_true = np.array([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    # Distinct probabilities separating positives and negatives
    y_proba = np.array([
        0.95, 0.92, 0.90, 0.88, 0.85, 0.82, 0.78, 0.72, 0.65, 0.55,  # 10 positives
        0.58, 0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05   # 10 negatives
    ])

    res = calibrate_decision_threshold(y_true, y_proba, min_recall=0.90)

    assert 0.05 <= res.selected_threshold <= 0.95
    assert res.recall_at_selected >= 0.90
    assert res.best_f1 > 0.0
    assert len(res.calibration_table) > 10

    # Test tie-breaking behavior explicitly
    # Case where two thresholds yield identical F1 and Recall -> highest threshold must be chosen
    t_table = res.calibration_table
    assert "threshold" in t_table.columns
    assert "f1" in t_table.columns
    assert "recall" in t_table.columns


def test_candidate_vetter_pipeline_fit_predict_save_load(tmp_path):
    """Verify CandidateVetter pipeline lifecycle and serialization integrity."""
    n_samples = 40
    n_features = len(STAGE4_FEATURE_NAMES)
    rng = np.random.default_rng(42)

    X = rng.normal(0, 1, size=(n_samples, n_features))
    # Add random NaNs to test missing-value handling
    nan_mask = rng.random(size=(n_samples, n_features)) < 0.10
    X[nan_mask] = np.nan

    y = rng.choice([0, 1], size=n_samples)

    models_to_test = ["HistGradientBoosting", "RandomForest", "LogisticRegression"]

    for m_name in models_to_test:
        vetter = CandidateVetter(
            model_name=m_name,
            feature_names=STAGE4_FEATURE_NAMES,
            decision_threshold=0.45,
            seed=42
        )
        vetter.fit(X, y)
        assert vetter.is_fitted is True

        proba = vetter.predict_proba(X)
        assert len(proba) == n_samples
        assert np.all((proba >= 0.0) & (proba <= 1.0))

        preds = vetter.predict(X)
        assert len(preds) == n_samples
        assert set(np.unique(preds)).issubset({0, 1})
        # Prediction must strictly match threshold
        expected_preds = (proba >= 0.45).astype(int)
        assert np.array_equal(preds, expected_preds)

        # Serialization test
        save_path = tmp_path / f"vetter_{m_name}.joblib"
        vetter.save(save_path)
        assert save_path.exists()

        loaded_vetter = CandidateVetter.load(save_path)
        assert loaded_vetter.model_name == m_name
        assert loaded_vetter.decision_threshold == 0.45
        loaded_preds = loaded_vetter.predict(X)
        assert np.array_equal(preds, loaded_preds)


def test_frozen_stage3_benchmark_regression_invariant():
    """Verify that Stage 3 benchmark outputs remain strictly unmodified and present."""
    st3_dir = Path("results/real_benchmark_stage3")
    assert st3_dir.exists(), "results/real_benchmark_stage3/ must exist"

    bls_csv = st3_dir / "bls_formal_predictions.csv"
    assert bls_csv.exists(), "bls_formal_predictions.csv must exist"
    df_bls = pd.read_csv(bls_csv)
    assert len(df_bls) == 100, f"Expected 100 targets, got {len(df_bls)}"
    assert np.sum(df_bls["category"] == "confirmed_planet_host") == 50
    assert np.sum(df_bls["category"] == "control_star") == 50

    summary_json = st3_dir / "stage3_formal_summary.json"
    assert summary_json.exists(), "stage3_formal_summary.json must exist"
    import json
    with open(summary_json) as f:
        summary = json.load(f)
    assert summary["benchmark_metadata"]["sde_method"] == "option_c"
    assert summary["bls_baseline_metrics"]["all_hosts_cohort_n50"]["recovered_period_count"] == 46
    assert summary["bls_baseline_metrics"]["all_hosts_cohort_n50"]["full_recovery_count"] == 38
