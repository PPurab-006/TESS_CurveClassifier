"""
Unit tests for Stage 4 52-Feature Schema and Transit Morphology Extractor.
"""
import numpy as np
import pytest

from tess_benchmark.data.protocol import LightCurveData, TargetCategory
from tess_benchmark.data.synthetic import SyntheticTransitConfig, generate_synthetic_light_curve
from tess_benchmark.stage4.features import (
    STAGE4_FEATURE_NAMES,
    STAGE4_NEW_FEATURE_NAMES,
    BASELINE_FEATURE_NAMES,
    STAGE4_FEATURE_GROUPS,
    extract_all_candidate_features,
    extract_stage4_new_features,
)


def test_stage4_feature_schema_invariants():
    """Verify programmatic schema integrity and deterministic ordering."""
    assert len(STAGE4_FEATURE_NAMES) == 52
    assert len(set(STAGE4_FEATURE_NAMES)) == 52
    assert len(BASELINE_FEATURE_NAMES) == 22
    assert len(STAGE4_NEW_FEATURE_NAMES) == 30

    # Ensure all groups are represented
    assert "baseline" in STAGE4_FEATURE_GROUPS
    assert "shape" in STAGE4_FEATURE_GROUPS
    assert "morphology" in STAGE4_FEATURE_GROUPS
    assert "event_consistency" in STAGE4_FEATURE_GROUPS
    assert "odd_even" in STAGE4_FEATURE_GROUPS
    assert "variability" in STAGE4_FEATURE_GROUPS
    assert "localization" in STAGE4_FEATURE_GROUPS


def test_extract_all_candidate_features_standard_transit():
    """Verify feature extraction on a clean synthetic planetary transit."""
    cfg = SyntheticTransitConfig(
        duration_days=10.0,
        cadence_minutes=2.0,
        has_transit=True,
        period_days=2.5,
        t0_days=0.5,
        depth=0.008,
        duration_hours=2.5,
        noise_sigma=0.0005,
        seed=123
    )
    lc = generate_synthetic_light_curve(cfg, target_id="TEST-TRANSIT-01")

    res = extract_all_candidate_features(
        lc=lc,
        candidate_period=2.5,
        candidate_t0=0.5,
        candidate_duration=2.5 / 24.0,
        candidate_depth=0.008,
        bls_sde=25.0,
        bls_snr=30.0,
        bls_max_power=100.0
    )

    feats = res.to_dict()
    assert len(feats) == 52
    for name in STAGE4_FEATURE_NAMES:
        assert name in feats, f"Missing feature: {name}"
        val = feats[name]
        # Must be finite or valid np.nan, never Inf
        assert not np.isinf(val), f"Feature {name} is infinite: {val}"

    # Physical checks for genuine clean transit
    assert feats["shape_depth_to_local_mad"] > 5.0
    assert feats["shape_candidate_duty_cycle"] < 0.10
    assert feats["shape_in_out_contrast"] > 3.0
    assert feats["event_n_observed"] >= 3
    assert feats["event_n_adequate"] >= 3
    assert feats["event_adequate_fraction"] == 1.0


def test_extract_features_edge_case_zero_transits():
    """Verify graceful handling when period or duration is zero or non-physical."""
    time = np.linspace(0, 10, 1000)
    flux = np.ones(1000)

    lc = LightCurveData(
        time=time,
        flux=flux,
        flux_err=np.full(1000, 0.001),
        target_id="EDGE-ZERO",
        category=TargetCategory.CONTROL_STAR,
        has_transit=False
    )

    res = extract_all_candidate_features(
        lc=lc,
        candidate_period=0.0,
        candidate_t0=0.0,
        candidate_duration=0.0,
        candidate_depth=0.0,
        bls_sde=0.0,
        bls_snr=0.0,
        bls_max_power=0.0
    )

    feats = res.to_dict()
    assert len(feats) == 52
    for name, val in feats.items():
        assert not np.isinf(val), f"Feature {name} is Inf"


def test_extract_features_single_transit_dominance():
    """Verify single transit dominance equals 1.0 when only one event occurs."""
    cfg = SyntheticTransitConfig(
        duration_days=3.0,
        cadence_minutes=2.0,
        has_transit=True,
        period_days=8.0,
        t0_days=1.5,
        depth=0.01,
        duration_hours=2.0,
        seed=42
    )
    lc = generate_synthetic_light_curve(cfg, target_id="SINGLE-EV")

    res = extract_all_candidate_features(
        lc=lc,
        candidate_period=8.0,
        candidate_t0=1.5,
        candidate_duration=2.0 / 24.0,
        candidate_depth=0.01,
        bls_sde=10.0,
        bls_snr=15.0,
        bls_max_power=50.0
    )
    feats = res.to_dict()

    assert feats["event_n_observed"] == 1.0
    assert feats["event_n_adequate"] == 1.0
    assert feats["event_single_event_dominance"] == 1.0
    # Depth scatter across events requires >= 3 events, so should be NaN
    assert np.isnan(feats["event_depth_scatter_mad"])


def test_odd_even_consistency_distinguishes_eb_from_planet():
    """Verify odd/even ratio captures depth asymmetry in alternating dips."""
    time = np.arange(0, 20.0, 2.0 / (24.0 * 60.0))
    flux = np.ones_like(time)
    period = 2.0

    # Inject alternating primary (10,000 ppm) and secondary (2,000 ppm) dips
    for k in range(10):
        t_c = 1.0 + k * period
        in_dip = np.abs(time - t_c) < (0.1 / 2.0)
        if k % 2 == 0:
            flux[in_dip] -= 0.010  # Primary
        else:
            flux[in_dip] -= 0.002  # Secondary

    lc = LightCurveData(
        time=time,
        flux=flux,
        flux_err=np.full_like(time, 0.0005),
        target_id="EB-TEST",
        category=TargetCategory.CONTROL_STAR,
        has_transit=False
    )

    res = extract_all_candidate_features(
        lc=lc,
        candidate_period=period,
        candidate_t0=1.0,
        candidate_duration=0.1,
        candidate_depth=0.010,
        bls_sde=20.0,
        bls_snr=25.0,
        bls_max_power=80.0
    )
    feats = res.to_dict()

    # Odd/even depth ratio should be approximately 0.20 (2,000 / 10,000)
    assert np.isfinite(feats["odd_even_depth_ratio_v2"])
    assert feats["odd_even_depth_ratio_v2"] < 0.40
    assert feats["odd_even_depth_difference"] > 0.005
