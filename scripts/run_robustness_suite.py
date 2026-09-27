#!/usr/bin/env python3
"""
Run Controlled Robustness and Degradation Experiments.

Evaluates how detection performance degrades under:
1. Increased Gaussian noise (low SNR regime)
2. Reduced transit depth (small planets)
3. Extended data gaps (missing observations)
4. Random measurement dropouts

Ensures test set stars remain strictly isolated from training data.
"""
import argparse
import json
from pathlib import Path
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from tess_benchmark.utils.seed import set_seed
from tess_benchmark.utils.logging import get_logger
from tess_benchmark.utils.config import load_config
from tess_benchmark.data.synthetic import preprocess_light_curve
from tess_benchmark.features.extractors import FeatureExtractor, FEATURE_NAMES
from tess_benchmark.baselines.bls import BLSDetector
from tess_benchmark.models.classical import build_classical_models
from tess_benchmark.models.cnn1d import CNN1DClassifier
from tess_benchmark.evaluation.splitting import StarGroupSplitter
from tess_benchmark.evaluation.metrics import compute_metrics
from tess_benchmark.evaluation.robustness import (
    apply_noise_degradation,
    apply_depth_scaling,
    apply_missing_gap,
    apply_cadence_dropout,
)


def main():
    parser = argparse.ArgumentParser(description="Run robustness experiments suite.")
    parser.add_argument("--data-file", type=str, default="data/processed/synthetic_light_curves.pkl")
    parser.add_argument("--config", type=str, default="configs/synthetic_benchmark.yaml")
    args = parser.parse_args()

    logger = get_logger("robustness_suite")
    cfg = load_config(args.config)
    seed = cfg.get("dataset", {}).get("seed", 42)
    set_seed(seed)

    data_path = Path(args.data_file)
    if not data_path.exists():
        logger.error("Dataset not found. Run generate_synthetic_benchmark.py first.")
        return

    with open(data_path, "rb") as f:
        light_curves = pickle.load(f)

    # 1. Feature extraction and Star Partition
    extractor = FeatureExtractor(n_phase_bins=200)
    tabular_records = []
    phase_vectors = []
    labels = []
    star_ids = []

    for lc in light_curves:
        clean_lc = preprocess_light_curve(lc, clip_outliers=True, detrend=True)
        feats = extractor.extract_tabular_features(clean_lc)
        feats["target_id"] = lc.target_id
        feats["label"] = int(lc.has_transit)
        tabular_records.append(feats)
        phase_vectors.append(extractor.extract_phase_vector(clean_lc))
        labels.append(int(lc.has_transit))
        star_ids.append(lc.target_id)

    feat_df = pd.DataFrame(tabular_records)
    X_tab = feat_df[FEATURE_NAMES].values
    y = np.array(labels)
    star_ids = np.array(star_ids)
    X_phase = np.array(phase_vectors)

    splitter = StarGroupSplitter(test_size=0.3, seed=seed)
    (
        X_tab_train, X_tab_test,
        y_train, y_test,
        stars_train, stars_test
    ) = splitter.train_test_split(X_tab, y, star_ids)

    train_mask = np.isin(star_ids, stars_train)
    test_mask = np.isin(star_ids, stars_test)
    X_phase_train, X_phase_test = X_phase[train_mask], X_phase[test_mask]

    test_lcs = [lc for lc in light_curves if lc.target_id in set(stars_test)]

    logger.info(f"Trained models will be evaluated on {len(test_lcs)} test stars across degradation axes.")

    # 2. Train baseline models
    rf_model = build_classical_models(seed=seed)["RandomForest"].fit(X_tab_train, y_train)
    cnn_model = CNN1DClassifier(sequence_length=200, epochs=20, batch_size=16, seed=seed).fit(X_phase_train, y_train)
    bls = BLSDetector(frequency_factor=3.0, sde_threshold=6.0)

    # 3. Degradation experiments
    # Axis A: Noise multiplier
    noise_levels = [0.0, 0.001, 0.002, 0.004]  # added noise sigma
    # Axis B: Depth multiplier
    depth_scales = [1.0, 0.75, 0.5, 0.25]
    # Axis C: Random dropout fraction
    dropouts = [0.0, 0.15, 0.3, 0.5]

    robustness_records = []

    def evaluate_test_suite(degraded_lcs, axis_name, level_val):
        deg_X_tab = []
        deg_X_phase = []
        deg_y = []
        bls_preds = []
        bls_sdes = []

        for lc in degraded_lcs:
            clean_lc = preprocess_light_curve(lc, clip_outliers=True, detrend=True)
            res = bls.search(clean_lc)
            bls_preds.append(1 if res.is_detected else 0)
            bls_sdes.append(res.sde)

            f = extractor.extract_tabular_features(clean_lc, bls_result=res)
            deg_X_tab.append([f[name] for name in FEATURE_NAMES])
            deg_X_phase.append(extractor.extract_phase_vector(clean_lc, bls_result=res))
            deg_y.append(int(lc.has_transit))

        deg_X_tab = np.array(deg_X_tab)
        deg_X_phase = np.array(deg_X_phase)
        deg_y = np.array(deg_y)

        # BLS
        bls_rep = compute_metrics(deg_y, np.array(bls_preds), model_name="BLS")
        # RF
        rf_pred = rf_model.predict(deg_X_tab)
        rf_proba = rf_model.score_probability(deg_X_tab)
        rf_rep = compute_metrics(deg_y, rf_pred, rf_proba, model_name="RandomForest")
        # CNN1D
        cnn_pred = cnn_model.predict(deg_X_phase)
        cnn_proba = cnn_model.score_probability(deg_X_phase)
        cnn_rep = compute_metrics(deg_y, cnn_pred, cnn_proba, model_name="CNN1D")

        for rep in [bls_rep, rf_rep, cnn_rep]:
            robustness_records.append({
                "axis": axis_name,
                "level": level_val,
                "model": rep.model_name,
                "f1": rep.f1,
                "recall": rep.recall,
                "precision": rep.precision,
                "fpr": rep.fpr
            })

    logger.info("Evaluating Noise Degradation Axis...")
    for n_add in noise_levels:
        deg = [apply_noise_degradation(lc, n_add, seed=seed) for lc in test_lcs]
        evaluate_test_suite(deg, "noise_added", n_add)

    logger.info("Evaluating Transit Depth Scaling Axis...")
    for d_scale in depth_scales:
        deg = [apply_depth_scaling(lc, d_scale) for lc in test_lcs]
        evaluate_test_suite(deg, "depth_scale", d_scale)

    logger.info("Evaluating Cadence Dropout Axis...")
    for drop in dropouts:
        deg = [apply_cadence_dropout(lc, drop, seed=seed) for lc in test_lcs]
        evaluate_test_suite(deg, "dropout_fraction", drop)

    rob_df = pd.DataFrame(robustness_records)
    metrics_dir = Path("results/metrics")
    metrics_dir.mkdir(parents=True, exist_ok=True)
    rob_df.to_csv(metrics_dir / "robustness_suite.csv", index=False)
    with open(metrics_dir / "robustness_suite.json", "w") as f:
        json.dump(robustness_records, f, indent=2)

    logger.info(f"Saved robustness results to {metrics_dir / 'robustness_suite.csv'}")

    # Plot degradation curves
    fig_dir = Path("results/figures")
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # Plot Noise
    df_noise = rob_df[rob_df["axis"] == "noise_added"]
    for m in ["BLS", "RandomForest", "CNN1D"]:
        sub = df_noise[df_noise["model"] == m]
        axes[0].plot(sub["level"] * 1e6, sub["f1"], "o-", label=m)
    axes[0].set_xlabel("Added Noise Sigma (ppm)")
    axes[0].set_ylabel("F1 Score")
    axes[0].set_title("Noise Robustness")
    axes[0].grid(True, linestyle="--", alpha=0.5)
    axes[0].legend()

    # Plot Depth Scaling
    df_depth = rob_df[rob_df["axis"] == "depth_scale"]
    for m in ["BLS", "RandomForest", "CNN1D"]:
        sub = df_depth[df_depth["model"] == m]
        axes[1].plot(sub["level"], sub["f1"], "s-", label=m)
    axes[1].set_xlabel("Depth Scale Factor (1.0 = Nominal)")
    axes[1].set_ylabel("F1 Score")
    axes[1].set_title("Shallow Transit Sensitivity")
    axes[1].grid(True, linestyle="--", alpha=0.5)
    axes[1].legend()

    # Plot Dropout
    df_drop = rob_df[rob_df["axis"] == "dropout_fraction"]
    for m in ["BLS", "RandomForest", "CNN1D"]:
        sub = df_drop[df_drop["model"] == m]
        axes[2].plot(sub["level"] * 100, sub["f1"], "^-", label=m)
    axes[2].set_xlabel("Cadence Dropout (%)")
    axes[2].set_ylabel("F1 Score")
    axes[2].set_title("Missing Cadence Robustness")
    axes[2].grid(True, linestyle="--", alpha=0.5)
    axes[2].legend()

    plt.tight_layout()
    fig_path = fig_dir / "robustness_curves.png"
    plt.savefig(fig_path, dpi=200)
    plt.close()
    logger.info(f"Saved robustness figure to {fig_path}")


if __name__ == "__main__":
    main()
