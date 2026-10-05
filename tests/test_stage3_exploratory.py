"""
Tests for Stage 3 Exploratory Benchmark Runner.
"""
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from scripts.run_stage3_exploratory import (
    run_stage3_exploratory_benchmark,
    KNOWN_MULTIPLANET_METADATA,
    build_fits_index
)


def test_cnn_probation_gate_enforcement(tmp_path):
    """Verify that attempting to enable CNN1D raises a RuntimeError under GATE-02 Option C."""
    dummy_manifest = tmp_path / "manifest.csv"
    dummy_manifest.write_text("dummy")

    with pytest.raises(RuntimeError, match="GATE-02 Violation"):
        run_stage3_exploratory_benchmark(
            manifest_path=dummy_manifest,
            raw_dir=tmp_path,
            synthetic_features_path=tmp_path / "synth.csv",
            protocol_config_path=Path("configs/real_benchmark_protocol.yaml"),
            output_dir=tmp_path / "out",
            enable_cnn=True
        )


def test_multiplanet_metadata_audit_integrity():
    """Verify the 9 audited multi-planet systems have valid metadata and sy_pnum > 1."""
    assert len(KNOWN_MULTIPLANET_METADATA) == 9
    for tic_id, meta in KNOWN_MULTIPLANET_METADATA.items():
        assert isinstance(tic_id, int)
        assert meta["sy_pnum"] > 1
        assert "hostname" in meta
        assert "toi_id" in meta


def test_fits_indexing(tmp_path):
    """Verify build_fits_index finds files properly."""
    sub = tmp_path / "sub" / "dir"
    sub.mkdir(parents=True)
    f1 = sub / "star1_lc.fits"
    f2 = sub / "star2_lc.fits"
    f1.write_text("fits1")
    f2.write_text("fits2")

    index = build_fits_index(tmp_path)
    assert "star1_lc.fits" in index
    assert "star2_lc.fits" in index
    assert index["star1_lc.fits"] == f1


def test_stage3_exploratory_execution_on_pilot_subset(tmp_path):
    """Execute end-to-end benchmark runner on a 2-star pilot subset (1 host, 1 control)."""
    # Create mini manifest with 2 stars from Stage 2 manifest that exist in pilot
    full_manifest = pd.read_csv("results/real_data_stage2/stage2_final_cohort_manifest.csv")
    host_row = full_manifest[full_manifest["tic_id"] == 25155310].iloc[0:1]  # WASP-126
    ctrl_row = full_manifest[full_manifest["category"] == "control_star"].iloc[0:1]

    mini_df = pd.concat([host_row, ctrl_row], ignore_index=True)
    mini_manifest = tmp_path / "mini_manifest.csv"
    mini_df.to_csv(mini_manifest, index=False)

    out_dir = tmp_path / "exploratory_out"

    summary = run_stage3_exploratory_benchmark(
        manifest_path=mini_manifest,
        raw_dir=Path("data/raw"),
        synthetic_features_path=Path("data/processed/features_tabular.csv"),
        protocol_config_path=Path("configs/real_benchmark_protocol.yaml"),
        output_dir=out_dir,
        seed=42,
        enable_cnn=False
    )

    assert summary["benchmark_metadata"]["total_targets"] == 2
    assert (out_dir / "bls_exploratory_predictions.csv").exists()
    assert (out_dir / "tabular_ml_exploratory_predictions.csv").exists()
    assert (out_dir / "real_cohort_tabular_features.csv").exists()
    assert (out_dir / "stage3_exploratory_summary.json").exists()
    assert (out_dir / "stage3_exploratory_report.md").exists()

    df_bls = pd.read_csv(out_dir / "bls_exploratory_predictions.csv")
    assert len(df_bls) == 2
    assert "recovery_type" in df_bls.columns

    # WASP-126 should be recovered at fundamental
    wasp126 = df_bls[df_bls["tic_id"] == 25155310].iloc[0]
    assert wasp126["is_period_recovered"] is True or wasp126["is_period_recovered"] == 1
    assert wasp126["recovery_type"] == "fundamental"
    assert wasp126["recovery_harmonic"] == 1.0


