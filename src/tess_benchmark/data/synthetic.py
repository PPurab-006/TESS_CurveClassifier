"""
Configurable Synthetic Light-Curve Generator and Preprocessing Pipeline.

NOTE ON SCIENTIFIC INTEGRITY:
Synthetic light curves are generated strictly for software pipeline verification,
unit testing, and controlled degradation experiments (noise sensitivity, gap robustness).
Synthetic validation does NOT substitute for or constitute empirical proof of detection
performance on genuine TESS photometric time series.
"""
from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, Any, List
import numpy as np

from .protocol import LightCurveData, TargetCategory


@dataclass
class SyntheticTransitConfig:
    """
    Configuration for synthetic light curve generation.

    Attributes
    ----------
    duration_days : float
        Total observation duration (default 27.4 days, standard TESS 1-sector baseline).
    cadence_minutes : float
        Cadence interval in minutes (default 2.0 min, standard TESS target pixel cadence).
    baseline_flux : float
        Mean baseline stellar flux (default 1.0).
    has_transit : bool
        Whether to inject a transit signal.
    period_days : float
        Orbital period in days (default 3.5).
    t0_days : float
        Time of first transit center in days (default 1.2).
    depth : float
        Fractional transit depth (delta = (R_p / R_*)^2, default 0.005 = 5000 ppm).
    duration_hours : float
        Total transit duration in hours (default 2.5 hours).
    ingress_fraction : float
        Fraction of duration spent in ingress/egress (default 0.15 for trapezoidal shape).
    noise_sigma : float
        Standard deviation of Gaussian white noise (default 0.001 = 1000 ppm).
    variability_amplitude : float
        Amplitude of slow stellar rotation/spot variability (default 0.002).
    variability_period_days : float
        Period of stellar rotation variability in days (default 7.0).
    flare_rate : float
        Cadence probability of positive flare outliers (default 0.0003).
    flare_amplitude_scale : float
        Scale factor for flare height relative to noise (default 8.0).
    include_sector_gap : bool
        Whether to simulate the ~1.2 day TESS data downlink gap around day 13-14.
    sector_gap_start : float
        Start time of downlink gap in days (default 13.2).
    sector_gap_duration : float
        Downlink gap duration in days (default 1.2).
    dropout_fraction : float
        Fraction of randomly dropped/flagged observations (default 0.02).
    seed : Optional[int]
        Reproducible random seed.
    """
    duration_days: float = 27.4
    cadence_minutes: float = 2.0
    baseline_flux: float = 1.0
    has_transit: bool = True
    period_days: float = 3.5
    t0_days: float = 1.2
    depth: float = 0.005
    duration_hours: float = 2.5
    ingress_fraction: float = 0.15
    noise_sigma: float = 0.001
    variability_amplitude: float = 0.002
    variability_period_days: float = 7.0
    flare_rate: float = 0.0003
    flare_amplitude_scale: float = 8.0
    include_sector_gap: bool = True
    sector_gap_start: float = 13.2
    sector_gap_duration: float = 1.2
    dropout_fraction: float = 0.02
    normalize_flux: bool = True
    normalization_method: str = "robust_continuum"
    calibration_uncertainty: float = 0.001
    seed: Optional[int] = None


