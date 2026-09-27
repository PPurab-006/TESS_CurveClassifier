#!/usr/bin/env python3
"""
Generate Synthetic Light Curve Benchmark Suite.

Produces a reproducible, balanced dataset of synthetic light curves with realistic
planetary transits, trapezoidal limb darkening profiles, stellar rotation variability,
flares, sector downlink gaps, and control stars for pipeline verification.
"""
import argparse
from pathlib import Path
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from tess_benchmark.utils.seed import set_seed
from tess_benchmark.utils.logging import get_logger
from tess_benchmark.utils.config import load_config
from tess_benchmark.data.synthetic import (
    SyntheticTransitConfig,
    generate_synthetic_light_curve,
    preprocess_light_curve,
)
from tess_benchmark.features.extractors import FeatureExtractor


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic benchmark light curves.")
    parser.add_argument("--config", type=str, default="configs/synthetic_benchmark.yaml", help="Path to config YAML")
    parser.add_argument("--n-stars", type=int, default=None, help="Override number of stars")
    parser.add_argument("--output-dir", type=str, default="data/processed", help="Output directory")
    args = parser.parse_args()

    logger = get_logger("synthetic_generator")
    config = load_config(args.config)
    seed = config["dataset"].get("seed", 42)
    set_seed(seed)

    n_stars = args.n_stars or config["dataset"].get("n_stars", 80)
    transit_frac = config["dataset"].get("transit_fraction", 0.5)
    n_transit = int(round(n_stars * transit_frac))
    n_control = n_stars - n_transit

    logger.info(f"Generating synthetic benchmark suite: {n_stars} stars ({n_transit} transits, {n_control} controls)")

    rng = np.random.default_rng(seed)
    t_params = config.get("transit_parameters", {})
    s_params = config.get("stellar_parameters", {})
    sys_params = config.get("systematics", {})

    light_curves = []
    star_ids = []
    labels = []

    # 1. Generate transit host stars
    for i in range(n_transit):
        star_id = f"SYNTH-HOST-{i+1:04d}"
        period = rng.uniform(t_params.get("period_min_days", 1.2), t_params.get("period_max_days", 8.5))
        depth = rng.uniform(t_params.get("depth_min", 0.002), t_params.get("depth_max", 0.012))
        duration = rng.uniform(t_params.get("duration_hours_min", 1.5), t_params.get("duration_hours_max", 4.0))
        t0 = rng.uniform(0.2, period * 0.8)
        noise = rng.uniform(s_params.get("noise_sigma_min", 0.0008), s_params.get("noise_sigma_max", 0.0015))
        var_amp = rng.uniform(0.0005, s_params.get("variability_amplitude_max", 0.003))
        var_period = rng.uniform(s_params.get("variability_period_min_days", 4.0), s_params.get("variability_period_max_days", 14.0))

        cfg = SyntheticTransitConfig(
            duration_days=config["dataset"].get("duration_days", 27.4),
            cadence_minutes=config["dataset"].get("cadence_minutes", 2.0),
            has_transit=True,
            period_days=float(period),
            t0_days=float(t0),
            depth=float(depth),
            duration_hours=float(duration),
            ingress_fraction=t_params.get("ingress_fraction", 0.15),
            noise_sigma=float(noise),
            variability_amplitude=float(var_amp),
            variability_period_days=float(var_period),
            flare_rate=s_params.get("flare_rate", 0.0002),
            flare_amplitude_scale=s_params.get("flare_amplitude_scale", 6.0),
            include_sector_gap=sys_params.get("include_sector_gap", True),
            sector_gap_start=sys_params.get("sector_gap_start", 13.1),
            sector_gap_duration=sys_params.get("sector_gap_duration", 1.2),
            dropout_fraction=sys_params.get("dropout_fraction", 0.01),
            seed=int(rng.integers(1, 1000000))
        )
        lc = generate_synthetic_light_curve(cfg, target_id=star_id)
        light_curves.append(lc)
        star_ids.append(star_id)
        labels.append(1)

    # 2. Generate control stars
    for i in range(n_control):
        star_id = f"SYNTH-CTRL-{i+1:04d}"
        noise = rng.uniform(s_params.get("noise_sigma_min", 0.0008), s_params.get("noise_sigma_max", 0.0015))
        var_amp = rng.uniform(0.0005, s_params.get("variability_amplitude_max", 0.003))
        var_period = rng.uniform(s_params.get("variability_period_min_days", 4.0), s_params.get("variability_period_max_days", 14.0))

        cfg = SyntheticTransitConfig(
            duration_days=config["dataset"].get("duration_days", 27.4),
            cadence_minutes=config["dataset"].get("cadence_minutes", 2.0),
            has_transit=False,
            noise_sigma=float(noise),
            variability_amplitude=float(var_amp),
            variability_period_days=float(var_period),
            flare_rate=s_params.get("flare_rate", 0.0002),
            flare_amplitude_scale=s_params.get("flare_amplitude_scale", 6.0),
            include_sector_gap=sys_params.get("include_sector_gap", True),
            sector_gap_start=sys_params.get("sector_gap_start", 13.1),
            sector_gap_duration=sys_params.get("sector_gap_duration", 1.2),
            dropout_fraction=sys_params.get("dropout_fraction", 0.01),
            seed=int(rng.integers(1, 1000000))
        )
        lc = generate_synthetic_light_curve(cfg, target_id=star_id)
        light_curves.append(lc)
        star_ids.append(star_id)
        labels.append(0)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save light curve objects
    lc_path = out_dir / "synthetic_light_curves.pkl"
    with open(lc_path, "wb") as f:
        pickle.dump(light_curves, f)
    logger.info(f"Saved {len(light_curves)} raw light curve objects to {lc_path}")

    # Extract features for all light curves
    logger.info("Extracting physical and statistical tabular features...")
    extractor = FeatureExtractor(n_phase_bins=200)
    tabular_records = []
    phase_vectors = []

    for idx, lc in enumerate(light_curves):
        clean_lc = preprocess_light_curve(lc, clip_outliers=True, detrend=True)
        feats = extractor.extract_tabular_features(clean_lc)
        feats["target_id"] = lc.target_id
        feats["label"] = lc.has_transit
        tabular_records.append(feats)

        pvec = extractor.extract_phase_vector(clean_lc)
        phase_vectors.append(pvec)

    feat_df = pd.DataFrame(tabular_records)
    feat_csv_path = out_dir / "features_tabular.csv"
    feat_df.to_csv(feat_csv_path, index=False)
    logger.info(f"Saved tabular features ({feat_df.shape}) to {feat_csv_path}")

    pvec_arr = np.array(phase_vectors)
    pvec_path = out_dir / "phase_vectors.npy"
    np.save(pvec_path, pvec_arr)
    logger.info(f"Saved phase vectors array {pvec_arr.shape} to {pvec_path}")

    # Save demonstration plot of sample transit and control
    fig_dir = Path("results/figures")
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex="col")

    lc_host = light_curves[0]
    lc_host_clean = preprocess_light_curve(lc_host, clip_outliers=True, detrend=True)
    axes[0, 0].plot(lc_host.time, lc_host.flux, "k.", alpha=0.3, markersize=2, label="Raw")
    axes[0, 0].set_title(f"Transit Host: {lc_host.target_id} (P={lc_host.metadata['period_days']:.2f}d, depth={lc_host.metadata['depth']*1e6:.0f}ppm)")
    axes[0, 0].set_ylabel("Normalized Flux")
    axes[0, 0].legend()

    axes[1, 0].plot(lc_host_clean.time, lc_host_clean.flux, "b.", alpha=0.4, markersize=2, label="Preprocessed & Detrended")
    axes[1, 0].set_xlabel("Time (days)")
    axes[1, 0].set_ylabel("Detrended Flux")
    axes[1, 0].legend()

    lc_ctrl = light_curves[n_transit]
    lc_ctrl_clean = preprocess_light_curve(lc_ctrl, clip_outliers=True, detrend=True)
    axes[0, 1].plot(lc_ctrl.time, lc_ctrl.flux, "k.", alpha=0.3, markersize=2, label="Raw")
    axes[0, 1].set_title(f"Control Star: {lc_ctrl.target_id} (No Injected Transit)")
    axes[0, 1].legend()

    axes[1, 1].plot(lc_ctrl_clean.time, lc_ctrl_clean.flux, "g.", alpha=0.4, markersize=2, label="Preprocessed")
    axes[1, 1].set_xlabel("Time (days)")
    axes[1, 1].legend()

    plt.tight_layout()
    demo_plot_path = fig_dir / "synthetic_samples.png"
    plt.savefig(demo_plot_path, dpi=200)
    plt.close()
    logger.info(f"Saved sample visualization to {demo_plot_path}")


if __name__ == "__main__":
    main()
