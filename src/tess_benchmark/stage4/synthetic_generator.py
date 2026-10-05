"""
Synthetic Candidate Generator for Stage 4 Vetting.

Simulates the complete candidate discovery pipeline:
Synthetic Light Curve -> BLS Periodogram -> Candidate Detection -> 52-Feature Extraction

Generates balanced training populations comprising:
- Genuine Planetary Transits (Positive, label=1)
- Astrophysical & Systematic Confounders (Negative, label=0):
  1. Eclipsing Binaries (alternating primary/secondary depths, V-shaped)
  2. Stellar Rotation & Spot Modulation (multi-harmonic sinusoids)
  3. Active Flare Stars (stochastic flares with asymmetric dip artifacts)
  4. Instrumental Systematics & Thermal Ramps (step jumps, momentum dump harmonics)
  5. Noise-Driven BLS Artifacts (red/pink noise false alarms)
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from ..data.protocol import LightCurveData, TargetCategory
from ..data.synthetic import trapezoidal_transit, normalize_light_curve, preprocess_light_curve
from ..baselines.bls import BLSDetector, BLSResult
from .features import extract_all_candidate_features, STAGE4_FEATURE_NAMES


@dataclass
class SyntheticCandidateConfig:
    """Configuration for synthetic candidate cohort generation."""
    n_targets_per_class: Optional[int] = None
    n_transits: int = 300
    n_confounders_per_class: int = 60
    duration_days: float = 27.4
    cadence_minutes: float = 2.0
    seed: int = 42
    sde_threshold: float = 6.0
    min_snr: float = 5.0
    frequency_factor: float = 4.0
    sde_method: str = "option_c"


@dataclass
class SyntheticCandidateInstance:
    """A single synthetic light curve with its BLS candidate and 52-feature representation."""
    target_id: str
    class_label: str
    is_transit: bool
    bls_detected: bool
    candidate_period: float
    candidate_t0: float
    candidate_duration: float
    candidate_depth: float
    bls_sde: float
    bls_snr: float
    bls_max_power: float
    features: Dict[str, float] = field(default_factory=dict)

    def to_flat_dict(self) -> Dict[str, Any]:
        """Convert instance metadata and features to a flat dictionary for DataFrame conversion."""
        row = {
            "target_id": self.target_id,
            "class_label": self.class_label,
            "is_transit": int(self.is_transit),
            "label": int(self.is_transit),
            "bls_detected": self.bls_detected,
            "candidate_period": self.candidate_period,
            "candidate_t0": self.candidate_t0,
            "candidate_duration": self.candidate_duration,
            "candidate_depth": self.candidate_depth,
            "bls_sde": self.bls_sde,
            "bls_snr": self.bls_snr,
            "bls_max_power": self.bls_max_power,
        }
        row.update(self.features)
        return row


def _simulate_planetary_transit(
    time: np.ndarray,
    rng: np.random.Generator,
    baseline_flux: float = 1.0,
    noise_sigma: float = 0.001
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Simulate authentic planetary transit with limb-darkened trapezoidal profile."""
    t_span = time[-1] - time[0]
    period = rng.uniform(0.8, min(14.0, t_span * 0.45))
    t0 = rng.uniform(0.2, period * 0.8)
    depth = rng.uniform(0.0008, 0.015)  # 800 to 15,000 ppm
    duration_days = rng.uniform(0.04, min(0.25, period * 0.08))  # 1 to 6 hours
    ingress_frac = rng.uniform(0.10, 0.22)

    flux = np.full_like(time, baseline_flux, dtype=float)

    # Transit signal
    dip = trapezoidal_transit(
        time=time,
        period=period,
        t0=t0,
        depth=depth,
        duration_days=duration_days,
        ingress_fraction=ingress_frac
    )
    flux += dip

    # Small stellar nuisance variability
    var_p = rng.uniform(4.0, 18.0)
    var_amp = rng.uniform(0.0003, 0.0015)
    flux += var_amp * np.sin(2.0 * np.pi * time / var_p)

    meta = {
        "true_period": period,
        "true_t0": t0,
        "true_duration": duration_days,
        "true_depth": depth,
    }
    return flux, meta


