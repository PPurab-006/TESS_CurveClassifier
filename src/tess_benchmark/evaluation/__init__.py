"""Evaluation metrics, star-group splitting, and robustness experiment suite."""
from .splitting import StarGroupSplitter, DataLeakageError
from .metrics import EvaluationReport, compute_metrics
from .robustness import (
    DegradationParams,
    apply_noise_degradation,
    apply_depth_scaling,
    apply_missing_gap,
    apply_cadence_dropout,
)

__all__ = [
    "StarGroupSplitter",
    "DataLeakageError",
    "EvaluationReport",
    "compute_metrics",
    "DegradationParams",
    "apply_noise_degradation",
    "apply_depth_scaling",
    "apply_missing_gap",
    "apply_cadence_dropout",
]
