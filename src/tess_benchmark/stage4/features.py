"""
Transit-Specific Candidate Feature Extraction Module.

Implements the deterministic 52-feature schema for Stage 4 candidate vetting:
- 22 Baseline Features (identical to Stage 3)
- 30 New Transit Morphology & Context Features

Features are strictly label-blind and calculated per-light-curve from:
(LightCurveData, candidate_period, candidate_t0, candidate_duration, candidate_depth, sde, snr)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from scipy import stats

from ..data.protocol import LightCurveData
from ..baselines.bls import BLSResult
from ..features.extractors import FeatureExtractor, FEATURE_NAMES as BASELINE_FEATURE_NAMES
from ..features.folding import phase_fold, bin_folded_light_curve


# Group A: Basic Transit Shape & Geometry (7 features)
GROUP_A_SHAPE = [
    "shape_depth_to_local_mad",
    "shape_candidate_duty_cycle",
    "shape_in_out_contrast",
    "shape_ingress_ratio",
    "shape_in_transit_fraction",
    "shape_in_transit_mad",
    "shape_mad_ratio",
]

# Group B: Morphology & Profile Characterization (5 features)
GROUP_B_MORPHOLOGY = [
    "morph_symmetry",
    "morph_ingress_egress_diff",
    "morph_flat_bottom_kurtosis",
    "morph_broad_depression_ratio",
    "morph_core_to_wing_ratio",
]

# Group C: Individual Event Consistency (5 features)
GROUP_C_EVENT_CONSISTENCY = [
    "event_n_observed",
    "event_n_adequate",
    "event_adequate_fraction",
    "event_depth_scatter_mad",
    "event_single_event_dominance",
]

# Group D: Odd/Even Consistency (4 features)
GROUP_D_ODD_EVEN = [
    "odd_even_depth_difference",
    "odd_even_depth_ratio_v2",
    "odd_even_significance",
    "secondary_eclipse_max_depth_ratio",
]

# Group E: Stellar Variability & Activity (5 features)
GROUP_E_VARIABILITY = [
    "var_global_to_local_std",
    "var_autocorr_peak",
    "var_has_autocorr_modulation",
    "var_flare_cadence_rate",
    "var_out_of_transit_smoothness",
]

# Group F: Signal Localization (4 features)
GROUP_F_LOCALIZATION = [
    "local_variance_contrast",
    "local_flux_deficit_concentration",
    "local_dip_isolation",
    "local_baseline_flatness",
]

STAGE4_NEW_FEATURE_NAMES: List[str] = (
    GROUP_A_SHAPE
    + GROUP_B_MORPHOLOGY
    + GROUP_C_EVENT_CONSISTENCY
    + GROUP_D_ODD_EVEN
    + GROUP_E_VARIABILITY
    + GROUP_F_LOCALIZATION
)

STAGE4_FEATURE_GROUPS: Dict[str, List[str]] = {
    "baseline": list(BASELINE_FEATURE_NAMES),
    "shape": list(GROUP_A_SHAPE),
    "morphology": list(GROUP_B_MORPHOLOGY),
    "event_consistency": list(GROUP_C_EVENT_CONSISTENCY),
    "odd_even": list(GROUP_D_ODD_EVEN),
    "variability": list(GROUP_E_VARIABILITY),
    "localization": list(GROUP_F_LOCALIZATION),
}

# Master deterministic ordered 52-feature schema
STAGE4_FEATURE_NAMES: List[str] = [
    feat for group in STAGE4_FEATURE_GROUPS.values() for feat in group
]

# Strict programmatic schema invariants
assert len(BASELINE_FEATURE_NAMES) == 22, f"Expected 22 baseline features, got {len(BASELINE_FEATURE_NAMES)}"
assert len(STAGE4_NEW_FEATURE_NAMES) == 30, f"Expected 30 new features, got {len(STAGE4_NEW_FEATURE_NAMES)}"
assert len(STAGE4_FEATURE_NAMES) == 52, f"Expected 52 features, got {len(STAGE4_FEATURE_NAMES)}"
assert len(set(STAGE4_FEATURE_NAMES)) == 52, "Feature names must be strictly unique"


@dataclass
class TransitCandidateFeatures:
    """Container for the complete 52-dimensional candidate feature vector."""
    features: Dict[str, float]

    def to_array(self, feature_order: Optional[List[str]] = None) -> np.ndarray:
        """Convert features to numpy array following exact schema ordering."""
        order = feature_order or STAGE4_FEATURE_NAMES
        return np.array([self.features[name] for name in order], dtype=float)

    def to_dict(self) -> Dict[str, float]:
        return dict(self.features)


def _compute_autocorrelation_peak(
    time: np.ndarray,
    flux: np.ndarray,
    min_lag_days: float = 0.5,
    max_lag_days: float = 10.0,
    cadence_hours: float = 1.0
) -> Tuple[float, float]:
    """
    Compute peak prominence and lag of out-of-transit flux autocorrelation.
    Returns (peak_value, peak_lag_days). Returns (np.nan, np.nan) if baseline too short.
    """
    t_span = time[-1] - time[0]
    if t_span < 5.0 or len(time) < 50:
        return np.nan, np.nan

    # Bin flux to regular 1-hour grid
    dt_days = cadence_hours / 24.0
    grid_times = np.arange(time[0], time[-1], dt_days)
    if len(grid_times) < 20:
        return np.nan, np.nan

    bin_idx = np.digitize(time, grid_times) - 1
    grid_flux = np.full(len(grid_times), np.nan)
    for i in range(len(grid_times)):
        mask = (bin_idx == i)
        if np.any(mask):
            grid_flux[i] = np.nanmedian(flux[mask])

    valid_mask = np.isfinite(grid_flux)
    if np.sum(valid_mask) < 20:
        return np.nan, np.nan

    grid_flux = np.interp(grid_times, grid_times[valid_mask], grid_flux[valid_mask])
    grid_flux = grid_flux - np.mean(grid_flux)
    var = np.var(grid_flux)
    if var <= 0:
        return 0.0, 0.0

    # FFT-based autocorrelation
    n = len(grid_flux)
    n_fft = 2 ** int(np.ceil(np.log2(2 * n - 1)))
    fx = np.fft.fft(grid_flux, n=n_fft)
    acf = np.fft.ifft(fx * np.conj(fx)).real[:n]
    acf /= (np.arange(n, 0, -1) * var)

    lags_days = np.arange(n) * dt_days
    lag_mask = (lags_days >= min_lag_days) & (lags_days <= min(max_lag_days, t_span * 0.5))
    if not np.any(lag_mask):
        return np.nan, np.nan

    acf_sub = acf[lag_mask]
    lags_sub = lags_days[lag_mask]

    peak_val = float(np.max(acf_sub))
    peak_lag = float(lags_sub[np.argmax(acf_sub)])
    return np.clip(peak_val, 0.0, 1.0), peak_lag


def extract_stage4_new_features(
    time: np.ndarray,
    flux: np.ndarray,
    candidate_period: float,
    candidate_t0: float,
    candidate_duration: float,
    candidate_depth: float,
) -> Dict[str, float]:
    """
    Extract 30 new Stage 4 transit morphology, consistency, and variability features.

    Parameters
    ----------
    time : np.ndarray
        Observation timestamps in days.
    flux : np.ndarray
        Normalized flux (median ~ 1.0).
    candidate_period : float
        Candidate orbital period in days.
    candidate_t0 : float
        Candidate center epoch in days.
    candidate_duration : float
        Candidate transit duration in days.
    candidate_depth : float
        Candidate fractional depth.

    Returns
    -------
    Dict[str, float]
        Mapping of 30 feature names to float values (or np.nan where undefined).
    """
    feats: Dict[str, float] = {}

    P = float(candidate_period)
    t0 = float(candidate_t0)
    T_dur = float(candidate_duration)
    delta = float(candidate_depth)

    n_pts = len(time)
    if n_pts == 0 or P <= 0 or T_dur <= 0:
        for name in STAGE4_NEW_FEATURE_NAMES:
            feats[name] = np.nan
        return feats

    # Phase folding into [-0.5, 0.5) centered on t0
    phase = phase_fold(time, P, t0)
    half_dur_phase = T_dur / (2.0 * P)

    # In-transit and out-of-transit masks
    in_transit = np.abs(phase) < half_dur_phase
    out_transit = ~in_transit

    n_in = int(np.sum(in_transit))
    n_out = int(np.sum(out_transit))

    # Robust local statistics
    med_out = float(np.median(flux[out_transit])) if n_out >= 3 else 1.0
    mad_out = float(np.median(np.abs(flux[out_transit] - med_out))) if n_out >= 3 else 0.0
    sigma_out = 1.4826 * mad_out

    med_in = float(np.median(flux[in_transit])) if n_in >= 3 else med_out
    mad_in = float(np.median(np.abs(flux[in_transit] - med_in))) if n_in >= 3 else 0.0
    sigma_in = 1.4826 * mad_in

    # Phase binning (50 bins across [-0.5, 0.5])
    bin_centers, binned_flux, binned_err = bin_folded_light_curve(
        phase, flux, n_bins=50, phase_min=-0.5, phase_max=0.5
    )

    # -------------------------------------------------------------
    # Group A: Basic Transit Shape & Geometry (7 features)
    # -------------------------------------------------------------
    # 1. shape_depth_to_local_mad
    # Local out-of-transit window within +/- 3.5 T_dur
    local_out_mask = out_transit & (np.abs(phase) <= min(0.49, 3.5 * half_dur_phase))
    if np.sum(local_out_mask) >= 5:
        local_med = np.median(flux[local_out_mask])
        local_mad = np.median(np.abs(flux[local_out_mask] - local_med))
        local_sigma = 1.4826 * local_mad
        feats["shape_depth_to_local_mad"] = float(delta / (local_sigma + 1e-12)) if local_sigma > 0 else np.nan
    else:
        feats["shape_depth_to_local_mad"] = np.nan

    # 2. shape_candidate_duty_cycle
    feats["shape_candidate_duty_cycle"] = float(T_dur / P) if (P > 0 and T_dur > 0) else np.nan

    # 3. shape_in_out_contrast
    if n_in >= 3 and n_out >= 10 and sigma_out > 0:
        feats["shape_in_out_contrast"] = float((med_out - med_in) / (sigma_out + 1e-12))
    else:
        feats["shape_in_out_contrast"] = np.nan

    # 4. shape_ingress_ratio
    # Measure width at 90% depth and 10% depth from binned profile around phase 0
    in_binned = np.abs(bin_centers) <= (2.0 * half_dur_phase)
    if np.any(in_binned) and np.sum(in_binned) >= 6:
        b_phase = bin_centers[in_binned]
        b_flux = binned_flux[in_binned]
        min_f = np.min(b_flux)
        baseline_f = med_out
        dip_depth = baseline_f - min_f
        if dip_depth > 0:
            threshold_10 = baseline_f - 0.10 * dip_depth
            threshold_90 = baseline_f - 0.90 * dip_depth
            w10_mask = b_flux <= threshold_10
            w90_mask = b_flux <= threshold_90
            w10 = (np.max(b_phase[w10_mask]) - np.min(b_phase[w10_mask])) if np.any(w10_mask) else 0.0
            w90 = (np.max(b_phase[w90_mask]) - np.min(b_phase[w90_mask])) if np.any(w90_mask) else 0.0
            if w10 > 0:
                feats["shape_ingress_ratio"] = float(np.clip((w10 - w90) / w10, 0.0, 1.0))
            else:
                feats["shape_ingress_ratio"] = np.nan
        else:
            feats["shape_ingress_ratio"] = np.nan
    else:
        feats["shape_ingress_ratio"] = np.nan

    # 5. shape_in_transit_fraction
    feats["shape_in_transit_fraction"] = float(n_in / max(1, n_pts))

    # 6. shape_in_transit_mad
    feats["shape_in_transit_mad"] = float(sigma_in) if n_in >= 5 else np.nan

    # 7. shape_mad_ratio
    feats["shape_mad_ratio"] = float(sigma_in / (sigma_out + 1e-12)) if (n_in >= 5 and n_out >= 10 and sigma_out > 0) else np.nan

    # -------------------------------------------------------------
    # Group B: Morphology & Profile Characterization (5 features)
    # -------------------------------------------------------------
    # 8. morph_symmetry
    # Folded binned ingress vs egress correlation
    wing_binned = np.abs(bin_centers) <= half_dur_phase
    if np.sum(wing_binned) >= 6:
        # Separate into negative and positive phases
        neg_mask = (bin_centers < 0) & (bin_centers >= -half_dur_phase)
        pos_mask = (bin_centers > 0) & (bin_centers <= half_dur_phase)
        k_min = min(np.sum(neg_mask), np.sum(pos_mask))
        if k_min >= 3:
            left = binned_flux[neg_mask][-k_min:]
            right = binned_flux[pos_mask][:k_min][::-1]  # reversed to match ingress to egress
            if np.std(left) > 0 and np.std(right) > 0:
                r_val, _ = stats.pearsonr(left, right)
                feats["morph_symmetry"] = float(r_val) if np.isfinite(r_val) else np.nan
            else:
                feats["morph_symmetry"] = 1.0 if np.allclose(left, right, atol=1e-5) else np.nan
        else:
            feats["morph_symmetry"] = np.nan
    else:
        feats["morph_symmetry"] = np.nan

    # 9. morph_ingress_egress_diff
    ingress_cadences = flux[(phase >= -half_dur_phase) & (phase < 0)]
    egress_cadences = flux[(phase > 0) & (phase <= half_dur_phase)]
    if len(ingress_cadences) >= 3 and len(egress_cadences) >= 3 and delta > 0:
        feats["morph_ingress_egress_diff"] = float(
            (np.median(ingress_cadences) - np.median(egress_cadences)) / (delta + 1e-12)
        )
    else:
        feats["morph_ingress_egress_diff"] = np.nan

    # 10. morph_flat_bottom_kurtosis
    if n_in >= 10:
        in_kurt = float(stats.kurtosis(flux[in_transit], fisher=True))
        feats["morph_flat_bottom_kurtosis"] = in_kurt if np.isfinite(in_kurt) else np.nan
    else:
        feats["morph_flat_bottom_kurtosis"] = np.nan

    # 11. morph_broad_depression_ratio
    # Width 1x vs 3x duration
    if (T_dur / P) < 0.30:
        w1_mask = np.abs(phase) <= half_dur_phase
        w2_mask = (np.abs(phase) > half_dur_phase) & (np.abs(phase) <= (3.0 * half_dur_phase))
        if np.sum(w1_mask) >= 3 and np.sum(w2_mask) >= 5:
            d1 = max(0.0, med_out - np.median(flux[w1_mask]))
            d2 = max(0.0, med_out - np.median(flux[w2_mask]))
            feats["morph_broad_depression_ratio"] = float(d2 / (d1 + 1e-12)) if d1 > 0 else np.nan
        else:
            feats["morph_broad_depression_ratio"] = np.nan
    else:
        feats["morph_broad_depression_ratio"] = np.nan

    # 12. morph_core_to_wing_ratio
    core_mask = np.abs(phase) <= (0.5 * half_dur_phase)
    wing_mask = (np.abs(phase) > (0.5 * half_dur_phase)) & (np.abs(phase) <= half_dur_phase)
    if np.sum(core_mask) >= 3 and np.sum(wing_mask) >= 3:
        d_core = max(0.0, med_out - np.median(flux[core_mask]))
        d_wing = max(0.0, med_out - np.median(flux[wing_mask]))
        denom = d_core + d_wing
        feats["morph_core_to_wing_ratio"] = float(d_core / (denom + 1e-12)) if denom > 0 else np.nan
    else:
        feats["morph_core_to_wing_ratio"] = np.nan

    # -------------------------------------------------------------
    # Group C: Individual Event Consistency (5 features)
    # -------------------------------------------------------------
    t_min = time[0]
    t_max = time[-1]
    k_start = int(np.floor((t_min - t0) / P))
    k_end = int(np.ceil((t_max - t0) / P))

    individual_event_depths: List[float] = []
    n_observed = 0
    n_adequate = 0

    for k in range(k_start, k_end + 1):
        t_center = t0 + k * P
        t_w_start = t_center - (T_dur / 2.0)
        t_w_end = t_center + (T_dur / 2.0)

        # Check if window intersects baseline
        if (t_w_end >= t_min) and (t_w_start <= t_max):
            n_observed += 1
            ev_in = (time >= t_w_start) & (time <= t_w_end)
            n_ev_in = int(np.sum(ev_in))

            # Temporal coverage check (Lebesgue coverage)
            if n_ev_in >= 2:
                ev_times = time[ev_in]
                t_cov = ev_times[-1] - ev_times[0]
                frac_cov = t_cov / max(1e-6, T_dur)
            else:
                frac_cov = 0.0

            if n_ev_in >= 5 and frac_cov >= 0.50:
                n_adequate += 1
                # Local baseline for this event (+/- 3 T_dur outside transit)
                ev_local_out = (time >= t_center - 3.0 * T_dur) & (time <= t_center + 3.0 * T_dur) & (~ev_in)
                if np.sum(ev_local_out) >= 5:
                    ev_out_med = np.median(flux[ev_local_out])
                else:
                    ev_out_med = med_out
                ev_depth = ev_out_med - np.median(flux[ev_in])
                individual_event_depths.append(float(ev_depth))

    # 13. event_n_observed
    feats["event_n_observed"] = float(n_observed)

    # 14. event_n_adequate
    feats["event_n_adequate"] = float(n_adequate)

    # 15. event_adequate_fraction
    feats["event_adequate_fraction"] = float(n_adequate / max(1, n_observed))

    # 16. event_depth_scatter_mad
    if len(individual_event_depths) >= 3:
        arr_depths = np.array(individual_event_depths)
        med_d = np.median(arr_depths)
        mad_d = 1.4826 * np.median(np.abs(arr_depths - med_d))
        feats["event_depth_scatter_mad"] = float(mad_d / (abs(med_d) + 1e-12)) if abs(med_d) > 0 else np.nan
    else:
        feats["event_depth_scatter_mad"] = np.nan

    # 17. event_single_event_dominance
    if len(individual_event_depths) >= 2:
        pos_depths = [max(0.0, d) for d in individual_event_depths]
        tot = sum(pos_depths)
        feats["event_single_event_dominance"] = float(max(pos_depths) / tot) if tot > 0 else np.nan
    elif len(individual_event_depths) == 1:
        feats["event_single_event_dominance"] = 1.0
    else:
        feats["event_single_event_dominance"] = np.nan

    # -------------------------------------------------------------
    # Group D: Odd/Even Consistency (4 features)
    # -------------------------------------------------------------
    # Compute odd vs even transit statistics
    epoch_numbers = np.round((time - t0) / P).astype(int)
    odd_in_mask = in_transit & (epoch_numbers % 2 == 1)
    even_in_mask = in_transit & (epoch_numbers % 2 == 0)

    n_odd = int(np.sum(odd_in_mask))
    n_even = int(np.sum(even_in_mask))

    d_odd = (med_out - np.median(flux[odd_in_mask])) if n_odd >= 3 else np.nan
    d_even = (med_out - np.median(flux[even_in_mask])) if n_even >= 3 else np.nan

    # 18. odd_even_depth_difference
    if np.isfinite(d_odd) and np.isfinite(d_even):
        feats["odd_even_depth_difference"] = float(abs(d_odd - d_even))
    else:
        feats["odd_even_depth_difference"] = np.nan

    # 19. odd_even_depth_ratio_v2
    if np.isfinite(d_odd) and np.isfinite(d_even) and max(d_odd, d_even) > 0:
        min_d = max(0.0, min(d_odd, d_even))
        max_d = max(0.0, max(d_odd, d_even))
        feats["odd_even_depth_ratio_v2"] = float(min_d / (max_d + 1e-12))
    else:
        feats["odd_even_depth_ratio_v2"] = np.nan

    # 20. odd_even_significance
    if n_odd >= 5 and n_even >= 5 and np.isfinite(d_odd) and np.isfinite(d_even):
        err_odd = (1.4826 * np.median(np.abs(flux[odd_in_mask] - np.median(flux[odd_in_mask])))) / np.sqrt(n_odd)
        err_even = (1.4826 * np.median(np.abs(flux[even_in_mask] - np.median(flux[even_in_mask])))) / np.sqrt(n_even)
        comb_err = np.sqrt(err_odd**2 + err_even**2)
        feats["odd_even_significance"] = float(abs(d_odd - d_even) / (comb_err + 1e-12)) if comb_err > 0 else np.nan
    else:
        feats["odd_even_significance"] = np.nan

    # 21. secondary_eclipse_max_depth_ratio
    # Secondary eclipse at phase 0.5 (or -0.5)
    if (T_dur / P) < 0.35:
        sec_mask = np.abs(np.abs(phase) - 0.5) < half_dur_phase
        if np.sum(sec_mask) >= 5 and delta > 0:
            d_sec = max(0.0, med_out - np.median(flux[sec_mask]))
            feats["secondary_eclipse_max_depth_ratio"] = float(d_sec / (delta + 1e-12))
        else:
            feats["secondary_eclipse_max_depth_ratio"] = np.nan
    else:
        feats["secondary_eclipse_max_depth_ratio"] = np.nan

    # -------------------------------------------------------------
    # Group E: Stellar Variability & Activity (5 features)
    # -------------------------------------------------------------
    # 22. var_global_to_local_std
    tot_std = float(np.std(flux))
    feats["var_global_to_local_std"] = float(tot_std / (sigma_out + 1e-12)) if sigma_out > 0 else 1.0

    # 23. var_autocorr_peak & 24. var_has_autocorr_modulation
    acf_peak, _ = _compute_autocorrelation_peak(
        time[out_transit], flux[out_transit], min_lag_days=max(0.5, 3.0 * T_dur)
    )
    feats["var_autocorr_peak"] = float(acf_peak) if np.isfinite(acf_peak) else np.nan
    feats["var_has_autocorr_modulation"] = float(1.0 if (np.isfinite(acf_peak) and acf_peak >= 0.20) else 0.0) if np.isfinite(acf_peak) else np.nan

    # 25. var_flare_cadence_rate
    # Fraction of cadences exceeding +4 sigma
    if sigma_out > 0:
        high_flare_thresh = med_out + 4.0 * sigma_out
        feats["var_flare_cadence_rate"] = float(np.mean(flux > high_flare_thresh))
    else:
        feats["var_flare_cadence_rate"] = 0.0

    # 26. var_out_of_transit_smoothness (Von Neumann ratio on out-of-transit flux)
    if n_out >= 10:
        flux_out_pts = flux[out_transit]
        var_o = float(np.var(flux_out_pts))
        if var_o > 0:
            diff_sq = np.sum(np.diff(flux_out_pts) ** 2)
            feats["var_out_of_transit_smoothness"] = float(diff_sq / ((len(flux_out_pts) - 1) * var_o))
        else:
            feats["var_out_of_transit_smoothness"] = 2.0
    else:
        feats["var_out_of_transit_smoothness"] = 2.0

    # -------------------------------------------------------------
    # Group F: Signal Localization (4 features)
    # -------------------------------------------------------------
    # 27. local_variance_contrast
    var_total = float(np.var(flux))
    var_in = float(np.var(flux[in_transit])) if n_in >= 5 else 0.0
    duty = float(T_dur / P)
    if n_in >= 5 and var_total > 0 and duty > 0:
        feats["local_variance_contrast"] = float((var_in / var_total) / duty)
    else:
        feats["local_variance_contrast"] = np.nan

    # 28. local_flux_deficit_concentration
    # Total deficit inside transit vs total deficit overall
    deficit = np.maximum(0.0, med_out - flux)
    sum_def_in = float(np.sum(deficit[in_transit]))
    sum_def_tot = float(np.sum(deficit))
    feats["local_flux_deficit_concentration"] = float(sum_def_in / (sum_def_tot + 1e-12)) if sum_def_tot > 0 else 0.0

    # 29. local_dip_isolation
    # Ratio of transit core dip to deepest binned out-of-transit dip
    b_in_mask = np.abs(bin_centers) <= half_dur_phase
    b_out_mask = ~b_in_mask
    if np.any(b_in_mask) and np.any(b_out_mask):
        dip_in = max(0.0, med_out - np.min(binned_flux[b_in_mask]))
        dip_out_deepest = max(0.0, med_out - np.min(binned_flux[b_out_mask]))
        feats["local_dip_isolation"] = float(dip_in / (dip_out_deepest + sigma_out + 1e-12))
    else:
        feats["local_dip_isolation"] = np.nan

    # 30. local_baseline_flatness
    if np.any(b_out_mask) and np.sum(b_out_mask) >= 5 and sigma_out > 0:
        std_binned_out = float(np.std(binned_flux[b_out_mask]))
        expected_noise = sigma_out / np.sqrt(max(1.0, float(n_out) / float(len(bin_centers))))
        feats["local_baseline_flatness"] = float(std_binned_out / (expected_noise + 1e-12))
    else:
        feats["local_baseline_flatness"] = np.nan

    return feats


def extract_all_candidate_features(
    lc: LightCurveData,
    candidate_period: float,
    candidate_t0: float,
    candidate_duration: float,
    candidate_depth: float,
    bls_sde: float,
    bls_snr: float,
    bls_max_power: float,
    bls_mean_power: float = 0.0,
    bls_std_power: float = 1.0,
) -> TransitCandidateFeatures:
    """
    Extract the complete, deterministic 52-feature vector for a transit candidate.

    Reuses the 22 baseline features from FeatureExtractor and appends
    the 30 new transit morphology, consistency, variability, and localization features.
    """
    cleaned = lc.clean()
    time = cleaned.time
    flux = cleaned.flux

    # Synthesize BLSResult for FeatureExtractor
    bls_res = BLSResult(
        best_period=float(candidate_period),
        best_t0=float(candidate_t0),
        best_duration=float(candidate_duration),
        best_depth=float(candidate_depth),
        sde=float(bls_sde),
        snr=float(bls_snr),
        max_power=float(bls_max_power),
        mean_power=float(bls_mean_power),
        std_power=float(bls_std_power),
        is_detected=True,
        runtime_sec=0.0
    )

    # 1. Extract 22 baseline features
    baseline_extractor = FeatureExtractor()
    base_dict = baseline_extractor.extract_tabular_features(cleaned, bls_result=bls_res)

    # 2. Extract 30 Stage 4 new features
    stage4_dict = extract_stage4_new_features(
        time=time,
        flux=flux,
        candidate_period=float(candidate_period),
        candidate_t0=float(candidate_t0),
        candidate_duration=float(candidate_duration),
        candidate_depth=float(candidate_depth),
    )

    # Combine into single dictionary
    all_feats: Dict[str, float] = {}
    for name in BASELINE_FEATURE_NAMES:
        all_feats[name] = float(base_dict[name])
    for name in STAGE4_NEW_FEATURE_NAMES:
        all_feats[name] = float(stage4_dict[name])

    assert len(all_feats) == 52, f"Expected 52 features, got {len(all_feats)}"
    return TransitCandidateFeatures(features=all_feats)
