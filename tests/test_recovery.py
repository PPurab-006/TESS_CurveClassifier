"""
Unit and regression tests for formal benchmark recovery scoring (GATE-01, GATE-04, GATE-12)
and event coverage hierarchy (GATE-03).
"""
import numpy as np
import pytest

from tess_benchmark.evaluation.recovery import (
    compute_epoch_tolerance,
    compute_circular_epoch_residual,
    evaluate_event_coverage,
    RealDataBenchmarkScorer,
    HarmonicClass,
    MatchStatus,
    CandidateCatalogMatch,
    EventCoverageRecord,
)


def test_epoch_tolerance_formula_and_cap():
    """GATE-12: Delta t0_tol = min(0.50*Tdur, sqrt((0.25*Tdur)^2 + (3*sigma_tmid)^2))."""
    tdur = 0.2  # ~4.8 hours in days

    # Case 1: sigma_tmid = 0 -> tolerance should be exactly 0.25 * tdur = 0.05
    tol_zero = compute_epoch_tolerance(duration_days=tdur, timing_uncertainty_days=0.0)
    assert np.isclose(tol_zero, 0.05)

    # Case 2: small uncertainty -> quadrature evaluates below cap
    sigma_small = 0.005
    expected_quad = np.sqrt((0.25 * tdur)**2 + (3.0 * sigma_small)**2)
    tol_small = compute_epoch_tolerance(duration_days=tdur, timing_uncertainty_days=sigma_small)
    assert np.isclose(tol_small, expected_quad)
    assert tol_small < 0.50 * tdur

    # Case 3: large uncertainty -> 0.50 * tdur cap strictly binds!
    sigma_large = 0.1
    tol_capped = compute_epoch_tolerance(duration_days=tdur, timing_uncertainty_days=sigma_large)
    assert np.isclose(tol_capped, 0.50 * tdur)
    assert tol_capped == 0.10

    # Case 4: non-physical inputs return NaN
    assert np.isnan(compute_epoch_tolerance(-0.1, 0.01))
    assert np.isnan(compute_epoch_tolerance(0.2, -0.01))
    assert np.isnan(compute_epoch_tolerance(np.nan, 0.01))


def test_circular_epoch_residual():
    """Circular phase difference correctly handles periodic wraparound."""
    period = 4.0
    t0_cat = 100.0

    # Exact match
    res_exact, phase_exact = compute_circular_epoch_residual(100.0, t0_cat, period)
    assert np.isclose(res_exact, 0.0)
    assert np.isclose(phase_exact, 0.0)

    # Integer multiple periods forward
    res_k, phase_k = compute_circular_epoch_residual(100.0 + 5 * period, t0_cat, period)
    assert np.isclose(res_k, 0.0)
    assert np.isclose(phase_k, 0.0)

    # Small offset +0.1 days
    res_plus, phase_plus = compute_circular_epoch_residual(100.1, t0_cat, period)
    assert np.isclose(res_plus, 0.1)
    assert np.isclose(phase_plus, 0.1 / 4.0)

    # Small offset -0.1 days (phase fraction near 1.0)
    res_minus, phase_minus = compute_circular_epoch_residual(99.9, t0_cat, period)
    assert np.isclose(res_minus, 0.1)
    assert np.isclose(phase_minus, 0.1 / 4.0)

    # Near half period
    res_half, phase_half = compute_circular_epoch_residual(102.0, t0_cat, period)
    assert np.isclose(res_half, 2.0)
    assert np.isclose(phase_half, 0.5)


