"""
Tests for preprocessing, outlier clipping, and detrending algorithms.
"""
import numpy as np
from tess_benchmark.data.synthetic import (
    sigma_clip,
    running_median_detrend,
    preprocess_light_curve,
    SyntheticTransitConfig,
    generate_synthetic_light_curve,
)


def test_sigma_clip_removes_flares_preserves_transits():
    """Asymmetric sigma clipping must reject positive flares while preserving transit dips."""
    flux = np.ones(1000)
    # Add negative transit dip
    flux[400:430] = 0.985
    # Add positive flare spikes
    flux[100] = 1.15
    flux[750] = 1.20

    mask = sigma_clip(flux, low_sigma=6.0, high_sigma=3.0)

    # Positive flares must be clipped (False)
    assert not mask[100]
    assert not mask[750]
    # Transit points must be preserved (True)
    assert np.all(mask[400:430])


def test_running_median_detrend():
    """Verify that running median detrends smooth sinusoidal modulation."""
    time = np.linspace(0.0, 10.0, 1000)
    smooth_modulation = 1.0 + 0.02 * np.sin(2.0 * np.pi * time / 5.0)
    noise = np.random.default_rng(42).normal(0.0, 0.001, size=1000)
    flux = smooth_modulation + noise

    detrended = running_median_detrend(time, flux, window_days=0.5)

    # The detrended flux should have near-zero trend and be centered near 1.0
    assert np.isclose(np.median(detrended), 1.0, atol=0.005)
    assert np.std(detrended) < np.std(flux)


def test_preprocess_light_curve_pipeline():
    """Verify full end-to-end preprocessing pipeline on synthetic light curve."""
    config = SyntheticTransitConfig(
        duration_days=8.0,
        cadence_minutes=5.0,
        has_transit=True,
        period_days=2.5,
        depth=0.008,
        variability_amplitude=0.005,
        flare_rate=0.001,
        seed=101
    )
    raw_lc = generate_synthetic_light_curve(config, target_id="SYNTH-PREP")
    clean_lc = preprocess_light_curve(raw_lc, clip_outliers=True, detrend=True)

    assert len(clean_lc.time) > 0
    assert np.all(np.isfinite(clean_lc.flux))
    assert np.all(clean_lc.flux > 0.5)
    assert np.isclose(np.median(clean_lc.flux), 1.0, atol=0.01)
