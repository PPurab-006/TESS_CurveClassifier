"""
Formal Benchmark Recovery Scorer and Event Coverage Module.

Implements approved protocol gates:
- GATE-01: Period recovery relative tolerance (default 0.01 = 1.0%).
- GATE-03: Event window cadence, temporal coverage adequacy, and boundary truncation policy (Option 2).
  - Primary interior-event track: fully interior events (W_k subset of baseline), f_temporal >= 0.50, N_valid >= 5.
  - Secondary boundary diagnostic track: boundary-truncated events, f_temporal >= 0.30, N_valid >= 3.
  - Strictly segregates boundary events from primary interior-event recovery.
- GATE-04: Narrow harmonic set {0.5, 1.0, 2.0}; fundamental (1.0) and harmonics (0.5, 2.0) scored separately.
- GATE-12: Bounded composite epoch matching tolerance (Option C):
  Delta t0_tol = min(0.50 * T_dur, sqrt((0.25 * T_dur)^2 + (3 * sigma_tmid)^2))
  with circular phase distance and one-to-one candidate/catalog matching.
"""
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Sequence, Set
import numpy as np


class HarmonicClass(str, Enum):
    """Classification of period ratio under approved GATE-04 Option B."""
    FUNDAMENTAL = "fundamental_1.0x"
    SUBHARMONIC = "subharmonic_0.5x"
    HARMONIC = "harmonic_2.0x"
    NON_MATCH = "non_match"


class MatchStatus(str, Enum):
    """Outcome of candidate-to-catalog planet recovery matching."""
    FULL_RECOVERY = "full_recovery"              # Both period and epoch match tolerance
    PERIOD_ONLY = "period_only_match"            # Period matches, epoch exceeds tolerance
    EPOCH_ONLY = "epoch_only_match"              # Epoch matches, period exceeds tolerance
    REJECTED = "no_match"                        # Neither matches
    INVALID_EPHEMERIS = "invalid_ephemeris"      # Ground truth values missing or non-physical


@dataclass
class EventCoverageRecord:
    """
    Coverage and adequacy record for a single transit event (GATE-03).
    """
    event_index: int
    t_mid: float
    duration_days: float
    window_start: float
    window_end: float
    t_base_min: float
    t_base_max: float
    is_interior: bool
    is_boundary_truncated: bool
    n_valid_cadences: int
    lebesgue_coverage_days: float
    temporal_coverage_fraction: float
    is_adequate_interior: bool
    is_adequate_boundary: bool
    exclusion_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_index": self.event_index,
            "t_mid": self.t_mid,
            "duration_days": self.duration_days,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "t_base_min": self.t_base_min,
            "t_base_max": self.t_base_max,
            "is_interior": self.is_interior,
            "is_boundary_truncated": self.is_boundary_truncated,
            "n_valid_cadences": self.n_valid_cadences,
            "lebesgue_coverage_days": self.lebesgue_coverage_days,
            "temporal_coverage_fraction": self.temporal_coverage_fraction,
            "is_adequate_interior": self.is_adequate_interior,
            "is_adequate_boundary": self.is_adequate_boundary,
            "exclusion_reason": self.exclusion_reason,
        }


@dataclass
class CandidateCatalogMatch:
    """
    Per-candidate matching result against catalog ephemeris (GATE-01, GATE-04, GATE-12).
    """
    candidate_id: str
    target_id: str
    catalog_planet_id: str
    detected_period: float
    catalog_period: float
    period_ratio: float
    nearest_accepted_ratio: Optional[float]
    relative_period_error: float
    is_period_match: bool
    harmonic_class: HarmonicClass
    detected_epoch: float
    catalog_epoch: float
    epoch_residual_days: float
    circular_phase_difference: float
    allowed_epoch_tolerance_days: float
    is_epoch_match: bool
    match_status: MatchStatus
    catalog_duration_days: float
    catalog_timing_uncertainty_days: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "target_id": self.target_id,
            "catalog_planet_id": self.catalog_planet_id,
            "detected_period": self.detected_period,
            "catalog_period": self.catalog_period,
            "period_ratio": self.period_ratio,
            "nearest_accepted_ratio": self.nearest_accepted_ratio,
            "relative_period_error": self.relative_period_error,
            "is_period_match": self.is_period_match,
            "harmonic_class": self.harmonic_class.value,
            "detected_epoch": self.detected_epoch,
            "catalog_epoch": self.catalog_epoch,
            "epoch_residual_days": self.epoch_residual_days,
            "circular_phase_difference": self.circular_phase_difference,
            "allowed_epoch_tolerance_days": self.allowed_epoch_tolerance_days,
            "is_epoch_match": self.is_epoch_match,
            "match_status": self.match_status.value,
            "catalog_duration_days": self.catalog_duration_days,
            "catalog_timing_uncertainty_days": self.catalog_timing_uncertainty_days,
            "metadata": self.metadata,
        }