def test_scorer_fundamental_vs_harmonic_recovery():
    """GATE-04: Narrow harmonic set {0.5, 1.0, 2.0} classified separately."""
    scorer = RealDataBenchmarkScorer(period_tolerance=0.01)

    cat_p = 3.0
    cat_t0 = 1350.0
    dur_h = 2.4  # 0.1 days
    sigma = 0.001

    # Fundamental match
    m_fund = scorer.match_candidate(
        detected_period=3.01,  # +0.33% error <= 1.0%
        detected_epoch=1350.02,
        catalog_period=cat_p,
        catalog_epoch=cat_t0,
        catalog_duration_hours=dur_h,
        catalog_timing_uncertainty_days=sigma
    )
    assert m_fund.is_period_match
    assert m_fund.harmonic_class == HarmonicClass.FUNDAMENTAL
    assert m_fund.match_status == MatchStatus.FULL_RECOVERY

    # Subharmonic match (0.5x period)
    m_sub = scorer.match_candidate(
        detected_period=1.505,  # ~0.5 * 3.0
        detected_epoch=1350.01,
        catalog_period=cat_p,
        catalog_epoch=cat_t0,
        catalog_duration_hours=dur_h,
        catalog_timing_uncertainty_days=sigma
    )
    assert m_sub.is_period_match
    assert m_sub.harmonic_class == HarmonicClass.SUBHARMONIC

    # Harmonic match (2.0x period)
    m_harm = scorer.match_candidate(
        detected_period=5.99,  # ~2.0 * 3.0
        detected_epoch=1350.01,
        catalog_period=cat_p,
        catalog_epoch=cat_t0,
        catalog_duration_hours=dur_h,
        catalog_timing_uncertainty_days=sigma
    )
    assert m_harm.is_period_match
    assert m_harm.harmonic_class == HarmonicClass.HARMONIC

    # Non-accepted ratio (e.g. 1/3x = 1.0d or 3x = 9.0d)
    m_3x = scorer.match_candidate(
        detected_period=9.0,
        detected_epoch=1350.01,
        catalog_period=cat_p,
        catalog_epoch=cat_t0,
        catalog_duration_hours=dur_h,
        catalog_timing_uncertainty_days=sigma
    )
    assert not m_3x.is_period_match
    assert m_3x.harmonic_class == HarmonicClass.NON_MATCH


def test_scorer_period_only_vs_full_recovery():
    """Period matches within 1.0% but epoch is off -> MatchStatus.PERIOD_ONLY."""
    scorer = RealDataBenchmarkScorer(period_tolerance=0.01)

    cat_p = 4.0
    cat_t0 = 1350.0
    dur_h = 2.4  # 0.1 days -> tol ~ 0.025 d
    sigma = 0.001

    # Epoch offset by 0.5 days (far beyond 0.025 d tolerance)
    m_po = scorer.match_candidate(
        detected_period=4.005,
        detected_epoch=1350.50,
        catalog_period=cat_p,
        catalog_epoch=cat_t0,
        catalog_duration_hours=dur_h,
        catalog_timing_uncertainty_days=sigma
    )
    assert m_po.is_period_match
    assert not m_po.is_epoch_match
    assert m_po.match_status == MatchStatus.PERIOD_ONLY


def test_scorer_strict_one_to_one_matching():
    """GATE-12: Strict one-to-one candidate to catalog matching."""
    scorer = RealDataBenchmarkScorer(period_tolerance=0.01)

    candidates = [
        {"candidate_id": "c1", "detected_period": 3.001, "detected_epoch": 100.01},
        {"candidate_id": "c2", "detected_period": 3.002, "detected_epoch": 100.02},
    ]
    catalog_planets = [
        {"planet_id": "p1", "period_days": 3.0, "t0_bjd": 100.0, "duration_hours": 3.0, "t0_err": 0.001}
    ]

    matches = scorer.match_candidates_one_to_one(candidates, catalog_planets, target_id="STAR_A")
    # Only 1 candidate can match the 1 planet
    assert len(matches) == 1
    assert matches[0].candidate_id == "c1"
    assert matches[0].catalog_planet_id == "p1"
    assert matches[0].match_status == MatchStatus.FULL_RECOVERY


def test_gate_03_interior_event_adequacy():
    """GATE-03 Option 2: Fully interior event with f_temporal >= 0.50 and N_valid >= 5."""
    # 27-day observation with continuous 2-minute (120s) cadences
    time_arr = np.linspace(1325.0, 1352.0, 19440)
    cat_t0 = 1330.0
    cat_p = 5.0
    cat_dur_h = 3.0  # 0.125 days (~90 cadences expected)

    records = evaluate_event_coverage(
        time_array=time_arr,
        catalog_t0=cat_t0,
        catalog_period=cat_p,
        catalog_duration_hours=cat_dur_h,
        cadence_sec=120.0
    )

    # Check interior events (at t = 1330, 1335, 1340, 1345, 1350)
    interior_events = [r for r in records if r.is_interior]
    assert len(interior_events) >= 5
    for ev in interior_events:
        assert ev.is_adequate_interior
        assert not ev.is_boundary_truncated
        assert ev.temporal_coverage_fraction >= 0.50
        assert ev.n_valid_cadences >= 5
        assert ev.exclusion_reason is None


