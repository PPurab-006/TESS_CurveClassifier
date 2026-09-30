#!/usr/bin/env python3
"""
Stage 3 Exploratory Benchmark Pipeline Runner for TESS Transit Detection.

Executes a bounded, exploratory baseline benchmark on the validated Stage 2 cohort:
- Cohort: 100 targets (50 candidate hosts, 50 observational comparison stars) from
  results/real_data_stage2/stage2_final_cohort_manifest.csv.
- Preprocessing: Native SPOC PDCSAP flux with scalar median normalization only (GATE-05 Option 4).
- Quality filtering: Strictly QUALITY == 0 cadences with finite time, flux, and flux_err.
- BLS Search: Astropy BoxLeastSquares with dy=flux_err (inverse-variance weighting, GATE-10),
  period grid [0.5, min(15.0, 0.95 * baseline)] days, frequency_factor=5.0 (GATE-09).
- Period matching: Approved GATE-01 Option A (1.0% relative tolerance) and GATE-04 Option B
  narrow harmonic set {0.5, 1.0, 2.0}.
- Tabular ML Baselines: RandomForest and HistGradientBoosting classifiers trained ONLY on
  disjoint external synthetic data (zero real-target leakage, GATE-02 / BDR-005).
- Deep Learning (CNN1D): Strictly DISABLED (GATE-02 Option C probation).
- Cohort Audit Caveat: Formally tracks and segregates the 9 host systems with sy_pnum > 1
  (selected under the TOI-row pl_pnum=1 convention; GATE-06 strict requirement not fully satisfied).
- Outputs saved to results/real_benchmark_exploratory/.
"""
import argparse
import datetime
import json
import logging
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import sklearn
import astropy

from tess_benchmark.baselines.bls import BLSDetector, BLSResult, match_period_to_harmonics
from tess_benchmark.data.protocol import LightCurveData, TargetCategory
from tess_benchmark.data.tess_loader import TESSDataLoader
from tess_benchmark.evaluation.metrics import compute_metrics
from tess_benchmark.features.extractors import FEATURE_NAMES, FeatureExtractor
from tess_benchmark.models.classical import build_classical_models
from tess_benchmark.utils.config import load_config
from tess_benchmark.utils.seed import set_seed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("stage3_exploratory")

# 9 host systems discovered in post-acquisition audit to have sy_pnum > 1 in NASA Exoplanet Archive
KNOWN_MULTIPLANET_METADATA: Dict[int, Dict[str, Any]] = {
    262530407: {"hostname": "GJ 3090", "sy_pnum": 2, "toi_id": "TOI-177.01"},
    189013224: {"hostname": "TOI-426", "sy_pnum": 2, "toi_id": "TOI-426.01"},
    92352620: {"hostname": "WASP-94 A", "sy_pnum": 2, "toi_id": "TOI-107.01"},
    31374837: {"hostname": "TOI-431", "sy_pnum": 3, "toi_id": "TOI-431.01"},
    183532609: {"hostname": "WASP-8", "sy_pnum": 2, "toi_id": "TOI-191.01"},
    307210830: {"hostname": "L 98-59", "sy_pnum": 5, "toi_id": "TOI-175.01"},
    33692729: {"hostname": "TOI-469", "sy_pnum": 3, "toi_id": "TOI-469.01"},
    52368076: {"hostname": "TOI-125", "sy_pnum": 3, "toi_id": "TOI-125.01"},
    251848941: {"hostname": "TOI-178", "sy_pnum": 6, "toi_id": "TOI-178.01"},
}


def build_fits_index(raw_dir: Path) -> Dict[str, Path]:
    """Index all FITS files under raw_dir by filename."""
    logger.info(f"Scanning for local FITS files in {raw_dir}...")
    index = {p.name: p for p in raw_dir.rglob("*.fits")}
    logger.info(f"Indexed {len(index)} FITS files.")
    return index


