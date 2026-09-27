"""
Tests for TESS data loader interfaces and protocol invariants.
"""
from pathlib import Path
import numpy as np
import pytest
from tess_benchmark.data.protocol import LightCurveData, TargetCategory
from tess_benchmark.data.tess_loader import TESSDataLoader


def test_light_curve_data_invariants():
    """LightCurveData must reject mismatched array lengths."""
    time = np.array([1.0, 2.0, 3.0])
    flux = np.array([1.0, 0.99])
    flux_err = np.array([0.01, 0.01, 0.01])

    with pytest.raises(ValueError):
        LightCurveData(
            time=time,
            flux=flux,
            flux_err=flux_err,
            target_id="TEST",
            category=TargetCategory.TOI_CANDIDATE,
            has_transit=True
        )


def test_tess_data_loader_initialization(tmp_path: Path):
    """TESSDataLoader must initialize with a custom cache directory."""
    loader = TESSDataLoader(cache_dir=tmp_path / "raw")
    assert loader.cache_dir.exists()