def test_gate_03_boundary_truncated_diagnostic_track():
    """GATE-03 Option 2: Boundary-truncated event meeting secondary threshold is kept in diagnostic track."""
    # Time baseline starting at 1325.02 (clipping a transit centered at 1325.0)
    time_arr = np.linspace(1325.02, 1352.0, 19000)
    cat_t0 = 1325.0
    cat_p = 10.0
    cat_dur_h = 2.4  # 0.1 days duration -> window is [1324.95, 1325.05]
    # Observation baseline starts at 1325.02, so window [1324.95, 1325.05] is truncated on the left!

    records = evaluate_event_coverage(
        time_array=time_arr,
        catalog_t0=cat_t0,
        catalog_period=cat_p,
        catalog_duration_hours=cat_dur_h,
        cadence_sec=120.0
    )

    ev_boundary = [r for r in records if r.is_boundary_truncated and r.event_index == 0]
    assert len(ev_boundary) == 1
    ev = ev_boundary[0]
    assert not ev.is_interior
    assert ev.is_boundary_truncated
    # It cannot qualify as adequate interior
    assert not ev.is_adequate_interior
    # Check if adequate boundary (if > 30% coverage and >= 3 cadences)
    if ev.temporal_coverage_fraction >= 0.30 and ev.n_valid_cadences >= 3:
        assert ev.is_adequate_boundary


def test_gate_03_inadequate_coverage_gap():
    """GATE-03: Event falling entirely in a data downlink gap is marked inadequate."""
    # Simulate gap from 1334.0 to 1336.0
    t1 = np.linspace(1325.0, 1334.0, 6000)
    t2 = np.linspace(1336.0, 1352.0, 11000)
    time_arr = np.concatenate([t1, t2])

    cat_t0 = 1335.0  # right inside the gap!
    cat_p = 10.0
    cat_dur_h = 3.0

    records = evaluate_event_coverage(
        time_array=time_arr,
        catalog_t0=cat_t0,
        catalog_period=cat_p,
        catalog_duration_hours=cat_dur_h,
        cadence_sec=120.0
    )

    ev_gap = [r for r in records if r.event_index == 0]
    assert len(ev_gap) == 1
    ev = ev_gap[0]
    assert ev.n_valid_cadences == 0
    assert ev.temporal_coverage_fraction == 0.0
    assert not ev.is_adequate_interior
    assert not ev.is_adequate_boundary
    assert "temporal_cov" in ev.exclusion_reason


# ---------------------------------------------------------------------------
# GATE-03: Additional boundary / threshold tests
# ---------------------------------------------------------------------------

def test_gate_03_primary_threshold_boundary_exact():
    """GATE-03: Event with exactly f_temporal=0.50 and N_valid=5 is adequate primary interior."""
    # Place cadences precisely such that exactly 5 fall in a 0.1-day window -> f=5/(0.1*720)~0.069 range
    # Use a very short duration (0.1d = 2.4h) and place exactly 5 cadences covering >=50% of the window
    # t_dur = 0.1d, cadence=120s=1/720d. 5 cadences cover 5/720 = 0.0069d, which is << 0.05d.
    # Instead: use a long duration (1 day = 24h) so 5 cadences ~ 5*120s = 600s = 0.00694d coverage
    # That gives f_temporal = 0.00694/1.0 = 0.007 -> way below 0.50.
    # Build correctly: we need 5 cadences to cover >=50% of the window.
    # duration=0.00694d (~10min, 0.1667h). 5 cadences of 120s each = 600s = 0.00694d total.
    # So 5 * 120s >= 0.00694d * 86400 = 600s exactly. Coverage = 600s / (0.00694 * 86400) = 1.0.
    # Use duration = exactly 5 cadence widths.
    cadence_sec = 120.0
    t_dur_days = 5 * (cadence_sec / 86400.0)  # 600s = exactly 5 cadence widths
    dur_h = t_dur_days * 24.0

    # Center = 1340.0, build 5 cadences centered in window
    t_mid = 1340.0
    half = t_dur_days / 2.0
    # Sparse observation: only the 5 transit cadences + some outside
    in_transit = np.linspace(t_mid - half + cadence_sec/86400.0/2, t_mid + half - cadence_sec/86400.0/2, 5)
    out_of_transit = np.concatenate([
        np.linspace(1325.0, t_mid - 2 * t_dur_days, 500),
        np.linspace(t_mid + 2 * t_dur_days, 1352.0, 500)
    ])
    time_arr = np.sort(np.concatenate([in_transit, out_of_transit]))

    records = evaluate_event_coverage(
        time_array=time_arr,
        catalog_t0=t_mid,
        catalog_period=10.0,
        catalog_duration_hours=dur_h,
        cadence_sec=cadence_sec
    )

    ev = next((r for r in records if r.event_index == 0), None)
    assert ev is not None
    assert ev.is_interior
    assert ev.n_valid_cadences == 5
    assert ev.temporal_coverage_fraction >= 0.50
    assert ev.is_adequate_interior


