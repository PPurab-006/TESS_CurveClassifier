"""Data structures, protocol definitions, synthetic generator, and TESS loader."""
from .protocol import LightCurveData, TargetCategory
from .synthetic import (
    SyntheticTransitConfig,
    generate_synthetic_light_curve,
    trapezoidal_transit,
    sigma_clip,
    running_median_detrend,
    preprocess_light_curve,
)
from .tess_loader import TESSDataLoader
from .cohort import CandidateTarget, ValidationRecord, Stage2CohortManager

__all__ = [
    "LightCurveData",
    "TargetCategory",
    "SyntheticTransitConfig",
    "generate_synthetic_light_curve",
    "trapezoidal_transit",
    "sigma_clip",
    "running_median_detrend",
    "preprocess_light_curve",
    "TESSDataLoader",
    "CandidateTarget",
    "ValidationRecord",
    "Stage2CohortManager",
]

