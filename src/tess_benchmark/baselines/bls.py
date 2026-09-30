"""
Classical Box Least Squares (BLS) Transit Detection Baseline.

Wraps Astropy's BoxLeastSquares algorithm with scientific detection criteria,
Signal Detection Efficiency (SDE), SNR estimation, harmonic checks, and runtime benchmarking.
"""
import math
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple, Sequence
import numpy as np
from astropy.timeseries import BoxLeastSquares

from ..data.protocol import LightCurveData


@dataclass
class BLSResult:
    """
    Structured outcome of a Box Least Squares periodogram search.

    Attributes
    ----------
    best_period : float
        Period corresponding to the maximum BLS power peak in days.
    best_t0 : float
        Transit center epoch in days.
    best_duration : float
        Transit duration in days.
    best_depth : float
        Transit depth (fractional flux decrease).
    max_power : float
        Maximum BLS objective function power.
    mean_power : float
        Mean power across the searched frequency spectrum.
    std_power : float
        Standard deviation of power across the searched frequency spectrum.
    sde : float
        Signal Detection Efficiency = (max_power - mean_power) / std_power.
    snr : float
        Estimated signal-to-noise ratio of detected transit.
    is_detected : bool
        Whether the signal passes the detection criteria threshold.
    runtime_sec : float
        Wall-clock search runtime in seconds.
    metadata : Dict[str, Any]
        Additional search metadata and configuration parameters.
    """
    best_period: float
    best_t0: float
    best_duration: float
    best_depth: float
    max_power: float
    mean_power: float
    std_power: float
    sde: float
    snr: float
    is_detected: bool
    runtime_sec: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_period_recovered(
        self,
        true_period: float,
        tolerance: float = 0.01,
        accepted_ratios: Optional[Sequence[float]] = None
    ) -> bool:
        """
        Check if the detected period matches the true period or its common harmonics.

        Parameters
        ----------
        true_period : float
            Ground-truth period.
        tolerance : float
            Fractional tolerance threshold (default 0.01 = 1.0%, approved under GATE-01).
        accepted_ratios : Optional[Sequence[float]]
            Candidate harmonic ratios to test. Defaults to approved GATE-04 Option B narrow set: (0.5, 1.0, 2.0).
            Exploratory sets (such as Option A: [1/3, 0.5, 1.0, 2.0, 3.0]) can be explicitly passed.

        Returns
        -------
        bool
            True if recovered at fundamental or any accepted harmonic / subharmonic.
        """
        if accepted_ratios is None:
            ratios = (0.5, 1.0, 2.0)
        else:
            ratios = accepted_ratios

        is_recovered, _, _ = match_period_to_harmonics(
            detected_period=self.best_period,
            catalog_period=true_period,
            accepted_ratios=ratios,
            tolerance=tolerance
        )
        return is_recovered


def match_period_to_harmonics(
    detected_period: float,
    catalog_period: float,
    accepted_ratios: Sequence[float] = (0.5, 1.0, 2.0),
    tolerance: float = 0.01
) -> Tuple[bool, Optional[float], float]:
    """
    Evaluate whether a detected period matches a catalog period under a set of accepted ratios.

    Parameters
    ----------
    detected_period : float
        Period detected by the algorithm in days.
    catalog_period : float
        Ground-truth catalog period in days.
    accepted_ratios : Sequence[float]
        Candidate harmonic multipliers to test against. Defaults to approved GATE-04 Option B
        narrow set: (0.5, 1.0, 2.0). Broad exploratory sets can be passed explicitly.
    tolerance : float
        Fractional tolerance threshold (approved 0.01 = 1.0% under GATE-01).

    Returns
    -------
    Tuple[bool, Optional[float], float]
        (is_recovered, nearest_ratio, min_relative_error)
        - is_recovered: True if min_relative_error <= tolerance (with machine-precision allowance).
        - nearest_ratio: The accepted ratio yielding the lowest relative error, or None if invalid.
        - min_relative_error: abs(detected_period - ratio * catalog_period) / (ratio * catalog_period).
    """
    if (not np.isfinite(detected_period) or not np.isfinite(catalog_period) or
            detected_period <= 0 or catalog_period <= 0 or tolerance < 0 or
            not accepted_ratios):
        return False, None, float("nan")

    # Narrowly bounded machine-precision allowance (100 ULPs ~ 1.7e-16 for tol=0.01)
    # to ensure exact mathematical boundaries (P_true * (1 +/- tol)) are robust
    # against IEEE 754 binary floating-point representation artifacts.
    effective_tol = tolerance + 100 * math.ulp(tolerance) if tolerance > 0 else tolerance

    best_ratio = None
    min_rel_err = float("inf")

    for ratio in accepted_ratios:
        if ratio <= 0 or not np.isfinite(ratio):
            continue
        target = catalog_period * ratio
        rel_err = abs(detected_period - target) / target
        if rel_err < min_rel_err:
            min_rel_err = rel_err
            best_ratio = ratio

    if best_ratio is None:
        return False, None, float("nan")

    is_recovered = (min_rel_err <= effective_tol)
    return is_recovered, best_ratio, min_rel_err