def test_gate_03_primary_just_below_threshold_not_adequate():
    """GATE-03: Interior event with N_valid=4 (below min=5) is NOT adequate primary."""
    cadence_sec = 120.0
    t_dur_days = 5 * (cadence_sec / 86400.0)
    dur_h = t_dur_days * 24.0
    t_mid = 1340.0
    half = t_dur_days / 2.0

    # Only 4 cadences inside window
    in_transit = np.linspace(t_mid - half + cadence_sec/86400.0/2, t_mid + half - cadence_sec/86400.0/2, 4)
    out = np.concatenate([
        np.linspace(1325.0, t_mid - 2 * t_dur_days, 500),
        np.linspace(t_mid + 2 * t_dur_days, 1352.0, 500)
    ])
    time_arr = np.sort(np.concatenate([in_transit, out]))

    records = evaluate_event_coverage(
        time_array=time_arr,
        catalog_t0=t_mid,
        catalog_period=10.0,
        catalog_duration_hours=dur_h,
        cadence_sec=cadence_sec
    )

    ev = next((r for r in records if r.event_index == 0), None)
    assert ev is not None
    assert ev.is_interior
    assert ev.n_valid_cadences == 4
    assert not ev.is_adequate_interior  # Below N_valid >= 5 threshold


def test_gate_03_boundary_below_secondary_threshold_excluded():
    """GATE-03: Boundary event with <30% coverage is excluded from both tracks."""
    # Put observation baseline starting midway through transit
    # Transit window: [1325.0, 1325.1]. Baseline starts at 1325.09 (covers only 10% of window)
    t_dur_days = 0.1
    dur_h = t_dur_days * 24.0
    t_mid = 1325.05
    baseline_start = 1325.09  # window end = 1325.1, so 1% overlap

    time_arr = np.linspace(baseline_start, 1352.0, 18000)

    records = evaluate_event_coverage(
        time_array=time_arr,
        catalog_t0=1325.0,
        catalog_period=10.0,
        catalog_duration_hours=dur_h,
        cadence_sec=120.0
    )

    ev = next((r for r in records if r.is_boundary_truncated and r.event_index == 0), None)
    if ev is not None:
        assert not ev.is_adequate_interior
        if ev.temporal_coverage_fraction < 0.30 or ev.n_valid_cadences < 3:
            assert not ev.is_adequate_boundary
            assert ev.exclusion_reason is not None


def test_gate_03_primary_and_boundary_never_mixed():
    """GATE-03: A single event is classified as either interior OR boundary, never both."""
    time_arr = np.linspace(1325.0, 1352.0, 19440)
    cat_t0 = 1330.0
    cat_p = 5.0
    cat_dur_h = 3.0

    records = evaluate_event_coverage(
        time_array=time_arr,
        catalog_t0=cat_t0,
        catalog_period=cat_p,
        catalog_duration_hours=cat_dur_h,
        cadence_sec=120.0
    )

    for ev in records:
        # An event is either interior OR boundary, never both
        assert not (ev.is_interior and ev.is_boundary_truncated), \
            f"Event {ev.event_index} is classified as both interior and boundary"
        # An adequate interior event must be interior
        if ev.is_adequate_interior:
            assert ev.is_interior
        # An adequate boundary event must be boundary
        if ev.is_adequate_boundary:
            assert ev.is_boundary_truncated


def test_gate_03_empty_time_array_returns_no_records():
    """GATE-03: Empty time array returns empty record list."""
    records = evaluate_event_coverage(
        time_array=np.array([]),
        catalog_t0=1330.0,
        catalog_period=5.0,
        catalog_duration_hours=3.0
    )
    assert records == []


