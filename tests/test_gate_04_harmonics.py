"""
Unit and regression tests for GATE-04 Harmonic Set Definition.

Evaluates candidate harmonic sets:
- Option A (Broad): {1/3, 1/2, 1, 2, 3}
- Option B (Narrow): {1/2, 1, 2}

Verifies:
- Exact accepted ratios under Option A and Option B
- Values just inside and just outside the 1% relative tolerance threshold
- Option-A-only ratios (1/3 and 3) correctly recover under A and fail under B
- Shared ratios (1/2, 1, 2) behave identically under A and B
- Invalid, nonpositive, and non-finite periods handled safely
- Deterministic identical input detections produce identical outputs
"""
import pytest
import numpy as np

from tess_benchmark.baselines.bls import BLSResult, match_period_to_harmonics

OPTION_A_RATIOS = (1.0 / 3.0, 0.5, 1.0, 2.0, 3.0)
OPTION_B_RATIOS = (0.5, 1.0, 2.0)


def test_gate_04_exact_accepted_ratios():
    """Verify exact harmonic ratios evaluate to 0.0% relative error and pass."""
    catalog_period = 6.0

    # Test all Option A ratios
    for ratio in OPTION_A_RATIOS:
        det_p = catalog_period * ratio
        rec_a, nearest_r_a, err_a = match_period_to_harmonics(
            det_p, catalog_period, accepted_ratios=OPTION_A_RATIOS, tolerance=0.01
        )
        assert rec_a is True
        assert nearest_r_a == pytest.approx(ratio, rel=1e-9)
        assert err_a == pytest.approx(0.0, abs=1e-15)

    # Test all Option B ratios
    for ratio in OPTION_B_RATIOS:
        det_p = catalog_period * ratio
        rec_b, nearest_r_b, err_b = match_period_to_harmonics(
            det_p, catalog_period, accepted_ratios=OPTION_B_RATIOS, tolerance=0.01
        )
        assert rec_b is True
        assert nearest_r_b == pytest.approx(ratio, rel=1e-9)
        assert err_b == pytest.approx(0.0, abs=1e-15)


def test_gate_04_shared_ratios_identical_behavior():
    """Verify shared ratios {1/2, 1, 2} behave identically between Option A and Option B."""
    catalog_period = 4.0
    shared_ratios = [0.5, 1.0, 2.0]

    for ratio in shared_ratios:
        det_exact = catalog_period * ratio
        rec_a, r_a, err_a = match_period_to_harmonics(det_exact, catalog_period, OPTION_A_RATIOS)
        rec_b, r_b, err_b = match_period_to_harmonics(det_exact, catalog_period, OPTION_B_RATIOS)
        assert rec_a == rec_b is True
        assert r_a == r_b == pytest.approx(ratio)
        assert err_a == err_b == pytest.approx(0.0, abs=1e-15)

        # Perturbation inside 1% boundary (0.5% error)
        det_in = det_exact * 1.005
        rec_a_in, r_a_in, err_a_in = match_period_to_harmonics(det_in, catalog_period, OPTION_A_RATIOS)
        rec_b_in, r_b_in, err_b_in = match_period_to_harmonics(det_in, catalog_period, OPTION_B_RATIOS)
        assert rec_a_in == rec_b_in is True
        assert r_a_in == r_b_in == pytest.approx(ratio)
        assert err_a_in == pytest.approx(err_b_in, rel=1e-9)

        # Perturbation outside 1% boundary (1.5% error)
        det_out = det_exact * 1.015
        rec_a_out, _, _ = match_period_to_harmonics(det_out, catalog_period, OPTION_A_RATIOS)
        rec_b_out, _, _ = match_period_to_harmonics(det_out, catalog_period, OPTION_B_RATIOS)
        assert rec_a_out == rec_b_out is False


def test_gate_04_option_a_only_ratios():
    """Verify 1/3 and 3 ratios pass under Option A and fail under Option B."""
    catalog_period = 9.0

    # 1/3 subharmonic: det = 3.0 days
    det_third = catalog_period * (1.0 / 3.0)
    rec_a, r_a, err_a = match_period_to_harmonics(det_third, catalog_period, OPTION_A_RATIOS)
    rec_b, r_b, err_b = match_period_to_harmonics(det_third, catalog_period, OPTION_B_RATIOS)
    assert rec_a is True
    assert r_a == pytest.approx(1.0 / 3.0)
    assert err_a == pytest.approx(0.0, abs=1e-15)
    # Under B, nearest is 0.5 (target = 4.5 d, err = |3.0 - 4.5| / 4.5 = 33.3% > 1%)
    assert rec_b is False
    assert r_b == pytest.approx(0.5)
    assert err_b == pytest.approx(1.0 / 3.0, rel=1e-4)

    # 3x harmonic: det = 27.0 days
    det_triple = catalog_period * 3.0
    rec_a_3, r_a_3, err_a_3 = match_period_to_harmonics(det_triple, catalog_period, OPTION_A_RATIOS)
    rec_b_3, r_b_3, err_b_3 = match_period_to_harmonics(det_triple, catalog_period, OPTION_B_RATIOS)
    assert rec_a_3 is True
    assert r_a_3 == pytest.approx(3.0)
    assert err_a_3 == pytest.approx(0.0, abs=1e-15)
    # Under B, nearest is 2.0 (target = 18.0 d, err = |27.0 - 18.0| / 18.0 = 50.0% > 1%)
    assert rec_b_3 is False
    assert r_b_3 == pytest.approx(2.0)
    assert err_b_3 == pytest.approx(0.50, rel=1e-4)


