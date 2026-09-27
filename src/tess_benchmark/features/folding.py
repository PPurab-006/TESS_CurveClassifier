"""
Phase-folding and phase-binning utilities for astronomical light curves.
"""
from typing import Tuple
import numpy as np


def phase_fold(time: np.ndarray, period: float, t0: float) -> np.ndarray:
    """
    Phase fold observation timestamps into [-0.5, 0.5) centered on transit epoch t0.

    Parameters
    ----------
    time : np.ndarray
        Observation timestamps.
    period : float
        Orbital period in same units as time.
    t0 : float
        Transit center epoch in same units as time.

    Returns
    -------
    np.ndarray
        Phase array in [-0.5, 0.5).
    """
    phase = ((time - t0 + 0.5 * period) % period) / period - 0.5
    return phase


def bin_folded_light_curve(
    phase: np.ndarray,
    flux: np.ndarray,
    n_bins: int = 200,
    statistic: str = "median",
    phase_min: float = -0.5,
    phase_max: float = 0.5
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Bin phase-folded flux into equally spaced phase intervals.

    Parameters
    ----------
    phase : np.ndarray
        Phases of observations in [phase_min, phase_max].
    flux : np.ndarray
        Corresponding flux values.
    n_bins : int
        Number of output phase bins.
    statistic : str
        Aggregation statistic ('median' or 'mean').
    phase_min : float
        Minimum phase edge.
    phase_max : float
        Maximum phase edge.

    Returns
    -------
    Tuple[np.ndarray, np.ndarray, np.ndarray]
        (bin_centers, binned_flux, binned_flux_err)
    """
    bin_edges = np.linspace(phase_min, phase_max, n_bins + 1)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    binned_flux = np.full(n_bins, np.nan, dtype=float)
    binned_flux_err = np.full(n_bins, np.nan, dtype=float)

    # Digitize phase points
    bin_idx = np.digitize(phase, bin_edges) - 1

    for i in range(n_bins):
        mask = (bin_idx == i)
        if np.any(mask):
            pts = flux[mask]
            pts_valid = pts[np.isfinite(pts)]
            if len(pts_valid) > 0:
                if statistic == "median":
                    binned_flux[i] = np.median(pts_valid)
                    mad = np.median(np.abs(pts_valid - binned_flux[i]))
                    binned_flux_err[i] = 1.4826 * mad / np.sqrt(len(pts_valid))
                else:
                    binned_flux[i] = np.mean(pts_valid)
                    binned_flux_err[i] = np.std(pts_valid) / np.sqrt(len(pts_valid))

    # Fill empty bins using linear interpolation from valid neighbors
    valid_mask = np.isfinite(binned_flux)
    if np.any(valid_mask):
        binned_flux = np.interp(bin_centers, bin_centers[valid_mask], binned_flux[valid_mask])
        binned_flux_err = np.nan_to_num(binned_flux_err, nan=float(np.nanmedian(binned_flux_err[valid_mask])))
    else:
        binned_flux.fill(1.0)
        binned_flux_err.fill(0.001)

    return bin_centers, binned_flux, binned_flux_err


def extract_phase_views(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    duration_days: float,
    n_global: int = 200,
    n_local: int = 60
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract global and local phase-folded views (as used in modern exoplanet CNN vetting).

    Parameters
    ----------
    time : np.ndarray
        Observation times.
    flux : np.ndarray
        Normalized flux.
    period : float
        Period in days.
    t0 : float
        Transit epoch in days.
    duration_days : float
        Transit duration in days.
    n_global : int
        Number of bins for full orbital phase [-0.5, 0.5).
    n_local : int
        Number of bins for zoomed-in transit window.

    Returns
    -------
    Tuple[np.ndarray, np.ndarray]
        (global_view_flux, local_view_flux)
    """
    phase = phase_fold(time, period, t0)

    # Global view: full phase
    _, global_flux, _ = bin_folded_light_curve(phase, flux, n_bins=n_global, phase_min=-0.5, phase_max=0.5)

    # Local view: zoom window around phase 0 (e.g. +/- 2 * transit duration)
    local_phase_width = max(0.01, min(0.4, 2.0 * duration_days / period))
    local_mask = np.abs(phase) <= local_phase_width

    if np.sum(local_mask) >= 5:
        _, local_flux, _ = bin_folded_light_curve(
            phase[local_mask],
            flux[local_mask],
            n_bins=n_local,
            phase_min=-local_phase_width,
            phase_max=local_phase_width
        )
    else:
        # Fallback if sparse observations in window
        local_flux = np.ones(n_local, dtype=float)

    return global_flux, local_flux