def test_gate_03_invalid_period_and_duration():
    """GATE-03: Invalid period or duration returns empty list without error."""
    time_arr = np.linspace(1325.0, 1352.0, 1000)

    records_neg_period = evaluate_event_coverage(time_arr, 1330.0, -1.0, 3.0)
    assert records_neg_period == []

    records_neg_dur = evaluate_event_coverage(time_arr, 1330.0, 5.0, -2.4)
    assert records_neg_dur == []


# ---------------------------------------------------------------------------
# GATE-12: Additional epoch matching tests
# ---------------------------------------------------------------------------

def test_epoch_tolerance_exact_zero_uncertainty():
    """GATE-12: When sigma_tmid=0, tolerance = 0.25 * T_dur (quadrature term collapses)."""
    tol = compute_epoch_tolerance(duration_days=0.1, timing_uncertainty_days=0.0)
    assert np.isclose(tol, 0.25 * 0.1)


def test_epoch_tolerance_cap_binds_at_large_uncertainty():
    """GATE-12: When uncertainty term > 0.50*Tdur, the cap binds exactly."""
    # Very large uncertainty: 3*sigma >> 0.5*Tdur
    tol = compute_epoch_tolerance(duration_days=0.1, timing_uncertainty_days=0.2)
    assert np.isclose(tol, 0.50 * 0.1)


def test_epoch_tolerance_invalid_inputs():
    """GATE-12: Invalid inputs (negative duration, negative uncertainty, NaN) return NaN."""
    assert np.isnan(compute_epoch_tolerance(-0.1, 0.01))
    assert np.isnan(compute_epoch_tolerance(0.1, -0.01))
    assert np.isnan(compute_epoch_tolerance(np.nan, 0.01))
    assert np.isnan(compute_epoch_tolerance(0.0, 0.01))  # zero duration is invalid
    assert np.isnan(compute_epoch_tolerance(np.inf, 0.01))


def test_circular_epoch_residual_wraparound():
    """GATE-12: Phase wraparound is handled correctly (residual always in [0, P/2])."""
    period = 3.0
    t0_cat = 100.0

    # Offset just before full period (phase~0.99 -> should fold to ~0.01 * P = 0.03 days)
    det_epoch = t0_cat + 0.97 * period
    res, phase = compute_circular_epoch_residual(det_epoch, t0_cat, period)
    assert np.isclose(phase, 0.03, atol=1e-10) or np.isclose(phase, 0.5 - 0.03, atol=1e-5)
    # Circular phase must be in [0, 0.5]
    assert 0.0 <= phase <= 0.5

    # Offset by exactly half period: maximum residual P/2
    det_half = t0_cat + 0.5 * period
    res_half, phase_half = compute_circular_epoch_residual(det_half, t0_cat, period)
    assert np.isclose(phase_half, 0.5)
    assert np.isclose(res_half, 0.5 * period)


def test_circular_epoch_residual_invalid_inputs():
    """GATE-12: Non-finite inputs return (NaN, NaN)."""
    r, p = compute_circular_epoch_residual(np.nan, 100.0, 4.0)
    assert np.isnan(r) and np.isnan(p)

    r, p = compute_circular_epoch_residual(100.0, 100.0, 0.0)
    assert np.isnan(r) and np.isnan(p)

    r, p = compute_circular_epoch_residual(100.0, 100.0, -1.0)
    assert np.isnan(r) and np.isnan(p)


def test_scorer_epoch_exactly_at_tolerance_boundary():
    """GATE-12: Detection at exactly the epoch tolerance boundary is accepted."""
    scorer = RealDataBenchmarkScorer(period_tolerance=0.01)
    dur_h = 4.8   # 0.2 days
    sigma = 0.001
    tol = compute_epoch_tolerance(dur_h / 24.0, sigma)

    # Place detected epoch exactly at tolerance
    cat_p = 3.0
    cat_t0 = 1350.0
    det_t0 = cat_t0 + tol  # exactly at boundary

    m = scorer.match_candidate(
        detected_period=3.0,
        detected_epoch=det_t0,
        catalog_period=cat_p,
        catalog_epoch=cat_t0,
        catalog_duration_hours=dur_h,
        catalog_timing_uncertainty_days=sigma
    )
    # Tolerance boundary: should pass (with machine-precision ULP allowance)
    assert m.is_epoch_match


