"""
Tests for Box Least Squares (BLS) transit detector baseline.
"""
import numpy as np
from tess_benchmark.data.synthetic import SyntheticTransitConfig, generate_synthetic_light_curve, preprocess_light_curve
from tess_benchmark.baselines.bls import BLSDetector


def test_bls_detects_transit_and_recovers_period():
    """BLS detector must identify transit and recover the true period on high-SNR signal."""
    true_period = 3.2
    config = SyntheticTransitConfig(
        duration_days=16.0,
        cadence_minutes=5.0,
        has_transit=True,
        period_days=true_period,
        t0_days=0.8,
        depth=0.01,  # 10,000 ppm (clear transit)
        duration_hours=3.0,
        noise_sigma=0.0008,
        variability_amplitude=0.0,
        seed=42
    )
    raw_lc = generate_synthetic_light_curve(config, target_id="SYNTH-BLS-PASS")
    clean_lc = preprocess_light_curve(raw_lc, clip_outliers=False, detrend=False)

    detector = BLSDetector(min_period=1.0, max_period=8.0, frequency_factor=5.0, sde_threshold=5.0)
    result = detector.search(clean_lc)

    assert result.is_detected is True
    assert result.sde > 5.0
    assert result.best_depth > 0
    assert result.runtime_sec > 0.0
    assert result.is_period_recovered(true_period, tolerance=0.05) is True


def test_bls_rejects_pure_noise_control():
    """BLS detector must not falsely detect transits on pure Gaussian noise control star."""
    config = SyntheticTransitConfig(
        duration_days=10.0,
        cadence_minutes=10.0,
        has_transit=False,
        noise_sigma=0.001,
        variability_amplitude=0.0,
        seed=777
    )
    raw_lc = generate_synthetic_light_curve(config, target_id="CONTROL-BLS")
    clean_lc = preprocess_light_curve(raw_lc, clip_outliers=False, detrend=False)

    detector = BLSDetector(min_period=1.0, max_period=6.0, frequency_factor=3.0, sde_threshold=8.0)
    result = detector.search(clean_lc)

    assert result.is_detected is False