def run_stage3_exploratory_benchmark(
    manifest_path: Path,
    raw_dir: Path,
    synthetic_features_path: Path,
    protocol_config_path: Path,
    output_dir: Path,
    seed: int = 42,
    enable_cnn: bool = False
) -> Dict[str, Any]:
    """Execute the exploratory Stage 3 baseline detection and vetting benchmark."""
    t_start_total = time.perf_counter()
    set_seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Enforce Protocol Gates & Prohibitions
    protocol_cfg = load_config(protocol_config_path) if protocol_config_path.exists() else {}
    cnn_cfg = protocol_cfg.get("search_methods", {}).get("cnn1d_deep_baseline", {})
    cnn_enabled_in_config = cnn_cfg.get("enabled", False)

    if enable_cnn or cnn_enabled_in_config:
        raise RuntimeError(
            "GATE-02 Violation: 1D CNN baseline is strictly disabled (enabled: false) "
            "on conditional probation under GATE-02 Option C. Formal qualification "
            "remains unmet; enabling CNN is blocked."
        )

    # 2. Load Manifest & Index FITS Files
    if not manifest_path.exists():
        raise FileNotFoundError(f"Cohort manifest not found: {manifest_path}")

    df_manifest = pd.read_csv(manifest_path)
    logger.info(f"Loaded cohort manifest with {len(df_manifest)} targets from {manifest_path}")

    fits_index = build_fits_index(raw_dir)
    missing_fits = [fn for fn in df_manifest["fits_filename"] if fn not in fits_index]
    if missing_fits:
        raise FileNotFoundError(
            f"Missing {len(missing_fits)} FITS files from {raw_dir}. First 3: {missing_fits[:3]}"
        )

    # 3. Initialize Loader, BLS Detector, and Feature Extractor
    loader = TESSDataLoader()
    detector = BLSDetector(
        min_period=0.5,
        max_period=15.0,
        frequency_factor=5.0,
        sde_threshold=6.0,
        min_snr=5.0
    )
    feature_extractor = FeatureExtractor()

    # 4. Train Disjoint External Tabular ML Models (Zero Real-Cohort Leakage)
    if not synthetic_features_path.exists():
        raise FileNotFoundError(
            f"External synthetic features file not found: {synthetic_features_path}. "
            "Supervised models require disjoint training data to avoid test set contamination."
        )

    df_synth = pd.read_csv(synthetic_features_path)
    X_train_synth = df_synth[FEATURE_NAMES].values
    y_train_synth = df_synth["label"].values.astype(int)
    logger.info(
        f"Training classical ML baselines on disjoint external synthetic dataset "
        f"({len(df_synth)} samples, zero real-target overlap)..."
    )

    all_models = build_classical_models(seed=seed)
    # Approved models from protocol: RandomForest and HistGradientBoosting (GradientBoosting)
    approved_models = {
        "RandomForest": all_models["RandomForest"],
        "HistGradientBoosting": all_models["GradientBoosting"]
    }

    model_train_times = {}
    for m_name, wrapper in approved_models.items():
        wrapper.fit(X_train_synth, y_train_synth)
        model_train_times[m_name] = wrapper.train_time_sec
        logger.info(f"Model {m_name} fitted in {wrapper.train_time_sec:.3f}s")

    # 5. Process Cohort Light Curves: BLS Search & Feature Extraction
    logger.info("Executing BLS search and feature extraction across all 100 targets...")
    bls_records: List[Dict[str, Any]] = []
    features_records: List[Dict[str, Any]] = []

    for idx, row in df_manifest.iterrows():
        tic_id = int(row["tic_id"])
        target_name = str(row["target_name"])
        category = str(row["category"])
        sector = int(row["sector"])
        is_host = (category == "confirmed_planet_host")
        fits_file = fits_index[row["fits_filename"]]

        # Load light curve with scalar median normalization
        target_cat = TargetCategory.CONFIRMED_PLANET_HOST if is_host else TargetCategory.CONTROL_STAR
        lc = loader.load_fits_file(
            fits_path=fits_file,
            flux_column="pdcsap_flux",
            category=target_cat,
            has_transit=is_host,
            target_name=target_name
        )

        # Execute BLS search
        bls_res = detector.search(lc)

        # Extract 22 tabular features (passing precomputed BLS result)
        feats = feature_extractor.extract_tabular_features(lc, bls_res)
        feats_row = dict(feats)
        feats_row["tic_id"] = tic_id
        feats_row["target_name"] = target_name
        feats_row["category"] = category
        feats_row["sector"] = sector
        features_records.append(feats_row)

        # Ephemeris & period recovery matching (for hosts)
        catalog_period = float(row["period_days"]) if is_host and pd.notna(row["period_days"]) else None
        catalog_t0 = float(row["t0_bjd"]) if is_host and pd.notna(row["t0_bjd"]) else None
        catalog_dur = float(row["duration_hours"]) if is_host and pd.notna(row["duration_hours"]) else None
        catalog_depth = float(row["depth_ppm"]) if is_host and pd.notna(row["depth_ppm"]) else None

        is_recovered = False
        recovery_harmonic: Optional[float] = None
        period_rel_err: Optional[float] = None
        period_ratio: Optional[float] = None

        if is_host and catalog_period is not None and catalog_period > 0:
            rec, harmonic, rel_err = match_period_to_harmonics(
                detected_period=bls_res.best_period,
                catalog_period=catalog_period,
                accepted_ratios=(0.5, 1.0, 2.0),
                tolerance=0.01  # GATE-01 Option A: 1.0% relative tolerance
            )
            is_recovered = rec
            recovery_harmonic = harmonic if is_recovered else None
            period_rel_err = float(rel_err)
            period_ratio = float(bls_res.best_period / catalog_period)

        # Multi-planet audit metadata
        is_known_multi = tic_id in KNOWN_MULTIPLANET_METADATA
        multi_info = KNOWN_MULTIPLANET_METADATA.get(tic_id, {})
        sy_pnum = multi_info.get("sy_pnum", 1 if is_host else 0)

        bls_records.append({
            "target_name": target_name,
            "tic_id": tic_id,
            "category": category,
            "sector": sector,
            "is_host": is_host,
            "is_known_multiplanet_system": is_known_multi,
            "sy_pnum": sy_pnum,
            "planet_name": row.get("planet_name"),
            "toi_id": row.get("toi_id"),
            "catalog_period_days": catalog_period,
            "catalog_t0_bjd": catalog_t0,
            "catalog_duration_hours": catalog_dur,
            "catalog_depth_ppm": catalog_depth,
            "detected_period_days": bls_res.best_period,
            "detected_t0_btjd": bls_res.best_t0,
            "detected_duration_days": bls_res.best_duration,
            "detected_depth": bls_res.best_depth,
            "detected_depth_ppm": bls_res.best_depth * 1e6,
            "sde": bls_res.sde,
            "snr": bls_res.snr,
            "max_power": bls_res.max_power,
            "is_detected": bls_res.is_detected,  # SDE >= 6.0 and SNR >= 5.0
            "period_ratio": period_ratio,
            "period_relative_error": period_rel_err,
            "is_period_recovered": is_recovered,
            "recovery_harmonic": recovery_harmonic,
            "recovery_type": (
                "fundamental" if (is_recovered and recovery_harmonic == 1.0)
                else ("harmonic" if (is_recovered and recovery_harmonic in (0.5, 2.0))
                      else ("unrecovered" if is_host else "N/A_control"))
            ),
            "search_runtime_sec": bls_res.runtime_sec
        })

    df_bls = pd.DataFrame(bls_records)
    df_features = pd.DataFrame(features_records)

    # 6. Tabular ML Candidate Vetting Inference on Real Cohort
    logger.info("Evaluating pretrained Tabular ML baselines on real cohort features...")
    X_real = df_features[FEATURE_NAMES].values

    ml_predictions_records: List[Dict[str, Any]] = []
    ml_inference_times = {}

    for m_name, wrapper in approved_models.items():
        t0_inf = time.perf_counter()
        preds = wrapper.predict(X_real)
        probas = wrapper.score_probability(X_real)
        elapsed_inf = time.perf_counter() - t0_inf
        ml_inference_times[m_name] = (elapsed_inf / len(X_real)) * 1000.0  # ms per target

        for i, row in df_manifest.iterrows():
            if len(ml_predictions_records) <= i:
                ml_predictions_records.append({
                    "target_name": row["target_name"],
                    "tic_id": int(row["tic_id"]),
                    "category": row["category"],
                    "sector": int(row["sector"]),
                    "is_host": (row["category"] == "confirmed_planet_host"),
                    "is_known_multiplanet_system": int(row["tic_id"]) in KNOWN_MULTIPLANET_METADATA,
                })
            ml_predictions_records[i][f"{m_name}_pred"] = int(preds[i])
            ml_predictions_records[i][f"{m_name}_proba"] = float(probas[i])

    df_ml_preds = pd.DataFrame(ml_predictions_records)

    # 7. Compute Rigorous Benchmark Metrics & Multi-Planet Breakdown
    hosts_mask = df_bls["is_host"]
    controls_mask = ~df_bls["is_host"]
    single_hosts_mask = hosts_mask & (~df_bls["is_known_multiplanet_system"])
    multi_hosts_mask = hosts_mask & df_bls["is_known_multiplanet_system"]

    n_total = len(df_bls)
    n_hosts = int(hosts_mask.sum())
    n_controls = int(controls_mask.sum())
    n_single_hosts = int(single_hosts_mask.sum())
    n_multi_hosts = int(multi_hosts_mask.sum())

    # BLS Metrics on Full 50 Hosts (Provisional Omnibus)
    bls_hosts_det = int((hosts_mask & df_bls["is_detected"]).sum())
    bls_hosts_rec = int((hosts_mask & df_bls["is_period_recovered"]).sum())
    bls_hosts_fund = int((hosts_mask & df_bls["is_period_recovered"] & (df_bls["recovery_harmonic"] == 1.0)).sum())
    bls_hosts_harm = int((hosts_mask & df_bls["is_period_recovered"] & df_bls["recovery_harmonic"].isin([0.5, 2.0])).sum())

    # BLS Metrics on 41 Single-Planet Hosts
    bls_single_det = int((single_hosts_mask & df_bls["is_detected"]).sum())
    bls_single_rec = int((single_hosts_mask & df_bls["is_period_recovered"]).sum())
    bls_single_fund = int((single_hosts_mask & df_bls["is_period_recovered"] & (df_bls["recovery_harmonic"] == 1.0)).sum())
    bls_single_harm = int((single_hosts_mask & df_bls["is_period_recovered"] & df_bls["recovery_harmonic"].isin([0.5, 2.0])).sum())

    # BLS Metrics on 9 Multi-Planet Hosts (Segregated Ledger)
    bls_multi_det = int((multi_hosts_mask & df_bls["is_detected"]).sum())
    bls_multi_rec = int((multi_hosts_mask & df_bls["is_period_recovered"]).sum())
    bls_multi_fund = int((multi_hosts_mask & df_bls["is_period_recovered"] & (df_bls["recovery_harmonic"] == 1.0)).sum())
    bls_multi_harm = int((multi_hosts_mask & df_bls["is_period_recovered"] & df_bls["recovery_harmonic"].isin([0.5, 2.0])).sum())

    # BLS Metrics on 50 Comparison Stars (Observational Candidate Detections)
    bls_ctrl_det = int((controls_mask & df_bls["is_detected"]).sum())

    # Tabular ML Metrics (Candidate Vetting)
    ml_summary = {}
    for m_name in approved_models.keys():
        pred_col = f"{m_name}_pred"
        proba_col = f"{m_name}_proba"

        hosts_positive = int((hosts_mask & (df_ml_preds[pred_col] == 1)).sum())
        single_positive = int((single_hosts_mask & (df_ml_preds[pred_col] == 1)).sum())
        multi_positive = int((multi_hosts_mask & (df_ml_preds[pred_col] == 1)).sum())
        ctrl_positive = int((controls_mask & (df_ml_preds[pred_col] == 1)).sum())

        ml_summary[m_name] = {
            "training_sample_count": len(df_synth),
            "training_time_sec": model_train_times[m_name],
            "inference_latency_ms_per_target": ml_inference_times[m_name],
            "all_hosts_positive_count": hosts_positive,
            "all_hosts_recall_rate": hosts_positive / max(1, n_hosts),
            "single_planet_hosts_positive_count": single_positive,
            "single_planet_hosts_recall_rate": single_positive / max(1, n_single_hosts),
            "multi_planet_hosts_positive_count": multi_positive,
            "multi_planet_hosts_recall_rate": multi_positive / max(1, n_multi_hosts),
            "controls_positive_count": ctrl_positive,
            "controls_positive_rate": ctrl_positive / max(1, n_controls),
            "controls_clean_rejection_rate": (n_controls - ctrl_positive) / max(1, n_controls),
        }

    total_bls_runtime = float(df_bls["search_runtime_sec"].sum())
    mean_bls_runtime = float(df_bls["search_runtime_sec"].mean())

    summary_data: Dict[str, Any] = {
        "benchmark_metadata": {
            "run_type": "BOUNDED_EXPLORATORY_PROVISIONAL",
            "formal_benchmark_qualification": False,
            "execution_timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "manifest_file": str(manifest_path),
            "total_targets": n_total,
            "confirmed_planet_hosts": n_hosts,
            "observational_controls": n_controls,
            "single_planet_hosts_count": n_single_hosts,
            "multi_planet_hosts_count": n_multi_hosts,
            "multi_planet_tics": list(KNOWN_MULTIPLANET_METADATA.keys()),
            "protocol_reference": "docs/real_data_benchmark_protocol.md (v1.3.2)",
            "config_file": str(protocol_config_path),
            "random_seed": seed,
            "system_info": {
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
                "astropy_version": astropy.__version__,
                "scikit_learn_version": sklearn.__version__,
                "numpy_version": np.__version__,
                "pandas_version": pd.__version__,
            }
        },
        "bls_baseline_metrics": {
            "all_hosts_cohort_n50": {
                "target_count": n_hosts,
                "detected_count_sde6_snr5": bls_hosts_det,
                "detection_rate": bls_hosts_det / max(1, n_hosts),
                "recovered_period_count": bls_hosts_rec,
                "period_recovery_rate": bls_hosts_rec / max(1, n_hosts),
                "fundamental_recovery_count": bls_hosts_fund,
                "fundamental_recovery_rate": bls_hosts_fund / max(1, n_hosts),
                "harmonic_recovery_count": bls_hosts_harm,
                "harmonic_recovery_rate": bls_hosts_harm / max(1, n_hosts),
                "median_sde": float(df_bls[hosts_mask]["sde"].median()),
                "median_snr": float(df_bls[hosts_mask]["snr"].median()),
            },
            "single_planet_hosts_subcohort_n41": {
                "target_count": n_single_hosts,
                "detected_count_sde6_snr5": bls_single_det,
                "detection_rate": bls_single_det / max(1, n_single_hosts),
                "recovered_period_count": bls_single_rec,
                "period_recovery_rate": bls_single_rec / max(1, n_single_hosts),
                "fundamental_recovery_count": bls_single_fund,
                "fundamental_recovery_rate": bls_single_fund / max(1, n_single_hosts),
                "harmonic_recovery_count": bls_single_harm,
                "harmonic_recovery_rate": bls_single_harm / max(1, n_single_hosts),
                "median_sde": float(df_bls[single_hosts_mask]["sde"].median()),
                "median_snr": float(df_bls[single_hosts_mask]["snr"].median()),
            },
            "multi_planet_hosts_subcohort_n9": {
                "target_count": n_multi_hosts,
                "detected_count_sde6_snr5": bls_multi_det,
                "detection_rate": bls_multi_det / max(1, n_multi_hosts),
                "recovered_period_count": bls_multi_rec,
                "period_recovery_rate": bls_multi_rec / max(1, n_multi_hosts),
                "fundamental_recovery_count": bls_multi_fund,
                "fundamental_recovery_rate": bls_multi_fund / max(1, n_multi_hosts),
                "harmonic_recovery_count": bls_multi_harm,
                "harmonic_recovery_rate": bls_multi_harm / max(1, n_multi_hosts),
                "median_sde": float(df_bls[multi_hosts_mask]["sde"].median()),
                "median_snr": float(df_bls[multi_hosts_mask]["snr"].median()),
            },
            "observational_controls_n50": {
                "target_count": n_controls,
                "candidate_detection_count_sde6_snr5": bls_ctrl_det,
                "candidate_detection_rate": bls_ctrl_det / max(1, n_controls),
                "clean_non_detection_count": n_controls - bls_ctrl_det,
                "clean_non_detection_rate": (n_controls - bls_ctrl_det) / max(1, n_controls),
                "median_sde": float(df_bls[controls_mask]["sde"].median()),
                "median_snr": float(df_bls[controls_mask]["snr"].median()),
                "notes": "Controls are observational non-detections (BDR-005), NOT confirmed planet-free negatives."
            },
            "runtime_performance": {
                "total_search_runtime_sec": total_bls_runtime,
                "mean_search_runtime_sec_per_target": mean_bls_runtime,
                "total_elapsed_benchmark_runtime_sec": float(time.perf_counter() - t_start_total)
            }
        },
        "tabular_ml_vetting_metrics": ml_summary,
        "deep_learning_baseline_status": {
            "model_name": "CNN1D",
            "enabled": False,
            "status": "DISABLED_UNDER_GATE_02_OPTION_C",
            "reason": "Conditional probation active; qualification gate unmet; excluded from primary benchmark execution."
        },
        "protocol_deviations_and_caveats": [
            "PROVISIONAL/EXPLORATORY RUN: Results do not claim formal benchmark qualification.",
            "GATE-06 INCOMPLETE: 9/50 host systems have sy_pnum > 1 in NASA Exoplanet Archive (selected via TOI-row pl_pnum=1).",
            "BDR-005 APPLIED: Observational comparison stars are treated as non-detection controls, not confirmed negatives.",
            "NO TEST TUNING: Detection thresholds and ML hyperparameters were NOT tuned on this test cohort.",
            "ZERO DATA LEAKAGE: Feature extraction was strictly per-light-curve; supervised ML models were trained exclusively on disjoint external synthetic data."
        ]
    }

    # 8. Export Output Artifacts
    bls_csv_out = output_dir / "bls_exploratory_predictions.csv"
    ml_csv_out = output_dir / "tabular_ml_exploratory_predictions.csv"
    feats_csv_out = output_dir / "real_cohort_tabular_features.csv"
    summary_json_out = output_dir / "stage3_exploratory_summary.json"
    report_md_out = output_dir / "stage3_exploratory_report.md"

    df_bls.to_csv(bls_csv_out, index=False)
    df_ml_preds.to_csv(ml_csv_out, index=False)
    df_features.to_csv(feats_csv_out, index=False)

    with open(summary_json_out, "w") as f:
        json.dump(summary_data, f, indent=2)

    # 9. Generate Detailed Markdown Report
    report_content = generate_markdown_report(summary_data, df_bls, df_ml_preds, output_dir)
    with open(report_md_out, "w") as f:
        f.write(report_content)

    logger.info("=" * 70)
    logger.info("Stage 3 Exploratory Benchmark Run Complete!")
    logger.info(f"BLS Predictions: {bls_csv_out}")
    logger.info(f"ML Vetting Predictions: {ml_csv_out}")
    logger.info(f"Summary JSON: {summary_json_out}")
    logger.info(f"Markdown Report: {report_md_out}")
    logger.info(
        f"BLS All Hosts Recovery Rate: "
        f"{summary_data['bls_baseline_metrics']['all_hosts_cohort_n50']['period_recovery_rate']:.1%} "
        f"({bls_hosts_rec}/{n_hosts})"
    )
    logger.info(
        f"BLS Single-Planet Recovery Rate: "
        f"{summary_data['bls_baseline_metrics']['single_planet_hosts_subcohort_n41']['period_recovery_rate']:.1%} "
        f"({bls_single_rec}/{n_single_hosts})"
    )
    logger.info(
        f"BLS Comparison Star Candidate Detection Rate: "
        f"{summary_data['bls_baseline_metrics']['observational_controls_n50']['candidate_detection_rate']:.1%} "
        f"({bls_ctrl_det}/{n_controls})"
    )
    logger.info("=" * 70)

    return summary_data