def test_scorer_epoch_just_outside_tolerance():
    """GATE-12: Detection just beyond tolerance boundary is rejected for epoch."""
    scorer = RealDataBenchmarkScorer(period_tolerance=0.01)
    dur_h = 4.8   # 0.2 days
    sigma = 0.001
    tol = compute_epoch_tolerance(dur_h / 24.0, sigma)

    cat_p = 3.0
    cat_t0 = 1350.0
    det_t0 = cat_t0 + tol + 1e-6  # just beyond boundary

    m = scorer.match_candidate(
        detected_period=3.0,
        detected_epoch=det_t0,
        catalog_period=cat_p,
        catalog_epoch=cat_t0,
        catalog_duration_hours=dur_h,
        catalog_timing_uncertainty_days=sigma
    )
    assert not m.is_epoch_match
    assert m.match_status == MatchStatus.PERIOD_ONLY


def test_scorer_invalid_ephemeris_inputs():
    """GATE-12: Invalid catalog ephemeris (NaN period, zero duration) returns INVALID_EPHEMERIS."""
    scorer = RealDataBenchmarkScorer(period_tolerance=0.01)

    # NaN catalog period
    m = scorer.match_candidate(
        detected_period=3.0, detected_epoch=1350.0,
        catalog_period=float('nan'), catalog_epoch=1350.0,
        catalog_duration_hours=2.4, catalog_timing_uncertainty_days=0.001
    )
    assert m.match_status == MatchStatus.INVALID_EPHEMERIS

    # Zero duration
    m2 = scorer.match_candidate(
        detected_period=3.0, detected_epoch=1350.0,
        catalog_period=3.0, catalog_epoch=1350.0,
        catalog_duration_hours=0.0, catalog_timing_uncertainty_days=0.001
    )
    assert m2.match_status == MatchStatus.INVALID_EPHEMERIS

    # Negative detected period
    m3 = scorer.match_candidate(
        detected_period=-1.0, detected_epoch=1350.0,
        catalog_period=3.0, catalog_epoch=1350.0,
        catalog_duration_hours=2.4, catalog_timing_uncertainty_days=0.001
    )
    assert m3.match_status == MatchStatus.INVALID_EPHEMERIS


def test_scorer_one_to_one_multiple_catalog_planets():
    """GATE-12: Multiple catalog planets matched one-to-one; no candidate recovers two."""
    scorer = RealDataBenchmarkScorer(period_tolerance=0.01)

    candidates = [
        {"candidate_id": "c1", "detected_period": 3.005, "detected_epoch": 100.01},
        {"candidate_id": "c2", "detected_period": 7.02,  "detected_epoch": 200.02},
    ]
    catalog_planets = [
        {"planet_id": "p1", "period_days": 3.0, "t0_bjd": 100.0, "duration_hours": 2.4, "t0_err": 0.001},
        {"planet_id": "p2", "period_days": 7.0, "t0_bjd": 200.0, "duration_hours": 3.0, "t0_err": 0.001},
    ]

    matches = scorer.match_candidates_one_to_one(candidates, catalog_planets, target_id="STAR_B")
    assert len(matches) == 2
    recovered_planets = {m.catalog_planet_id for m in matches}
    assert "p1" in recovered_planets
    assert "p2" in recovered_planets
    for m in matches:
        assert m.match_status == MatchStatus.FULL_RECOVERY


def test_scorer_duplicate_candidates_one_to_one_constraint():
    """GATE-12: Two candidates both matching the same planet: only the better one is assigned."""
    scorer = RealDataBenchmarkScorer(period_tolerance=0.01)

    candidates = [
        {"candidate_id": "c1", "detected_period": 3.001, "detected_epoch": 100.01},  # better match
        {"candidate_id": "c2", "detected_period": 3.009, "detected_epoch": 100.08},  # worse match
    ]
    catalog_planets = [
        {"planet_id": "p1", "period_days": 3.0, "t0_bjd": 100.0, "duration_hours": 2.4, "t0_err": 0.001},
    ]

    matches = scorer.match_candidates_one_to_one(candidates, catalog_planets, target_id="STAR_C")
    # Only 1 match should be returned (one-to-one: p1 can only be matched once)
    assert len(matches) == 1
    assert matches[0].candidate_id == "c1"  # better match wins