def test_gate_04_just_inside_and_just_outside_threshold():
    """Verify values just inside and outside the 1% boundary across ratios."""
    catalog_period = 6.0

    for ratio in OPTION_A_RATIOS:
        target = catalog_period * ratio

        # Boundary exact
        rec, _, err = match_period_to_harmonics(target * 1.01, catalog_period, OPTION_A_RATIOS)
        assert rec is True, f"Failed at upper boundary for ratio {ratio}"
        rec_low, _, err_low = match_period_to_harmonics(target * 0.99, catalog_period, OPTION_A_RATIOS)
        assert rec_low is True, f"Failed at lower boundary for ratio {ratio}"

        # Just inside (0.99% error)
        rec_in_up, _, _ = match_period_to_harmonics(target * 1.0099, catalog_period, OPTION_A_RATIOS)
        assert rec_in_up is True
        rec_in_low, _, _ = match_period_to_harmonics(target * 0.9901, catalog_period, OPTION_A_RATIOS)
        assert rec_in_low is True

        # Just outside (1.01% error)
        rec_out_up, _, _ = match_period_to_harmonics(target * 1.0101, catalog_period, OPTION_A_RATIOS)
        assert rec_out_up is False, f"Unexpected pass outside upper boundary for ratio {ratio}"
        rec_out_low, _, _ = match_period_to_harmonics(target * 0.9899, catalog_period, OPTION_A_RATIOS)
        assert rec_out_low is False, f"Unexpected pass outside lower boundary for ratio {ratio}"


def test_gate_04_invalid_nonpositive_inputs():
    """Verify safe rejection of invalid, nonpositive, and non-finite periods."""
    # Zero or negative catalog period
    rec, r, err = match_period_to_harmonics(5.0, 0.0, OPTION_A_RATIOS)
    assert rec is False and r is None and np.isnan(err)

    rec, r, err = match_period_to_harmonics(5.0, -2.0, OPTION_A_RATIOS)
    assert rec is False and r is None and np.isnan(err)

    # Zero or negative detected period
    rec, r, err = match_period_to_harmonics(0.0, 5.0, OPTION_A_RATIOS)
    assert rec is False and r is None and np.isnan(err)

    rec, r, err = match_period_to_harmonics(-1.0, 5.0, OPTION_A_RATIOS)
    assert rec is False and r is None and np.isnan(err)

    # Non-finite inputs
    rec, r, err = match_period_to_harmonics(float("nan"), 5.0, OPTION_A_RATIOS)
    assert rec is False and r is None and np.isnan(err)

    rec, r, err = match_period_to_harmonics(5.0, float("nan"), OPTION_A_RATIOS)
    assert rec is False and r is None and np.isnan(err)

    rec, r, err = match_period_to_harmonics(float("inf"), 5.0, OPTION_A_RATIOS)
    assert rec is False and r is None and np.isnan(err)

    rec, r, err = match_period_to_harmonics(5.0, float("inf"), OPTION_A_RATIOS)
    assert rec is False and r is None and np.isnan(err)

    # BLSResult method compatibility
    res = BLSResult(
        best_period=10.0, best_t0=1.0, best_duration=0.2, best_depth=0.005,
        max_power=10.0, mean_power=2.0, std_power=1.0, sde=8.0, snr=10.0,
        is_detected=True, runtime_sec=0.1
    )
    assert res.is_period_recovered(0.0, accepted_ratios=OPTION_A_RATIOS) is False
    assert res.is_period_recovered(-5.0, accepted_ratios=OPTION_B_RATIOS) is False
    assert res.is_period_recovered(float("nan"), accepted_ratios=OPTION_A_RATIOS) is False