def normalize_light_curve(
    flux: np.ndarray,
    quality_mask: Optional[np.ndarray] = None,
    method: str = "robust_continuum",
    calibration_uncertainty: float = 0.0,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, float]:
    """
    Apply unsupervised continuum normalization to a photometric flux series.

    Removes arbitrary stellar baseline flux offsets across both transit host and
    control stars without using transit labels or known transit timestamps.

    Methods
    -------
    'robust_continuum' :
        Computes the out-of-gap median continuum and applies realistic zero-point
        photometric calibration dispersion (default 1000 ppm / 0.1%), simulating
        the calibration uncertainty inherent in space-telescope aperture photometry.
        This prevents classifiers from exploiting the tiny integrated flux attenuation
        of transit dips as a class shortcut while preserving transit morphology.
    'median' :
        Divides flux by the median of valid cadences.
    'mean' :
        Divides flux by the sample mean of valid cadences.
    'none' :
        Identity pass-through (no normalization applied).

    Parameters
    ----------
    flux : np.ndarray
        Raw photometric flux values.
    quality_mask : Optional[np.ndarray]
        Boolean mask where True indicates unflagged, valid cadences.
    method : str
        Normalization strategy ('robust_continuum', 'median', 'mean', 'none').
    calibration_uncertainty : float
        Standard deviation of residual photometric zero-point calibration error.
    rng : Optional[np.random.Generator]
        Reproducible random number generator for calibration uncertainty sampling.

    Returns
    -------
    Tuple[np.ndarray, float]
        Normalized flux array and the computed continuum factor.

    Limitations
    -----------
    In genuine space mission data (e.g. TESS/Kepler), instrumental systematics such as
    pointing jitter, thermal dissipation after momentum dumps, and scattered Earthshine
    cause time-dependent baseline trends. Scalar continuum normalization is sufficient
    for stationary synthetic benchmarks but cannot replace cotrending basis vectors (CBVs)
    or spline/Gaussian-process detrending required on real spacecraft photometry.
    """
    if method == "none":
        return flux.copy(), 1.0

    mask = quality_mask if quality_mask is not None else np.ones(len(flux), dtype=bool)
    valid_flux = flux[mask]
    if len(valid_flux) == 0:
        valid_flux = flux

    if method == "mean":
        continuum = float(np.mean(valid_flux))
    elif method == "median":
        continuum = float(np.median(valid_flux))
    elif method == "robust_continuum":
        med = float(np.median(valid_flux))
        if calibration_uncertainty > 0 and rng is not None:
            cal_err = float(rng.normal(0.0, calibration_uncertainty))
            continuum = med * (1.0 + cal_err)
        else:
            continuum = med
    else:
        raise ValueError(f"Unknown normalization method: {method}")

    if continuum <= 0 or not np.isfinite(continuum):
        continuum = 1.0

    return flux / continuum, continuum


def trapezoidal_transit(
    time: np.ndarray,
    period: float,
    t0: float,
    depth: float,
    duration_days: float,
    ingress_fraction: float = 0.15
) -> np.ndarray:
    """
    Compute a periodic trapezoidal transit dip time series.

    Parameters
    ----------
    time : np.ndarray
        Observation timestamps in days.
    period : float
        Orbital period in days.
    t0 : float
        Center epoch of transit in days.
    depth : float
        Fractional transit depth (dip amplitude).
    duration_days : float
        Full transit duration in days.
    ingress_fraction : float
        Fraction of duration spent in ingress (and egress).

    Returns
    -------
    np.ndarray
        Array of fractional flux variations (0 outside transit, -depth during flat bottom).
    """
    t_ing = duration_days * ingress_fraction
    t_flat = duration_days * (1.0 - 2.0 * ingress_fraction)

    # Fold time into [-period/2, period/2) around t0
    phase_dt = ((time - t0 + period / 2.0) % period) - (period / 2.0)
    abs_dt = np.abs(phase_dt)

    dip = np.zeros_like(time, dtype=float)

    # Full transit mask
    in_transit = abs_dt < (duration_days / 2.0)
    # Flat bottom mask
    in_flat = abs_dt <= (t_flat / 2.0)
    # Ingress/egress transition mask
    in_slope = in_transit & (~in_flat)

    dip[in_flat] = -depth

    if np.any(in_slope) and t_ing > 0:
        slope_factor = 1.0 - (abs_dt[in_slope] - (t_flat / 2.0)) / t_ing
        dip[in_slope] = -depth * np.clip(slope_factor, 0.0, 1.0)

    return dip


