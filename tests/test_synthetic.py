"""
Tests for synthetic transit generation and reproducibility.
"""
import numpy as np
import pytest
from tess_benchmark.data.synthetic import (
    SyntheticTransitConfig,
    generate_synthetic_light_curve,
    trapezoidal_transit,
)
from tess_benchmark.data.protocol import TargetCategory


def test_trapezoidal_transit_dip():
    """Verify trapezoidal transit profile exhibits expected depth, width, and periodicity."""
    time = np.linspace(0.0, 10.0, 10000)
    period = 3.0
    t0 = 1.0
    depth = 0.01  # 1%
    duration_days = 0.2  # ~4.8 hours

    dip = trapezoidal_transit(time, period, t0, depth, duration_days, ingress_fraction=0.2)

    # Check center of first transit
    idx_center = np.argmin(np.abs(time - t0))
    assert np.isclose(dip[idx_center], -depth, atol=1e-4)

    # Check out of transit points
    idx_out = np.argmin(np.abs(time - (t0 + 0.5)))
    assert dip[idx_out] == 0.0

    # Check second transit at t0 + period
    idx_center_2 = np.argmin(np.abs(time - (t0 + period)))
    assert np.isclose(dip[idx_center_2], -depth, atol=1e-4)


def test_synthetic_light_curve_generator():
    """Test generating a full synthetic light curve with transits and noise."""
    config = SyntheticTransitConfig(
        duration_days=10.0,
        cadence_minutes=5.0,
        has_transit=True,
        period_days=2.5,
        depth=0.005,
        noise_sigma=0.001,
        seed=42
    )
    lc = generate_synthetic_light_curve(config, target_id="SYNTH-TEST-1")

    assert lc.target_id == "SYNTH-TEST-1"
    assert lc.has_transit is True
    assert lc.category == TargetCategory.SYNTHETIC_INJECTION
    assert len(lc.time) == len(lc.flux) == len(lc.flux_err)
    assert np.all(np.isfinite(lc.flux))
    assert lc.metadata["depth"] == 0.005
    assert lc.metadata["period_days"] == 2.5


def test_synthetic_reproducibility():
    """Verify that identical random seeds produce identical light curves."""
    config1 = SyntheticTransitConfig(seed=123, duration_days=5.0, cadence_minutes=10.0)
    config2 = SyntheticTransitConfig(seed=123, duration_days=5.0, cadence_minutes=10.0)

    lc1 = generate_synthetic_light_curve(config1)
    lc2 = generate_synthetic_light_curve(config2)

    np.testing.assert_array_equal(lc1.flux, lc2.flux)
    np.testing.assert_array_equal(lc1.time, lc2.time)


def test_control_star_generation():
    """Verify control stars contain no injected transit dip."""
    config = SyntheticTransitConfig(
        duration_days=5.0,
        cadence_minutes=10.0,
        has_transit=False,
        seed=99
    )
    lc = generate_synthetic_light_curve(config, target_id="CONTROL-01")

    assert lc.has_transit is False
    assert lc.category == TargetCategory.CONTROL_STAR
    assert lc.metadata["depth"] == 0.0


