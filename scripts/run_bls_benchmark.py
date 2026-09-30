#!/usr/bin/env python3
"""
Run Box Least Squares (BLS) Transit Detection Benchmark.

Evaluates the Astropy BoxLeastSquares baseline detector against the synthetic suite,
measuring detection metrics, period recovery accuracy, and wall-clock execution runtime.
"""
import argparse
import json
from pathlib import Path
import pickle
import numpy as np
import matplotlib.pyplot as plt

from tess_benchmark.utils.logging import get_logger
from tess_benchmark.utils.config import load_config
from tess_benchmark.data.synthetic import preprocess_light_curve
from tess_benchmark.baselines.bls import BLSDetector
from tess_benchmark.evaluation.metrics import compute_metrics


def main():
    parser = argparse.ArgumentParser(description="Run BLS baseline benchmark.")
    parser.add_argument("--data-file", type=str, default="data/processed/synthetic_light_curves.pkl")
    parser.add_argument("--config", type=str, default="configs/default.yaml")
    parser.add_argument("--sde-threshold", type=float, default=6.0)
    parser.add_argument("--output-json", type=str, default="results/metrics/bls_benchmark.json")
    parser.add_argument("--plot-path", type=str, default="results/figures/bls_sde_distribution.png")
    args = parser.parse_args()

    logger = get_logger("bls_benchmark")
    cfg = load_config(args.config)
    bls_cfg = cfg.get("bls", {})

    data_path = Path(args.data_file)
    if not data_path.exists():
        logger.error(f"Data file not found at {data_path}. Run generate_synthetic_benchmark.py first.")
        return

    with open(data_path, "rb") as f:
        light_curves = pickle.load(f)

    logger.info(f"Loaded {len(light_curves)} light curves. Running BLS detector...")

    detector = BLSDetector(
        min_period=bls_cfg.get("min_period", 0.5),
        max_period=bls_cfg.get("max_period", 15.0),
        frequency_factor=bls_cfg.get("frequency_factor", 4.0),
        sde_threshold=args.sde_threshold,
        min_snr=bls_cfg.get("min_snr", 5.0)
    )

    y_true = []
    y_pred = []
    sde_scores = []
    runtimes = []
    period_recovered = []

    for lc in light_curves:
        clean_lc = preprocess_light_curve(lc, clip_outliers=True, detrend=True)
        res = detector.search(clean_lc)

        y_true.append(1 if lc.has_transit else 0)
        y_pred.append(1 if res.is_detected else 0)
        sde_scores.append(res.sde)
        runtimes.append(res.runtime_sec)

        if lc.has_transit:
            true_p = lc.metadata.get("period_days", 0.0)
            rec = res.is_period_recovered(true_p, tolerance=0.03)
            period_recovered.append(rec)

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    sde_scores = np.array(sde_scores)

    # Scale SDE to [0, 1] pseudo-probabilities via sigmoid for PR/ROC curves
    sde_scaled = 1.0 / (1.0 + np.exp(-(sde_scores - args.sde_threshold)))

    report = compute_metrics(
        y_true=y_true,
        y_pred=y_pred,
        y_proba=sde_scaled,
        model_name="BoxLeastSquares",
        train_time_sec=0.0,
        inference_latency_ms=float(np.mean(runtimes) * 1000.0)
    )

    period_rec_rate = float(np.mean(period_recovered)) if len(period_recovered) > 0 else 0.0

    metrics_dict = report.to_dict()
    metrics_dict["period_recovery_rate"] = period_rec_rate
    metrics_dict["mean_search_runtime_sec"] = float(np.mean(runtimes))
    metrics_dict["total_runtime_sec"] = float(np.sum(runtimes))

    out_json = Path(args.output_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w") as f:
        json.dump(metrics_dict, f, indent=2)

    logger.info(f"BLS Results -> Precision: {report.precision:.3f}, Recall: {report.recall:.3f}, "
                f"F1: {report.f1:.3f}, Period Recovery: {period_rec_rate:.1%}, "
                f"Latency: {report.inference_latency_ms:.1f}ms/target")

    # Plot diagnostic SDE distribution
    plot_path = Path(args.plot_path)
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(8, 5))
    plt.hist(sde_scores[y_true == 1], bins=15, alpha=0.6, label="Transit Hosts", color="navy")
    plt.hist(sde_scores[y_true == 0], bins=15, alpha=0.6, label="Control Stars", color="orange")
    plt.axvline(args.sde_threshold, color="red", linestyle="--", label=f"Detection Threshold (SDE={args.sde_threshold})")
    plt.xlabel("Signal Detection Efficiency (SDE)")
    plt.ylabel("Star Count")
    plt.title("BLS Periodogram Signal Detection Efficiency Distribution")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_path, dpi=200)
    plt.close()
    logger.info(f"Saved BLS diagnostic figure to {plot_path}")


if __name__ == "__main__":
    main()
