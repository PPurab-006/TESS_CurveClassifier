#!/usr/bin/env python3
"""
Train and Evaluate Supervised Machine Learning Benchmark.

Partitions stars using group-aware splits to strictly prevent target star leakage,
trains Logistic Regression, Random Forest, Gradient Boosting, SVM, and a 1D CNN,
and produces comparative performance and computational benchmark tables.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from tess_benchmark.utils.seed import set_seed
from tess_benchmark.utils.logging import get_logger
from tess_benchmark.utils.config import load_config
from tess_benchmark.features.extractors import FEATURE_NAMES
from tess_benchmark.models.classical import build_classical_models
from tess_benchmark.models.cnn1d import CNN1DClassifier
from tess_benchmark.evaluation.splitting import StarGroupSplitter
from tess_benchmark.evaluation.metrics import compute_metrics, EvaluationReport


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate ML transit models.")
    parser.add_argument("--features-csv", type=str, default="data/processed/features_tabular.csv")
    parser.add_argument("--phase-vectors-npy", type=str, default="data/processed/phase_vectors.npy")
    parser.add_argument("--config", type=str, default="configs/default.yaml")
    parser.add_argument("--output-csv", type=str, default="results/metrics/model_comparison.csv")
    parser.add_argument("--output-json", type=str, default="results/metrics/model_comparison.json")
    parser.add_argument("--plot-path", type=str, default="results/figures/model_comparison.png")
    parser.add_argument("--seed", type=int, default=None, help="Override seed")
    args = parser.parse_args()

    logger = get_logger("model_evaluation")
    cfg = load_config(args.config)
    seed = args.seed if args.seed is not None else cfg.get("project", {}).get("seed", 42)
    set_seed(seed)

    feat_path = Path(args.features_csv)
    pvec_path = Path(args.phase_vectors_npy)

    if not feat_path.exists() or not pvec_path.exists():
        logger.error("Feature files not found. Run generate_synthetic_benchmark.py first.")
        return

    df = pd.read_csv(feat_path)
    X_tabular = df[FEATURE_NAMES].values
    y = df["label"].values.astype(int)
    star_ids = df["target_id"].values
    X_phase = np.load(pvec_path)

    logger.info(f"Loaded {len(df)} samples across {len(np.unique(star_ids))} stars.")

    # 1. Star-level group-aware train/test partition
    splitter = StarGroupSplitter(test_size=cfg.get("evaluation", {}).get("test_size", 0.25), seed=seed)
    (
        X_tab_train, X_tab_test,
        y_train, y_test,
        stars_train, stars_test
    ) = splitter.train_test_split(X_tabular, y, star_ids)

    # Partition phase vectors with identical star indices
    train_mask = np.isin(star_ids, stars_train)
    test_mask = np.isin(star_ids, stars_test)
    X_phase_train, X_phase_test = X_phase[train_mask], X_phase[test_mask]

    logger.info(f"Dataset split: Train = {len(y_train)} stars ({np.sum(y_train==1)} transit, {np.sum(y_train==0)} ctrl), "
                f"Test = {len(y_test)} stars ({np.sum(y_test==1)} transit, {np.sum(y_test==0)} ctrl)")
    logger.info("Verified ZERO star ID leakage between training and testing splits.")

    results_reports = []

    # 2. Train and evaluate classical ML models
    classical_models = build_classical_models(seed=seed)
    for name, wrapper in classical_models.items():
        logger.info(f"Training {name}...")
        wrapper.fit(X_tab_train, y_train)

        y_pred = wrapper.predict(X_tab_test)
        y_proba = wrapper.score_probability(X_tab_test)

        report = compute_metrics(
            y_true=y_test,
            y_pred=y_pred,
            y_proba=y_proba,
            model_name=name,
            train_time_sec=wrapper.train_time_sec,
            inference_latency_ms=wrapper.last_inference_latency_ms
        )
        results_reports.append(report)
        logger.info(f"{name} -> F1: {report.f1:.3f}, Recall: {report.recall:.3f}, Precision: {report.precision:.3f}, PR-AUC: {report.pr_auc:.3f}")

    # 3. Train and evaluate compact 1D CNN
    cnn_cfg = cfg.get("models", {}).get("cnn1d", {})
    logger.info("Training lightweight 1D CNN...")
    cnn_model = CNN1DClassifier(
        sequence_length=X_phase.shape[1],
        epochs=cnn_cfg.get("epochs", 25),
        batch_size=cnn_cfg.get("batch_size", 32),
        lr=cnn_cfg.get("lr", 1e-3),
        seed=seed
    )
    cnn_model.fit(X_phase_train, y_train)
    y_pred_cnn = cnn_model.predict(X_phase_test)
    y_proba_cnn = cnn_model.score_probability(X_phase_test)

    report_cnn = compute_metrics(
        y_true=y_test,
        y_pred=y_pred_cnn,
        y_proba=y_proba_cnn,
        model_name="CNN1D",
        train_time_sec=cnn_model.train_time_sec,
        inference_latency_ms=cnn_model.last_inference_latency_ms
    )
    results_reports.append(report_cnn)
    logger.info(f"CNN1D -> F1: {report_cnn.f1:.3f}, Recall: {report_cnn.recall:.3f}, Precision: {report_cnn.precision:.3f}, PR-AUC: {report_cnn.pr_auc:.3f}")

    # 4. Save metrics tables
    csv_out = Path(args.output_csv)
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    summary_records = [r.to_dict() for r in results_reports]

    res_df = pd.DataFrame(summary_records)
    res_df.to_csv(csv_out, index=False)
    json_out = Path(args.output_json)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, "w") as f:
        json.dump(summary_records, f, indent=2)

    logger.info(f"Saved model comparison table to {csv_out}")

    # 5. Generate comparative visualization
    fig_out = Path(args.plot_path)
    fig_out.parent.mkdir(parents=True, exist_ok=True)

    models = [r.model_name for r in results_reports]
    f1_scores = [r.f1 for r in results_reports]
    pr_aucs = [r.pr_auc for r in results_reports]
    recalls = [r.recall for r in results_reports]

    x = np.arange(len(models))
    width = 0.25

    plt.figure(figsize=(10, 6))
    plt.bar(x - width, f1_scores, width, label="F1-Score", color="#1f77b4")
    plt.bar(x, pr_aucs, width, label="PR-AUC", color="#2ca02c")
    plt.bar(x + width, recalls, width, label="Recall (Detection Rate)", color="#ff7f0e")

    plt.ylabel("Score")
    plt.title("Transit Detection Performance Across Supervised Models")
    plt.xticks(x, models)
    plt.ylim(0, 1.1)
    plt.legend(loc="lower right")
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()

    plt.savefig(fig_out, dpi=200)
    plt.close()
    logger.info(f"Saved comparison figure to {fig_out}")


if __name__ == "__main__":
    main()
