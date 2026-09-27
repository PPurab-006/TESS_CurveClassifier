"""
Scientific Data Protocol and Provenance Specifications.

Defines target classification categories, metadata standards, and data integrity
invariants for the TESS Transit Detection Benchmark.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import numpy as np


class TargetCategory(str, Enum):
    """
    Astronomical classification category for stellar targets in benchmark.
    
    CRITICAL SCIENTIFIC INTEGRITY INVARIANT:
    Stars without known planetary detections MUST NOT be labeled as "confirmed negatives".
    They represent observational control stars where no transits have been detected
    above historical detection limits, but low-amplitude or long-period planets may still exist.
    """
    CONFIRMED_PLANET_HOST = "confirmed_planet_host"
    TOI_CANDIDATE = "toi_candidate"
    FALSE_POSITIVE = "false_positive"  # e.g., eclipsing binary (EB), background EB (BEB)
    CONTROL_STAR = "control_star"       # Field star without detected transits (unconfirmed negative)
    SYNTHETIC_INJECTION = "synthetic_injection"  # Explicitly injected synthetic transit


@dataclass
class LightCurveData:
    """
    Standard in-memory representation of a photometric light curve.

    Attributes
    ----------
    time : np.ndarray
        Time series array (typically Barycentric TESS Julian Date, BTJD = BJD - 2457000).
    flux : np.ndarray
        Normalized stellar flux.
    flux_err : np.ndarray
        Uncertainty / standard error of the flux measurements.
    target_id : str
        Unique identifier for the star (e.g. "TIC-12345678" or "SYNTH-0001").
    category : TargetCategory
        Astronomical provenance category.
    has_transit : bool
        Binary ground-truth label (True if transit signal is present, False otherwise).
    metadata : Dict[str, Any]
        Observational metadata (e.g., sector, cadence_sec, ground-truth period, depth).
    quality_mask : Optional[np.ndarray]
        Boolean mask of valid points (True = good quality cadence).
    """
    time: np.ndarray
    flux: np.ndarray
    flux_err: np.ndarray
    target_id: str
    category: TargetCategory
    has_transit: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    quality_mask: Optional[np.ndarray] = None

    def __post_init__(self):
        if not (len(self.time) == len(self.flux) == len(self.flux_err)):
            raise ValueError(
                f"Array length mismatch: time ({len(self.time)}), "
                f"flux ({len(self.flux)}), flux_err ({len(self.flux_err)}) must match."
            )
        if self.quality_mask is not None and len(self.quality_mask) != len(self.time):
            raise ValueError("quality_mask length must match time array length.")

    @property
    def valid_indices(self) -> np.ndarray:
        """Return boolean mask of finite and non-flagged points."""
        mask = np.isfinite(self.time) & np.isfinite(self.flux) & np.isfinite(self.flux_err)
        if self.quality_mask is not None:
            mask = mask & self.quality_mask
        return mask

    def clean(self) -> "LightCurveData":
        """Return a copy containing only valid, finite cadences."""
        mask = self.valid_indices
        return LightCurveData(
            time=self.time[mask].copy(),
            flux=self.flux[mask].copy(),
            flux_err=self.flux_err[mask].copy(),
            target_id=self.target_id,
            category=self.category,
            has_transit=self.has_transit,
            metadata=dict(self.metadata),
            quality_mask=np.ones(np.sum(mask), dtype=bool)
        )