def compute_epoch_tolerance(
    duration_days: float,
    timing_uncertainty_days: float
) -> float:
    """
    Compute bounded composite epoch matching tolerance under approved GATE-12 Option C:

    Delta t0_tol = min(
        0.50 * T_dur,
        sqrt((0.25 * T_dur)^2 + (3 * sigma_tmid)^2)
    )

    Parameters
    ----------
    duration_days : float
        Transit duration in days (T_dur). Must be positive and finite.
    timing_uncertainty_days : float
        Mid-transit timing uncertainty in days (sigma_tmid). Must be non-negative and finite.

    Returns
    -------
    float
        Allowed epoch tolerance in days. Returns NaN if parameters are invalid.
    """
    if (not np.isfinite(duration_days) or duration_days <= 0 or
            not np.isfinite(timing_uncertainty_days) or timing_uncertainty_days < 0):
        return float("nan")

    normative_core = 0.25 * duration_days
    uncertainty_term = 3.0 * timing_uncertainty_days
    quadrature = math.sqrt(normative_core**2 + uncertainty_term**2)
    physical_cap = 0.50 * duration_days

    return min(physical_cap, quadrature)


def compute_circular_epoch_residual(
    detected_epoch: float,
    catalog_epoch: float,
    period_days: float
) -> Tuple[float, float]:
    """
    Compute circular phase difference and time-domain epoch residual.

    Parameters
    ----------
    detected_epoch : float
        Detected transit center time t_0,det in days (BTJD/BJD).
    catalog_epoch : float
        Catalog reference mid-transit time t_0,cat in days.
    period_days : float
        Orbital period in days over which phase is folded.

    Returns
    -------
    Tuple[float, float]
        (epoch_residual_days, circular_phase_diff)
        - circular_phase_diff in [0, 0.5]
        - epoch_residual_days = circular_phase_diff * period_days
    """
    if (not np.isfinite(detected_epoch) or not np.isfinite(catalog_epoch) or
            not np.isfinite(period_days) or period_days <= 0):
        return float("nan"), float("nan")

    delta_t = detected_epoch - catalog_epoch
    phase_frac = (delta_t % period_days) / period_days
    circ_phase = min(phase_frac, 1.0 - phase_frac)
    epoch_residual = circ_phase * period_days

    return epoch_residual, circ_phase


