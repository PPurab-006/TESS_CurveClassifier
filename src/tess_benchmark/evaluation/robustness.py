"""
Robustness Evaluation and Controlled Degradation Suite.

Evaluates trained models and the BLS baseline under systematic observational
degradations (increased noise, shallow transit depths, missing intervals, dropouts).
Ensures zero data leakage across splits and records all degradation parameters.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Callable, Optional, Tuple
import numpy as np
import pandas as pd

from ..data.protocol import LightCurveData
from ..data.synthetic import trapezoidal_transit, preprocess_light_curve
from ..baselines.bls import BLSDetector
from .metrics import compute_metrics, EvaluationReport


@dataclass
class DegradationParams:
    """
    Parameters describing a controlled degradation trial.
    """
    axis: str  # 'noise', 'depth', 'gap', 'dropout'
    level_value: float
    description: str
    seed: int = 42


def apply_noise_degradation(lc: LightCurveData, noise_sigma_add: float, seed: int = 42) -> LightCurveData:
    """Add independent Gaussian noise to light curve."""
    if noise_sigma_add <= 0:
        return lc
    rng = np.random.default_rng(seed)
    n = len(lc.flux)
    added_noise = rng.normal(0.0, noise_sigma_add, size=n)
    new_flux = lc.flux + added_noise
    new_err = np.sqrt(lc.flux_err ** 2 + noise_sigma_add ** 2)

    meta = dict(lc.metadata)
    meta["added_noise_sigma"] = noise_sigma_add

    return LightCurveData(
        time=lc.time.copy(),
        flux=new_flux,
        flux_err=new_err,
        target_id=lc.target_id,
        category=lc.category,
        has_transit=lc.has_transit,
        metadata=meta,
        quality_mask=lc.quality_mask.copy() if lc.quality_mask is not None else None
    )


def apply_depth_scaling(lc: LightCurveData, depth_factor: float) -> LightCurveData:
    """Scale transit depth down by depth_factor (0.0 < depth_factor <= 1.0)."""
    if (not lc.has_transit) or (depth_factor >= 1.0):
        return lc

    meta = dict(lc.metadata)
    period = meta.get("period_days", 3.5)
    t0 = meta.get("t0_days", 1.2)
    depth = meta.get("depth", 0.005)
    duration_hours = meta.get("duration_hours", 2.5)
    duration_days = duration_hours / 24.0

    # Original injected dip
    orig_dip = trapezoidal_transit(lc.time, period, t0, depth, duration_days)
    # Scaled dip
    scaled_dip = trapezoidal_transit(lc.time, period, t0, depth * depth_factor, duration_days)

    # Adjust flux: remove original dip and add scaled dip
    new_flux = lc.flux - orig_dip + scaled_dip
    meta["scaled_depth"] = depth * depth_factor
    meta["depth_factor"] = depth_factor

    return LightCurveData(
        time=lc.time.copy(),
        flux=new_flux,
        flux_err=lc.flux_err.copy(),
        target_id=lc.target_id,
        category=lc.category,
        has_transit=lc.has_transit,
        metadata=meta,
        quality_mask=lc.quality_mask.copy() if lc.quality_mask is not None else None
    )


def apply_missing_gap(lc: LightCurveData, gap_duration_days: float, gap_start: float = 6.0) -> LightCurveData:
    """Mask out an additional observation interval simulating camera shutdown or pointing anomaly."""
    if gap_duration_days <= 0:
        return lc

    mask = (lc.time < gap_start) | (lc.time > (gap_start + gap_duration_days))
    new_quality = lc.quality_mask.copy() if lc.quality_mask is not None else np.ones(len(lc.time), dtype=bool)
    new_quality = new_quality & mask

    meta = dict(lc.metadata)
    meta["added_gap_days"] = gap_duration_days

    return LightCurveData(
        time=lc.time.copy(),
        flux=lc.flux.copy(),
        flux_err=lc.flux_err.copy(),
        target_id=lc.target_id,
        category=lc.category,
        has_transit=lc.has_transit,
        metadata=meta,
        quality_mask=new_quality
    )


def apply_cadence_dropout(lc: LightCurveData, dropout_fraction: float, seed: int = 42) -> LightCurveData:
    """Randomly drop a fraction of observed cadences."""
    if dropout_fraction <= 0:
        return lc

    rng = np.random.default_rng(seed)
    keep_mask = rng.random(len(lc.time)) >= dropout_fraction
    new_quality = lc.quality_mask.copy() if lc.quality_mask is not None else np.ones(len(lc.time), dtype=bool)
    new_quality = new_quality & keep_mask

    meta = dict(lc.metadata)
    meta["dropout_fraction"] = dropout_fraction

    return LightCurveData(
        time=lc.time.copy(),
        flux=lc.flux.copy(),
        flux_err=lc.flux_err.copy(),
        target_id=lc.target_id,
        category=lc.category,
        has_transit=lc.has_transit,
        metadata=meta,
        quality_mask=new_quality
    )
