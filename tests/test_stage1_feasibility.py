"""
Tests for Stage 1 Real-Data Feasibility execution components.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from tess_benchmark.data.protocol import LightCurveData, TargetCategory
from tess_benchmark.baselines.bls import BLSResult, match_period_to_harmonics
from scripts.run_stage1_feasibility import CATALOG_HOST_EPHEM, plot_target_diagnostics, plot_overview_all_10


def test_stage1_catalog_ephemerides_integrity():
    """Verify that all 5 confirmed hosts in Stage 1 have valid, positive ephemerides."""
    assert len(CATALOG_HOST_EPHEM) == 5
    for tic_id, ephem in CATALOG_HOST_EPHEM.items():
        assert ephem["period_days"] > 0
        assert ephem["t0_btjd"] > 1300.0  # TESS Sector 1 BTJD epoch
        assert ephem["duration_hours"] > 0
        assert ephem["depth_ppm"] > 0
        assert "target_name" in ephem
        assert "planet_name" in ephem


def test_stage1_harmonic_classification():
    """Test harmonic matching classification under Stage 1 protocol."""
    # WASP-126 fundamental
    rec, ratio, err = match_period_to_harmonics(3.287304, 3.2887898, accepted_ratios=(0.5, 1.0, 2.0), tolerance=0.01)
    assert rec is True
    assert np.isclose(ratio, 1.0)
    assert err < 0.001

    # LHS 3844 harmonic 2x
    rec, ratio, err = match_period_to_harmonics(0.925350, 0.4629304, accepted_ratios=(0.5, 1.0, 2.0), tolerance=0.01)
    assert rec is True
    assert np.isclose(ratio, 2.0)
    assert err < 0.001


def test_stage1_diagnostic_plot_creation(tmp_path):
    """Test that plot_target_diagnostics generates valid image without errors."""
    n_pts = 200
    t = 1325.0 + np.linspace(0, 27.0, n_pts)
    f = np.ones(n_pts)
    fe = np.full(n_pts, 0.001)
    q = np.ones(n_pts, dtype=bool)

    lc = LightCurveData(
        time=t,
        flux=f,
        flux_err=fe,
        target_id="TIC 25155310",
        category=TargetCategory.CONFIRMED_PLANET_HOST,
        has_transit=True,
        metadata={"target_name": "WASP-126", "tic_id": 25155310, "flux_unit": "e-/s"},
        quality_mask=q,
        raw_flux=f * 5000.0,
        raw_flux_err=fe * 5000.0
    )

    bls_res = BLSResult(
        best_period=3.288,
        best_t0=1327.5,
        best_duration=0.14,
        best_depth=0.007,
        max_power=100.0,
        mean_power=10.0,
        std_power=5.0,
        sde=18.0,
        snr=50.0,
        is_detected=True,
        runtime_sec=0.1
    )

    out_file = tmp_path / "test_diag.png"
    plot_target_diagnostics(lc, bls_res, CATALOG_HOST_EPHEM["25155310"], out_file)
    assert out_file.exists()
    assert out_file.stat().st_size > 1000


def test_stage1_output_artifacts_exist():
    """Verify that Stage 1 output directory contains summary CSV, metadata JSON, and report."""
    stage1_dir = Path("results/real_data_pilot/stage1")
    assert stage1_dir.exists()
    assert (stage1_dir / "stage1_summary.csv").exists()
    assert (stage1_dir / "stage1_metadata.json").exists()
    assert (stage1_dir / "stage1_run_report.md").exists()
    assert (stage1_dir / "plots" / "stage1_overview_all_10.png").exists()

    df = pd.read_csv(stage1_dir / "stage1_summary.csv")
    assert len(df) == 10
    assert set(df["category"].unique()) == {"confirmed_planet_host", "control_star"}


def test_wasp126_depth_consistency_regression():
    """
    Regression audit for WASP-126:
    Ensures raw flux, normalized flux, binned median curve, and BLS depth are quantitatively consistent.
    """
    from tess_benchmark.data.tess_loader import TESSDataLoader
    from scripts.run_stage1_feasibility import load_target_data, BLSDetector, phase_fold, bin_folded_light_curve

    raw_dir = Path("data/raw/real_tess_pilot")
    loader = TESSDataLoader(cache_dir=raw_dir)
    lc = load_target_data("25155310", raw_dir, loader)

    v = lc.valid_indices
    t_val = lc.time[v]
    f_raw = lc.raw_flux[v]
    f_norm = lc.flux[v]

    # 1. Normalization consistency
    med_raw = np.median(f_raw)
    assert np.allclose(f_norm, f_raw / med_raw)
    assert np.isclose(med_raw, 9282.11, rtol=1e-3)

    # 2. No flux cadences approach 0.90 (all cadences >= 0.98)
    assert np.min(f_norm) > 0.985
    assert np.max(f_norm) < 1.015

    # 3. BLS period search and depth
    detector = BLSDetector(min_period=0.5, max_period=15.0, frequency_factor=5.0)
    res = detector.search(lc)
    assert np.isclose(res.best_period, 3.2873, atol=0.01)
    # BLS depth is ~6512 ppm (~0.65%), NOT 651 ppm
    assert 6000 <= (res.best_depth * 1e6) <= 7000

    # 4. Binned median curve depth matches catalog (~7005 ppm)
    p_cat = CATALOG_HOST_EPHEM["25155310"]["period_days"]
    t0_cat = CATALOG_HOST_EPHEM["25155310"]["t0_btjd"]
    phase_cat = phase_fold(t_val, p_cat, t0_cat)
    bin_c, bin_f, _ = bin_folded_light_curve(phase_cat, f_norm, n_bins=100)

    min_binned_flux = np.nanmin(bin_f)
    binned_depth_ppm = (1.0 - min_binned_flux) * 1e6

    # Minimum binned flux is ~0.993, depth ~7000 ppm
    assert np.isclose(min_binned_flux, 0.993, atol=0.002)
    assert 6500 <= binned_depth_ppm <= 7500