def generate_markdown_report(
    summary: Dict[str, Any],
    df_bls: pd.DataFrame,
    df_ml: pd.DataFrame,
    output_dir: Path
) -> str:
    """Generate comprehensive markdown report for the exploratory run."""
    meta = summary["benchmark_metadata"]
    bls_all = summary["bls_baseline_metrics"]["all_hosts_cohort_n50"]
    bls_single = summary["bls_baseline_metrics"]["single_planet_hosts_subcohort_n41"]
    bls_multi = summary["bls_baseline_metrics"]["multi_planet_hosts_subcohort_n9"]
    bls_ctrl = summary["bls_baseline_metrics"]["observational_controls_n50"]
    ml = summary["tabular_ml_vetting_metrics"]
    rt = summary["bls_baseline_metrics"]["runtime_performance"]

    lines = [
        "# Stage 3 Exploratory Benchmark Run Report (Provisional Baselines)",
        "",
        "> **IMPORTANT PROTOCOL NOTICE**: This execution is a **BOUNDED, EXPLORATORY / PROVISIONAL** benchmark run.",
        "> It does **NOT** claim formal benchmark qualification or establish model superiority.",
        "> An unresolved protocol issue remains: 9/50 host systems have `sy_pnum > 1` in the NASA Exoplanet Archive,",
        "> having been selected under the TOI-row `pl_pnum=1` convention. GATE-06 strict single-planet-host",
        "> requirements are therefore not fully satisfied. Metrics for single-planet and multi-planet systems",
        "> are strictly segregated below.",
        "",
        "## 1. Execution & Provenance Metadata",
        "",
        f"- **Execution Timestamp (UTC)**: `{meta['execution_timestamp_utc']}`",
        f"- **Run Type**: `{meta['run_type']}`",
        f"- **Cohort Manifest**: [`{meta['manifest_file']}`](file://{Path(meta['manifest_file']).resolve()})",
        f"- **Protocol Configuration**: [`{meta['config_file']}`](file://{Path(meta['config_file']).resolve()})",
        f"- **Total Cohort Size**: `{meta['total_targets']}` (50 Confirmed Hosts, 50 Observational Controls)",
        f"- **Single-Planet Host Pool**: `{meta['single_planet_hosts_count']}` targets (`sy_pnum == 1`)",
        f"- **Multi-Planet Host Pool**: `{meta['multi_planet_hosts_count']}` targets (`sy_pnum > 1`, segregated)",
        f"- **Random Seed**: `{meta['random_seed']}`",
        f"- **Python Version**: `{meta['system_info']['python_version']}`",
        f"- **Astropy Version**: `{meta['system_info']['astropy_version']}`",
        f"- **Scikit-Learn Version**: `{meta['system_info']['scikit_learn_version']}`",
        f"- **Total Benchmark Wall-Clock Runtime**: `{rt['total_elapsed_benchmark_runtime_sec']:.2f} s`",
        "",
        "## 2. BLS Primary Baseline Detection Results",
        "",
        "The Box Least Squares (BLS) baseline was executed strictly according to approved protocol settings:",
        "- Period search range: $P \\in [0.5, \\min(15.0, 0.95 \\times T_{\\text{base}})]$ days",
        "- Adaptive frequency grid: `frequency_factor = 5.0` (GATE-09 Option A)",
        "- Weighting: Inverse-variance weighting $w_i = 1 / \\sigma_i^2$ via $dy = \\sigma_{\\text{flux}}$ (GATE-10)",
        "- Thresholds: $\\text{SDE} \\ge 6.0$, $\\text{SNR} \\ge 5.0$",
        "- Period matching tolerance: $1.0\\%$ relative error (GATE-01 Option A)",
        "- Harmonic policy: Narrow harmonic set $\\mathcal{H} = \\{0.5, 1.0, 2.0\\}$ (GATE-04 Option B)",
        "",
        "| Cohort / Subcohort | Sample Size ($N$) | Candidate Detections (SDE$\\ge$6, SNR$\\ge$5) | Period Recovered (Tol $\\le$ 1%) | Fundamental Recovery ($r=1.0$) | Harmonic Recovery ($r \\in \\{0.5, 2.0\\}$) | Median SDE | Median SNR |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        f"| **Single-Planet Hosts (Strict)** | {bls_single['target_count']} | {bls_single['detected_count_sde6_snr5']} ({bls_single['detection_rate']:.1%}) | **{bls_single['recovered_period_count']} ({bls_single['period_recovery_rate']:.1%})** | {bls_single['fundamental_recovery_count']} ({bls_single['fundamental_recovery_rate']:.1%}) | {bls_single['harmonic_recovery_count']} ({bls_single['harmonic_recovery_rate']:.1%}) | {bls_single['median_sde']:.2f} | {bls_single['median_snr']:.2f} |",
        f"| **Multi-Planet Hosts (Segregated)** | {bls_multi['target_count']} | {bls_multi['detected_count_sde6_snr5']} ({bls_multi['detection_rate']:.1%}) | **{bls_multi['recovered_period_count']} ({bls_multi['period_recovery_rate']:.1%})** | {bls_multi['fundamental_recovery_count']} ({bls_multi['fundamental_recovery_rate']:.1%}) | {bls_multi['harmonic_recovery_count']} ({bls_multi['harmonic_recovery_rate']:.1%}) | {bls_multi['median_sde']:.2f} | {bls_multi['median_snr']:.2f} |",
        f"| **All Confirmed Hosts (Omnibus)** | {bls_all['target_count']} | {bls_all['detected_count_sde6_snr5']} ({bls_all['detection_rate']:.1%}) | **{bls_all['recovered_period_count']} ({bls_all['period_recovery_rate']:.1%})** | {bls_all['fundamental_recovery_count']} ({bls_all['fundamental_recovery_rate']:.1%}) | {bls_all['harmonic_recovery_count']} ({bls_all['harmonic_recovery_rate']:.1%}) | {bls_all['median_sde']:.2f} | {bls_all['median_snr']:.2f} |",
        f"| **Observational Comparison Stars** | {bls_ctrl['target_count']} | {bls_ctrl['candidate_detection_count_sde6_snr5']} ({bls_ctrl['candidate_detection_rate']:.1%}) | N/A (Controls) | N/A | N/A | {bls_ctrl['median_sde']:.2f} | {bls_ctrl['median_snr']:.2f} |",
        "",
        f"- **Total BLS Execution Time**: `{rt['total_search_runtime_sec']:.2f} s` (`{rt['mean_search_runtime_sec_per_target']*1000.0:.1f} ms / target`)",
        "",
        "## 3. Segregated Audit of the 9 Multi-Planet Host Systems",
        "",
        "The following 9 host stars in the Stage 2 cohort were selected using the TOI-row `pl_pnum=1` convention,",
        "but an audit against the NASA Exoplanet Archive composite parameters (`ps` table) revealed `sy_pnum > 1`:",
        "",
        "| TIC ID | Hostname | TOI ID | System Planet Count (`sy_pnum`) | Catalog Period (d) | Detected BLS Period (d) | SDE | SNR | Period Recovery Status |",
        "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
    ]

    for tic, info in KNOWN_MULTIPLANET_METADATA.items():
        row_match = df_bls[df_bls["tic_id"] == tic]
        if len(row_match) > 0:
            r = row_match.iloc[0]
            lines.append(
                f"| {tic} | {info['hostname']} | {r['toi_id']} | {info['sy_pnum']} | "
                f"{r['catalog_period_days']:.4f} | {r['detected_period_days']:.4f} | "
                f"{r['sde']:.2f} | {r['snr']:.2f} | {r['recovery_type']} |"
            )

    lines.extend([
        "",
        "## 4. Tabular Machine Learning Candidate Vetting Baselines",
        "",
        "Tabular ML models were trained **strictly on external synthetic data** (zero real-target leakage):",
        "- Feature dimension: 22 astronomical, statistical, and periodogram features",
        "- Decision threshold: 0.50 (predefined; zero test tuning)",
        "- Evaluated on all 100 authentic TESS targets",
        "",
        "| Model | Train Time (s) | Inference Latency (ms/target) | Single-Planet Host Recall ($N=41$) | Multi-Planet Host Recall ($N=9$) | All Hosts Recall ($N=50$) | Control Rejection Rate ($N=50$) | Control Candidate Flag Rate |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])

    for m_name, res in ml.items():
        lines.append(
            f"| **{m_name}** | {res['training_time_sec']:.3f} | {res['inference_latency_ms_per_target']:.2f} | "
            f"{res['single_planet_hosts_recall_rate']:.1%} ({res['single_planet_hosts_positive_count']}/41) | "
            f"{res['multi_planet_hosts_recall_rate']:.1%} ({res['multi_planet_hosts_positive_count']}/9) | "
            f"**{res['all_hosts_recall_rate']:.1%} ({res['all_hosts_positive_count']}/50)** | "
            f"**{res['controls_clean_rejection_rate']:.1%}** | {res['controls_positive_rate']:.1%} ({res['controls_positive_count']}/50) |"
        )

    lines.extend([
        "",
        "## 5. Deep Learning (1D CNN) Status",
        "",
        "- **Status**: **STRICTLY DISABLED** (`enabled: false`)",
        "- **Protocol Authority**: Approved GATE-02 Option C conditional probation",
        "- **Rationale**: Historical all-positive collapse ($FPR=1.0$) on imbalanced data; formal qualification",
        "  admission gate (specificity $\\ge 0.85$, sensitivity $\\ge 0.75$) remains deferred pending independent",
        "  validation cohort assembly. Pipeline correctly enforced this gate by withholding CNN execution.",
        "",
        "## 6. Leakage & Invariant Audit Checklist",
        "",
        "- [x] **Zero Target-Star Leakage**: Preprocessing and normalization ($F / \\text{median}(F)$) computed per-star independently.",
        "- [x] **Zero Feature Selection Leakage**: Predefined 22 features extracted without reference to cohort labels.",
        "- [x] **Zero Test Set Tuning**: BLS thresholds (SDE=6.0, SNR=5.0) and ML decision thresholds (0.50) were fixed a priori.",
        "- [x] **Zero Training Contamination**: Supervised classifiers trained exclusively on disjoint synthetic data (`data/processed/features_tabular.csv`).",
        "- [x] **Observational Control Non-Detection**: Controls designated strictly as `control_star` (BDR-005; non-detections, not confirmed planet-free negatives).",
        "- [x] **Multi-Planet Accountability**: 9 multi-planet systems segregated and explicitly tracked; not silently pooled or concealed.",
        "",
        "## 7. Artifact Index",
        "",
        f"- **BLS Predictions CSV**: [`bls_exploratory_predictions.csv`](file://{(output_dir / 'bls_exploratory_predictions.csv').resolve()})",
        f"- **Tabular ML Predictions CSV**: [`tabular_ml_exploratory_predictions.csv`](file://{(output_dir / 'tabular_ml_exploratory_predictions.csv').resolve()})",
        f"- **Real Cohort Features CSV**: [`real_cohort_tabular_features.csv`](file://{(output_dir / 'real_cohort_tabular_features.csv').resolve()})",
        f"- **Summary JSON**: [`stage3_exploratory_summary.json`](file://{(output_dir / 'stage3_exploratory_summary.json').resolve()})",
        "",
        "## 8. Conclusion & Resumption Safety",
        "",
        "This exploratory run successfully established authentic real-data baseline metrics for the TESS Transit",
        "Detection Benchmark under zero-leakage conditions. Outputs are safely isolated in `results/real_benchmark_exploratory/`.",
        "The project is fully safe to resume later for formal benchmarking once the GATE-06 multi-planet cohort",
        "decision is formally resolved by the researcher."
    ])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3 Exploratory Benchmark Runner")
    parser.add_argument(
        "--cohort-manifest",
        type=str,
        default="results/real_data_stage2/stage2_final_cohort_manifest.csv",
        help="Path to Stage 2 validated cohort manifest CSV"
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="data/raw",
        help="Root directory containing raw FITS files"
    )
    parser.add_argument(
        "--synthetic-features",
        type=str,
        default="data/processed/features_tabular.csv",
        help="Path to external synthetic tabular features for supervised training"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/real_benchmark_protocol.yaml",
        help="Protocol configuration YAML"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results/real_benchmark_exploratory",
        help="Directory to save exploratory benchmark outputs"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible execution"
    )
    parser.add_argument(
        "--enable-cnn",
        action="store_true",
        help="Attempt to enable CNN (prohibited under GATE-02 Option C)"
    )

    args = parser.parse_args()

    try:
        run_stage3_exploratory_benchmark(
            manifest_path=Path(args.cohort_manifest),
            raw_dir=Path(args.raw_dir),
            synthetic_features_path=Path(args.synthetic_features),
            protocol_config_path=Path(args.config),
            output_dir=Path(args.output_dir),
            seed=args.seed,
            enable_cnn=args.enable_cnn
        )
        return 0
    except Exception as e:
        logger.error(f"Stage 3 Exploratory Benchmark failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
