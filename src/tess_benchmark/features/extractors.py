"""
Feature Extraction Pipeline for Exoplanet Transit Detection.

Extracts physically meaningful astronomical, statistical, and BLS periodogram
features from photometric light curves for classical machine-learning classifiers.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scipy import stats

from ..data.protocol import LightCurveData
from ..baselines.bls import BLSDetector, BLSResult
from .folding import phase_fold, bin_folded_light_curve


FEATURE_NAMES = [
    # BLS Periodogram Features
    "bls_sde",
    "bls_snr",
    "bls_period",
    "bls_depth",
    "bls_duration",
    "bls_duty_cycle",
    "bls_max_power",
    # Statistical Distribution Features
    "flux_std",
    "flux_skewness",
    "flux_kurtosis",
    "flux_mad",
    "flux_p1",
    "flux_p5",
    "flux_iqr",
    "flux_min",
    "flux_depth_robust",
    # Dynamical & Correlated Noise Features
    "von_neumann_ratio",
    "outlier_fraction_low",
    "outlier_fraction_high",
    # Folded Transit Diagnostics (EB vs Planet tests)
    "folded_transit_depth",
    "odd_even_depth_ratio",
    "secondary_eclipse_depth",
]


def compute_von_neumann_ratio(flux: np.ndarray) -> float:
    """
    Compute Von Neumann ratio (eta) to detect serial correlation.
    
    eta = sum((flux[i+1] - flux[i])^2) / ((N-1) * var(flux))
    For pure Gaussian white noise, eta ~ 2.0.
    Values < 2 indicate positive autocorrelation (stellar variability, flares).
    """
    n = len(flux)
    if n < 4:
        return 2.0
    var = np.var(flux)
    if var <= 0:
        return 2.0
    diff_sq = np.sum(np.diff(flux) ** 2)
    return float(diff_sq / ((n - 1) * var))


def compute_odd_even_ratio(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    duration: float
) -> float:
    """
    Compute odd vs even transit depth ratio to distinguish eclipsing binaries from planets.
    """
    if period <= 0 or duration <= 0:
        return 1.0

    # Number of periods since t0
    epoch_num = np.round((time - t0) / period).astype(int)
    phase = ((time - t0 + 0.5 * period) % period) / period - 0.5
    in_transit = np.abs(phase) < (duration / (2.0 * period))

    odd_mask = in_transit & (epoch_num % 2 == 1)
    even_mask = in_transit & (epoch_num % 2 == 0)

    med_out = np.median(flux[~in_transit]) if np.any(~in_transit) else 1.0

    odd_depth = (med_out - np.median(flux[odd_mask])) if np.sum(odd_mask) > 3 else 0.0
    even_depth = (med_out - np.median(flux[even_mask])) if np.sum(even_mask) > 3 else 0.0

    if odd_depth <= 0 or even_depth <= 0:
        return 1.0

    # Closer to 1.0 means identical depth (planet candidate); deviates for EBs with primary/secondary
    return float(min(odd_depth, even_depth) / max(odd_depth, even_depth))


def compute_secondary_depth(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    duration: float
) -> float:
    """
    Compute secondary eclipse depth at phase 0.5.
    """
    if period <= 0 or duration <= 0:
        return 0.0

    phase = ((time - t0 + 0.5 * period) % period) / period - 0.5
    # Window centered at phase 0.5 (or -0.5)
    sec_mask = np.abs(np.abs(phase) - 0.5) < (duration / (2.0 * period))

    if np.sum(sec_mask) < 3:
        return 0.0

    med_out = np.median(flux[np.abs(phase) > 0.1]) if np.any(np.abs(phase) > 0.1) else 1.0
    sec_depth = max(0.0, med_out - np.median(flux[sec_mask]))
    return float(sec_depth)


class FeatureExtractor:
    """
    Extracts tabular features and phase-binned vectors from light curves.

    Parameters
    ----------
    bls_detector : Optional[BLSDetector]
        Detector instance for periodogram peak extraction.
    n_phase_bins : int
        Number of bins for 1D phase profile vector (used by 1D CNN / spectral ML).
    """

    def __init__(
        self,
        bls_detector: Optional[BLSDetector] = None,
        n_phase_bins: int = 200
    ):
        self.bls = bls_detector or BLSDetector(frequency_factor=3.0)
        self.n_phase_bins = n_phase_bins

    def extract_tabular_features(
        self,
        lc: LightCurveData,
        bls_result: Optional[BLSResult] = None
    ) -> Dict[str, float]:
        """
        Extract numerical scalar features from a light curve.

        Parameters
        ----------
        lc : LightCurveData
            Photometric light curve.
        bls_result : Optional[BLSResult]
            Precomputed BLS result if available.

        Returns
        -------
        Dict[str, float]
            Dictionary mapping feature names to extracted float values.
        """
        cleaned = lc.clean()
        time = cleaned.time
        flux = cleaned.flux

        if bls_result is None:
            bls_result = self.bls.search(cleaned)

        # 1. BLS metrics
        duty_cycle = (
            bls_result.best_duration / bls_result.best_period
            if bls_result.best_period > 0
            else 0.0
        )

        # 2. Statistical moments
        med = float(np.median(flux))
        mad = float(np.median(np.abs(flux - med)))
        std = float(np.std(flux))
        skew = float(stats.skew(flux)) if len(flux) > 5 else 0.0
        kurt = float(stats.kurtosis(flux)) if len(flux) > 5 else 0.0

        p1, p5, p25, p75, p95 = np.percentile(flux, [1, 5, 25, 75, 95])
        iqr = float(p75 - p25)
        f_min = float(np.min(flux))
        depth_robust = float(med - p1)

        # 3. Dynamics
        vn_ratio = compute_von_neumann_ratio(flux)
        sig = 1.4826 * mad if mad > 0 else (std if std > 0 else 0.001)
        outlier_low = float(np.mean(flux < (med - 3.0 * sig)))
        outlier_high = float(np.mean(flux > (med + 3.0 * sig)))

        # 4. Folded diagnostics
        odd_even = compute_odd_even_ratio(
            time, flux, bls_result.best_period, bls_result.best_t0, bls_result.best_duration
        )
        sec_depth = compute_secondary_depth(
            time, flux, bls_result.best_period, bls_result.best_t0, bls_result.best_duration
        )

        # In-transit vs out-of-transit folded depth
        if bls_result.best_period > 0:
            phase = phase_fold(time, bls_result.best_period, bls_result.best_t0)
            in_transit = np.abs(phase) < (bls_result.best_duration / (2.0 * bls_result.best_period))
            if np.any(in_transit) and np.any(~in_transit):
                folded_depth = float(np.median(flux[~in_transit]) - np.median(flux[in_transit]))
            else:
                folded_depth = float(bls_result.best_depth)
        else:
            folded_depth = 0.0

        features = {
            "bls_sde": float(np.nan_to_num(bls_result.sde, nan=0.0)),
            "bls_snr": float(np.nan_to_num(bls_result.snr, nan=0.0)),
            "bls_period": float(np.nan_to_num(bls_result.best_period, nan=0.0)),
            "bls_depth": float(np.nan_to_num(bls_result.best_depth, nan=0.0)),
            "bls_duration": float(np.nan_to_num(bls_result.best_duration, nan=0.0)),
            "bls_duty_cycle": float(np.nan_to_num(duty_cycle, nan=0.0)),
            "bls_max_power": float(np.nan_to_num(bls_result.max_power, nan=0.0)),
            "flux_std": float(np.nan_to_num(std, nan=0.0)),
            "flux_skewness": float(np.nan_to_num(skew, nan=0.0)),
            "flux_kurtosis": float(np.nan_to_num(kurt, nan=0.0)),
            "flux_mad": float(np.nan_to_num(mad, nan=0.0)),
            "flux_p1": float(np.nan_to_num(p1, nan=1.0)),
            "flux_p5": float(np.nan_to_num(p5, nan=1.0)),
            "flux_iqr": float(np.nan_to_num(iqr, nan=0.0)),
            "flux_min": float(np.nan_to_num(f_min, nan=1.0)),
            "flux_depth_robust": float(np.nan_to_num(depth_robust, nan=0.0)),
            "von_neumann_ratio": float(np.nan_to_num(vn_ratio, nan=2.0)),
            "outlier_fraction_low": float(np.nan_to_num(outlier_low, nan=0.0)),
            "outlier_fraction_high": float(np.nan_to_num(outlier_high, nan=0.0)),
            "folded_transit_depth": float(np.nan_to_num(folded_depth, nan=0.0)),
            "odd_even_depth_ratio": float(np.nan_to_num(odd_even, nan=1.0)),
            "secondary_eclipse_depth": float(np.nan_to_num(sec_depth, nan=0.0)),
        }
        return features

    def extract_phase_vector(
        self,
        lc: LightCurveData,
        bls_result: Optional[BLSResult] = None
    ) -> np.ndarray:
        """
        Extract fixed-length phase-folded binned vector for 1D CNN or sequence models.

        Parameters
        ----------
        lc : LightCurveData
            Photometric light curve.
        bls_result : Optional[BLSResult]
            Precomputed BLS result.

        Returns
        -------
        np.ndarray
            1D array of shape (n_phase_bins,).
        """
        cleaned = lc.clean()
        time = cleaned.time
        flux = cleaned.flux

        if bls_result is None:
            bls_result = self.bls.search(cleaned)

        period = bls_result.best_period if bls_result.best_period > 0 else 3.5
        t0 = bls_result.best_t0

        phase = phase_fold(time, period, t0)
        _, binned_flux, _ = bin_folded_light_curve(
            phase, flux, n_bins=self.n_phase_bins, phase_min=-0.5, phase_max=0.5
        )
        return binned_flux
