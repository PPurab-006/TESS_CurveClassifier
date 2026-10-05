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
    """Verify is_period_recovered correctly enforces approved GATE-04 Option B default {0.5, 1, 2} and supports explicit sets."""
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

    # 1. Fundamental period matches using approved default {0.5, 1.0, 2.0} and 0.01 tolerance
    assert dummy_res.is_period_recovered(6.0) is True
    # 2. Half harmonic (true period is 12.0, detected is 6.0 -> ratio 0.5)
    assert dummy_res.is_period_recovered(12.0) is True
    # 3. Double harmonic (true period is 3.0, detected is 6.0 -> ratio 2.0)
    assert dummy_res.is_period_recovered(3.0) is True

    # 4. Default formal rule REJECTS 1/3x and 3x (GATE-04 Option B approved rule)
    # One-third subharmonic (true period is 18.0, detected is 6.0 -> ratio 1/3)
    assert dummy_res.is_period_recovered(18.0) is False
    # Triple harmonic (true period is 2.0, detected is 6.0 -> ratio 3.0)
    assert dummy_res.is_period_recovered(2.0) is False

    # 5. Callers can explicitly pass broad exploratory set without changing formal default
    broad_ratios = [1.0 / 3.0, 0.5, 1.0, 2.0, 3.0]
    assert dummy_res.is_period_recovered(18.0, accepted_ratios=broad_ratios) is True
    assert dummy_res.is_period_recovered(2.0, accepted_ratios=broad_ratios) is True

    # 6. Unrelated period fails under both
    assert dummy_res.is_period_recovered(7.8) is False
    assert dummy_res.is_period_recovered(7.8, accepted_ratios=broad_ratios) is False


