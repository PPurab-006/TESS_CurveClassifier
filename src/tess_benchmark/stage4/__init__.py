"""
Stage 4 Candidate Vetting Package.

Implements transit-specific candidate vetting modules:
- Deterministic 52-feature extraction pipeline (22 baseline + 30 morphology/context features)
- Realistic synthetic candidate discovery pipeline (LC -> BLS -> Candidate -> Features)
- Leakage-resistant CandidateVetter with deterministic decision-threshold calibration
"""

from .features import (
    BASELINE_FEATURE_NAMES,
    STAGE4_NEW_FEATURE_NAMES,
    STAGE4_FEATURE_GROUPS,
    STAGE4_FEATURE_NAMES,
    TransitCandidateFeatures,
    extract_all_candidate_features,
)
from .synthetic_generator import (
    SyntheticCandidateConfig,
    SyntheticCandidateInstance,
    generate_synthetic_candidate_dataset,
)
from .vetter import (
    CandidateVetter,
    ThresholdCalibrationResult,
    train_and_calibrate_candidate_vetter,
)

__all__ = [
    "BASELINE_FEATURE_NAMES",
    "STAGE4_NEW_FEATURE_NAMES",
    "STAGE4_FEATURE_GROUPS",
    "STAGE4_FEATURE_NAMES",
    "TransitCandidateFeatures",
    "extract_all_candidate_features",
    "SyntheticCandidateConfig",
    "SyntheticCandidateInstance",
    "generate_synthetic_candidate_dataset",
    "CandidateVetter",
    "ThresholdCalibrationResult",
    "train_and_calibrate_candidate_vetter",
]