def test_recovery_counts_exact_mathematical_identity(tmp_path):
    """Regression test: verify recovered_period_count == fundamental + harmonic for all cohorts."""
    full_manifest = pd.read_csv("results/real_data_stage2/stage2_final_cohort_manifest.csv")
    host_row = full_manifest[full_manifest["tic_id"] == 25155310].iloc[0:1]  # WASP-126
    ctrl_row = full_manifest[full_manifest["category"] == "control_star"].iloc[0:1]

    mini_df = pd.concat([host_row, ctrl_row], ignore_index=True)
    mini_manifest = tmp_path / "mini_manifest.csv"
    mini_df.to_csv(mini_manifest, index=False)

    out_dir = tmp_path / "math_check_out"

    summary = run_stage3_exploratory_benchmark(
        manifest_path=mini_manifest,
        raw_dir=Path("data/raw"),
        synthetic_features_path=Path("data/processed/features_tabular.csv"),
        protocol_config_path=Path("configs/real_benchmark_protocol.yaml"),
        output_dir=out_dir,
        seed=42,
        enable_cnn=False
    )

    bls_all = summary["bls_baseline_metrics"]["all_hosts_cohort_n50"]
    assert bls_all["recovered_period_count"] == (
        bls_all["fundamental_recovery_count"] + bls_all["harmonic_recovery_count"]
    )

    bls_single = summary["bls_baseline_metrics"]["single_planet_hosts_subcohort_n41"]
    assert bls_single["recovered_period_count"] == (
        bls_single["fundamental_recovery_count"] + bls_single["harmonic_recovery_count"]
    )

    bls_multi = summary["bls_baseline_metrics"]["multi_planet_hosts_subcohort_n9"]
    assert bls_multi["recovered_period_count"] == (
        bls_multi["fundamental_recovery_count"] + bls_multi["harmonic_recovery_count"]
    )

    # Observational controls terminology check
    ctrl_metrics = summary["bls_baseline_metrics"]["observational_controls_n50"]
    assert "candidate_detection_count_sde6_snr5" in ctrl_metrics
    assert "candidate_detection_rate" in ctrl_metrics
    assert "false_detection_count_sde6_snr5" not in ctrl_metrics


def test_runner_gate_03_event_coverage_integration(tmp_path):
    """Verify that Stage 3 runner executes GATE-03 event coverage logic on authentic light curves."""
    full_manifest = pd.read_csv("results/real_data_stage2/stage2_final_cohort_manifest.csv")
    host_row = full_manifest[full_manifest["tic_id"] == 25155310].iloc[0:1]  # WASP-126
    ctrl_row = full_manifest[full_manifest["category"] == "control_star"].iloc[0:1]

    mini_df = pd.concat([host_row, ctrl_row], ignore_index=True)
    mini_manifest = tmp_path / "mini_manifest_g03.csv"
    mini_df.to_csv(mini_manifest, index=False)

    out_dir = tmp_path / "g03_out"

    summary = run_stage3_exploratory_benchmark(
        manifest_path=mini_manifest,
        raw_dir=Path("data/raw"),
        synthetic_features_path=Path("data/processed/features_tabular.csv"),
        protocol_config_path=Path("configs/real_benchmark_protocol.yaml"),
        output_dir=out_dir,
        seed=42,
        enable_cnn=False
    )

    df_bls = pd.read_csv(out_dir / "bls_exploratory_predictions.csv")
    wasp126 = df_bls[df_bls["tic_id"] == 25155310].iloc[0]

    # Verify event coverage columns are populated for host
    assert wasp126["n_events_predicted"] == 8
    assert wasp126["n_primary_adequate_events"] == 8
    assert wasp126["n_boundary_adequate_events"] == 0
    assert wasp126["n_inadequate_events"] == 0
    assert bool(wasp126["has_primary_adequate_coverage"]) is True

    # Verify control star has zero predicted events
    ctrl = df_bls[df_bls["tic_id"] != 25155310].iloc[0]
    assert ctrl["n_events_predicted"] == 0
    assert ctrl["n_primary_adequate_events"] == 0

    # Verify summary-level GATE-03 event coverage metrics
    cov_meta = summary["event_coverage_metrics"]
    assert cov_meta["total_predicted_events"] == 8
    assert cov_meta["total_primary_adequate_interior_events"] == 8
    assert cov_meta["total_secondary_boundary_diagnostic_events"] == 0
    assert cov_meta["hosts_with_primary_adequate_coverage_count"] == 1
    assert "primary_interior" in cov_meta["rules"]
    assert "secondary_boundary_diagnostic" in cov_meta["rules"]