class BLSDetector:
    """
    Standardized Box Least Squares detector for exoplanetary transits.

    Parameters
    ----------
    min_period : float
        Minimum search period in days (default 0.5 days).
    max_period : float
        Maximum search period in days (default 15.0 days).
    duration_grid : Optional[np.ndarray]
        Grid of test transit durations in days.
    frequency_factor : float
        Oversampling parameter for the periodogram frequency grid (default 5.0).
    sde_threshold : float
        Signal Detection Efficiency threshold for claiming a transit detection (default 6.0).
    min_snr : float
        Minimum transit signal-to-noise ratio (default 5.0).
    """

    def __init__(
        self,
        min_period: float = 0.5,
        max_period: float = 15.0,
        duration_grid: Optional[np.ndarray] = None,
        frequency_factor: float = 5.0,
        sde_threshold: float = 6.0,
        min_snr: float = 5.0
    ):
        self.min_period = min_period
        self.max_period = max_period
        if duration_grid is None:
            # Durations from ~1 hour to ~8 hours (in days)
            self.duration_grid = np.linspace(0.04, 0.35, 8)
        else:
            self.duration_grid = np.asarray(duration_grid, dtype=float)
        self.frequency_factor = frequency_factor
        self.sde_threshold = sde_threshold
        self.min_snr = min_snr

    def search(self, lc: LightCurveData) -> BLSResult:
        """
        Execute BLS transit search on a light curve.

        Parameters
        ----------
        lc : LightCurveData
            Cleaned and normalized photometric time series.

        Returns
        -------
        BLSResult
            Detailed search results and detection verdict.
        """
        t_start = time.perf_counter()

        cleaned = lc.clean()
        time_arr = cleaned.time
        flux_arr = cleaned.flux
        err_arr = cleaned.flux_err

        if len(time_arr) < 50:
            runtime = time.perf_counter() - t_start
            return BLSResult(
                best_period=0.0,
                best_t0=0.0,
                best_duration=0.0,
                best_depth=0.0,
                max_power=0.0,
                mean_power=0.0,
                std_power=1.0,
                sde=0.0,
                snr=0.0,
                is_detected=False,
                runtime_sec=runtime,
                metadata={"error": "Insufficient valid observations"}
            )

        # Baseline astropy BoxLeastSquares model
        model = BoxLeastSquares(time_arr, flux_arr, dy=err_arr)

        # Compute periodogram
        periodogram = model.autopower(
            duration=self.duration_grid,
            minimum_period=self.min_period,
            maximum_period=min(self.max_period, (time_arr[-1] - time_arr[0]) * 0.95),
            frequency_factor=self.frequency_factor
        )

        power = periodogram.power
        periods = periodogram.period

        # Find peak
        best_idx = np.argmax(power)
        max_pow = float(power[best_idx])
        mean_pow = float(np.mean(power))
        std_pow = float(np.std(power))
        sde = (max_pow - mean_pow) / std_pow if std_pow > 0 else 0.0

        best_period = float(periods[best_idx])
        best_duration = float(periodogram.duration[best_idx])
        best_t0 = float(periodogram.transit_time[best_idx])
        best_depth = float(periodogram.depth[best_idx])

        # Compute transit SNR
        # SNR ~ depth / (noise / sqrt(N_in_transit))
        phase = ((time_arr - best_t0 + 0.5 * best_period) % best_period) / best_period - 0.5
        phase_in_transit = np.abs(phase) < (best_duration / (2.0 * best_period))
        n_in = int(np.sum(phase_in_transit))
        if n_in > 0:
            typical_noise = np.median(err_arr)
            if typical_noise <= 0:
                typical_noise = np.std(flux_arr)
            snr = (best_depth * np.sqrt(n_in)) / typical_noise if typical_noise > 0 else 0.0
        else:
            snr = 0.0

        is_detected = bool((sde >= self.sde_threshold) and (snr >= self.min_snr) and (best_depth > 0))
        runtime = time.perf_counter() - t_start

        return BLSResult(
            best_period=best_period,
            best_t0=best_t0,
            best_duration=best_duration,
            best_depth=best_depth,
            max_power=max_pow,
            mean_power=mean_pow,
            std_power=std_pow,
            sde=float(sde),
            snr=float(snr),
            is_detected=is_detected,
            runtime_sec=float(runtime),
            metadata={
                "n_cadences": len(time_arr),
                "n_in_transit": n_in,
                "target_id": lc.target_id
            }
        )
