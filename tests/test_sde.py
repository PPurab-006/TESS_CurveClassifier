"""
Unit and regression tests for periodogram SDE background estimation (GATE-11).
"""
import numpy as np
import pytest

from tess_benchmark.baselines.sde import compute_sde, SDEResult
from tess_benchmark.baselines.bls import BLSDetector
from tess_benchmark.data.protocol import LightCurveData, TargetCategory


def test_sde_option_a_basic():
    """Option A computes parametric mean and std over all finite bins."""
    periods = np.linspace(0.5, 15.0, 1000)
    np.random.seed(42)
    power = np.random.normal(loc=10.0, scale=2.0, size=len(periods))
    # Place a prominent peak at index 500
    power[500] = 30.0

    res = compute_sde(power, periods, method="option_a")
    assert isinstance(res, SDEResult)
    assert res.method == "option_a"
    assert not res.sde_degenerate
    assert not res.mad_zero
    assert res.mask_fraction == 0.0
    assert res.n_unmasked_bins == 1000
    assert np.isclose(res.max_power, 30.0)
    expected_mean = np.mean(power)
    expected_std = np.std(power)
    assert np.isclose(res.background_mean, expected_mean)
    assert np.isclose(res.background_dispersion, expected_std)
    assert np.isclose(res.sde, (30.0 - expected_mean) / expected_std)


def test_sde_option_b_peak_exclusion():
    """Option B excludes E_0 fundamental peak window and uses robust MAD."""
    periods = np.linspace(0.5, 15.0, 1000)
    power = np.ones(len(periods)) * 5.0
    # Add Gaussian noise
    np.random.seed(42)
    noise = np.random.normal(0, 0.5, len(periods))
    power += noise
    power[500] = 50.0  # Big peak

    res = compute_sde(power, periods, method="option_b", exclusion_half_width_steps=3)
    assert res.method == "option_b"
    assert not res.sde_degenerate
    assert res.n_masked_bins > 0
    assert res.n_unmasked_bins < 1000
    assert len(res.exclusion_intervals) == 1
    # Robust dispersion should not be inflated by the peak
    assert res.background_dispersion < np.std(power)
    # SDE should be high
    assert res.sde > 10.0


def test_sde_option_c_alias_masking():
    """Option C excludes peak, harmonics (1/3, 1/2, 2, 3), and satellite aliases."""
    periods = np.linspace(0.5, 15.0, 2000)
    power = np.full(len(periods), 2.0)
    np.random.seed(42)
    power += np.random.exponential(scale=0.5, size=len(periods))

    # Place peak at period 4.0 d (f = 0.25 d^-1)
    f0 = 0.25
    p0 = 1.0 / f0
    idx_peak = np.argmin(np.abs(periods - p0))
    power[idx_peak] = 40.0

    res = compute_sde(power, periods, method="option_c", exclusion_half_width_steps=3)
    assert res.method == "option_c"
    assert not res.sde_degenerate
    assert len(res.exclusion_intervals) >= 3
    assert res.n_masked_bins > 0
    assert res.mask_fraction > 0.0
    assert res.sde > 10.0


def test_sde_option_d_sigma_clipping():
    """Option D performs iterative 3-sigma clipping."""
    periods = np.linspace(0.5, 15.0, 1000)
    np.random.seed(42)
    power = np.random.normal(5.0, 1.0, len(periods))
    power[100] = 25.0
    power[200] = 30.0
    power[300] = 35.0

    res = compute_sde(power, periods, method="option_d")
    assert res.method == "option_d"
    assert not res.sde_degenerate
    assert res.n_unmasked_bins < 1000
    assert res.sde > 10.0


def test_sde_degenerate_fewer_than_50_bins():
    """Periodograms with fewer than 50 valid bins return NaN and sde_degenerate=True."""
    periods = np.linspace(1.0, 5.0, 40)
    power = np.ones(40) * 10.0

    res = compute_sde(power, periods, method="option_a")
    assert res.sde_degenerate
    assert np.isnan(res.sde)

    res_c = compute_sde(power, periods, method="option_c")
    assert res_c.sde_degenerate
    assert np.isnan(res_c.sde)


def test_sde_degenerate_when_mask_removes_too_much():
    """If mask leaves fewer than 50 bins, SDE returns degenerate."""
    # Small grid with 60 bins, peak exclusion removes 15 bins -> leaves 45 bins < 50
    periods = np.linspace(1.0, 3.0, 60)
    power = np.ones(60) * 10.0
    power[30] = 50.0

    res = compute_sde(power, periods, method="option_c", exclusion_half_width_steps=8)
    assert res.sde_degenerate
    assert np.isnan(res.sde)
    assert res.n_unmasked_bins < 50


def test_sde_zero_mad_handling():
    """Constant power in background yields zero MAD and mad_zero=True flag."""
    periods = np.linspace(0.5, 15.0, 500)
    # Strictly flat background
    power = np.ones(500) * 2.5
    power[250] = 100.0  # Lone peak

    res = compute_sde(power, periods, method="option_b")
    assert res.mad_zero
    assert np.isnan(res.sde)


def test_sde_invalid_bins_handling():
    """Non-finite or non-positive power values are stripped before masking."""
    periods = np.linspace(0.5, 15.0, 200)
    power = np.ones(200) * 5.0
    power[10] = -1.0
    power[20] = 0.0
    power[30] = np.nan
    power[40] = np.inf
    power[100] = 50.0

    res = compute_sde(power, periods, method="option_a")
    assert res.n_total_bins == 200
    assert res.n_valid_bins == 196  # 4 invalid bins stripped
    assert not res.sde_degenerate


def test_bls_detector_supports_sde_methods():
    """BLSDetector accepts sde_method and computes appropriate metadata."""
    t = np.linspace(0, 20, 500)
    f = np.ones_like(t)
    err = np.full_like(t, 0.001)
    lc = LightCurveData(
        time=t, flux=f, flux_err=err,
        target_id="TEST_001",
        category=TargetCategory.CONFIRMED_PLANET_HOST,
        has_transit=True
    )

    det_a = BLSDetector(min_period=1.0, max_period=5.0, sde_method="option_a")
    res_a = det_a.search(lc)
    assert res_a.metadata["sde_method"] == "option_a"

    det_c = BLSDetector(min_period=1.0, max_period=5.0, sde_method="option_c")
    res_c = det_c.search(lc)
    assert res_c.metadata["sde_method"] == "option_c"
