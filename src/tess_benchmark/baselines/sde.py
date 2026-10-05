"""
Periodogram Signal Detection Efficiency (SDE) and Background Estimation Module.

Implements approved GATE-11 SDE background estimation distributions:
- Option A: All finite valid frequency bins unclipped (parametric mean and std).
            Approved baseline for Stage 1 feasibility.
- Option B: Fundamental peak-excluded (E_0 = [f_0 - 3*df, f_0 + 3*df]) robust normalized MAD.
- Option C: Composite alias union mask E = E_0 U (U_h E_h) U (U_s E_s) robust normalized MAD.
            Approved candidate for Stage 2/3 production, conditional on Experiment 2.
- Option D: Iterative 3-sigma clipped parametric mean and std.

Strictly decouples physical transit SNR (photometric depth / photometric noise)
from spectral SDE (peak prominence / periodogram noise floor).
"""
import math
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Sequence
import numpy as np


@dataclass
class SDEResult:
    """
    Structured outcome of periodogram background estimation and SDE computation.

    Attributes
    ----------
    sde : float
        Signal Detection Efficiency = (P_max - background_mean) / background_dispersion.
    max_power : float
        Global maximum periodogram objective function power.
    background_mean : float
        Estimated central location (mean or median) of the spectral noise floor.
    background_dispersion : float
        Estimated dispersion (std or normalized MAD: 1.4826 * MAD) of spectral noise.
    method : str
        Method identifier ('option_a', 'option_b', 'option_c', 'option_d').
    peak_frequency : float
        Frequency of maximum power peak (1 / days).
    peak_period : float
        Period corresponding to peak frequency (days).
    df : float
        Frequency grid spacing (1 / days).
    n_total_bins : int
        Total number of frequency bins in the periodogram.
    n_valid_bins : int
        Number of finite, positive power bins prior to masking.
    n_unmasked_bins : int
        Number of power bins surviving after alias/peak exclusion masking.
    n_masked_bins : int
        Number of bins excluded by the mask (n_valid_bins - n_unmasked_bins).
    mask_fraction : float
        Fraction of valid bins excluded by the mask.
    sde_degenerate : bool
        True if valid unmasked bins < 50 or SDE cannot be calculated reliably.
    mad_zero : bool
        True if MAD or dispersion is zero or near-zero (< 1e-12).
    exclusion_intervals : List[Tuple[float, float]]
        List of (f_low, f_high) frequency intervals excluded.
    metadata : Dict[str, Any]
        Additional diagnostics and parameters.
    """
    sde: float
    max_power: float
    background_mean: float
    background_dispersion: float
    method: str
    peak_frequency: float
    peak_period: float
    df: float
    n_total_bins: int
    n_valid_bins: int
    n_unmasked_bins: int
    n_masked_bins: int
    mask_fraction: float
    sde_degenerate: bool
    mad_zero: bool
    exclusion_intervals: List[Tuple[float, float]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert SDE result to dictionary."""
        d = {
            "sde": self.sde,
            "max_power": self.max_power,
            "background_mean": self.background_mean,
            "background_dispersion": self.background_dispersion,
            "method": self.method,
            "peak_frequency": self.peak_frequency,
            "peak_period": self.peak_period,
            "df": self.df,
            "n_total_bins": self.n_total_bins,
            "n_valid_bins": self.n_valid_bins,
            "n_unmasked_bins": self.n_unmasked_bins,
            "n_masked_bins": self.n_masked_bins,
            "mask_fraction": self.mask_fraction,
            "sde_degenerate": self.sde_degenerate,
            "mad_zero": self.mad_zero,
            "metadata": self.metadata,
        }
        return d


def compute_sde(
    power: np.ndarray,
    periods: np.ndarray,
    method: str = "option_a",
    exclusion_half_width_steps: int = 3,
    harmonic_multipliers: Sequence[float] = (1.0 / 3.0, 0.5, 2.0, 3.0),
    satellite_freq_delta: float = 0.0730,
    min_valid_bins: int = 50,
    max_clip_iter: int = 10,
    clip_sigma: float = 3.0
) -> SDEResult:
    """
    Compute Signal Detection Efficiency (SDE) under specified GATE-11 distribution option.

    Parameters
    ----------
    power : np.ndarray
        Array of periodogram objective function values.
    periods : np.ndarray
        Array of trial orbital periods in days corresponding to `power`.
    method : str
        SDE background estimation method:
        - 'option_a': All finite, positive bins; parametric mean/std.
        - 'option_b': Fundamental peak-excluded (E_0); robust normalized MAD.
        - 'option_c': Full alias union mask E = E_0 U (U_h E_h) U (U_s E_s); robust normalized MAD.
        - 'option_d': Iterative 3-sigma clipped parametric mean/std.
    exclusion_half_width_steps : int
        Standardized peak exclusion half-width in units of grid spacing delta_f (default 3, resolving INC-02).
    harmonic_multipliers : Sequence[float]
        Multipliers for orbital harmonics and subharmonics to mask in Option C (default 1/3, 1/2, 2, 3).
    satellite_freq_delta : float
        TESS orbital / downlink alias frequency delta in 1/days (default 0.0730 d^-1 ~ 1 / 13.7 d).
    min_valid_bins : int
        Minimum number of valid unmasked bins required to avoid degenerate SDE (default 50).
    max_clip_iter : int
        Maximum iterations for Option D sigma-clipping (default 10).
    clip_sigma : float
        Sigma rejection threshold for Option D (default 3.0).

    Returns
    -------
    SDEResult
        Container with SDE, background statistics, mask statistics, and diagnostic flags.
    """
    method_lower = method.lower().strip()
    valid_methods = {"option_a", "option_b", "option_c", "option_d"}
    if method_lower not in valid_methods:
        raise ValueError(f"Unknown SDE method '{method}'. Valid options: {sorted(valid_methods)}")

    power_arr = np.asarray(power, dtype=float)
    period_arr = np.asarray(periods, dtype=float)

    if power_arr.ndim != 1 or period_arr.ndim != 1 or len(power_arr) != len(period_arr):
        raise ValueError("power and periods must be 1D arrays of identical length.")

    n_total = len(power_arr)
    if n_total == 0:
        return SDEResult(
            sde=float("nan"),
            max_power=float("nan"),
            background_mean=float("nan"),
            background_dispersion=float("nan"),
            method=method_lower,
            peak_frequency=float("nan"),
            peak_period=float("nan"),
            df=float("nan"),
            n_total_bins=0,
            n_valid_bins=0,
            n_unmasked_bins=0,
            n_masked_bins=0,
            mask_fraction=0.0,
            sde_degenerate=True,
            mad_zero=False,
            metadata={"error": "Empty input periodogram"}
        )

    # Convert to frequency and sort in ascending frequency order
    with np.errstate(divide="ignore", invalid="ignore"):
        freq_raw = 1.0 / period_arr

    # Identify valid bins: finite period > 0, finite power > 0
    finite_mask = (
        np.isfinite(power_arr) &
        (power_arr > 0) &
        np.isfinite(freq_raw) &
        (freq_raw > 0)
    )

    n_valid = int(np.sum(finite_mask))
    if n_valid < min_valid_bins:
        max_p = float(np.nanmax(power_arr[finite_mask])) if n_valid > 0 else float("nan")
        return SDEResult(
            sde=float("nan"),
            max_power=max_p,
            background_mean=float("nan"),
            background_dispersion=float("nan"),
            method=method_lower,
            peak_frequency=float("nan"),
            peak_period=float("nan"),
            df=float("nan"),
            n_total_bins=n_total,
            n_valid_bins=n_valid,
            n_unmasked_bins=0,
            n_masked_bins=n_valid,
            mask_fraction=1.0,
            sde_degenerate=True,
            mad_zero=False,
            metadata={"error": f"Fewer than {min_valid_bins} valid frequency bins ({n_valid})"}
        )

    # Sort valid points by frequency
    valid_indices = np.where(finite_mask)[0]
    sort_order = np.argsort(freq_raw[valid_indices])
    valid_idx_sorted = valid_indices[sort_order]

    freq = freq_raw[valid_idx_sorted]
    pow_valid = power_arr[valid_idx_sorted]

    # Global maximum peak
    best_loc = np.argmax(pow_valid)
    max_power = float(pow_valid[best_loc])
    f0 = float(freq[best_loc])
    p0 = float(1.0 / f0)

    # Frequency grid spacing
    freq_diffs = np.diff(freq)
    df = float(np.median(freq_diffs)) if len(freq_diffs) > 0 else 0.0
    delta_f_excl = exclusion_half_width_steps * df

    # OPTION A: All valid frequencies unclipped (parametric mean/std)
    if method_lower == "option_a":
        bg_mean = float(np.mean(pow_valid))
        bg_disp = float(np.std(pow_valid))
        mad_zero = (bg_disp < 1e-12)
        sde = (max_power - bg_mean) / bg_disp if bg_disp >= 1e-12 else float("nan")
        return SDEResult(
            sde=sde,
            max_power=max_power,
            background_mean=bg_mean,
            background_dispersion=bg_disp,
            method="option_a",
            peak_frequency=f0,
            peak_period=p0,
            df=df,
            n_total_bins=n_total,
            n_valid_bins=n_valid,
            n_unmasked_bins=n_valid,
            n_masked_bins=0,
            mask_fraction=0.0,
            sde_degenerate=False,
            mad_zero=mad_zero,
            exclusion_intervals=[],
            metadata={"description": "All finite bins unclipped parametric mean and standard deviation"}
        )

    # Build exclusion intervals for Option B and Option C
    intervals: List[Tuple[float, float]] = []

    # E_0: Fundamental peak window
    intervals.append((f0 - delta_f_excl, f0 + delta_f_excl))

    if method_lower == "option_c":
        # Harmonics & subharmonics: h * f0
        f_min, f_max = float(freq[0]), float(freq[-1])
        for h in harmonic_multipliers:
            if not np.isfinite(h) or h <= 0:
                continue
            fh = float(h * f0)
            if f_min <= fh <= f_max:
                intervals.append((fh - delta_f_excl, fh + delta_f_excl))

        # Satellite aliases: f0 +/- satellite_freq_delta
        if satellite_freq_delta > 0:
            for s_sign in (-1.0, 1.0):
                fs = float(f0 + s_sign * satellite_freq_delta)
                if f_min <= fs <= f_max:
                    intervals.append((fs - delta_f_excl, fs + delta_f_excl))

    # Apply composite exclusion mask as formal union of intervals
    in_mask = np.zeros(len(freq), dtype=bool)
    for f_low, f_high in intervals:
        in_mask |= ((freq >= f_low) & (freq <= f_high))

    unmasked_indices = np.where(~in_mask)[0]
    n_unmasked = len(unmasked_indices)
    n_masked = n_valid - n_unmasked
    mask_fraction = float(n_masked / n_valid)

    # Degeneracy guard: If unmasked bins < min_valid_bins, return NaN
    if n_unmasked < min_valid_bins:
        return SDEResult(
            sde=float("nan"),
            max_power=max_power,
            background_mean=float("nan"),
            background_dispersion=float("nan"),
            method=method_lower,
            peak_frequency=f0,
            peak_period=p0,
            df=df,
            n_total_bins=n_total,
            n_valid_bins=n_valid,
            n_unmasked_bins=n_unmasked,
            n_masked_bins=n_masked,
            mask_fraction=mask_fraction,
            sde_degenerate=True,
            mad_zero=False,
            exclusion_intervals=intervals,
            metadata={"error": f"Fewer than {min_valid_bins} unmasked bins ({n_unmasked}) after exclusion"}
        )

    pow_bg = pow_valid[unmasked_indices]

    # OPTION B & OPTION C: Robust normalized MAD
    if method_lower in ("option_b", "option_c"):
        bg_mean = float(np.median(pow_bg))
        abs_dev = np.abs(pow_bg - bg_mean)
        mad_raw = float(np.median(abs_dev))
        bg_disp = float(1.4826 * mad_raw)
        mad_zero = bool(bg_disp < 1e-12)

        sde = (max_power - bg_mean) / bg_disp if not mad_zero else float("nan")
        return SDEResult(
            sde=sde,
            max_power=max_power,
            background_mean=bg_mean,
            background_dispersion=bg_disp,
            method=method_lower,
            peak_frequency=f0,
            peak_period=p0,
            df=df,
            n_total_bins=n_total,
            n_valid_bins=n_valid,
            n_unmasked_bins=n_unmasked,
            n_masked_bins=n_masked,
            mask_fraction=mask_fraction,
            sde_degenerate=False,
            mad_zero=mad_zero,
            exclusion_intervals=intervals,
            metadata={
                "description": "Peak-excluded robust normalized MAD" if method_lower == "option_b" else "Alias-aware composite union mask robust normalized MAD",
                "raw_mad": mad_raw,
                "n_intervals": len(intervals),
            }
        )

    # OPTION D: Iterative 3-sigma clipping
    current_bg = pow_valid.copy()
    for iter_i in range(max_clip_iter):
        m = float(np.mean(current_bg))
        s = float(np.std(current_bg))
        if s < 1e-12:
            break
        keep = np.abs(current_bg - m) <= clip_sigma * s
        if np.all(keep) or np.sum(keep) < min_valid_bins:
            break
        current_bg = current_bg[keep]

    n_unmasked_d = len(current_bg)
    if n_unmasked_d < min_valid_bins:
        return SDEResult(
            sde=float("nan"),
            max_power=max_power,
            background_mean=float("nan"),
            background_dispersion=float("nan"),
            method="option_d",
            peak_frequency=f0,
            peak_period=p0,
            df=df,
            n_total_bins=n_total,
            n_valid_bins=n_valid,
            n_unmasked_bins=n_unmasked_d,
            n_masked_bins=n_valid - n_unmasked_d,
            mask_fraction=float((n_valid - n_unmasked_d) / n_valid),
            sde_degenerate=True,
            mad_zero=False,
            metadata={"error": "Fewer than 50 bins after sigma clipping"}
        )

    bg_mean_d = float(np.mean(current_bg))
    bg_disp_d = float(np.std(current_bg))
    mad_zero_d = bool(bg_disp_d < 1e-12)
    sde_d = (max_power - bg_mean_d) / bg_disp_d if not mad_zero_d else float("nan")

    return SDEResult(
        sde=sde_d,
        max_power=max_power,
        background_mean=bg_mean_d,
        background_dispersion=bg_disp_d,
        method="option_d",
        peak_frequency=f0,
        peak_period=p0,
        df=df,
        n_total_bins=n_total,
        n_valid_bins=n_valid,
        n_unmasked_bins=n_unmasked_d,
        n_masked_bins=n_valid - n_unmasked_d,
        mask_fraction=float((n_valid - n_unmasked_d) / n_valid),
        sde_degenerate=False,
        mad_zero=mad_zero_d,
        metadata={"description": "Iterative 3-sigma clipped mean and std", "converged_iterations": iter_i + 1}
    )