def test_runner_gate_12_scorer_integration(tmp_path):
    """Verify that Stage 3 runner executes RealDataBenchmarkScorer composite epoch matching."""
    full_manifest = pd.read_csv("results/real_data_stage2/stage2_final_cohort_manifest.csv")
    host_row = full_manifest[full_manifest["tic_id"] == 25155310].iloc[0:1]  # WASP-126
    ctrl_row = full_manifest[full_manifest["category"] == "control_star"].iloc[0:1]

    mini_df = pd.concat([host_row, ctrl_row], ignore_index=True)
    mini_manifest = tmp_path / "mini_manifest_g12.csv"
    mini_df.to_csv(mini_manifest, index=False)

    out_dir = tmp_path / "g12_out"

    summary = run_stage3_exploratory_benchmark(
        manifest_path=mini_manifest,
        raw_dir=Path("data/raw"),
        synthetic_features_path=Path("data/processed/features_tabular.csv"),
        protocol_config_path=Path("configs/real_benchmark_protocol.yaml"),
        output_dir=out_dir,
        seed=42,
        enable_cnn=False
    )

    df_bls = pd.read_csv(out_dir / "bls_exploratory_predictions.csv")
    wasp126 = df_bls[df_bls["tic_id"] == 25155310].iloc[0]

    # Verify composite match attributes
    assert bool(wasp126["is_period_recovered"]) is True
    assert bool(wasp126["is_epoch_match"]) is True
    assert bool(wasp126["is_full_recovery"]) is True
    assert wasp126["match_status"] == "full_recovery"
    assert wasp126["harmonic_class"] == "fundamental_1.0x"
    assert wasp126["epoch_residual_days"] <= wasp126["allowed_epoch_tolerance_days"]
    assert 0.0 <= wasp126["circular_phase_difference"] <= 0.5

    # Verify summary-level GATE-12 metrics
    bls_all = summary["bls_baseline_metrics"]["all_hosts_cohort_n50"]
    assert bls_all["full_recovery_count"] == 1
    assert bls_all["fundamental_full_recovery_count"] == 1
    assert bls_all["harmonic_full_recovery_count"] == 0
    assert bls_all["period_only_match_count"] == 0


def test_runner_gate_12_period_match_fails_epoch_integration(tmp_path):
    """
    Demonstrate that a candidate passing period matching can fail the composite epoch criterion.
    Injects a half-period phase offset in catalog t0 to force epoch mismatch while preserving period.
    """
    full_manifest = pd.read_csv("results/real_data_stage2/stage2_final_cohort_manifest.csv")
    host_row = full_manifest[full_manifest["tic_id"] == 25155310].iloc[0:1].copy()  # WASP-126
    ctrl_row = full_manifest[full_manifest["category"] == "control_star"].iloc[0:1].copy()

    # Shift catalog t0 by half a period (~1.64 days), far exceeding allowed tolerance (~0.036 days)
    period = float(host_row["period_days"].iloc[0])
    host_row["t0_bjd"] = float(host_row["t0_bjd"].iloc[0]) + 0.5 * period

    mini_df = pd.concat([host_row, ctrl_row], ignore_index=True)
    mini_manifest = tmp_path / "mini_manifest_epoch_fail.csv"
    mini_df.to_csv(mini_manifest, index=False)

    out_dir = tmp_path / "epoch_fail_out"

    summary = run_stage3_exploratory_benchmark(
        manifest_path=mini_manifest,
        raw_dir=Path("data/raw"),
        synthetic_features_path=Path("data/processed/features_tabular.csv"),
        protocol_config_path=Path("configs/real_benchmark_protocol.yaml"),
        output_dir=out_dir,
        seed=42,
        enable_cnn=False
    )

    df_bls = pd.read_csv(out_dir / "bls_exploratory_predictions.csv")
    wasp126 = df_bls[df_bls["tic_id"] == 25155310].iloc[0]

    # Period matches (1% relative tolerance passed)
    assert bool(wasp126["is_period_recovered"]) is True
    assert wasp126["period_relative_error"] <= 0.01

    # BUT composite epoch matching fails strictly
    assert bool(wasp126["is_epoch_match"]) is False
    assert bool(wasp126["is_full_recovery"]) is False
    assert wasp126["match_status"] == "period_only_match"
    assert wasp126["epoch_residual_days"] > wasp126["allowed_epoch_tolerance_days"]

    # Verify summary ledger classifies this as period-only
    bls_all = summary["bls_baseline_metrics"]["all_hosts_cohort_n50"]
    assert bls_all["recovered_period_count"] == 1
    assert bls_all["full_recovery_count"] == 0
    assert bls_all["period_only_match_count"] == 1


