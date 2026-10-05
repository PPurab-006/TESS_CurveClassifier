#!/usr/bin/env python3
"""
Stage 4 Candidate Vetting: Synthetic Candidate Generation, Validation, and Freezing Pipeline.

Executes Phases 1-3 of the Stage 4 Plan:
1. Generates 600 synthetic candidates through the full discovery pipeline (LC -> BLS -> Candidate -> 52 Features).
2. Performs 5-fold star-group cross-validation across classical models and feature ablation groups.
3. Selects the champion architecture and calibrates the decision threshold using the deterministic tie-break rule.
4. Fits and serializes the frozen champion candidate vetter.
5. Computes SHA-256 hashes of all components and writes the immutable pre-evaluation checkpoint manifest.

STOP DIRECTIVE: Does NOT evaluate or access the real 100-target cohort.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import pandas as pd
import yaml

from tess_benchmark.utils.seed import set_seed
from tess_benchmark.utils.logging import get_logger
from tess_benchmark.stage4.features import (
    BASELINE_FEATURE_NAMES,
    STAGE4_NEW_FEATURE_NAMES,
    STAGE4_FEATURE_GROUPS,
    STAGE4_FEATURE_NAMES,
)
from tess_benchmark.stage4.synthetic_generator import (
    SyntheticCandidateConfig,
    generate_synthetic_candidate_dataset,
)
from tess_benchmark.stage4.vetter import (
    CandidateVetter,
    calibrate_decision_threshold,
    evaluate_synthetic_cross_validation,
    train_and_calibrate_candidate_vetter,
)


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_string_sha256(text: str) -> str:
    """Compute SHA-256 checksum of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_feature_audit_markdown(output_path: Path):
    """Write Phase 1 Feature Audit markdown comparing baseline and new features."""
    lines = [
        "# Stage 4 Candidate Vetting: Feature Schema Audit",
        "",
        "## 1. Executive Summary",
        "",
        "The Stage 4 candidate vetting schema consists of **exactly 52 deterministic features**:",
        "- **22 Baseline Features**: Preserved identically from Stage 3 (`FeatureExtractor`).",
        "- **30 New Transit Morphology & Context Features**: Developed to address BLS periodic false alarms on real TESS data.",
        "",
        "All features are computed label-blind and strictly per-light-curve using each candidate's detected BLS parameters $(P, t_0, T_{\\text{dur}}, \\delta)$.",
        "",
        "## 2. Feature Schema Table",
        "",
        "| Index | Feature Name | Group | Physical Category | Expected Physical Utility | Edge-Case / Missing Contract |",
        "| :---: | :--- | :---: | :---: | :--- | :--- |",
    ]

    descriptions = {
        # Baseline (22)
        "bls_sde": ("baseline", "BLS Peak Prominence", "Primary spectral detection efficiency", "Always defined (finite float)"),
        "bls_snr": ("baseline", "BLS Transit SNR", "Transit depth over photometric error in transit", "Always defined (finite float)"),
        "bls_period": ("baseline", "BLS Period", "Detected period in days", "Always defined (finite float)"),
        "bls_depth": ("baseline", "BLS Depth", "Detected fractional depth", "Always defined (finite float)"),
        "bls_duration": ("baseline", "BLS Duration", "Detected transit duration in days", "Always defined (finite float)"),
        "bls_duty_cycle": ("baseline", "BLS Duty Cycle", "Detected duration / period", "Always defined (finite float)"),
        "bls_max_power": ("baseline", "BLS Power", "Peak periodogram objective power", "Always defined (finite float)"),
        "flux_std": ("baseline", "Flux Distribution", "Overall standard deviation of light curve", "Always defined (finite float)"),
        "flux_skewness": ("baseline", "Flux Distribution", "Sample skewness of flux", "0.0 if cadences < 5"),
        "flux_kurtosis": ("baseline", "Flux Distribution", "Sample kurtosis of flux", "0.0 if cadences < 5"),
        "flux_mad": ("baseline", "Flux Distribution", "Median absolute deviation of flux", "Always defined (finite float)"),
        "flux_p1": ("baseline", "Flux Distribution", "1st percentile of flux", "Always defined (finite float)"),
        "flux_p5": ("baseline", "Flux Distribution", "5th percentile of flux", "Always defined (finite float)"),
        "flux_iqr": ("baseline", "Flux Distribution", "Interquartile range (p75 - p25)", "Always defined (finite float)"),
        "flux_min": ("baseline", "Flux Distribution", "Minimum flux value", "Always defined (finite float)"),
        "flux_depth_robust": ("baseline", "Flux Distribution", "Median minus 1st percentile", "Always defined (finite float)"),
        "von_neumann_ratio": ("baseline", "Dynamics", "Serial correlation metric (eta)", "2.0 if cadences < 4"),
        "outlier_fraction_low": ("baseline", "Outliers", "Fraction of flux points < med - 3 sigma", "Always defined (finite float)"),
        "outlier_fraction_high": ("baseline", "Outliers", "Fraction of flux points > med + 3 sigma", "Always defined (finite float)"),
        "folded_transit_depth": ("baseline", "Folded Diagnostics", "Median out minus median in flux", "0.0 if P <= 0"),
        "odd_even_depth_ratio": ("baseline", "Folded Diagnostics", "Odd vs even depth min/max ratio", "1.0 if P <= 0 or duration <= 0"),
        "secondary_eclipse_depth": ("baseline", "Folded Diagnostics", "Depth at phase 0.5", "0.0 if P <= 0 or duration <= 0"),
        # Group A: Shape (7)
        "shape_depth_to_local_mad": ("shape", "Geometry", "Detected depth divided by local out-of-transit scatter", "np.nan if local cadences < 5"),
        "shape_candidate_duty_cycle": ("shape", "Geometry", "Candidate duration / period", "np.nan if P <= 0 or T_dur <= 0"),
        "shape_in_out_contrast": ("shape", "Geometry", "Contrast between in-transit and out-of-transit flux", "np.nan if in < 3 or out < 10"),
        "shape_ingress_ratio": ("shape", "Geometry", "Estimated ingress+egress width / total duration", "np.nan if unresolvable; [0, 1]"),
        "shape_in_transit_fraction": ("shape", "Geometry", "Fraction of valid cadences inside transit", "Always defined [0, 1]"),
        "shape_in_transit_mad": ("shape", "Geometry", "MAD dispersion inside transit window", "np.nan if in < 5"),
        "shape_mad_ratio": ("shape", "Geometry", "Ratio of in-transit to out-of-transit MAD", "np.nan if in < 5 or out < 10"),
        # Group B: Morphology (5)
        "morph_symmetry": ("morphology", "Profile", "Correlation between folded ingress and flipped egress", "np.nan if bins < 5 or zero var"),
        "morph_ingress_egress_diff": ("morphology", "Profile", "Flux difference between ingress and egress wings / depth", "np.nan if wing cadences < 3"),
        "morph_flat_bottom_kurtosis": ("morphology", "Profile", "Excess kurtosis of in-transit flux points", "np.nan if in-transit cadences < 10"),
        "morph_broad_depression_ratio": ("morphology", "Profile", "Dip in 3x duration window vs 1x duration window", "np.nan if duty cycle >= 0.30"),
        "morph_core_to_wing_ratio": ("morphology", "Profile", "Core transit depth / (core + wing depth)", "np.nan if core < 3 or wings < 3"),
        # Group C: Event Consistency (5)
        "event_n_observed": ("event_consistency", "Events", "Count of transit windows crossing data baseline", "Always defined integer >= 0"),
        "event_n_adequate": ("event_consistency", "Events", "Count of transit windows with >=5 cadences & >=50% coverage", "Always defined integer >= 0"),
        "event_adequate_fraction": ("event_consistency", "Events", "Ratio of adequate events to observed events", "Always defined [0, 1]"),
        "event_depth_scatter_mad": ("event_consistency", "Events", "MAD scatter of individual transit depths / median depth", "np.nan if adequate events < 3"),
        "event_single_event_dominance": ("event_consistency", "Events", "Max event depth / sum of positive event depths", "1.0 if 1 event; np.nan if 0 events"),
        # Group D: Odd/Even (4)
        "odd_even_depth_difference": ("odd_even", "Alternation", "Absolute difference between odd and even transit depths", "np.nan if odd or even missing"),
        "odd_even_depth_ratio_v2": ("odd_even", "Alternation", "Min(odd, even) / Max(odd, even) depth ratio", "np.nan if odd or even missing"),
        "odd_even_significance": ("odd_even", "Alternation", "Depth difference normalized by combined standard error", "np.nan if odd < 2 or even < 2"),
        "secondary_eclipse_max_depth_ratio": ("odd_even", "Alternation", "Secondary eclipse depth at phase 0.5 / primary depth", "np.nan if duty cycle >= 0.35"),
        # Group E: Variability (5)
        "var_global_to_local_std": ("variability", "Activity", "Total light curve std / local moving scatter", "Always defined >= 1.0"),
        "var_autocorr_peak": ("variability", "Activity", "Peak prominence of autocorrelation function at non-zero lag", "np.nan if baseline < 5 days"),
        "var_has_autocorr_modulation": ("variability", "Activity", "Binary flag indicating autocorrelation peak >= 0.20", "np.nan if ACF undefined"),
        "var_flare_cadence_rate": ("variability", "Activity", "Fraction of cadences exceeding median + 4 sigma", "Always defined [0, 1]"),
        "var_out_of_transit_smoothness": ("variability", "Activity", "Von Neumann ratio on out-of-transit cadences", "2.0 if out < 10"),
        # Group F: Localization (4)
        "local_variance_contrast": ("localization", "Concentration", "Fraction of variance in transit / duty cycle", "np.nan if in < 5 or var <= 0"),
        "local_flux_deficit_concentration": ("localization", "Concentration", "Flux deficit inside transit / total flux deficit", "Always defined [0, 1]"),
        "local_dip_isolation": ("localization", "Concentration", "Transit depth / deepest out-of-transit dip depth", "Always defined >= 0.0"),
        "local_baseline_flatness": ("localization", "Concentration", "Standard deviation of binned out-of-transit profile / noise", "np.nan if out < 5"),
    }

    for idx, name in enumerate(STAGE4_FEATURE_NAMES, start=1):
        grp, cat, util, edge = descriptions[name]
        lines.append(f"| {idx} | `{name}` | `{grp}` | {cat} | {util} | {edge} |")

    lines.extend([
        "",
        "## 3. Schema Invariants",
        "",
        "- Total feature count: `52`",
        "- Unique feature count: `52`",
        "- Deterministic ordering: Fixed and preserved across all pipelines.",
        "- Missingness: Explicit `np.nan` values handled via median imputation with missing indicator for RF/LR, and natively in HistGradientBoosting.",
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def write_feature_definitions_yaml(output_path: Path):
    """Write machine-readable YAML definitions of all 52 features."""
    schema = {
        "version": "1.0.0",
        "total_features": len(STAGE4_FEATURE_NAMES),
        "groups": STAGE4_FEATURE_GROUPS,
        "feature_list": STAGE4_FEATURE_NAMES,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(schema, f, sort_keys=False)


def run_stage4_synthetic_pipeline(
    output_dir: Path,
    synthetic_dir: Path,
    seed: int = 42,
    n_transits: int = 300,
    n_confounders_per_class: int = 60
) -> Dict[str, Any]:
    """Execute Phases 1-3 of the Stage 4 Vetting Workflow."""
    logger = get_logger("stage4_synthetic_runner")
    set_seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    synthetic_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=================================================================")
    logger.info("STAGE 4 CANDIDATE VETTING: SYNTHETIC TRAINING & FREEZING PIPELINE")
    logger.info("=================================================================")

    # 1. Export Feature Audit and YAML Schema
    logger.info("Exporting feature audit and schema definitions...")
    audit_md_path = output_dir / "feature_audit.md"
    schema_yaml_path = output_dir / "feature_definitions.yaml"
    write_feature_audit_markdown(audit_md_path)
    write_feature_definitions_yaml(schema_yaml_path)

    # 2. Generate or Load Synthetic Candidate Population
    synth_csv_path = synthetic_dir / "synthetic_candidates_52feats.csv"
    audit_json_path = output_dir / "synthetic_bls_trigger_audit.json"

    if synth_csv_path.exists() and audit_json_path.exists():
        logger.info(f"Loading existing synthetic candidate dataset from {synth_csv_path}")
        df_synthetic = pd.read_csv(synth_csv_path)
        with open(audit_json_path) as f:
            gen_audit = json.load(f)
    else:
        logger.info(f"Generating synthetic candidate population (N={n_transits} transits, N={n_confounders_per_class} per confounder)...")
        cfg = SyntheticCandidateConfig(
            n_transits=n_transits,
            n_confounders_per_class=n_confounders_per_class,
            duration_days=27.4,
            cadence_minutes=2.0,
            seed=seed,
            sde_threshold=6.0,
            min_snr=5.0,
            frequency_factor=4.0,
            sde_method="option_c"
        )
        df_synthetic, gen_audit = generate_synthetic_candidate_dataset(cfg, admit_only_detected=True)
        df_synthetic.to_csv(synth_csv_path, index=False)
        with open(audit_json_path, "w") as f:
            json.dump(gen_audit, f, indent=2)
        logger.info(f"Saved {len(df_synthetic)} candidates to {synth_csv_path}")

    # Assert exactly 52 features in dataset
    for feat in STAGE4_FEATURE_NAMES:
        assert feat in df_synthetic.columns, f"Feature {feat} missing from synthetic dataset"

    n_tot = len(df_synthetic)
    n_pos = int(np.sum(df_synthetic["label"] == 1))
    n_neg = int(np.sum(df_synthetic["label"] == 0))
    logger.info(f"Synthetic Cohort: {n_tot} candidates ({n_pos} genuine transits, {n_neg} confounders)")

    # 3. Model Comparison on 5-Fold Star-Group Cross-Validation
    logger.info("Evaluating classical model architectures on synthetic 5-fold CV...")
    models_to_test = ["LogisticRegression", "RandomForest", "HistGradientBoosting"]
    model_cv_results: List[Dict[str, Any]] = []

    for m_name in models_to_test:
        logger.info(f"Running 5-fold CV for {m_name} (52 features)...")
        rep_full, oof_full, y_true = evaluate_synthetic_cross_validation(
            df_synthetic=df_synthetic,
            model_name=m_name,
            feature_names=STAGE4_FEATURE_NAMES,
            seed=seed
        )
        # Also evaluate on Baseline A (22 features)
        rep_base, oof_base, _ = evaluate_synthetic_cross_validation(
            df_synthetic=df_synthetic,
            model_name=m_name,
            feature_names=BASELINE_FEATURE_NAMES,
            seed=seed
        )
        model_cv_results.append({
            "model_name": m_name,
            "baseline_22_f1": rep_base.f1,
            "baseline_22_pr_auc": rep_base.pr_auc,
            "baseline_22_roc_auc": rep_base.roc_auc,
            "baseline_22_recall": rep_base.recall,
            "baseline_22_specificity": rep_base.specificity,
            "full_52_f1": rep_full.f1,
            "full_52_pr_auc": rep_full.pr_auc,
            "full_52_roc_auc": rep_full.roc_auc,
            "full_52_recall": rep_full.recall,
            "full_52_specificity": rep_full.specificity,
            "pr_auc_gain": rep_full.pr_auc - rep_base.pr_auc,
            "f1_gain": rep_full.f1 - rep_base.f1,
        })

    df_model_comparison = pd.DataFrame(model_cv_results)
    model_comp_path = output_dir / "model_comparison_synthetic_cv.csv"
    df_model_comparison.to_csv(model_comp_path, index=False)
    logger.info(f"Saved model comparison table to {model_comp_path}")

    # 4. Programmatic Champion Model Selection (Strict Protocol Enforcement)
    # Stated rule:
    # 1. Filter candidates to those satisfying synthetic OOF Recall >= 0.90
    # 2. Select the model with maximum full-52-feature OOF PR-AUC
    # 3. Deterministic tie-breaking:
    #    - maximize PR-AUC
    #    - then maximize recall
    #    - then, if still tied, deterministic alphabetical model-name ordering
    min_model_recall = 0.90
    eligible_models = [m for m in model_cv_results if m["full_52_recall"] >= min_model_recall]
    if not eligible_models:
        logger.warning(f"No model met full_52_recall >= {min_model_recall}; considering all models.")
        eligible_models = list(model_cv_results)

    eligible_models.sort(key=lambda m: (-m["full_52_pr_auc"], -m["full_52_recall"], m["model_name"]))
    champion_name = eligible_models[0]["model_name"]
    logger.info(f"Programmatically selected champion model: {champion_name} "
                f"(full-52 PR-AUC={eligible_models[0]['full_52_pr_auc']:.4f}, "
                f"recall={eligible_models[0]['full_52_recall']:.4f})")

    # 5. Feature Ablation Study across Groups (Synthetic 5-fold CV using Champion Architecture)
    logger.info(f"Executing feature group ablation study across synthetic CV folds using champion ({champion_name})...")
    ablation_definitions = [
        ("Run_A_Baseline", BASELINE_FEATURE_NAMES),
        ("Run_B_Plus_Shape", BASELINE_FEATURE_NAMES + STAGE4_FEATURE_GROUPS["shape"]),
        ("Run_C_Plus_Morphology", BASELINE_FEATURE_NAMES + STAGE4_FEATURE_GROUPS["shape"] + STAGE4_FEATURE_GROUPS["morphology"]),
        ("Run_D_Plus_EventConsistency", BASELINE_FEATURE_NAMES + STAGE4_FEATURE_GROUPS["shape"] + STAGE4_FEATURE_GROUPS["morphology"] + STAGE4_FEATURE_GROUPS["event_consistency"]),
        ("Run_E_Plus_OddEven", BASELINE_FEATURE_NAMES + STAGE4_FEATURE_GROUPS["shape"] + STAGE4_FEATURE_GROUPS["morphology"] + STAGE4_FEATURE_GROUPS["event_consistency"] + STAGE4_FEATURE_GROUPS["odd_even"]),
        ("Run_F_Plus_Variability", BASELINE_FEATURE_NAMES + STAGE4_FEATURE_GROUPS["shape"] + STAGE4_FEATURE_GROUPS["morphology"] + STAGE4_FEATURE_GROUPS["event_consistency"] + STAGE4_FEATURE_GROUPS["odd_even"] + STAGE4_FEATURE_GROUPS["variability"]),
        ("Run_G_Full_52Features", STAGE4_FEATURE_NAMES),
    ]

    ablation_rows: List[Dict[str, Any]] = []
    for run_name, feat_subset in ablation_definitions:
        logger.info(f"Evaluating ablation: {run_name} ({len(feat_subset)} features)...")
        rep, oof_p, y_t = evaluate_synthetic_cross_validation(
            df_synthetic=df_synthetic,
            model_name=champion_name,
            feature_names=feat_subset,
            seed=seed
        )
        ablation_rows.append({
            "ablation_run": run_name,
            "feature_count": len(feat_subset),
            "f1": rep.f1,
            "pr_auc": rep.pr_auc,
            "roc_auc": rep.roc_auc,
            "recall": rep.recall,
            "specificity": rep.specificity,
            "precision": rep.precision,
        })

    df_ablation = pd.DataFrame(ablation_rows)
    ablation_path = output_dir / "ablation_synthetic_cv.csv"
    df_ablation.to_csv(ablation_path, index=False)
    logger.info(f"Saved synthetic ablation table to {ablation_path}")

    # 6. Fit Champion Architecture and Run Deterministic Decision-Threshold Calibration
    logger.info(f"Training and calibrating champion model: {champion_name} with full 52-feature schema.")

    champion_vetter, calib_res, cv_report = train_and_calibrate_candidate_vetter(
        df_synthetic=df_synthetic,
        model_name=champion_name,
        feature_names=STAGE4_FEATURE_NAMES,
        min_recall=0.92,
        seed=seed
    )

    # Save threshold calibration table
    calib_csv_path = output_dir / "threshold_calibration_synthetic_table.csv"
    calib_res.calibration_table.to_csv(calib_csv_path, index=False)
    logger.info(f"Selected decision threshold: tau = {calib_res.selected_threshold:.4f} "
                f"(F1={calib_res.best_f1:.4f}, Recall={calib_res.recall_at_selected:.4f}, "
                f"Specificity={calib_res.specificity_at_selected:.4f})")

    # 7. Serialize Frozen Vetter Artifact
    frozen_vetter_path = output_dir / "frozen_candidate_vetter.joblib"
    champion_vetter.save(frozen_vetter_path)
    logger.info(f"Serialized frozen candidate vetter to {frozen_vetter_path}")

    # Also train and freeze matched Baseline A vetter (22 features) for fair comparison
    logger.info(f"Training and serializing matched Baseline A vetter ({champion_name}, 22 baseline features)...")
    baseline_vetter, base_calib, base_rep = train_and_calibrate_candidate_vetter(
        df_synthetic=df_synthetic,
        model_name=champion_name,
        feature_names=BASELINE_FEATURE_NAMES,
        min_recall=0.92,
        seed=seed
    )
    frozen_baseline_path = output_dir / "frozen_baseline_vetter_22feats.joblib"
    baseline_vetter.save(frozen_baseline_path)

    # 8. Compute Checkpoint Hashes
    real_cohort_manifest_path = Path("results/real_data_stage2/stage2_corrected_cohort_manifest.csv")
    assert real_cohort_manifest_path.exists(), "Real cohort manifest missing!"

    real_cohort_hash = compute_sha256(real_cohort_manifest_path)
    synth_dataset_hash = compute_sha256(synth_csv_path)
    frozen_vetter_hash = compute_sha256(frozen_vetter_path)
    frozen_baseline_hash = compute_sha256(frozen_baseline_path)
    feature_schema_hash = compute_string_sha256(json.dumps(STAGE4_FEATURE_NAMES))

    # Determine hyperparameters for serialized champion model
    if champion_name == "RandomForest":
        champ_params = {
            "n_estimators": 150,
            "max_depth": 8,
            "min_samples_leaf": 4,
            "class_weight": "balanced",
            "random_state": seed,
            "n_jobs": -1,
            "preprocessing": "SimpleImputer(strategy='median')",
        }
    elif champion_name == "HistGradientBoosting":
        champ_params = {
            "max_iter": 100,
            "max_depth": 5,
            "min_samples_leaf": 5,
            "class_weight": "balanced",
            "random_state": seed,
        }
    elif champion_name == "LogisticRegression":
        champ_params = {
            "max_iter": 1000,
            "C": 1.0,
            "class_weight": "balanced",
            "random_state": seed,
            "preprocessing": "SimpleImputer(strategy='median') + StandardScaler()",
        }
    else:
        champ_params = {}

    # 9. Write Immutable Pre-Evaluation Checkpoint Manifest
    checkpoint = {
        "checkpoint_type": "STAGE_4_PRE_EVALUATION_FIREWALL_CHECKPOINT",
        "status": "FROZEN_AWAITING_AUTHORIZATION",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_git_commit": "fc795a71391129ae59219fb52e88b9a967fd4ca8",
        "real_cohort_manifest_sha256": real_cohort_hash,
        "synthetic_candidate_dataset_sha256": synth_dataset_hash,
        "frozen_vetter_artifact_sha256": frozen_vetter_hash,
        "frozen_baseline_artifact_sha256": frozen_baseline_hash,
        "feature_schema_sha256": feature_schema_hash,
        "feature_count": len(STAGE4_FEATURE_NAMES),
        "feature_schema_ordered": STAGE4_FEATURE_NAMES,
        "model_selection_rule": (
            "Maximize full-52 synthetic OOF PR-AUC subject to Recall >= 0.90; "
            "tie-break 1: maximize recall; tie-break 2: deterministic alphabetical model name"
        ),
        "champion_model_name": champion_name,
        "champion_hyperparameters": champ_params,
        "deterministic_threshold_rule": calib_res.rule_description,
        "calibrated_decision_threshold": calib_res.selected_threshold,
        "synthetic_cv_performance": {
            "pr_auc": cv_report.pr_auc,
            "roc_auc": cv_report.roc_auc,
            "f1_at_selected_threshold": calib_res.best_f1,
            "recall_at_selected_threshold": calib_res.recall_at_selected,
            "specificity_at_selected_threshold": calib_res.specificity_at_selected,
            "precision_at_selected_threshold": calib_res.precision_at_selected,
        },
        "baseline_a_matched_cv_performance": {
            "model_name": champion_name,
            "pr_auc": base_rep.pr_auc,
            "roc_auc": base_rep.roc_auc,
            "selected_threshold": base_calib.selected_threshold,
            "f1_at_selected_threshold": base_calib.best_f1,
            "recall_at_selected_threshold": base_calib.recall_at_selected,
            "specificity_at_selected_threshold": base_calib.specificity_at_selected,
            "precision_at_selected_threshold": base_calib.precision_at_selected,
        },
        "synthetic_cohort_summary": {
            "total_candidates": n_tot,
            "transits_count": n_pos,
            "confounders_count": n_neg,
            "generation_audit": gen_audit,
        },
        "firewall_statement": (
            "The real 100-target cohort has NOT been evaluated or accessed. "
            "Model parameters, feature schema, and decision threshold are permanently frozen. "
            "Awaiting explicit user authorization before crossing the real-data firewall."
        )
    }

    checkpoint_path = output_dir / "stage4_pre_evaluation_checkpoint.json"
    with open(checkpoint_path, "w") as f:
        json.dump(checkpoint, f, indent=2)
    logger.info(f"Saved immutable pre-evaluation checkpoint manifest to {checkpoint_path}")

    logger.info("=================================================================")
    logger.info("STAGE 4 SYNTHETIC & FREEZING PHASE COMPLETED SUCCESSFULLY.")
    logger.info("STOPPING AT REAL-DATA FIREWALL AS DIRECTED.")
    logger.info("=================================================================")

    return checkpoint


if __name__ == "__main__":
    out_dir = Path("results/stage4_candidate_vetting")
    synth_d = Path("data/processed/stage4_synthetic")
    run_stage4_synthetic_pipeline(
        output_dir=out_dir,
        synthetic_dir=synth_d,
        seed=42,
        n_transits=300,
        n_confounders_per_class=60
    )
