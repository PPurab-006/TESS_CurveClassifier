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


def test_bls_harmonic_period_recovery():
    """Verify is_period_recovered correctly identifies 1x, 0.5x, and 2x harmonics."""
    from tess_benchmark.baselines.bls import BLSResult

    dummy_res = BLSResult(
        best_period=6.0,
        best_t0=1.0,
        best_duration=0.2,
        best_depth=0.005,
        max_power=10.0,
        mean_power=2.0,
        std_power=1.0,
        sde=8.0,
        snr=10.0,
        is_detected=True,
        runtime_sec=0.1
    )

    # Fundamental period matches
    assert dummy_res.is_period_recovered(6.0, tolerance=0.02) is True
    # Half harmonic (true period is 12.0, detected is 6.0)
    assert dummy_res.is_period_recovered(12.0, tolerance=0.02) is True
    # Double harmonic (true period is 3.0, detected is 6.0)
    assert dummy_res.is_period_recovered(3.0, tolerance=0.02) is True
    # Unrelated period
    assert dummy_res.is_period_recovered(7.8, tolerance=0.02) is False


def test_bls_insufficient_data_handling():
    """BLS detector must return undetected result when light curve has fewer than 50 points."""
    from tess_benchmark.data.protocol import LightCurveData, TargetCategory
    sparse_lc = LightCurveData(
        time=np.array([1.0, 2.0, 3.0]),
        flux=np.array([1.0, 0.99, 1.0]),
        flux_err=np.array([0.01, 0.01, 0.01]),
        target_id="SPARSE",
        category=TargetCategory.CONTROL_STAR,
        has_transit=False
    )
    detector = BLSDetector()
    res = detector.search(sparse_lc)
    assert res.is_detected is False
    assert res.best_period == 0.0

