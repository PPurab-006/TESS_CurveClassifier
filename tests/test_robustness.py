"""
Tests for controlled degradation transformations and robustness tracking.
"""
import numpy as np
from tess_benchmark.data.synthetic import SyntheticTransitConfig, generate_synthetic_light_curve
from tess_benchmark.evaluation.robustness import (
    apply_noise_degradation,
    apply_depth_scaling,
    apply_missing_gap,
    apply_cadence_dropout,
)


def test_apply_noise_degradation():
    """Verify added noise increases variance and updates metadata."""
    config = SyntheticTransitConfig(duration_days=5.0, cadence_minutes=10.0, noise_sigma=0.001, seed=1)
    lc = generate_synthetic_light_curve(config)
    std_orig = np.std(lc.flux)

    degraded = apply_noise_degradation(lc, noise_sigma_add=0.005, seed=42)
    std_deg = np.std(degraded.flux)

    assert std_deg > std_orig
    assert degraded.metadata["added_noise_sigma"] == 0.005


def test_apply_depth_scaling():
    """Verify depth scaling reduces the transit dip amplitude."""
    config = SyntheticTransitConfig(
        duration_days=5.0,
        cadence_minutes=10.0,
        has_transit=True,
        depth=0.01,
        noise_sigma=0.0001,
        seed=2
    )
    lc = generate_synthetic_light_curve(config)
    min_orig = np.min(lc.flux)

    scaled = apply_depth_scaling(lc, depth_factor=0.5)
    min_scaled = np.min(scaled.flux)

    # Scaled transit is shallower (minimum flux is higher / closer to 1.0)
    assert min_scaled > min_orig
    assert scaled.metadata["depth_factor"] == 0.5


def test_apply_missing_gap():
    """Verify missing gap masks out cadences in specified time window."""
    config = SyntheticTransitConfig(duration_days=10.0, cadence_minutes=10.0, seed=3)
    lc = generate_synthetic_light_curve(config)

    gapped = apply_missing_gap(lc, gap_duration_days=2.0, gap_start=4.0)
    clean_gapped = gapped.clean()

    # Time values inside [4.0, 6.0] should be excluded from clean light curve
    assert not np.any((clean_gapped.time >= 4.0) & (clean_gapped.time <= 6.0))


def test_apply_cadence_dropout():
    """Verify dropout masks out approximately the requested fraction of points."""
    config = SyntheticTransitConfig(duration_days=10.0, cadence_minutes=10.0, seed=4)
    lc = generate_synthetic_light_curve(config)
    n_orig = len(lc.clean().time)

    dropped = apply_cadence_dropout(lc, dropout_fraction=0.3, seed=42)
    n_dropped = len(dropped.clean().time)

    fraction_kept = n_dropped / n_orig
    assert np.isclose(fraction_kept, 0.7, atol=0.05)