def test_runner_gate_09_grid_serialization_integration(tmp_path):
    """Verify that Stage 3 runner persists exact BLS frequency grids to compressed archive."""
    full_manifest = pd.read_csv("results/real_data_stage2/stage2_final_cohort_manifest.csv")
    host_row = full_manifest[full_manifest["tic_id"] == 25155310].iloc[0:1]
    ctrl_row = full_manifest[full_manifest["category"] == "control_star"].iloc[0:1]

    mini_df = pd.concat([host_row, ctrl_row], ignore_index=True)
    mini_manifest = tmp_path / "mini_manifest_g09.csv"
    mini_df.to_csv(mini_manifest, index=False)

    out_dir = tmp_path / "g09_out"

    summary = run_stage3_exploratory_benchmark(
        manifest_path=mini_manifest,
        raw_dir=Path("data/raw"),
        synthetic_features_path=Path("data/processed/features_tabular.csv"),
        protocol_config_path=Path("configs/real_benchmark_protocol.yaml"),
        output_dir=out_dir,
        seed=42,
        enable_cnn=False
    )

    grid_file = out_dir / "bls_frequency_grids.npz"
    assert grid_file.exists()

    npz = np.load(grid_file)
    assert "TIC_25155310" in npz.files

    freq_arr = npz["TIC_25155310"]
    assert isinstance(freq_arr, np.ndarray)
    assert len(freq_arr) > 1000
    assert np.all(freq_arr > 0)
    assert np.all(np.isfinite(freq_arr))

    # Verify consistency with CSV predictions
    df_bls = pd.read_csv(out_dir / "bls_exploratory_predictions.csv")
    wasp126 = df_bls[df_bls["tic_id"] == 25155310].iloc[0]
    assert len(freq_arr) == wasp126["grid_n_frequencies"]
    assert np.isclose(float(np.min(freq_arr)), wasp126["grid_min_frequency"], rtol=1e-5)
    assert np.isclose(float(np.max(freq_arr)), wasp126["grid_max_frequency"], rtol=1e-5)

    # Verify summary metadata
    grid_meta = summary["bls_frequency_grid_serialization"]
    assert grid_meta["status"] == "SERIALIZED_AND_PERSISTED"
    assert grid_meta["total_grids_persisted"] == 2
    assert grid_meta["grid_specification"]["frequency_factor"] == 5.0


def test_corrected_gate_06_cohort_integrity():
    """Verify that the corrected cohort manifest satisfies all GATE-06 and protocol invariants."""
    manifest_path = Path("results/real_data_stage2/stage2_corrected_cohort_manifest.csv")
    assert manifest_path.exists(), "Corrected cohort manifest must exist"

    df = pd.read_csv(manifest_path)
    assert len(df) == 100, f"Expected exactly 100 targets, got {len(df)}"

    hosts = df[df["category"] == "confirmed_planet_host"]
    controls = df[df["category"] == "control_star"]
    assert len(hosts) == 50, f"Expected 50 confirmed planet hosts, got {len(hosts)}"
    assert len(controls) == 50, f"Expected 50 observational controls, got {len(controls)}"

    # Unique TICs
    assert df["tic_id"].nunique() == 100, "All 100 TICs must be strictly unique"

    # Strictly no Sector 13 targets
    assert 13 not in df["sector"].values, "Sector 13 is unauthorized and must be absent"
    assert (df["tic_id"] == 290348383).sum() == 0, "TIC 290348383 (HD 207496) must be removed"

    # New replacement WASP-4 (TIC 402026209) is present in Sector 2
    wasp4 = df[df["tic_id"] == 402026209]
    assert len(wasp4) == 1, "WASP-4 (TIC 402026209) must be present in corrected cohort"
    assert wasp4.iloc[0]["sector"] == 2
    assert wasp4.iloc[0]["category"] == "confirmed_planet_host"

    # Baseline duration >= 20.0 days and usable cadence fraction >= 0.80 for all 100 targets
    assert (df["duration_days"] >= 20.0).all(), "All targets must satisfy baseline >= 20 days"
    assert (df["usable_cadence_fraction"] >= 0.80).all(), "All targets must satisfy usable cadence >= 0.80"

    # All 50 hosts have sy_pnum == 1
    assert (hosts["sy_pnum"] == 1).all(), "All 50 hosts must have sy_pnum == 1"


