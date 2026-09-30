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