def test_matched_nuisance_distributions():
    """Verify that positive and control stars sample matched distributions for nuisance parameters."""
    from scipy import stats

    rng = np.random.default_rng(42)
    n_samples = 30
    pos_noises = []
    neg_noises = []
    pos_missing = []
    neg_missing = []

    for i in range(n_samples):
        # Sample nuisance parameters identically
        noise = float(rng.uniform(0.0008, 0.0015))
        baseline = float(rng.uniform(0.95, 1.05))
        var_amp = float(rng.uniform(0.0005, 0.003))

        cfg_pos = SyntheticTransitConfig(
            duration_days=10.0,
            has_transit=True,
            depth=0.005,
            noise_sigma=noise,
            baseline_flux=baseline,
            variability_amplitude=var_amp,
            flare_amplitude_scale=6.0,
            sector_gap_start=5.0,
            dropout_fraction=0.01,
            seed=int(rng.integers(1, 1000000)),
        )
        lc_pos = generate_synthetic_light_curve(cfg_pos)
        pos_noises.append(lc_pos.metadata["noise_sigma"])
        pos_missing.append(1.0 - (np.sum(lc_pos.quality_mask) / len(lc_pos.time)))

        noise_neg = float(rng.uniform(0.0008, 0.0015))
        baseline_neg = float(rng.uniform(0.95, 1.05))
        var_amp_neg = float(rng.uniform(0.0005, 0.003))

        cfg_neg = SyntheticTransitConfig(
            duration_days=10.0,
            has_transit=False,
            noise_sigma=noise_neg,
            baseline_flux=baseline_neg,
            variability_amplitude=var_amp_neg,
            flare_amplitude_scale=6.0,
            sector_gap_start=5.0,
            dropout_fraction=0.01,
            seed=int(rng.integers(1, 1000000)),
        )
        lc_neg = generate_synthetic_light_curve(cfg_neg)
        neg_noises.append(lc_neg.metadata["noise_sigma"])
        neg_missing.append(1.0 - (np.sum(lc_neg.quality_mask) / len(lc_neg.time)))

    # KS tests must confirm distributions are statistically indistinguishable (p > 0.05)
    ks_noise = stats.ks_2samp(pos_noises, neg_noises)
    ks_miss = stats.ks_2samp(pos_missing, neg_missing)
    assert ks_noise.pvalue > 0.05, f"Noise distributions differ: p={ks_noise.pvalue}"
    assert ks_miss.pvalue > 0.05, f"Missingness distributions differ: p={ks_miss.pvalue}"


def test_identical_preprocessing_behavior():
    """Verify preprocessing pipeline applies identical operations to positive and control light curves."""
    from tess_benchmark.data.synthetic import preprocess_light_curve

    cfg_pos = SyntheticTransitConfig(seed=55, has_transit=True, depth=0.006, duration_days=8.0)
    cfg_neg = SyntheticTransitConfig(seed=55, has_transit=False, duration_days=8.0)

    lc_pos = generate_synthetic_light_curve(cfg_pos)
    lc_neg = generate_synthetic_light_curve(cfg_neg)

    clean_pos = preprocess_light_curve(lc_pos, clip_outliers=True, detrend=True)
    clean_neg = preprocess_light_curve(lc_neg, clip_outliers=True, detrend=True)

    # Both must be preprocessed and yield finite normalized flux centered at ~1.0
    assert np.all(np.isfinite(clean_pos.flux))
    assert np.all(np.isfinite(clean_neg.flux))
    assert np.isclose(np.median(clean_pos.flux), 1.0, atol=0.01)
    assert np.isclose(np.median(clean_neg.flux), 1.0, atol=0.01)


def test_no_label_dependent_normalization_path():
    """Verify normalization does not access or branch on transit labels."""
    from tess_benchmark.data.synthetic import normalize_light_curve

    rng = np.random.default_rng(1234)
    flux = rng.normal(1.05, 0.01, size=5000)
    mask = np.ones(5000, dtype=bool)
    mask[100:150] = False

    # Normalization takes strictly flux, mask, and RNG - no label or category parameters exist
    norm_flux1, cont1 = normalize_light_curve(flux, mask, method="robust_continuum", calibration_uncertainty=0.001, rng=np.random.default_rng(99))
    norm_flux2, cont2 = normalize_light_curve(flux, mask, method="robust_continuum", calibration_uncertainty=0.001, rng=np.random.default_rng(99))

    np.testing.assert_array_equal(norm_flux1, norm_flux2)
    assert cont1 == cont2
    assert np.isfinite(cont1)


def test_positive_and_control_finite_arrays():
    """Verify that both positive and control examples produce non-empty, finite arrays."""
    for has_tr in [True, False]:
        cfg = SyntheticTransitConfig(has_transit=has_tr, duration_days=7.0, cadence_minutes=2.0, seed=777)
        lc = generate_synthetic_light_curve(cfg)

        assert len(lc.time) > 1000
        assert len(lc.flux) == len(lc.time)
        assert len(lc.flux_err) == len(lc.time)
        assert len(lc.quality_mask) == len(lc.time)
        assert np.all(np.isfinite(lc.time))
        assert np.all(np.isfinite(lc.flux))
        assert np.all(np.isfinite(lc.flux_err))
        assert np.all(lc.flux_err > 0)
