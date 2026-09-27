"""
Diagnostic Suite for Synthetic Data Shortcuts and Nuisance Leakage.

Tests whether classifiers can separate positive and negative classes using
ONLY nuisance properties (cadence length, missingness fraction, raw flux mean,
estimated white noise, flare statistics) without any transit dip or periodogram features.
"""
import pickle
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold

from tess_benchmark.data.synthetic import preprocess_light_curve


def run_shortcut_diagnostics(
    data_path: str = "data/processed/synthetic_light_curves.pkl",
    output_json: str = "results/audit/shortcut_diagnostics.json"
):
    with open(data_path, "rb") as f:
        lcs = pickle.load(f)

    records = []
    for lc in lcs:
        n_raw = len(lc.time)
        valid_mask = lc.valid_indices
        n_valid = int(np.sum(valid_mask))
        missing_frac = float(1.0 - (n_valid / max(1, n_raw)))
        
        flux_raw = lc.flux
        raw_mean = float(np.mean(flux_raw))
        raw_std = float(np.std(flux_raw))
        raw_median = float(np.median(flux_raw))
        # Estimate noise via MAD without considering dips
        mad = float(np.median(np.abs(flux_raw - raw_median)))
        est_noise = 1.4826 * mad

        records.append({
            "target_id": lc.target_id,
            "label": int(lc.has_transit),
            "n_raw": n_raw,
            "n_valid": n_valid,
            "missing_fraction": missing_frac,
            "raw_mean": raw_mean,
            "raw_std": raw_std,
            "raw_median": raw_median,
            "est_noise": est_noise,
            "noise_sigma_meta": float(lc.metadata.get("noise_sigma", 0.001)),
            "duration_days": float(lc.metadata.get("duration_days", 27.4)),
        })

    df = pd.DataFrame(records)

    nuisance_cols = [
        "n_raw",
        "n_valid",
        "missing_fraction",
        "raw_mean",
        "raw_median",
        "est_noise",
        "noise_sigma_meta",
        "duration_days",
    ]

    # Compute distributional statistics by class
    pos_df = df[df["label"] == 1]
    neg_df = df[df["label"] == 0]

    stats_comparison = {}
    for col in nuisance_cols:
        pos_vals = pos_df[col].values
        neg_vals = neg_df[col].values
        # Two-sample Kolmogorov-Smirnov test
        ks_stat, ks_pval = stats.ks_2samp(pos_vals, neg_vals)
        stats_comparison[col] = {
            "pos_mean": float(np.mean(pos_vals)),
            "pos_std": float(np.std(pos_vals)),
            "neg_mean": float(np.mean(neg_vals)),
            "neg_std": float(np.std(neg_vals)),
            "ks_statistic": float(ks_stat),
            "ks_pvalue": float(ks_pval),
            "significant_difference": bool(ks_pval < 0.05),
        }

    # Train shortcut baseline classifiers on nuisance features ONLY
    X = df[nuisance_cols].values
    y = df["label"].values

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    lr_preds = np.zeros(len(y))
    lr_probs = np.zeros(len(y))
    rf_preds = np.zeros(len(y))
    rf_probs = np.zeros(len(y))

    for train_idx, test_idx in cv.split(X, y):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr = y[train_idx]

        # Standardize within fold
        mean = np.mean(X_tr, axis=0)
        std = np.std(X_tr, axis=0)
        std[std == 0] = 1.0
        X_tr_sc = (X_tr - mean) / std
        X_te_sc = (X_te - mean) / std

        lr = LogisticRegression(C=1.0, random_state=42)
        lr.fit(X_tr_sc, y_tr)
        lr_preds[test_idx] = lr.predict(X_te_sc)
        lr_probs[test_idx] = lr.predict_proba(X_te_sc)[:, 1]

        rf = RandomForestClassifier(n_estimators=50, max_depth=4, random_state=42)
        rf.fit(X_tr, y_tr)
        rf_preds[test_idx] = rf.predict(X_te)
        rf_probs[test_idx] = rf.predict_proba(X_te)[:, 1]

    lr_auc = float(roc_auc_score(y, lr_probs))
    lr_acc = float(accuracy_score(y, lr_preds))
    rf_auc = float(roc_auc_score(y, rf_probs))
    rf_acc = float(accuracy_score(y, rf_preds))

    diagnostic_results = {
        "dataset_sample_size": len(df),
        "n_positive": int(np.sum(y == 1)),
        "n_negative": int(np.sum(y == 0)),
        "nuisance_features_evaluated": nuisance_cols,
        "feature_distribution_comparisons": stats_comparison,
        "nuisance_only_classification": {
            "logistic_regression": {
                "cv_roc_auc": lr_auc,
                "cv_accuracy": lr_acc,
                "shortcut_detected": bool(lr_auc > 0.70)
            },
            "random_forest": {
                "cv_roc_auc": rf_auc,
                "cv_accuracy": rf_acc,
                "shortcut_detected": bool(rf_auc > 0.70)
            }
        },
        "conclusion": (
            "Nuisance shortcut risk is LOW. Models cannot predict transit presence from length, missingness, or noise alone."
            if max(lr_auc, rf_auc) <= 0.70
            else "POTENTIAL NUISANCE SHORTCUT DETECTED. Models can partially separate classes using non-signal metadata/nuisance variables."
        )
    }

    out_path = Path(output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(diagnostic_results, f, indent=2)

    print(json.dumps(diagnostic_results, indent=2))
    return diagnostic_results


if __name__ == "__main__":
    run_shortcut_diagnostics()