def evaluate_event_coverage(
    time_array: np.ndarray,
    catalog_t0: float,
    catalog_period: float,
    catalog_duration_hours: float,
    cadence_sec: float = 120.0,
    min_temporal_coverage_primary: float = 0.50,
    min_valid_cadences_primary: int = 5,
    min_temporal_coverage_boundary: float = 0.30,
    min_valid_cadences_boundary: int = 3
) -> List[EventCoverageRecord]:
    """
    Evaluate transit event window coverage under approved GATE-03 Option 2 policy.

    Parameters
    ----------
    time_array : np.ndarray
        Array of observation timestamps (must be sorted in increasing order).
    catalog_t0 : float
        Reference mid-transit epoch in days (BTJD).
    catalog_period : float
        Orbital period in days.
    catalog_duration_hours : float
        Transit duration in hours.
    cadence_sec : float
        Exposure time / cadence duration in seconds (default 120s for TESS SPOC).
    min_temporal_coverage_primary : float
        Minimum continuous coverage fraction for primary interior events (approved 0.50).
    min_valid_cadences_primary : int
        Minimum valid cadences for primary interior events (approved 5).
    min_temporal_coverage_boundary : float
        Minimum coverage fraction for secondary boundary track (approved 0.30).
    min_valid_cadences_boundary : int
        Minimum valid cadences for secondary boundary track (approved 3).

    Returns
    -------
    List[EventCoverageRecord]
        List of coverage records for all predicted transit windows intersecting the observation span.
    """
    time_clean = np.asarray(time_array, dtype=float)
    time_clean = time_clean[np.isfinite(time_clean)]
    if len(time_clean) == 0 or catalog_period <= 0 or catalog_duration_hours <= 0:
        return []

    t_exp_days = cadence_sec / 86400.0
    t_dur_days = catalog_duration_hours / 24.0

    t_base_min = float(time_clean[0] - 0.5 * t_exp_days)
    t_base_max = float(time_clean[-1] + 0.5 * t_exp_days)

    # Determine index range of transits crossing the observation span
    k_min = math.floor((t_base_min - catalog_t0 - 0.5 * t_dur_days) / catalog_period)
    k_max = math.ceil((t_base_max - catalog_t0 + 0.5 * t_dur_days) / catalog_period)

    records: List[EventCoverageRecord] = []

    for k in range(k_min, k_max + 1):
        t_mid_k = catalog_t0 + k * catalog_period
        w_start = t_mid_k - 0.5 * t_dur_days
        w_end = t_mid_k + 0.5 * t_dur_days

        # Check if window intersects observational baseline at all
        if w_end < t_base_min or w_start > t_base_max:
            continue

        # Check interior vs boundary
        is_interior = bool(w_start >= t_base_min and w_end <= t_base_max)
        is_boundary = not is_interior

        # Continuous-interval Lebesgue measure computation:
        # Each valid exposure is I_i = [t_i - dt/2, t_i + dt/2].
        # Intersection with [w_start, w_end]:
        # [max(t_i - dt/2, w_start), min(t_i + dt/2, w_end)]
        # Sum length over all valid cadences.
        exp_starts = time_clean - 0.5 * t_exp_days
        exp_ends = time_clean + 0.5 * t_exp_days

        inter_starts = np.maximum(exp_starts, w_start)
        inter_ends = np.minimum(exp_ends, w_end)
        lengths = np.maximum(0.0, inter_ends - inter_starts)

        lebesgue_days = float(np.sum(lengths))
        temporal_frac = min(1.0, float(lebesgue_days / t_dur_days))

        # Cadences intersecting the window
        n_valid = int(np.sum(lengths > 0))

        # Primary interior adequacy
        is_adequate_interior = bool(
            is_interior and
            (temporal_frac >= min_temporal_coverage_primary) and
            (n_valid >= min_valid_cadences_primary)
        )

        # Boundary adequacy (secondary track)
        is_adequate_boundary = bool(
            is_boundary and
            (temporal_frac >= min_temporal_coverage_boundary) and
            (n_valid >= min_valid_cadences_boundary)
        )

        exclusion_reason = None
        if not is_adequate_interior and not is_adequate_boundary:
            reasons = []
            if is_interior:
                if temporal_frac < min_temporal_coverage_primary:
                    reasons.append(f"temporal_cov_{temporal_frac:.2f}_lt_{min_temporal_coverage_primary}")
                if n_valid < min_valid_cadences_primary:
                    reasons.append(f"n_valid_{n_valid}_lt_{min_valid_cadences_primary}")
            else:
                reasons.append("boundary_truncated")
                if temporal_frac < min_temporal_coverage_boundary:
                    reasons.append(f"temporal_cov_{temporal_frac:.2f}_lt_{min_temporal_coverage_boundary}")
                if n_valid < min_valid_cadences_boundary:
                    reasons.append(f"n_valid_{n_valid}_lt_{min_valid_cadences_boundary}")
            exclusion_reason = "; ".join(reasons)

        records.append(EventCoverageRecord(
            event_index=k,
            t_mid=t_mid_k,
            duration_days=t_dur_days,
            window_start=w_start,
            window_end=w_end,
            t_base_min=t_base_min,
            t_base_max=t_base_max,
            is_interior=is_interior,
            is_boundary_truncated=is_boundary,
            n_valid_cadences=n_valid,
            lebesgue_coverage_days=lebesgue_days,
            temporal_coverage_fraction=temporal_frac,
            is_adequate_interior=is_adequate_interior,
            is_adequate_boundary=is_adequate_boundary,
            exclusion_reason=exclusion_reason
        ))

    return records


