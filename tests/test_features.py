"""
Tests for feature extraction and phase-folding modules.
"""
import numpy as np
from tess_benchmark.features.folding import phase_fold, bin_folded_light_curve, extract_phase_views
from tess_benchmark.features.extractors import FeatureExtractor, FEATURE_NAMES
from tess_benchmark.data.synthetic import SyntheticTransitConfig, generate_synthetic_light_curve


def test_phase_fold():
    """Verify phase folding wraps time into [-0.5, 0.5) centered on t0."""
    period = 4.0
    t0 = 1.0
    time = np.array([1.0, 3.0, 5.0, 0.0])
    phases = phase_fold(time, period, t0)

    # At t0 = 1.0, phase should be 0.0
    assert np.isclose(phases[0], 0.0, atol=1e-5)
    # At t = 5.0 (t0 + P), phase should be 0.0
    assert np.isclose(phases[2], 0.0, atol=1e-5)
    # Phases must strictly be within [-0.5, 0.5)
    assert np.all(phases >= -0.5)
    assert np.all(phases < 0.5)


def test_bin_folded_light_curve():
    """Verify binning produces requested number of bins with no missing values."""
    n_pts = 1000
    phases = np.linspace(-0.5, 0.5, n_pts)
    flux = 1.0 - 0.01 * np.exp(-((phases) ** 2) / 0.001)

    bin_centers, binned_flux, binned_err = bin_folded_light_curve(phases, flux, n_bins=50)

    assert len(bin_centers) == 50
    assert len(binned_flux) == 50
    assert len(binned_err) == 50
    assert np.all(np.isfinite(binned_flux))
    # Minimum flux should be at center phase
    assert np.argmin(binned_flux) == 24 or np.argmin(binned_flux) == 25


def test_feature_extractor_tabular():
    """FeatureExtractor must extract all defined features without NaNs or Infinities."""
    config = SyntheticTransitConfig(
        duration_days=6.0,
        cadence_minutes=10.0,
        has_transit=True,
        period_days=2.0,
        depth=0.006,
        seed=42
    )
    lc = generate_synthetic_light_curve(config, target_id="FEAT-TEST")
    extractor = FeatureExtractor(n_phase_bins=50)
    features = extractor.extract_tabular_features(lc)

    for name in FEATURE_NAMES:
        assert name in features, f"Missing feature {name}"
        assert np.isfinite(features[name]), f"Feature {name} is not finite: {features[name]}"


def test_feature_extractor_phase_vector():
    """FeatureExtractor must produce 1D array of expected length."""
    config = SyntheticTransitConfig(
        duration_days=5.0,
        cadence_minutes=15.0,
        has_transit=False,
        seed=12
    )
    lc = generate_synthetic_light_curve(config)
    extractor = FeatureExtractor(n_phase_bins=64)
    vec = extractor.extract_phase_vector(lc)

    assert vec.shape == (64,)
    assert np.all(np.isfinite(vec))
