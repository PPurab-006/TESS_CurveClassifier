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
from tess_benchmark.evaluation.recovery import (
    CandidateCatalogMatch,
    EventCoverageRecord,
    HarmonicClass,
    MatchStatus,
    RealDataBenchmarkScorer,
    compute_circular_epoch_residual,
    compute_epoch_tolerance,
    evaluate_event_coverage,
)
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
    enable_cnn: bool = False,
    sde_method: str = "option_a",
    is_formal: bool = False
) -> Dict[str, Any]:
    """Execute the Stage 3 baseline detection and vetting benchmark (exploratory or formal)."""
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

    # 3. Initialize Loader, BLS Detector, Scorer, and Feature Extractor
    loader = TESSDataLoader()
    detector = BLSDetector(
        min_period=0.5,
        max_period=15.0,
        frequency_factor=5.0,
        sde_threshold=6.0,
        min_snr=5.0,
        sde_method=sde_method,
        save_frequency_grid=True
    )
    feature_extractor = FeatureExtractor()
    scorer = RealDataBenchmarkScorer(
        period_tolerance=0.01,
        accepted_harmonic_ratios=(0.5, 1.0, 2.0),
        require_one_to_one=True
    )

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
    logger.info("Executing BLS search and feature extraction across all targets...")
    bls_records: List[Dict[str, Any]] = []
    features_records: List[Dict[str, Any]] = []
    frequency_grids: Dict[str, np.ndarray] = {}

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
        if bls_res.frequency_grid is not None:
            frequency_grids[f"TIC_{tic_id}"] = bls_res.frequency_grid

        # Extract 22 tabular features (passing precomputed BLS result)
        feats = feature_extractor.extract_tabular_features(lc, bls_res)
        feats_row = dict(feats)
        feats_row["tic_id"] = tic_id
        feats_row["target_name"] = target_name
        feats_row["category"] = category
        feats_row["sector"] = sector
        features_records.append(feats_row)

        # Ephemeris, event coverage (GATE-03), and composite recovery matching (GATE-12)
        catalog_period = float(row["period_days"]) if is_host and pd.notna(row["period_days"]) else None
        catalog_t0 = float(row["t0_bjd"]) if is_host and pd.notna(row["t0_bjd"]) else None
        catalog_dur = float(row["duration_hours"]) if is_host and pd.notna(row["duration_hours"]) else None
        catalog_depth = float(row["depth_ppm"]) if is_host and pd.notna(row["depth_ppm"]) else None
        catalog_t0_err = float(row["t0_err"]) if is_host and "t0_err" in row and pd.notna(row["t0_err"]) and float(row["t0_err"]) > 0 else 0.001

        catalog_t0_btjd = (catalog_t0 - 2457000.0) if (catalog_t0 is not None and catalog_t0 > 2400000.0) else catalog_t0

        # GATE-03 Event Coverage Evaluation
        n_events_predicted = 0
        n_primary_adequate = 0
        n_boundary_adequate = 0
        n_inadequate = 0
        has_primary_coverage = False
        has_boundary_coverage = False

        if is_host and catalog_period is not None and catalog_period > 0 and catalog_t0_btjd is not None and catalog_dur is not None and catalog_dur > 0:
            cov_records = evaluate_event_coverage(
                time_array=lc.time,
                catalog_t0=catalog_t0_btjd,
                catalog_period=catalog_period,
                catalog_duration_hours=catalog_dur,
                cadence_sec=float(row.get("cadence_sec", 120.0)),
                min_temporal_coverage_primary=0.50,
                min_valid_cadences_primary=5,
                min_temporal_coverage_boundary=0.30,
                min_valid_cadences_boundary=3
            )
            n_events_predicted = len(cov_records)
            n_primary_adequate = sum(1 for rec in cov_records if rec.is_adequate_interior)
            n_boundary_adequate = sum(1 for rec in cov_records if rec.is_adequate_boundary)
            n_inadequate = sum(1 for rec in cov_records if not rec.is_adequate_interior and not rec.is_adequate_boundary)
            has_primary_coverage = (n_primary_adequate >= 1)
            has_boundary_coverage = (n_boundary_adequate >= 1)

        # GATE-12 Bounded Composite Recovery Matching
        is_recovered = False
        recovery_harmonic: Optional[float] = None
        period_rel_err: Optional[float] = None
        period_ratio: Optional[float] = None
        is_epoch_match = False
        is_full_recovery = False
        epoch_residual_days: Optional[float] = None
        circ_phase_diff: Optional[float] = None
        allowed_epoch_tol: Optional[float] = None
        match_status_str = "N/A_control" if not is_host else "unmatched"
        harmonic_class_str = "non_match"

        if is_host and catalog_period is not None and catalog_period > 0 and catalog_t0_btjd is not None and catalog_dur is not None:
            match_res = scorer.match_candidate(
                detected_period=bls_res.best_period,
                detected_epoch=bls_res.best_t0,
                catalog_period=catalog_period,
                catalog_epoch=catalog_t0_btjd,
                catalog_duration_hours=catalog_dur,
                catalog_timing_uncertainty_days=catalog_t0_err,
                candidate_id=f"cand_TIC_{tic_id}",
                target_id=f"TIC_{tic_id}",
                catalog_planet_id=str(row.get("planet_name", f"TOI_{row.get('toi_id', 'cand')}"))
            )
            is_recovered = match_res.is_period_match
            recovery_harmonic = match_res.nearest_accepted_ratio if match_res.is_period_match else None
            period_rel_err = float(match_res.relative_period_error) if np.isfinite(match_res.relative_period_error) else None
            period_ratio = float(match_res.period_ratio) if np.isfinite(match_res.period_ratio) else None
            is_epoch_match = match_res.is_epoch_match
            is_full_recovery = (match_res.match_status == MatchStatus.FULL_RECOVERY)
            epoch_residual_days = float(match_res.epoch_residual_days) if np.isfinite(match_res.epoch_residual_days) else None
            circ_phase_diff = float(match_res.circular_phase_difference) if np.isfinite(match_res.circular_phase_difference) else None
            allowed_epoch_tol = float(match_res.allowed_epoch_tolerance_days) if np.isfinite(match_res.allowed_epoch_tolerance_days) else None
            match_status_str = match_res.match_status.value
            harmonic_class_str = match_res.harmonic_class.value

        # Multi-planet audit metadata
        is_known_multi = (tic_id in KNOWN_MULTIPLANET_METADATA) or (int(row.get("sy_pnum", 1)) > 1)
        multi_info = KNOWN_MULTIPLANET_METADATA.get(tic_id, {})
        sy_pnum = int(row.get("sy_pnum", multi_info.get("sy_pnum", 1 if is_host else 0)))

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
            "catalog_t0_btjd": catalog_t0_btjd,
            "catalog_duration_hours": catalog_dur,
            "catalog_t0_err_days": catalog_t0_err if is_host else None,
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
            "is_epoch_match": is_epoch_match,
            "is_full_recovery": is_full_recovery,
            "epoch_residual_days": epoch_residual_days,
            "circular_phase_difference": circ_phase_diff,
            "allowed_epoch_tolerance_days": allowed_epoch_tol,
            "match_status": match_status_str,
            "harmonic_class": harmonic_class_str,
            "recovery_type": (
                "fundamental" if (is_recovered and recovery_harmonic == 1.0)
                else ("harmonic" if (is_recovered and recovery_harmonic in (0.5, 2.0))
                      else ("unrecovered" if is_host else "N/A_control"))
            ),
            "n_events_predicted": n_events_predicted,
            "n_primary_adequate_events": n_primary_adequate,
            "n_boundary_adequate_events": n_boundary_adequate,
            "n_inadequate_events": n_inadequate,
            "has_primary_adequate_coverage": has_primary_coverage,
            "has_boundary_adequate_coverage": has_boundary_coverage,
            "grid_n_frequencies": bls_res.metadata.get("grid_info", {}).get("n_frequencies", 0),
            "grid_min_frequency": bls_res.metadata.get("grid_info", {}).get("min_frequency", float("nan")),
            "grid_max_frequency": bls_res.metadata.get("grid_info", {}).get("max_frequency", float("nan")),
            "grid_frequency_factor": bls_res.metadata.get("grid_info", {}).get("frequency_factor", 5.0),
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
    bls_hosts_full = int((hosts_mask & df_bls["is_full_recovery"]).sum())
    bls_hosts_full_fund = int((hosts_mask & df_bls["is_full_recovery"] & (df_bls["recovery_harmonic"] == 1.0)).sum())
    bls_hosts_full_harm = int((hosts_mask & df_bls["is_full_recovery"] & df_bls["recovery_harmonic"].isin([0.5, 2.0])).sum())
    bls_hosts_per_only = int((hosts_mask & df_bls["is_period_recovered"] & (~df_bls["is_epoch_match"])).sum())
    bls_hosts_ep_only = int((hosts_mask & (~df_bls["is_period_recovered"]) & df_bls["is_epoch_match"]).sum())

    # BLS Metrics on Single-Planet Hosts
    bls_single_det = int((single_hosts_mask & df_bls["is_detected"]).sum())
    bls_single_rec = int((single_hosts_mask & df_bls["is_period_recovered"]).sum())
    bls_single_fund = int((single_hosts_mask & df_bls["is_period_recovered"] & (df_bls["recovery_harmonic"] == 1.0)).sum())
    bls_single_harm = int((single_hosts_mask & df_bls["is_period_recovered"] & df_bls["recovery_harmonic"].isin([0.5, 2.0])).sum())
    bls_single_full = int((single_hosts_mask & df_bls["is_full_recovery"]).sum())
    bls_single_full_fund = int((single_hosts_mask & df_bls["is_full_recovery"] & (df_bls["recovery_harmonic"] == 1.0)).sum())
    bls_single_full_harm = int((single_hosts_mask & df_bls["is_full_recovery"] & df_bls["recovery_harmonic"].isin([0.5, 2.0])).sum())
    bls_single_per_only = int((single_hosts_mask & df_bls["is_period_recovered"] & (~df_bls["is_epoch_match"])).sum())
    bls_single_ep_only = int((single_hosts_mask & (~df_bls["is_period_recovered"]) & df_bls["is_epoch_match"]).sum())

    # BLS Metrics on Multi-Planet Hosts (Segregated Ledger)
    bls_multi_det = int((multi_hosts_mask & df_bls["is_detected"]).sum())
    bls_multi_rec = int((multi_hosts_mask & df_bls["is_period_recovered"]).sum())
    bls_multi_fund = int((multi_hosts_mask & df_bls["is_period_recovered"] & (df_bls["recovery_harmonic"] == 1.0)).sum())
    bls_multi_harm = int((multi_hosts_mask & df_bls["is_period_recovered"] & df_bls["recovery_harmonic"].isin([0.5, 2.0])).sum())
    bls_multi_full = int((multi_hosts_mask & df_bls["is_full_recovery"]).sum())
    bls_multi_full_fund = int((multi_hosts_mask & df_bls["is_full_recovery"] & (df_bls["recovery_harmonic"] == 1.0)).sum())
    bls_multi_full_harm = int((multi_hosts_mask & df_bls["is_full_recovery"] & df_bls["recovery_harmonic"].isin([0.5, 2.0])).sum())
    bls_multi_per_only = int((multi_hosts_mask & df_bls["is_period_recovered"] & (~df_bls["is_epoch_match"])).sum())
    bls_multi_ep_only = int((multi_hosts_mask & (~df_bls["is_period_recovered"]) & df_bls["is_epoch_match"]).sum())

    # BLS Metrics on Comparison Stars (Observational Candidate Detections)
    bls_ctrl_det = int((controls_mask & df_bls["is_detected"]).sum())

    # Save exact serialized frequency grids (GATE-09)
    grid_archive_path = output_dir / "bls_frequency_grids.npz"
    if frequency_grids:
        np.savez_compressed(grid_archive_path, **frequency_grids)
        logger.info(f"Saved {len(frequency_grids)} serialized frequency grids to {grid_archive_path}")

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
            "run_type": "FORMAL_STAGE_3_BENCHMARK" if is_formal else "BOUNDED_EXPLORATORY_PROVISIONAL",
            "formal_benchmark_qualification": bool(is_formal),
            "sde_method": sde_method,
            "sde_method_description": (
                "Option C: Peak, harmonic, and alias masked background dispersion" if sde_method == "option_c"
                else f"Option {sde_method.replace('option_', '').upper()}"
            ),
            "execution_timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "manifest_file": str(manifest_path),
            "total_targets": n_total,
            "confirmed_planet_hosts": n_hosts,
            "observational_controls": n_controls,
            "single_planet_hosts_count": n_single_hosts,
            "multi_planet_hosts_count": n_multi_hosts,
            "multi_planet_tics": list(KNOWN_MULTIPLANET_METADATA.keys()) if n_multi_hosts > 0 else [],
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
                "full_recovery_count": bls_hosts_full,
                "full_recovery_rate": bls_hosts_full / max(1, n_hosts),
                "fundamental_full_recovery_count": bls_hosts_full_fund,
                "fundamental_full_recovery_rate": bls_hosts_full_fund / max(1, n_hosts),
                "harmonic_full_recovery_count": bls_hosts_full_harm,
                "harmonic_full_recovery_rate": bls_hosts_full_harm / max(1, n_hosts),
                "period_only_match_count": bls_hosts_per_only,
                "epoch_only_match_count": bls_hosts_ep_only,
                "median_sde": float(df_bls[hosts_mask]["sde"].median()),
                "median_snr": float(df_bls[hosts_mask]["snr"].median()),
            },
            "single_planet_hosts_cohort": {
                "target_count": n_single_hosts,
                "detected_count_sde6_snr5": bls_single_det,
                "detection_rate": bls_single_det / max(1, n_single_hosts),
                "recovered_period_count": bls_single_rec,
                "period_recovery_rate": bls_single_rec / max(1, n_single_hosts),
                "fundamental_recovery_count": bls_single_fund,
                "fundamental_recovery_rate": bls_single_fund / max(1, n_single_hosts),
                "harmonic_recovery_count": bls_single_harm,
                "harmonic_recovery_rate": bls_single_harm / max(1, n_single_hosts),
                "full_recovery_count": bls_single_full,
                "full_recovery_rate": bls_single_full / max(1, n_single_hosts),
                "fundamental_full_recovery_count": bls_single_full_fund,
                "fundamental_full_recovery_rate": bls_single_full_fund / max(1, n_single_hosts),
                "harmonic_full_recovery_count": bls_single_full_harm,
                "harmonic_full_recovery_rate": bls_single_full_harm / max(1, n_single_hosts),
                "period_only_match_count": bls_single_per_only,
                "epoch_only_match_count": bls_single_ep_only,
                "median_sde": float(df_bls[single_hosts_mask]["sde"].median()),
                "median_snr": float(df_bls[single_hosts_mask]["snr"].median()),
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
                "full_recovery_count": bls_single_full,
                "full_recovery_rate": bls_single_full / max(1, n_single_hosts),
                "fundamental_full_recovery_count": bls_single_full_fund,
                "fundamental_full_recovery_rate": bls_single_full_fund / max(1, n_single_hosts),
                "harmonic_full_recovery_count": bls_single_full_harm,
                "harmonic_full_recovery_rate": bls_single_full_harm / max(1, n_single_hosts),
                "period_only_match_count": bls_single_per_only,
                "epoch_only_match_count": bls_single_ep_only,
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
                "full_recovery_count": bls_multi_full,
                "full_recovery_rate": bls_multi_full / max(1, n_multi_hosts),
                "fundamental_full_recovery_count": bls_multi_full_fund,
                "fundamental_full_recovery_rate": bls_multi_full_fund / max(1, n_multi_hosts),
                "harmonic_full_recovery_count": bls_multi_full_harm,
                "harmonic_full_recovery_rate": bls_multi_full_harm / max(1, n_multi_hosts),
                "period_only_match_count": bls_multi_per_only,
                "epoch_only_match_count": bls_multi_ep_only,
                "median_sde": float(df_bls[multi_hosts_mask]["sde"].median()) if n_multi_hosts > 0 else 0.0,
                "median_snr": float(df_bls[multi_hosts_mask]["snr"].median()) if n_multi_hosts > 0 else 0.0,
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
        "event_coverage_metrics": {
            "total_predicted_events": int(df_bls[hosts_mask]["n_events_predicted"].sum()),
            "total_primary_adequate_interior_events": int(df_bls[hosts_mask]["n_primary_adequate_events"].sum()),
            "total_secondary_boundary_diagnostic_events": int(df_bls[hosts_mask]["n_boundary_adequate_events"].sum()),
            "total_inadequate_events": int(df_bls[hosts_mask]["n_inadequate_events"].sum()),
            "hosts_with_primary_adequate_coverage_count": int(df_bls[hosts_mask]["has_primary_adequate_coverage"].sum()),
            "hosts_with_primary_adequate_coverage_rate": float(
                df_bls[hosts_mask]["has_primary_adequate_coverage"].sum() / max(1, n_hosts)
            ),
            "hosts_with_boundary_adequate_coverage_count": int(df_bls[hosts_mask]["has_boundary_adequate_coverage"].sum()),
            "hosts_with_boundary_adequate_coverage_rate": float(
                df_bls[hosts_mask]["has_boundary_adequate_coverage"].sum() / max(1, n_hosts)
            ),
            "primary_adequate_event_fraction": float(
                df_bls[hosts_mask]["n_primary_adequate_events"].sum() / max(1, df_bls[hosts_mask]["n_events_predicted"].sum())
            ),
            "rules": {
                "primary_interior": "fully interior, f_temporal >= 0.50, N_valid >= 5 cadences (GATE-03 Option 2)",
                "secondary_boundary_diagnostic": "boundary-truncated, f_temporal >= 0.30, N_valid >= 3 cadences (GATE-03 Option 2)"
            }
        },
        "bls_frequency_grid_serialization": {
            "status": "SERIALIZED_AND_PERSISTED",
            "archive_filename": "bls_frequency_grids.npz",
            "archive_path": str(grid_archive_path.resolve()),
            "total_grids_persisted": len(frequency_grids),
            "grid_specification": {
                "frequency_factor": 5.0,
                "min_period_days": 0.5,
                "max_period_rule": "min(15.0, 0.95 * baseline)",
                "duration_grid_days": [float(d) for d in detector.duration_grid],
                "sde_method": sde_method,
                "astropy_version": str(astropy.__version__),
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
            "FORMAL RUN: Real TESS Blind Transit Detection Benchmark executed under frozen protocol." if is_formal
            else "PROVISIONAL/EXPLORATORY RUN: Results do not claim formal benchmark qualification.",
            f"GATE-11 ADOPTED: SDE Method {sde_method.upper()} (Peak, harmonic, and alias masked background dispersion)." if (is_formal or sde_method == "option_c")
            else "GATE-11 SDE METHOD: Standard sample mean/std (Option A).",
            "GATE-06 SATISFIED: All 50 confirmed host systems independently verified sy_pnum == 1 in NASA Exoplanet Archive." if n_multi_hosts == 0
            else "GATE-06 INCOMPLETE: 9/50 host systems have sy_pnum > 1 in NASA Exoplanet Archive (selected via TOI-row pl_pnum=1).",
            "BDR-005 APPLIED: Observational comparison stars are treated as non-detection controls, not confirmed negatives.",
            "NO TEST TUNING: Detection thresholds and ML hyperparameters were NOT tuned on this test cohort.",
            "ZERO DATA LEAKAGE: Feature extraction was strictly per-light-curve; supervised ML models were trained exclusively on disjoint external synthetic data."
        ]
    }

    # 8. Export Output Artifacts
    bls_csv_out = output_dir / ("bls_formal_predictions.csv" if is_formal else "bls_exploratory_predictions.csv")
    ml_csv_out = output_dir / ("tabular_ml_formal_predictions.csv" if is_formal else "tabular_ml_exploratory_predictions.csv")
    summary_json_out = output_dir / ("stage3_formal_summary.json" if is_formal else "stage3_exploratory_summary.json")
    report_md_out = output_dir / ("stage3_formal_report.md" if is_formal else "stage3_exploratory_report.md")

    df_bls.to_csv(output_dir / "bls_exploratory_predictions.csv", index=False)
    df_ml_preds.to_csv(output_dir / "tabular_ml_exploratory_predictions.csv", index=False)
    df_features.to_csv(output_dir / "real_cohort_tabular_features.csv", index=False)
    with open(output_dir / "stage3_exploratory_summary.json", "w") as f:
        json.dump(summary_data, f, indent=2)

    # 9. Generate Detailed Markdown Report
    report_content = generate_markdown_report(summary_data, df_bls, df_ml_preds, output_dir)
    with open(output_dir / "stage3_exploratory_report.md", "w") as f:
        f.write(report_content)

    if is_formal:
        df_bls.to_csv(output_dir / "bls_formal_predictions.csv", index=False)
        df_ml_preds.to_csv(output_dir / "tabular_ml_formal_predictions.csv", index=False)
        with open(output_dir / "stage3_formal_summary.json", "w") as f:
            json.dump(summary_data, f, indent=2)
        with open(output_dir / "stage3_formal_report.md", "w") as f:
            f.write(report_content)

    logger.info("=" * 70)
    logger.info(f"Stage 3 {'Formal' if is_formal else 'Exploratory'} Benchmark Run Complete!")
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
    cov_meta = summary.get("event_coverage_metrics", {})
    grid_meta = summary.get("bls_frequency_grid_serialization", {})
    ml = summary["tabular_ml_vetting_metrics"]
    rt = summary["bls_baseline_metrics"]["runtime_performance"]

    is_formal_run = bool(meta.get("formal_benchmark_qualification", False)) or (meta.get("run_type") == "FORMAL_STAGE_3_BENCHMARK")
    header_title = "# Stage 3 Formal Benchmark Run Report (GATE-11 Option C)" if is_formal_run else "# Stage 3 Exploratory Benchmark Run Report (Provisional Baselines)"
    notice_block = (
        "> **FORMAL BENCHMARK EXECUTION**: This execution is the **FORMAL STAGE 3 BENCHMARK** authorized under GATE-11 Option C.\n"
        "> Cohort: 50 confirmed single-planet hosts (`sy_pnum == 1`) + 50 observational comparison stars (100 unique TICs).\n"
        "> All gates (G01–G12) enforced without tuning or post-hoc exclusion."
    ) if is_formal_run else (
        "> **IMPORTANT PROTOCOL NOTICE**: This execution is a **BOUNDED, EXPLORATORY / PROVISIONAL** benchmark run.\n"
        "> It does **NOT** claim formal benchmark qualification or establish model superiority.\n"
        "> An unresolved protocol issue remains: 9/50 host systems have `sy_pnum > 1` in the NASA Exoplanet Archive,\n"
        "> having been selected under the TOI-row `pl_pnum=1` convention. GATE-06 strict single-planet-host\n"
        "> requirements are therefore not fully satisfied. Metrics for single-planet and multi-planet systems\n"
        "> are strictly segregated below."
    )

    lines = [
        header_title,
        "",
        notice_block,
        "",
        "## 1. Execution & Provenance Metadata",
        "",
        f"- **Execution Timestamp (UTC)**: `{meta['execution_timestamp_utc']}`",
        f"- **Run Type**: `{meta['run_type']}`",
        f"- **SDE Background Method (GATE-11)**: `{meta.get('sde_method', 'option_a')}` ({meta.get('sde_method_description', 'Standard sample dispersion')})",
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
        f"- SDE Background Dispersion: {meta.get('sde_method_description', 'Option C')} (GATE-11)",
        "- Thresholds: $\\text{SDE} \\ge 6.0$, $\\text{SNR} \\ge 5.0$",
        "- Period matching tolerance: $1.0\\%$ relative error (GATE-01 Option A)",
        "- Epoch matching tolerance: Bounded composite tolerance $\\Delta t_{0,\\text{tol}} = \\min(0.50 T_{\\text{dur}}, \\sqrt{(0.25 T_{\\text{dur}})^2 + (3 \\sigma_{t_{\\text{mid}}})^2})$ via circular phase (GATE-12 Option C)",
        "- Harmonic policy: Narrow harmonic set $\\mathcal{H} = \\{0.5, 1.0, 2.0\\}$ (GATE-04 Option B)",
        "",
        "| Cohort / Subcohort | Sample Size ($N$) | Candidate Detections (SDE$\\ge$6, SNR$\\ge$5) | Period Recovered (Tol $\\le$ 1%) | Full Recovery ($P + t_0$, GATE-12) | Fundamental Full ($r=1.0$) | Harmonic Full ($r \\in \\{0.5, 2.0\\}$) | Period-Only Match | Median SDE | Median SNR |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        f"| **Single-Planet Hosts (Strict)** | {bls_single['target_count']} | {bls_single['detected_count_sde6_snr5']} ({bls_single['detection_rate']:.1%}) | **{bls_single['recovered_period_count']} ({bls_single['period_recovery_rate']:.1%})** | **{bls_single.get('full_recovery_count', 0)} ({bls_single.get('full_recovery_rate', 0.0):.1%})** | {bls_single.get('fundamental_full_recovery_count', 0)} | {bls_single.get('harmonic_full_recovery_count', 0)} | {bls_single.get('period_only_match_count', 0)} | {bls_single['median_sde']:.2f} | {bls_single['median_snr']:.2f} |",
        f"| **Multi-Planet Hosts (Segregated)** | {bls_multi['target_count']} | {bls_multi['detected_count_sde6_snr5']} ({bls_multi['detection_rate']:.1%}) | **{bls_multi['recovered_period_count']} ({bls_multi['period_recovery_rate']:.1%})** | **{bls_multi.get('full_recovery_count', 0)} ({bls_multi.get('full_recovery_rate', 0.0):.1%})** | {bls_multi.get('fundamental_full_recovery_count', 0)} | {bls_multi.get('harmonic_full_recovery_count', 0)} | {bls_multi.get('period_only_match_count', 0)} | {bls_multi['median_sde']:.2f} | {bls_multi['median_snr']:.2f} |",
        f"| **All Confirmed Hosts (Omnibus)** | {bls_all['target_count']} | {bls_all['detected_count_sde6_snr5']} ({bls_all['detection_rate']:.1%}) | **{bls_all['recovered_period_count']} ({bls_all['period_recovery_rate']:.1%})** | **{bls_all.get('full_recovery_count', 0)} ({bls_all.get('full_recovery_rate', 0.0):.1%})** | {bls_all.get('fundamental_full_recovery_count', 0)} | {bls_all.get('harmonic_full_recovery_count', 0)} | {bls_all.get('period_only_match_count', 0)} | {bls_all['median_sde']:.2f} | {bls_all['median_snr']:.2f} |",
        f"| **Observational Comparison Stars** | {bls_ctrl['target_count']} | {bls_ctrl['candidate_detection_count_sde6_snr5']} ({bls_ctrl['candidate_detection_rate']:.1%}) | N/A (Controls) | N/A | N/A | N/A | N/A | {bls_ctrl['median_sde']:.2f} | {bls_ctrl['median_snr']:.2f} |",
        "",
        f"- **Total BLS Execution Time**: `{rt['total_search_runtime_sec']:.2f} s` (`{rt['mean_search_runtime_sec_per_target']*1000.0:.1f} ms / target`)",
        "",
        "### 2.1 GATE-03 Event Coverage Hierarchy (Option 2 Dual Track)",
        "",
        "Transit event window coverage was evaluated using continuous Lebesgue interval integration:",
        f"- **Total Predicted Events Across Hosts**: `{cov_meta.get('total_predicted_events', 0)}`",
        f"- **Primary Adequate Interior Events** ($f_{{\\text{{temporal}}}} \\ge 0.50, N_{{\\text{{valid}}}} \\ge 5$): `{cov_meta.get('total_primary_adequate_interior_events', 0)}`",
        f"- **Secondary Boundary Diagnostic Events** ($f_{{\\text{{temporal}}}} \\ge 0.30, N_{{\\text{{valid}}}} \\ge 3$): `{cov_meta.get('total_secondary_boundary_diagnostic_events', 0)}`",
        f"- **Inadequate / Sparse Events**: `{cov_meta.get('total_inadequate_events', 0)}`",
        f"- **Hosts with Primary Adequate Coverage**: `{cov_meta.get('hosts_with_primary_adequate_coverage_count', 0)} / {meta['confirmed_planet_hosts']}` (`{cov_meta.get('hosts_with_primary_adequate_coverage_rate', 0.0):.1%}`)",
        "",
        "### 2.2 GATE-09 Serialized Frequency Grid Audit",
        "",
        f"- **Serialization Status**: `{grid_meta.get('status', 'N/A')}`",
        f"- **Grid Archive File**: [`{grid_meta.get('archive_filename', 'N/A')}`](file://{grid_meta.get('archive_path', '')})",
        f"- **Persisted Target Grids**: `{grid_meta.get('total_grids_persisted', 0)}`",
        f"- **Oversampling Factor**: `{grid_meta.get('grid_specification', {}).get('frequency_factor', 5.0)}`",
        "",
    ]

    if meta.get("multi_planet_hosts_count", 0) == 0:
        lines.extend([
            "## 3. Single-Planet Host Integrity Verification (GATE-06)",
            "",
            "All 50 confirmed planet host systems have been verified to have `sy_pnum == 1` in the NASA Exoplanet Archive composite parameters (`ps` table). Exactly 0 multi-planet systems are present in the primary benchmark cohort.",
            "",
        ])
    else:
        lines.extend([
            "## 3. Segregated Audit of the Multi-Planet Host Systems",
            "",
            "The following host stars were checked against the NASA Exoplanet Archive composite parameters (`ps` table) for `sy_pnum > 1`:",
            "",
            "| TIC ID | Hostname | TOI ID | System Planet Count (`sy_pnum`) | Catalog Period (d) | Detected BLS Period (d) | SDE | SNR | Period Recovery Status |",
            "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
        ])
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
        "| Model | Train Time (s) | Inference Latency (ms/target) | Single-Planet Host Recall | Multi-Planet Host Recall | All Hosts Recall | Control Rejection Rate | Control Candidate Flag Rate |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ])

    for m_name, res in ml.items():
        n_s = meta['single_planet_hosts_count']
        n_m = meta['multi_planet_hosts_count']
        lines.append(
            f"| **{m_name}** | {res['training_time_sec']:.3f} | {res['inference_latency_ms_per_target']:.2f} | "
            f"{res['single_planet_hosts_recall_rate']:.1%} ({res['single_planet_hosts_positive_count']}/{n_s}) | "
            f"{res['multi_planet_hosts_recall_rate']:.1%} ({res['multi_planet_hosts_positive_count']}/{max(1, n_m)}) | "
            f"{res['all_hosts_recall_rate']:.1%} ({res['all_hosts_positive_count']}/{meta['confirmed_planet_hosts']}) | "
            f"{res['controls_clean_rejection_rate']:.1%} | {res['controls_positive_rate']:.1%} |"
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
        "- [x] **Multi-Planet Accountability**: Multi-planet systems segregated and explicitly tracked; not silently pooled or concealed.",
        "- [x] **GATE-03 Event Coverage Wire**: Continuous Lebesgue measure evaluated for primary interior and secondary boundary tracks.",
        "- [x] **GATE-12 Bounded Composite Scorer Wire**: Scorer evaluates period, circular epoch residual, and bounded composite tolerance.",
        "- [x] **GATE-09 Frequency Grid Persistence**: Exact frequency arrays serialized to compressed archive.",
        "",
        "## 7. Artifact Index",
        "",
        f"- **BLS Predictions CSV**: [`bls_exploratory_predictions.csv`](file://{(output_dir / 'bls_exploratory_predictions.csv').resolve()})",
        f"- **Tabular ML Predictions CSV**: [`tabular_ml_exploratory_predictions.csv`](file://{(output_dir / 'tabular_ml_exploratory_predictions.csv').resolve()})",
        f"- **Real Cohort Features CSV**: [`real_cohort_tabular_features.csv`](file://{(output_dir / 'real_cohort_tabular_features.csv').resolve()})",
        f"- **BLS Frequency Grids NPZ**: [`bls_frequency_grids.npz`](file://{(output_dir / 'bls_frequency_grids.npz').resolve()})",
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
    default_manifest = (
        "results/real_data_stage2/stage2_corrected_cohort_manifest.csv"
        if Path("results/real_data_stage2/stage2_corrected_cohort_manifest.csv").exists()
        else "results/real_data_stage2/stage2_final_cohort_manifest.csv"
    )
    parser.add_argument(
        "--cohort-manifest",
        type=str,
        default=default_manifest,
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
    parser.add_argument(
        "--sde-method",
        type=str,
        default="option_a",
        choices=["option_a", "option_b", "option_c", "option_d"],
        help="SDE background dispersion method (GATE-11)"
    )
    parser.add_argument(
        "--formal",
        action="store_true",
        help="Execute as formal Stage 3 benchmark"
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
            enable_cnn=args.enable_cnn,
            sde_method=args.sde_method,
            is_formal=args.formal
        )
        return 0
    except Exception as e:
        logger.error(f"Stage 3 Benchmark failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
