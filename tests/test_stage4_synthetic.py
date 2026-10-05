"""
Unit tests for Stage 4 Synthetic Candidate Discovery Generator.
"""
import numpy as np
import pytest

from tess_benchmark.stage4.synthetic_generator import (
    SyntheticCandidateConfig,
    generate_synthetic_candidate_dataset,
    _simulate_planetary_transit,
    _simulate_eclipsing_binary,
    _simulate_stellar_rotation,
    _simulate_active_flare_star,
    _simulate_instrumental_systematics,
    _simulate_red_noise_artifact,
)
from tess_benchmark.stage4.features import STAGE4_FEATURE_NAMES


def test_simulate_individual_confounder_classes():
    """Verify each confounder simulation produces finite flux arrays of expected size."""
    time = np.linspace(0, 27.4, 1000)
    rng = np.random.default_rng(42)

    sims = [
        ("transit", _simulate_planetary_transit),
        ("eclipsing_binary", _simulate_eclipsing_binary),
        ("stellar_rotation", _simulate_stellar_rotation),
        ("active_flare", _simulate_active_flare_star),
        ("systematics", _simulate_instrumental_systematics),
        ("red_noise", _simulate_red_noise_artifact),
    ]

    for name, fn in sims:
        flux, meta = fn(time, rng, baseline_flux=1.0, noise_sigma=0.001)
        assert len(flux) == 1000
        assert np.all(np.isfinite(flux)), f"Class {name} produced non-finite flux"
        assert len(meta) > 0


def test_generate_synthetic_candidate_dataset_mini():
    """Verify end-to-end synthetic candidate pipeline on a small quota."""
    config = SyntheticCandidateConfig(
        n_targets_per_class=2,  # 2 per class * 6 classes = 12 total candidates
        duration_days=10.0,
        cadence_minutes=5.0,
        seed=100,
        sde_threshold=3.0,  # lowered for quick test
        min_snr=3.0,
        frequency_factor=3.0
    )

    df_cand, audit = generate_synthetic_candidate_dataset(config, admit_only_detected=True)

    assert len(df_cand) == 12
    assert audit["total_transits"] == 2
    assert audit["total_confounders"] == 10

    # Verify all 52 features are present in the DataFrame
    for feat in STAGE4_FEATURE_NAMES:
        assert feat in df_cand.columns, f"Missing feature in DataFrame: {feat}"

    # Verify metadata columns
    assert "target_id" in df_cand.columns
    assert "class_label" in df_cand.columns
    assert "is_transit" in df_cand.columns
    assert "candidate_period" in df_cand.columns
    assert "candidate_depth" in df_cand.columns
    assert "bls_sde" in df_cand.columns
    assert "bls_snr" in df_cand.columns
