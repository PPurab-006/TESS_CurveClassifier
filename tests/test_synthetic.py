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