def generate_synthetic_light_curve(
    config: SyntheticTransitConfig,
    target_id: str = "SYNTH-0001"
) -> LightCurveData:
    """
    Generate a synthetic light curve matching the specified configuration.

    Parameters
    ----------
    config : SyntheticTransitConfig
        Configuration options.
    target_id : str
        Target identifier.

    Returns
    -------
    LightCurveData
        Standardized light curve object.
    """
    rng = np.random.default_rng(config.seed)

    cadence_days = config.cadence_minutes / (24.0 * 60.0)
    time = np.arange(0.0, config.duration_days, cadence_days)
    n_points = len(time)

    # 1. Baseline stellar flux
    flux = np.full(n_points, config.baseline_flux, dtype=float)

    # 2. Slow stellar variability (quasi-periodic sinusoidal modulation)
    if config.variability_amplitude > 0 and config.variability_period_days > 0:
        phase = 2.0 * np.pi * time / config.variability_period_days
        # Add primary harmonic and small secondary harmonic for asymmetry
        variability = config.variability_amplitude * (
            np.sin(phase) + 0.25 * np.cos(2.0 * phase)
        )
        flux += variability

    # 3. Planetary transit signal
    duration_days = config.duration_hours / 24.0
    if config.has_transit and config.depth > 0:
        transit_dip = trapezoidal_transit(
            time=time,
            period=config.period_days,
            t0=config.t0_days,
            depth=config.depth,
            duration_days=duration_days,
            ingress_fraction=config.ingress_fraction
        )
        flux += transit_dip

    # 4. Flares and cosmic ray outliers
    if config.flare_rate > 0:
        flare_mask = rng.random(n_points) < config.flare_rate
        n_flares = int(np.sum(flare_mask))
        if n_flares > 0:
            flare_heights = rng.exponential(
                scale=config.flare_amplitude_scale * config.noise_sigma,
                size=n_flares
            )
            flux[flare_mask] += flare_heights

    # 5. Gaussian white noise
    noise = rng.normal(loc=0.0, scale=config.noise_sigma, size=n_points)
    flux += noise
    flux_err = np.full(n_points, config.noise_sigma, dtype=float)

    # 6. Quality flags & Data gaps
    quality_mask = np.ones(n_points, dtype=bool)

    # Sector transmission gap
    if config.include_sector_gap:
        gap_mask = (time >= config.sector_gap_start) & (
            time <= (config.sector_gap_start + config.sector_gap_duration)
        )
        quality_mask[gap_mask] = False

    # Random dropouts
    if config.dropout_fraction > 0:
        dropout_mask = rng.random(n_points) < config.dropout_fraction
        quality_mask[dropout_mask] = False

    # 7. Unsupervised baseline continuum normalization
    continuum_factor = 1.0
    if config.normalize_flux and config.normalization_method != "none":
        flux, continuum_factor = normalize_light_curve(
            flux=flux,
            quality_mask=quality_mask,
            method=config.normalization_method,
            calibration_uncertainty=config.calibration_uncertainty,
            rng=rng,
        )
        flux_err = flux_err / continuum_factor

    metadata: Dict[str, Any] = {
        "duration_days": config.duration_days,
        "cadence_minutes": config.cadence_minutes,
        "period_days": config.period_days if config.has_transit else None,
        "t0_days": config.t0_days if config.has_transit else None,
        "depth": config.depth if config.has_transit else 0.0,
        "duration_hours": config.duration_hours if config.has_transit else 0.0,
        "noise_sigma": config.noise_sigma,
        "snr_analytic": (
            (config.depth / config.noise_sigma) * np.sqrt((config.duration_hours / 24.0) / cadence_days * (config.duration_days / config.period_days))
            if config.has_transit and config.noise_sigma > 0 else 0.0
        ),
        "synthetic": True,
        "seed": config.seed,
        "baseline_flux_raw": config.baseline_flux,
        "continuum_factor": continuum_factor,
        "normalization_method": config.normalization_method if config.normalize_flux else "none",
    }

    category = (
        TargetCategory.SYNTHETIC_INJECTION
        if config.has_transit
        else TargetCategory.CONTROL_STAR
    )

    return LightCurveData(
        time=time,
        flux=flux,
        flux_err=flux_err,
        target_id=target_id,
        category=category,
        has_transit=config.has_transit,
        metadata=metadata,
        quality_mask=quality_mask
    )