def test_gate_04_deterministic_identical_input_detections():
    """Verify that both options evaluate against identical input period detections."""
    from tess_benchmark.baselines.bls import BLSDetector
    from tess_benchmark.data.protocol import LightCurveData, TargetCategory

    # Create synthetic sinusoidal light curve to get deterministic BLS detection
    t = np.linspace(0, 20.0, 2000)
    p_sim = 2.5
    f = 1.0 - 0.01 * (np.sin(2.0 * np.pi * t / p_sim) > 0.9).astype(float)
    lc = LightCurveData(
        time=t, flux=f, flux_err=np.ones_like(t) * 0.001,
        target_id="DETERMINISTIC_TEST",
        category=TargetCategory.CONFIRMED_PLANET_HOST,
        has_transit=True
    )

    detector = BLSDetector(min_period=0.5, max_period=10.0)
    result = detector.search(lc)

    # Both options receive the exact same result.best_period
    det_period = result.best_period
    rec_a, r_a, err_a = match_period_to_harmonics(det_period, p_sim, accepted_ratios=OPTION_A_RATIOS)
    rec_b, r_b, err_b = match_period_to_harmonics(det_period, p_sim, accepted_ratios=OPTION_B_RATIOS)

    # Ensure evaluation is deterministic and inputs were identical
    assert rec_a == rec_b
    assert r_a == r_b
    assert err_a == err_b


def test_gate_04_default_formal_rule_rejects_broad_ratios_and_accepts_narrow():
    """
    Verify the formal default rule:
    - Default accepted ratios are {0.5, 1.0, 2.0} (Option B).
    - Default formal rule accepts 0.5x, 1x, 2x.
    - Default formal rule rejects 1/3x and 3x.
    - Callers can explicitly pass broad exploratory set without changing formal default.
    """
    catalog_period = 12.0

    # 1. Fundamental 1x (P_det = 12.0) -> True under default
    res_fund = BLSResult(
        best_period=12.0, best_t0=1.0, best_duration=0.2, best_depth=0.005,
        max_power=10.0, mean_power=2.0, std_power=1.0, sde=8.0, snr=10.0,
        is_detected=True, runtime_sec=0.1
    )
    assert res_fund.is_period_recovered(catalog_period) is True
    rec_fund, r_fund, _ = match_period_to_harmonics(12.0, catalog_period)
    assert rec_fund is True and r_fund == pytest.approx(1.0)

    # 2. Half harmonic 0.5x (P_det = 6.0) -> True under default
    res_half = BLSResult(
        best_period=6.0, best_t0=1.0, best_duration=0.2, best_depth=0.005,
        max_power=10.0, mean_power=2.0, std_power=1.0, sde=8.0, snr=10.0,
        is_detected=True, runtime_sec=0.1
    )
    assert res_half.is_period_recovered(catalog_period) is True
    rec_half, r_half, _ = match_period_to_harmonics(6.0, catalog_period)
    assert rec_half is True and r_half == pytest.approx(0.5)

    # 3. Double harmonic 2.0x (P_det = 24.0) -> True under default
    res_double = BLSResult(
        best_period=24.0, best_t0=1.0, best_duration=0.2, best_depth=0.005,
        max_power=10.0, mean_power=2.0, std_power=1.0, sde=8.0, snr=10.0,
        is_detected=True, runtime_sec=0.1
    )
    assert res_double.is_period_recovered(catalog_period) is True
    rec_double, r_double, _ = match_period_to_harmonics(24.0, catalog_period)
    assert rec_double is True and r_double == pytest.approx(2.0)

    # 4. One-third subharmonic 1/3x (P_det = 4.0) -> False under default
    res_third = BLSResult(
        best_period=4.0, best_t0=1.0, best_duration=0.2, best_depth=0.005,
        max_power=10.0, mean_power=2.0, std_power=1.0, sde=8.0, snr=10.0,
        is_detected=True, runtime_sec=0.1
    )
    assert res_third.is_period_recovered(catalog_period) is False
    rec_third_def, _, _ = match_period_to_harmonics(4.0, catalog_period)
    assert rec_third_def is False
    # Explicitly passing Option A broad set succeeds
    assert res_third.is_period_recovered(catalog_period, accepted_ratios=OPTION_A_RATIOS) is True
    rec_third_exp, r_third_exp, _ = match_period_to_harmonics(4.0, catalog_period, accepted_ratios=OPTION_A_RATIOS)
    assert rec_third_exp is True and r_third_exp == pytest.approx(1.0 / 3.0)

    # 5. Triple harmonic 3.0x (P_det = 36.0) -> False under default
    res_triple = BLSResult(
        best_period=36.0, best_t0=1.0, best_duration=0.2, best_depth=0.005,
        max_power=10.0, mean_power=2.0, std_power=1.0, sde=8.0, snr=10.0,
        is_detected=True, runtime_sec=0.1
    )
    assert res_triple.is_period_recovered(catalog_period) is False
    rec_triple_def, _, _ = match_period_to_harmonics(36.0, catalog_period)
    assert rec_triple_def is False
    # Explicitly passing Option A broad set succeeds
    assert res_triple.is_period_recovered(catalog_period, accepted_ratios=OPTION_A_RATIOS) is True
    rec_triple_exp, r_triple_exp, _ = match_period_to_harmonics(36.0, catalog_period, accepted_ratios=OPTION_A_RATIOS)
    assert rec_triple_exp is True and r_triple_exp == pytest.approx(3.0)