def test_bls_period_recovery_tolerance_gate_01():
    """
    Test GATE-01 approved fixed 1.0% relative period-recovery tolerance.

    Verifies across multiple catalog periods (1.0 d, 2.0 d, 10.0 d):
    - Exact period recovery (error = 0%) -> pass
    - Upper and lower exact 1% mathematical boundaries (P * 1.01, P * 0.99) -> pass
    - Just-inside boundary cases (0.99% relative error) -> pass
    - Just-outside boundary cases (1.01% relative error) -> fail
    - Invalid, nonpositive, and non-finite catalog periods -> fail safely
    """
    from tess_benchmark.baselines.bls import BLSResult

    def make_result(period: float) -> BLSResult:
        return BLSResult(
            best_period=period,
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

    # Test periods across benchmark range: short (1.0 d), intermediate (2.0 d), long (10.0 d)
    test_periods = [1.0, 2.0, 10.0]

    for p_true in test_periods:
        # 1. Exact recovery (0.0% error) -> should pass
        res_exact = make_result(p_true)
        assert res_exact.is_period_recovered(p_true) is True

        # 2. Upper exact 1% boundary (P_det = P_true * 1.01) -> should pass
        res_boundary_upper = make_result(p_true * 1.01)
        assert res_boundary_upper.is_period_recovered(p_true) is True

        # 3. Lower exact 1% boundary (P_det = P_true * 0.99) -> should pass
        res_boundary_lower = make_result(p_true * 0.99)
        assert res_boundary_lower.is_period_recovered(p_true) is True

        # 4. Just inside boundary (0.99% error) -> should pass
        res_inside_upper = make_result(p_true * 1.0099)
        assert res_inside_upper.is_period_recovered(p_true) is True

        res_inside_lower = make_result(p_true * 0.9901)
        assert res_inside_lower.is_period_recovered(p_true) is True

        # 5. Just outside boundary (1.01% error) -> should fail
        res_outside_upper = make_result(p_true * 1.0101)
        assert res_outside_upper.is_period_recovered(p_true) is False

        res_outside_lower = make_result(p_true * 0.9899)
        assert res_outside_lower.is_period_recovered(p_true) is False

    # Explicit literal decimal boundary tests for P = 1.0, 2.0, 10.0
    assert make_result(1.01).is_period_recovered(1.0) is True
    assert make_result(0.99).is_period_recovered(1.0) is True
    assert make_result(1.0101).is_period_recovered(1.0) is False
    assert make_result(0.9899).is_period_recovered(1.0) is False

    assert make_result(2.02).is_period_recovered(2.0) is True
    assert make_result(1.98).is_period_recovered(2.0) is True
    assert make_result(2.0202).is_period_recovered(2.0) is False
    assert make_result(1.9798).is_period_recovered(2.0) is False

    assert make_result(10.1).is_period_recovered(10.0) is True
    assert make_result(9.9).is_period_recovered(10.0) is True
    assert make_result(10.101).is_period_recovered(10.0) is False
    assert make_result(9.899).is_period_recovered(10.0) is False

    # 6. Invalid / nonpositive / non-finite catalog periods -> fail safely
    res_valid = make_result(10.0)
    assert res_valid.is_period_recovered(0.0) is False
    assert res_valid.is_period_recovered(-5.0) is False
    assert res_valid.is_period_recovered(float("nan")) is False
    assert res_valid.is_period_recovered(float("inf")) is False
    assert res_valid.is_period_recovered(float("-inf")) is False

    # Also invalid best_period in result
    res_zero = BLSResult(
        best_period=0.0, best_t0=0.0, best_duration=0.0, best_depth=0.0,
        max_power=0.0, mean_power=0.0, std_power=1.0, sde=0.0, snr=0.0,
        is_detected=False, runtime_sec=0.0
    )
    assert res_zero.is_period_recovered(10.0) is False

    res_nan = BLSResult(
        best_period=float("nan"), best_t0=0.0, best_duration=0.0, best_depth=0.0,
        max_power=0.0, mean_power=0.0, std_power=1.0, sde=0.0, snr=0.0,
        is_detected=False, runtime_sec=0.0
    )
    assert res_nan.is_period_recovered(10.0) is False


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


def test_bls_frequency_grid_serialization(tmp_path):
    """
    Verify GATE-09 frequency grid persistence and correspondence to Astropy periodogram.
    """
    from astropy.timeseries import BoxLeastSquares

    config = SyntheticTransitConfig(
        duration_days=10.0,
        cadence_minutes=10.0,
        has_transit=True,
        period_days=2.5,
        t0_days=0.5,
        depth=0.008,
        duration_hours=2.0,
        noise_sigma=0.001,
        seed=123
    )
    raw_lc = generate_synthetic_light_curve(config, target_id="GRID-TEST")
    clean_lc = preprocess_light_curve(raw_lc, clip_outliers=False, detrend=False)

    detector = BLSDetector(
        min_period=0.5,
        max_period=8.0,
        frequency_factor=5.0,
        save_frequency_grid=True
    )
    res = detector.search(clean_lc)

    # 1. Frequency grid is present and non-empty
    assert res.frequency_grid is not None
    assert len(res.frequency_grid) > 100
    assert np.all(res.frequency_grid > 0)

    # 2. Independent computation via Astropy BoxLeastSquares directly matches
    cleaned = clean_lc.clean()
    model = BoxLeastSquares(cleaned.time, cleaned.flux, dy=cleaned.flux_err)
    max_p = min(8.0, (cleaned.time[-1] - cleaned.time[0]) * 0.95)
    direct_periodogram = model.autopower(
        duration=detector.duration_grid,
        minimum_period=0.5,
        maximum_period=max_p,
        frequency_factor=5.0
    )
    expected_frequencies = 1.0 / np.asarray(direct_periodogram.period, dtype=float)

    assert len(res.frequency_grid) == len(expected_frequencies)
    assert np.allclose(res.frequency_grid, expected_frequencies, rtol=1e-12)

    # 3. Serialization to disk via serialize_grid
    grid_path = tmp_path / "test_grid.npy"
    saved_path = res.serialize_grid(grid_path)
    assert saved_path == grid_path
    assert grid_path.exists()

    loaded_grid = np.load(grid_path)
    assert np.array_equal(res.frequency_grid, loaded_grid)

    # 4. Exact reconstruction metadata in grid_info
    grid_info = res.metadata.get("grid_info", {})
    assert grid_info["frequency_factor"] == 5.0
    assert grid_info["min_period"] == 0.5
    assert np.isclose(grid_info["max_period"], max_p)
    assert grid_info["n_frequencies"] == len(res.frequency_grid)
    assert np.isclose(grid_info["min_frequency"], np.min(expected_frequencies))
    assert np.isclose(grid_info["max_frequency"], np.max(expected_frequencies))