def sigma_clip(
    flux: np.ndarray,
    low_sigma: float = 5.0,
    high_sigma: float = 3.0,
    max_iters: int = 3
) -> np.ndarray:
    """
    Iterative asymmetric sigma clipping to remove high outliers (flares/cosmic rays)
    while preserving real shallow transit dips.

    Parameters
    ----------
    flux : np.ndarray
        Input flux values.
    low_sigma : float
        Sigma threshold for negative deviations (transit dips: set high to preserve dips).
    high_sigma : float
        Sigma threshold for positive deviations (flares: set lower to remove).
    max_iters : int
        Maximum clipping iterations.

    Returns
    -------
    np.ndarray
        Boolean mask where True denotes kept points.
    """
    mask = np.ones(len(flux), dtype=bool)
    for _ in range(max_iters):
        valid = flux[mask]
        if len(valid) == 0:
            break
        med = np.median(valid)
        mad = np.median(np.abs(valid - med))
        std_est = 1.4826 * mad
        if std_est == 0:
            std_est = np.std(valid)
        if std_est == 0:
            break

        new_mask = mask.copy()
        new_mask[mask] = (
            (flux[mask] >= med - low_sigma * std_est) &
            (flux[mask] <= med + high_sigma * std_est)
        )
        if np.array_equal(new_mask, mask):
            break
        mask = new_mask
    return mask


def running_median_detrend(
    time: np.ndarray,
    flux: np.ndarray,
    window_days: float = 0.5
) -> np.ndarray:
    """
    Robust running median filter for stellar variability detrending.

    Parameters
    ----------
    time : np.ndarray
        Time array in days.
    flux : np.ndarray
        Flux values.
    window_days : float
        Time window in days for running median filter.

    Returns
    -------
    np.ndarray
        Detrended, normalized flux (flux / trend).
    """
    n = len(time)
    trend = np.empty(n, dtype=float)
    half_win = window_days / 2.0

    for i in range(n):
        t_cur = time[i]
        window_mask = (time >= t_cur - half_win) & (time <= t_cur + half_win)
        trend[i] = np.median(flux[window_mask])

    # Avoid zero division
    trend = np.where(trend <= 0, 1.0, trend)
    return flux / trend


def preprocess_light_curve(
    lc: LightCurveData,
    clip_outliers: bool = True,
    detrend: bool = True,
    detrend_window_days: float = 0.5
) -> LightCurveData:
    """
    End-to-end preprocessing pipeline for astronomical light curves.
    
    Steps:
    1. Filter out invalid/flagged cadences.
    2. Optional asymmetric sigma clipping (removes positive flare spikes).
    3. Running median detrending to eliminate smooth stellar activity.
    4. Re-normalization.

    Parameters
    ----------
    lc : LightCurveData
        Input raw light curve.
    clip_outliers : bool
        Whether to perform flare/outlier rejection.
    detrend : bool
        Whether to detrend stellar variability.
    detrend_window_days : float
        Filter window in days for detrending.

    Returns
    -------
    LightCurveData
        Preprocessed clean light curve.
    """
    cleaned = lc.clean()
    if len(cleaned.time) == 0:
        return cleaned

    time = cleaned.time
    flux = cleaned.flux
    flux_err = cleaned.flux_err

    if clip_outliers:
        keep_mask = sigma_clip(flux, low_sigma=6.0, high_sigma=3.5)
        time = time[keep_mask]
        flux = flux[keep_mask]
        flux_err = flux_err[keep_mask]

    if detrend and len(time) > 10:
        detrended_flux = running_median_detrend(time, flux, window_days=detrend_window_days)
        # Normalize relative to median
        med = np.median(detrended_flux)
        if med > 0:
            detrended_flux /= med
            flux_err = flux_err / med
        flux = detrended_flux

    return LightCurveData(
        time=time,
        flux=flux,
        flux_err=flux_err,
        target_id=cleaned.target_id,
        category=cleaned.category,
        has_transit=cleaned.has_transit,
        metadata=dict(cleaned.metadata),
        quality_mask=np.ones(len(time), dtype=bool)
    )