class RealDataBenchmarkScorer:
    """
    Formal Benchmark Scoring Engine for Real TESS Light Curves.

    Enforces:
    - Fixed 1.0% relative period recovery tolerance (GATE-01).
    - Narrow harmonic multipliers {0.5, 1.0, 2.0} (GATE-04).
    - Bounded composite epoch matching tolerance (GATE-12 Option C).
    - One-to-one candidate-to-catalog-planet matching (GATE-12).
    - Separate accounting for fundamental recovery, harmonic recovery, period-only match, and control FP rate.
    """

    def __init__(
        self,
        period_tolerance: float = 0.01,
        accepted_harmonic_ratios: Sequence[float] = (0.5, 1.0, 2.0),
        require_one_to_one: bool = True
    ):
        self.period_tolerance = period_tolerance
        self.accepted_harmonic_ratios = tuple(accepted_harmonic_ratios)
        self.require_one_to_one = require_one_to_one

    def match_candidate(
        self,
        detected_period: float,
        detected_epoch: float,
        catalog_period: float,
        catalog_epoch: float,
        catalog_duration_hours: float,
        catalog_timing_uncertainty_days: float,
        candidate_id: str = "cand_0",
        target_id: str = "target_0",
        catalog_planet_id: str = "planet_b"
    ) -> CandidateCatalogMatch:
        """
        Evaluate single candidate against catalog ephemeris.
        """
        # Validate input ephemeris
        dur_days = catalog_duration_hours / 24.0 if catalog_duration_hours is not None else float("nan")
        sigma_tmid = catalog_timing_uncertainty_days if catalog_timing_uncertainty_days is not None else float("nan")

        if (not np.isfinite(catalog_period) or catalog_period <= 0 or
                not np.isfinite(dur_days) or dur_days <= 0 or
                not np.isfinite(sigma_tmid) or sigma_tmid < 0 or
                not np.isfinite(detected_period) or detected_period <= 0):
            return CandidateCatalogMatch(
                candidate_id=candidate_id,
                target_id=target_id,
                catalog_planet_id=catalog_planet_id,
                detected_period=detected_period,
                catalog_period=catalog_period,
                period_ratio=float("nan"),
                nearest_accepted_ratio=None,
                relative_period_error=float("nan"),
                is_period_match=False,
                harmonic_class=HarmonicClass.NON_MATCH,
                detected_epoch=detected_epoch,
                catalog_epoch=catalog_epoch,
                epoch_residual_days=float("nan"),
                circular_phase_difference=float("nan"),
                allowed_epoch_tolerance_days=float("nan"),
                is_epoch_match=False,
                match_status=MatchStatus.INVALID_EPHEMERIS,
                catalog_duration_days=dur_days,
                catalog_timing_uncertainty_days=sigma_tmid,
                metadata={"error": "Invalid or missing catalog ephemeris"}
            )

        # 1. Period matching across accepted ratios
        effective_tol = self.period_tolerance + 100 * math.ulp(self.period_tolerance) if self.period_tolerance > 0 else 0.0
        best_ratio = None
        min_rel_err = float("inf")

        for r in self.accepted_harmonic_ratios:
            target_p = catalog_period * r
            rel_err = abs(detected_period - target_p) / target_p
            if rel_err < min_rel_err:
                min_rel_err = rel_err
                best_ratio = r

        is_period_match = bool(min_rel_err <= effective_tol)
        ratio_actual = detected_period / catalog_period

        # Classify harmonic
        if is_period_match:
            if math.isclose(best_ratio, 1.0, rel_tol=1e-5):
                h_class = HarmonicClass.FUNDAMENTAL
            elif math.isclose(best_ratio, 0.5, rel_tol=1e-5):
                h_class = HarmonicClass.SUBHARMONIC
            elif math.isclose(best_ratio, 2.0, rel_tol=1e-5):
                h_class = HarmonicClass.HARMONIC
            else:
                h_class = HarmonicClass.NON_MATCH
        else:
            h_class = HarmonicClass.NON_MATCH

        # 2. Epoch matching tolerance under GATE-12 Option C
        tol_days = compute_epoch_tolerance(dur_days, sigma_tmid)

        # Fold at catalog period (or tested harmonic period)
        fold_period = catalog_period * (best_ratio if best_ratio is not None else 1.0)
        epoch_res_days, circ_phase = compute_circular_epoch_residual(
            detected_epoch=detected_epoch,
            catalog_epoch=catalog_epoch,
            period_days=fold_period
        )

        is_epoch_match = bool(np.isfinite(epoch_res_days) and (epoch_res_days <= tol_days + 100 * math.ulp(tol_days)))

        # 3. Overall match status
        if is_period_match and is_epoch_match:
            status = MatchStatus.FULL_RECOVERY
        elif is_period_match and not is_epoch_match:
            status = MatchStatus.PERIOD_ONLY
        elif not is_period_match and is_epoch_match:
            status = MatchStatus.EPOCH_ONLY
        else:
            status = MatchStatus.REJECTED

        return CandidateCatalogMatch(
            candidate_id=candidate_id,
            target_id=target_id,
            catalog_planet_id=catalog_planet_id,
            detected_period=detected_period,
            catalog_period=catalog_period,
            period_ratio=ratio_actual,
            nearest_accepted_ratio=best_ratio,
            relative_period_error=min_rel_err,
            is_period_match=is_period_match,
            harmonic_class=h_class,
            detected_epoch=detected_epoch,
            catalog_epoch=catalog_epoch,
            epoch_residual_days=epoch_res_days,
            circular_phase_difference=circ_phase,
            allowed_epoch_tolerance_days=tol_days,
            is_epoch_match=is_epoch_match,
            match_status=status,
            catalog_duration_days=dur_days,
            catalog_timing_uncertainty_days=sigma_tmid
        )

    def match_candidates_one_to_one(
        self,
        candidates: Sequence[Dict[str, Any]],
        catalog_planets: Sequence[Dict[str, Any]],
        target_id: str
    ) -> List[CandidateCatalogMatch]:
        """
        Match detected candidates against catalog planets with strict one-to-one constraint.

        One candidate cannot recover multiple planets, and one planet cannot be recovered
        by multiple candidates. Prioritizes FULL_RECOVERY over PERIOD_ONLY, then lowest
        joint relative error.
        """
        if not candidates or not catalog_planets:
            return []

        # Compute pairwise match objects
        pair_matches: List[Tuple[float, CandidateCatalogMatch]] = []
        for c in candidates:
            c_id = str(c.get("candidate_id", "cand"))
            det_p = float(c["detected_period"])
            det_t0 = float(c["detected_epoch"])

            for p in catalog_planets:
                p_id = str(p.get("planet_id", p.get("planet_name", "planet")))
                cat_p = float(p["period_days"])
                cat_t0 = float(p["t0_bjd"])
                cat_dur = float(p["duration_hours"])
                cat_sig = float(p.get("t0_err", 0.001))

                m = self.match_candidate(
                    detected_period=det_p,
                    detected_epoch=det_t0,
                    catalog_period=cat_p,
                    catalog_epoch=cat_t0,
                    catalog_duration_hours=cat_dur,
                    catalog_timing_uncertainty_days=cat_sig,
                    candidate_id=c_id,
                    target_id=target_id,
                    catalog_planet_id=p_id
                )

                # Priority score for greedy assignment:
                # 0 for FULL_RECOVERY, 1 for PERIOD_ONLY, 2 for EPOCH_ONLY, 3 for REJECTED
                status_penalty = {
                    MatchStatus.FULL_RECOVERY: 0.0,
                    MatchStatus.PERIOD_ONLY: 100.0,
                    MatchStatus.EPOCH_ONLY: 200.0,
                    MatchStatus.REJECTED: 300.0,
                    MatchStatus.INVALID_EPHEMERIS: 400.0
                }.get(m.match_status, 500.0)

                priority = status_penalty + (m.relative_period_error if np.isfinite(m.relative_period_error) else 10.0)
                pair_matches.append((priority, m))

        # Sort pairs by best match quality
        pair_matches.sort(key=lambda x: x[0])

        assigned_cands: Set[str] = set()
        assigned_planets: Set[str] = set()
        final_matches: List[CandidateCatalogMatch] = []

        for _, match_obj in pair_matches:
            if match_obj.candidate_id in assigned_cands:
                continue
            if match_obj.catalog_planet_id in assigned_planets:
                continue

            assigned_cands.add(match_obj.candidate_id)
            assigned_planets.add(match_obj.catalog_planet_id)
            final_matches.append(match_obj)

        return final_matches