def _simulate_eclipsing_binary(
    time: np.ndarray,
    rng: np.random.Generator,
    baseline_flux: float = 1.0,
    noise_sigma: float = 0.001
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Simulate eclipsing binary with alternating primary/secondary minima and V-shape."""
    t_span = time[-1] - time[0]
    period = rng.uniform(1.2, min(12.0, t_span * 0.45))
    t0 = rng.uniform(0.2, period * 0.8)
    primary_depth = rng.uniform(0.005, 0.05)  # 5,000 to 50,000 ppm
    sec_ratio = rng.uniform(0.25, 0.85)
    secondary_depth = primary_depth * sec_ratio
    duration_days = rng.uniform(0.06, min(0.30, period * 0.12))
    ingress_frac = rng.uniform(0.40, 0.50)  # V-shaped profile

    flux = np.full_like(time, baseline_flux, dtype=float)

    # Primary eclipse
    dip_prim = trapezoidal_transit(
        time=time,
        period=period,
        t0=t0,
        depth=primary_depth,
        duration_days=duration_days,
        ingress_fraction=ingress_frac
    )
    # Secondary eclipse at phase 0.5
    dip_sec = trapezoidal_transit(
        time=time,
        period=period,
        t0=t0 + 0.5 * period,
        depth=secondary_depth,
        duration_days=duration_days * 0.95,
        ingress_fraction=ingress_frac
    )
    flux += (dip_prim + dip_sec)

    # Ellipsoidal variation (cos 2*omega*t)
    ellip_amp = rng.uniform(0.0005, primary_depth * 0.15)
    flux += ellip_amp * np.cos(4.0 * np.pi * (time - t0) / period)

    meta = {
        "true_period": period,
        "primary_depth": primary_depth,
        "secondary_depth": secondary_depth,
    }
    return flux, meta


def _simulate_stellar_rotation(
    time: np.ndarray,
    rng: np.random.Generator,
    baseline_flux: float = 1.0,
    noise_sigma: float = 0.001
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Simulate strong multi-harmonic stellar spot rotation producing false periodic dips."""
    p_rot = rng.uniform(1.5, 12.0)
    a1 = rng.uniform(0.003, 0.025)
    a2 = a1 * rng.uniform(0.2, 0.6)
    a3 = a1 * rng.uniform(0.05, 0.3)
    phi1 = rng.uniform(0, 2 * np.pi)
    phi2 = rng.uniform(0, 2 * np.pi)
    phi3 = rng.uniform(0, 2 * np.pi)

    phase = 2.0 * np.pi * time / p_rot
    flux = np.full_like(time, baseline_flux, dtype=float)
    flux += (
        a1 * np.sin(phase + phi1)
        + a2 * np.sin(2.0 * phase + phi2)
        + a3 * np.sin(3.0 * phase + phi3)
    )

    meta = {"rot_period": p_rot, "amp_primary": a1}
    return flux, meta


def _simulate_active_flare_star(
    time: np.ndarray,
    rng: np.random.Generator,
    baseline_flux: float = 1.0,
    noise_sigma: float = 0.001
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Simulate active flare star with frequent flares and post-flare depression."""
    flux = np.full_like(time, baseline_flux, dtype=float)
    dt_cadence = (time[1] - time[0])

    # Intersperse 15-40 random flare events
    n_flares = rng.integers(15, 45)
    flare_times = rng.uniform(time[0], time[-1], size=n_flares)
    flare_amps = rng.exponential(scale=10.0 * noise_sigma, size=n_flares)
    flare_decay_hours = rng.uniform(0.5, 3.5, size=n_flares)

    for f_t, f_a, f_d in zip(flare_times, flare_amps, flare_decay_hours):
        f_decay_days = f_d / 24.0
        mask = (time >= f_t) & (time <= f_t + 5.0 * f_decay_days)
        if np.any(mask):
            dt = time[mask] - f_t
            # Sharp rise and exponential decay + slight post-flare thermal dip
            decay_curve = f_a * np.exp(-dt / f_decay_days)
            dip_curve = -0.15 * f_a * np.exp(-dt / (2.0 * f_decay_days))
            flux[mask] += (decay_curve + dip_curve)

    meta = {"n_flares": n_flares}
    return flux, meta


def _simulate_instrumental_systematics(
    time: np.ndarray,
    rng: np.random.Generator,
    baseline_flux: float = 1.0,
    noise_sigma: float = 0.001
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Simulate thermal settlement ramps, momentum dump steps, and harmonic systematics."""
    flux = np.full_like(time, baseline_flux, dtype=float)
    t_norm = (time - time[0]) / (time[-1] - time[0])

    # Thermal exponential settle ramp
    ramp_amp = rng.uniform(0.002, 0.010) * rng.choice([-1, 1])
    flux += ramp_amp * np.exp(-t_norm * 4.0)

    # Momentum dump steps every ~2.5 days
    dump_period = rng.uniform(2.3, 2.7)
    step_amp = rng.uniform(0.0005, 0.002)
    step_phases = np.floor((time - time[0]) / dump_period)
    flux += step_amp * (step_phases % 2)

    # High frequency 1-day sinusoidal harmonic
    harm_amp = rng.uniform(0.0005, 0.002)
    flux += harm_amp * np.sin(2.0 * np.pi * time / 1.05)

    meta = {"ramp_amp": ramp_amp, "dump_period": dump_period}
    return flux, meta


def _simulate_red_noise_artifact(
    time: np.ndarray,
    rng: np.random.Generator,
    baseline_flux: float = 1.0,
    noise_sigma: float = 0.001
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Simulate correlated red noise (AR(1) process) producing periodic noise false alarms."""
    n = len(time)
    phi = rng.uniform(0.85, 0.96)
    sig_e = noise_sigma * np.sqrt(1 - phi**2)

    red = np.zeros(n)
    white = rng.normal(0, sig_e, size=n)
    for i in range(1, n):
        red[i] = phi * red[i - 1] + white[i]

    flux = np.full(n, baseline_flux, dtype=float) + red
    meta = {"ar_phi": phi}
    return flux, meta


def generate_synthetic_candidate_dataset(
    config: SyntheticCandidateConfig,
    admit_only_detected: bool = True
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Generate complete synthetic candidate dataset through the full discovery pipeline:
    Light Curve -> BLS Detector -> Candidate Admission -> 52-Feature Extractor

    Parameters
    ----------
    config : SyntheticCandidateConfig
        Configuration options.
    admit_only_detected : bool
        If True, only candidates triggering BLS (SDE >= sde_threshold and SNR >= min_snr)
        are admitted into the final candidate training ledger.

    Returns
    -------
    Tuple[pd.DataFrame, Dict[str, Any]]
        (DataFrame of 52 features + labels, Generation Audit Metadata)
    """
    rng = np.random.default_rng(config.seed)
    dt_cadence = config.cadence_minutes / (24.0 * 60.0)
    time_arr = np.arange(0.0, config.duration_days, dt_cadence)

    classes = [
        ("transit", True, _simulate_planetary_transit),
        ("eclipsing_binary", False, _simulate_eclipsing_binary),
        ("stellar_rotation", False, _simulate_stellar_rotation),
        ("active_flare", False, _simulate_active_flare_star),
        ("systematics", False, _simulate_instrumental_systematics),
        ("red_noise", False, _simulate_red_noise_artifact),
    ]

    detector = BLSDetector(
        min_period=0.5,
        max_period=15.0,
        frequency_factor=config.frequency_factor,
        sde_threshold=config.sde_threshold,
        min_snr=config.min_snr,
        sde_method=config.sde_method,
        save_frequency_grid=False
    )

    records: List[Dict[str, Any]] = []
    class_audit: Dict[str, Dict[str, Any]] = {}

    target_idx = 1
    t0_start = time.perf_counter()

    for c_name, is_trans, sim_fn in classes:
        admitted = 0
        generated = 0
        detected_count = 0

        # Target quota of admitted candidates
        if config.n_targets_per_class is not None:
            target_quota = config.n_targets_per_class
        else:
            target_quota = config.n_transits if is_trans else config.n_confounders_per_class

        while admitted < target_quota:
            generated += 1
            star_id = f"SYNTH-{c_name.upper()[:4]}-{target_idx:04d}"
            target_idx += 1

            noise_sig = rng.uniform(0.0006, 0.0018)
            raw_flux, meta = sim_fn(time_arr, rng, baseline_flux=1.0, noise_sigma=noise_sig)

            # Add Gaussian noise
            raw_flux += rng.normal(0, noise_sig, size=len(time_arr))
            flux_err = np.full_like(time_arr, noise_sig)

            # Add TESS sector gap
            quality_mask = np.ones(len(time_arr), dtype=bool)
            gap_mask = (time_arr >= 13.1) & (time_arr <= 14.3)
            quality_mask[gap_mask] = False

            lc = LightCurveData(
                time=time_arr,
                flux=raw_flux,
                flux_err=flux_err,
                target_id=star_id,
                category=TargetCategory.SYNTHETIC_INJECTION if is_trans else TargetCategory.CONTROL_STAR,
                has_transit=is_trans,
                quality_mask=quality_mask
            )

            # Preprocess
            clean_lc = preprocess_light_curve(lc, clip_outliers=True, detrend=True)

            # Execute BLS discovery
            bls_res = detector.search(clean_lc)
            is_detected = bls_res.is_detected
            if is_detected:
                detected_count += 1

            if admit_only_detected and not is_detected:
                # Discard non-detections if admitting only candidates
                continue

            # Candidate feature extraction
            features_obj = extract_all_candidate_features(
                lc=clean_lc,
                candidate_period=bls_res.best_period,
                candidate_t0=bls_res.best_t0,
                candidate_duration=bls_res.best_duration,
                candidate_depth=bls_res.best_depth,
                bls_sde=bls_res.sde,
                bls_snr=bls_res.snr,
                bls_max_power=bls_res.max_power,
                bls_mean_power=bls_res.mean_power,
                bls_std_power=bls_res.std_power
            )

            inst = SyntheticCandidateInstance(
                target_id=star_id,
                class_label=c_name,
                is_transit=is_trans,
                bls_detected=is_detected,
                candidate_period=bls_res.best_period,
                candidate_t0=bls_res.best_t0,
                candidate_duration=bls_res.best_duration,
                candidate_depth=bls_res.best_depth,
                bls_sde=bls_res.sde,
                bls_snr=bls_res.snr,
                bls_max_power=bls_res.max_power,
                features=features_obj.to_dict()
            )
            records.append(inst.to_flat_dict())
            admitted += 1

        class_audit[c_name] = {
            "is_transit": is_trans,
            "generated_stars": generated,
            "admitted_candidates": admitted,
            "bls_triggered_count": detected_count,
            "bls_trigger_rate": float(detected_count / max(1, generated)),
        }

    elapsed = time.perf_counter() - t0_start
    df = pd.DataFrame(records)

    audit_summary = {
        "total_admitted_candidates": len(df),
        "total_transits": int(np.sum(df["is_transit"] == 1)),
        "total_confounders": int(np.sum(df["is_transit"] == 0)),
        "classes": class_audit,
        "feature_count": len(STAGE4_FEATURE_NAMES),
        "generation_time_sec": elapsed,
        "seed": config.seed,
    }

    return df, audit_summary
