"""
Reproducible Real-TESS Ingestion and Quality Assurance Pilot Runner.

Executes Phase 3 and Phase 4 of the Real-Data Pilot Protocol:
- Acquires authentic TESS SPOC 2-minute light curves from NASA MAST.
- Preserves raw unmodified FITS products in data/raw/real_tess_pilot/.
- Ingests and performs rigorous quality-assurance auditing.
- Computes transit ephemeris overlap for confirmed planet hosts.
- Generates publication-quality diagnostic plots.
- Exports structured manifests, inventory, and QA summaries.
"""
from pathlib import Path
from typing import Dict, Any, List
import json
import pickle
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from tess_benchmark.data.protocol import TargetCategory, LightCurveData
from tess_benchmark.data.tess_loader import TESSDataLoader, compute_file_sha256


# ---------------------------------------------------------------------------
# Pilot Target Definitions
# ---------------------------------------------------------------------------

TARGET_COHORT: List[Dict[str, Any]] = [
    # Confirmed Planet Hosts (N = 5)
    # Verified against NASA Exoplanet Archive (TOI Table, Sector 1 SPOC pipeline fits)
    {
        "target_name": "WASP-126",
        "tic_id": 25155310,
        "category": TargetCategory.CONFIRMED_PLANET_HOST,
        "sector": 1,
        "cadence_sec": 120,
        "author": "SPOC",
        "flux_column": "pdcsap_flux",
        "has_transit_label": True,
        "planet_name": "WASP-126 b",
        "toi_id": "TOI-114.01",
        "period_days": 3.2887898,
        "period_err": 3.0e-7,
        "t0_bjd": 2458327.519958,
        "t0_err": 6.1e-5,
        "duration_hours": 3.436772,
        "duration_err": 0.009988,
        "depth_ppm": 7005.72,
        "ephemeris_source": "NASA Exoplanet Archive (TOI Table, Sector 1 SPOC fit)",
        "notes": "Known transiting hot Jupiter; deep ~0.7% transit."
    },
    {
        "target_name": "WASP-46",
        "tic_id": 231663901,
        "category": TargetCategory.CONFIRMED_PLANET_HOST,
        "sector": 1,
        "cadence_sec": 120,
        "author": "SPOC",
        "flux_column": "pdcsap_flux",
        "has_transit_label": True,
        "planet_name": "WASP-46 b",
        "toi_id": "TOI-101.01",
        "period_days": 1.4303699,
        "period_err": 8.0e-7,
        "t0_bjd": 2458326.009117,
        "t0_err": 0.000132,
        "duration_hours": 1.616599,
        "duration_err": 0.019209,
        "depth_ppm": 18960.71,
        "ephemeris_source": "NASA Exoplanet Archive (TOI Table, Sector 1 SPOC fit)",
        "notes": "Known transiting hot Jupiter; very deep ~1.9% transit."
    },
    {
        "target_name": "WASP-91",
        "tic_id": 238176110,
        "category": TargetCategory.CONFIRMED_PLANET_HOST,
        "sector": 1,
        "cadence_sec": 120,
        "author": "SPOC",
        "flux_column": "pdcsap_flux",
        "has_transit_label": True,
        "planet_name": "WASP-91 b",
        "toi_id": "TOI-116.01",
        "period_days": 2.7985802,
        "period_err": 3.0e-7,
        "t0_bjd": 2458326.688916,
        "t0_err": 7.4e-5,
        "duration_hours": 2.380104,
        "duration_err": 0.012993,
        "depth_ppm": 16708.72,
        "ephemeris_source": "NASA Exoplanet Archive (TOI Table, Sector 1 SPOC fit)",
        "notes": "Known transiting gas giant; deep ~1.7% transit."
    },
    {
        "target_name": "LHS 3844",
        "tic_id": 410153553,
        "category": TargetCategory.CONFIRMED_PLANET_HOST,
        "sector": 1,
        "cadence_sec": 120,
        "author": "SPOC",
        "flux_column": "pdcsap_flux",
        "has_transit_label": True,
        "planet_name": "LHS 3844 b",
        "toi_id": "TOI-136.01",
        "period_days": 0.4629304,
        "period_err": 2.2e-6,
        "t0_bjd": 2458325.724125,
        "t0_err": 0.000118,
        "duration_hours": 0.540943,
        "duration_err": 0.050307,
        "depth_ppm": 4507.33,
        "ephemeris_source": "NASA Exoplanet Archive (TOI Table, Sector 1 SPOC fit)",
        "notes": "Ultra-short period terrestrial exoplanet around M dwarf; shallow transit."
    },
    {
        "target_name": "WASP-124",
        "tic_id": 97409519,
        "category": TargetCategory.CONFIRMED_PLANET_HOST,
        "sector": 1,
        "cadence_sec": 120,
        "author": "SPOC",
        "flux_column": "pdcsap_flux",
        "has_transit_label": True,
        "planet_name": "WASP-124 b",
        "toi_id": "TOI-113.01",
        "period_days": 3.372877,
        "period_err": 0.000147,
        "t0_bjd": 2458327.053085,
        "t0_err": 0.000623,
        "duration_hours": 2.634260,
        "duration_err": 0.043644,
        "depth_ppm": 17163.60,
        "ephemeris_source": "NASA Exoplanet Archive (TOI Table, Sector 1 SPOC fit)",
        "notes": "Known transiting gas giant; deep ~1.7% transit."
    },


    # Observational Comparison Targets (N = 5)
    # Field stars observed by SPOC in Sector 1 with zero TOI, TCE, or confirmed planet detections
    {
        "target_name": "TIC 265591866",
        "tic_id": 265591866,
        "category": TargetCategory.CONTROL_STAR,
        "sector": 1,
        "cadence_sec": 120,
        "author": "SPOC",
        "flux_column": "pdcsap_flux",
        "has_transit_label": False,
        "planet_name": None,
        "toi_id": None,
        "period_days": None,
        "period_err": None,
        "t0_bjd": None,
        "t0_err": None,
        "duration_hours": None,
        "duration_err": None,
        "depth_ppm": None,
        "ephemeris_source": "N/A (Observational Control)",
        "notes": "Field star in Sector 1; observational non-detection control (not claimed planet-free)."
    },
    {
        "target_name": "TIC 306573321",
        "tic_id": 306573321,
        "category": TargetCategory.CONTROL_STAR,
        "sector": 1,
        "cadence_sec": 120,
        "author": "SPOC",
        "flux_column": "pdcsap_flux",
        "has_transit_label": False,
        "planet_name": None,
        "toi_id": None,
        "period_days": None,
        "period_err": None,
        "t0_bjd": None,
        "t0_err": None,
        "duration_hours": None,
        "duration_err": None,
        "depth_ppm": None,
        "ephemeris_source": "N/A (Observational Control)",
        "notes": "Field star in Sector 1; observational non-detection control (not claimed planet-free)."
    },
    {
        "target_name": "TIC 277891181",
        "tic_id": 277891181,
        "category": TargetCategory.CONTROL_STAR,
        "sector": 1,
        "cadence_sec": 120,
        "author": "SPOC",
        "flux_column": "pdcsap_flux",
        "has_transit_label": False,
        "planet_name": None,
        "toi_id": None,
        "period_days": None,
        "period_err": None,
        "t0_bjd": None,
        "t0_err": None,
        "duration_hours": None,
        "duration_err": None,
        "depth_ppm": None,
        "ephemeris_source": "N/A (Observational Control)",
        "notes": "Field star in Sector 1; observational non-detection control (not claimed planet-free)."
    },
    {
        "target_name": "TIC 370041901",
        "tic_id": 370041901,
        "category": TargetCategory.CONTROL_STAR,
        "sector": 1,
        "cadence_sec": 120,
        "author": "SPOC",
        "flux_column": "pdcsap_flux",
        "has_transit_label": False,
        "planet_name": None,
        "toi_id": None,
        "period_days": None,
        "period_err": None,
        "t0_bjd": None,
        "t0_err": None,
        "duration_hours": None,
        "duration_err": None,
        "depth_ppm": None,
        "ephemeris_source": "N/A (Observational Control)",
        "notes": "Field star in Sector 1; observational non-detection control (not claimed planet-free)."
    },
    {
        "target_name": "TIC 197712257",
        "tic_id": 197712257,
        "category": TargetCategory.CONTROL_STAR,
        "sector": 1,
        "cadence_sec": 120,
        "author": "SPOC",
        "flux_column": "pdcsap_flux",
        "has_transit_label": False,
        "planet_name": None,
        "toi_id": None,
        "period_days": None,
        "period_err": None,
        "t0_bjd": None,
        "t0_err": None,
        "duration_hours": None,
        "duration_err": None,
        "depth_ppm": None,
        "ephemeris_source": "N/A (Observational Control)",
        "notes": "Field star in Sector 1; observational non-detection control (not claimed planet-free)."
    }
]


def plot_pilot_lightcurve(
    lc: LightCurveData,
    target_info: Dict[str, Any],
    overlap_info: Dict[str, Any],
    output_path: Path
) -> None:
    """Generate diagnostic visualization of raw vs normalized flux and data gaps."""
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)

    t_valid = lc.time[lc.valid_indices]
    f_valid_raw = lc.raw_flux[lc.valid_indices] if lc.raw_flux is not None else lc.flux[lc.valid_indices]
    f_valid_norm = lc.flux[lc.valid_indices]

    # Panel 1: Raw Unnormalized Flux with Quality-Flagged / Missing cadences indicated
    ax0 = axes[0]
    # Plot flagged cadences if any
    flagged = (~lc.quality_mask) & np.isfinite(lc.time) & np.isfinite(lc.raw_flux if lc.raw_flux is not None else lc.flux)
    if np.sum(flagged) > 0:
        ax0.scatter(
            lc.time[flagged],
            (lc.raw_flux[flagged] if lc.raw_flux is not None else lc.flux[flagged]),
            color="#d9534f",
            s=8,
            alpha=0.6,
            label=f"Quality Flagged (N={np.sum(flagged)})"
        )

    ax0.scatter(
        t_valid,
        f_valid_raw,
        color="#2c3e50",
        s=3,
        alpha=0.7,
        label=f"Valid Cadences (N={len(t_valid)})"
    )
    ax0.set_ylabel(f"Raw Flux ({lc.metadata.get('flux_unit', 'e-/s')})", fontsize=11, fontweight="bold")
    ax0.set_title(
        f"{target_info['target_name']} (TIC {target_info['tic_id']}) — Sector {target_info['sector']} "
        f"({target_info['category'].value})",
        fontsize=13,
        fontweight="bold"
    )
    ax0.grid(True, linestyle="--", alpha=0.5)
    ax0.legend(loc="upper right", framealpha=0.9)

    # Panel 2: Normalized Flux (Continuum Median Normalized) with Predicted Transits
    ax1 = axes[1]
    ax1.scatter(t_valid, f_valid_norm, color="#16a085", s=3, alpha=0.7, label="Normalized Flux")

    # If predicted transit windows overlap, shade them
    if overlap_info.get("overlaps_transit", False):
        first_patch = True
        for td in overlap_info.get("transit_details", []):
            if td["partially_observed"]:
                ax1.axvspan(
                    td["ingress_btjd"],
                    td["egress_btjd"],
                    color="#e74c3c",
                    alpha=0.25,
                    label="Predicted Transit Window" if first_patch else None
                )
                first_patch = False
                # Annotate epoch number
                ax1.text(
                    td["t_mid_btjd"],
                    np.nanpercentile(f_valid_norm, 1.0) - 0.005,
                    f"E={td['epoch']}",
                    ha="center",
                    va="top",
                    fontsize=8,
                    color="#c0392b"
                )

    ax1.set_xlabel("Time (Barycentric TESS Julian Date, BTJD = BJD - 2457000)", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Normalized Flux", fontsize=11, fontweight="bold")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right", framealpha=0.9)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close(fig)


def run_pilot(
    raw_dir: Path = Path("data/raw/real_tess_pilot"),
    processed_dir: Path = Path("data/processed/real_tess_pilot"),
    results_dir: Path = Path("results/real_data_pilot")
) -> Dict[str, Any]:
    """Execute complete ingestion, provenance, and QA pilot."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = results_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    loader = TESSDataLoader(cache_dir=raw_dir)

    target_inventory_records: List[Dict[str, Any]] = []
    observation_manifest_records: List[Dict[str, Any]] = []
    qa_summary_list: List[Dict[str, Any]] = []
    processed_lightcurves: Dict[str, LightCurveData] = {}

    print("=" * 80)
    print("STARTING TESS REAL-DATA INGESTION AND QUALITY-ASSURANCE PILOT")
    print(f"Target count: {len(TARGET_COHORT)} (5 Confirmed Hosts, 5 Comparison Controls)")
    print(f"Raw cache: {raw_dir.resolve()}")
    print(f"Processed cache: {processed_dir.resolve()}")
    print(f"Results directory: {results_dir.resolve()}")
    print("=" * 80)

    for i, target_info in enumerate(TARGET_COHORT, start=1):
        target_name = target_info["target_name"]
        tic_id = target_info["tic_id"]
        sector = target_info["sector"]
        category = target_info["category"]
        author = target_info["author"]
        flux_column = target_info["flux_column"]

        print(f"\n[{i}/{len(TARGET_COHORT)}] Processing {target_name} (TIC {tic_id}), Sector {sector}...")

        # 1. Acquire / Download FITS from MAST
        try:
            fits_path = loader.download_fits(
                target_name=f"TIC {tic_id}",
                sector=sector,
                author=author
            )
            print(f"   -> FITS file available: {fits_path.name}")
        except Exception as e:
            print(f"   -> ERROR downloading FITS for {target_name}: {e}")
            raise RuntimeError(f"Archive retrieval failed for {target_name}: {e}")

        # 2. Ingest and Validate FITS
        retrieval_date = datetime.date.today().isoformat()
        lc = loader.load_fits_file(
            fits_path=fits_path,
            flux_column=flux_column,
            category=category,
            has_transit=target_info["has_transit_label"],
            target_name=target_name,
            retrieval_date=retrieval_date
        )

        # 3. Calculate Transit Window Overlap (if ephemeris is available)
        if target_info.get("period_days") is not None:
            overlap = loader.calculate_transit_overlap(
                time=lc.time[lc.valid_indices],
                period_days=target_info["period_days"],
                t0_bjd=target_info["t0_bjd"],
                duration_hours=target_info["duration_hours"],
                period_err=target_info.get("period_err", 0.0),
                t0_err=target_info.get("t0_err", 0.0),
                duration_err_hours=target_info.get("duration_err", 0.0)
            )
        else:
            overlap = {
                "overlaps_transit": False,
                "n_predicted_transits": 0,
                "n_windows_with_cadences": 0,
                "n_windows_full_coverage": 0,
                "n_windows_zero_cadence": 0,
                "n_observed_transits": 0,
                "predicted_midtimes_btjd": [],
                "transit_details": []
            }

        # 4. Assess Visual Apparentness (qualitative inspection based on physical SNR / depth)
        # Deep transits (> 5000 ppm) with multiple transits are visually distinct
        is_visually_apparent = False
        if overlap["overlaps_transit"] and target_info.get("depth_ppm", 0) > 5000:
            is_visually_apparent = True
        elif target_info["category"] == TargetCategory.CONTROL_STAR:
            is_visually_apparent = False

        # 5. Algorithmic Recovery Status
        # Pilot scope rule: NO detection algorithm is run in this pilot
        algo_recovery_status = "Not evaluated in pilot (no algorithm run)"

        # 6. Quality Checks Summary
        # Note: Raw SPOC FITS files assign TIME=NaN and QUALITY=8 during coarse pointing/momentum dumps.
        # Quality assurance requires that after filtering, cadences have 0 NaNs/Infs, time is strictly increasing,
        # and usable fraction exceeds 80%.
        qa_passed = bool(
            lc.metadata["n_usable_cadences"] > 10000 and
            lc.metadata["is_strictly_increasing"] and
            lc.metadata["usable_cadence_fraction"] > 0.80 and
            lc.metadata["n_nan_time_filtered"] == 0 and
            lc.metadata["n_nan_flux_filtered"] == 0 and
            lc.metadata["n_inf_flux_filtered"] == 0
        )

        qa_entry = {
            "target_name": target_name,
            "tic_id": tic_id,
            "sector": sector,
            "category": category.value,
            "fits_readable": True,
            "has_required_columns": True,
            "time_unit": lc.metadata["time_unit"],
            "flux_unit": lc.metadata["flux_unit"],
            "n_raw_cadences": lc.metadata["n_raw_cadences"],
            "n_usable_cadences": lc.metadata["n_usable_cadences"],
            "n_nan_flux_raw": lc.metadata["n_nan_flux_raw"],
            "n_nan_flux_filtered": lc.metadata["n_nan_flux_filtered"],
            "n_nan_time_raw": lc.metadata["n_nan_time_raw"],
            "n_nan_time_filtered": lc.metadata["n_nan_time_filtered"],
            "n_inf_flux": lc.metadata["n_inf_flux_filtered"],
            "n_quality_rejected": lc.metadata["n_quality_rejected"],
            "usable_cadence_fraction": round(lc.metadata["usable_cadence_fraction"], 4),
            "is_strictly_increasing": lc.metadata["is_strictly_increasing"],
            "gap_count": lc.metadata["gap_count"],
            "max_gap_days": round(lc.metadata["max_gap_days"], 4),
            "median_raw_flux": round(lc.metadata["median_raw_flux"], 2),
            "median_normalized_flux": round(float(np.nanmedian(lc.flux[lc.valid_indices])), 4),
            "duration_days": round(lc.metadata["duration_days"], 4),
            "cadence_sec": round(lc.metadata["cadence_sec"], 1),
            "overlaps_predicted_transit": overlap["overlaps_transit"],
            "n_predicted_transit_windows": overlap["n_predicted_transits"],
            "n_windows_with_cadences": overlap["n_windows_with_cadences"],
            "n_windows_full_coverage": overlap["n_windows_full_coverage"],
            "n_windows_zero_cadence": overlap["n_windows_zero_cadence"],
            "n_observed_transits": overlap["n_windows_with_cadences"],  # Legacy alias
            "is_visually_apparent": is_visually_apparent,
            "algorithmic_recovery": algo_recovery_status,
            "qa_passed": qa_passed
        }

        qa_summary_list.append(qa_entry)

        # 7. Generate diagnostic plot
        plot_path = plots_dir / f"lightcurve_TIC_{tic_id}_S{sector:02d}.png"
        plot_pilot_lightcurve(lc, target_info, overlap, plot_path)
        print(f"   -> Generated QA diagnostic plot: {plot_path.name}")

        # 8. Record in target inventory
        target_inventory_records.append({
            "target_name": target_name,
            "tic_id": tic_id,
            "category": category.value,
            "is_confirmed_host": bool(category == TargetCategory.CONFIRMED_PLANET_HOST),
            "planet_name": target_info["planet_name"] or "None",
            "toi_id": target_info["toi_id"] or "None",
            "orbital_period_days": target_info["period_days"] if target_info["period_days"] else "",
            "period_uncertainty": target_info["period_err"] if target_info["period_err"] else "",
            "t0_reference_bjd": target_info["t0_bjd"] if target_info["t0_bjd"] else "",
            "duration_hours": target_info["duration_hours"] if target_info["duration_hours"] else "",
            "depth_ppm": target_info["depth_ppm"] if target_info["depth_ppm"] else "",
            "ephemeris_source": target_info["ephemeris_source"],
            "notes": target_info["notes"]
        })

        # 9. Record in observation manifest
        observation_manifest_records.append({
            "target_name": target_name,
            "tic_id": tic_id,
            "category": category.value,
            "sector": sector,
            "cadence_sec": lc.metadata["cadence_sec"],
            "pipeline": lc.metadata["author"],
            "flux_column": lc.metadata["flux_column"],
            "tstart_btjd": round(lc.metadata["tstart"], 5),
            "tstop_btjd": round(lc.metadata["tstop"], 5),
            "duration_days": round(lc.metadata["duration_days"], 4),
            "n_raw_cadences": lc.metadata["n_raw_cadences"],
            "n_usable_cadences": lc.metadata["n_usable_cadences"],
            "n_quality_rejected": lc.metadata["n_quality_rejected"],
            "usable_cadence_fraction": round(lc.metadata["usable_cadence_fraction"], 4),
            "gap_count": lc.metadata["gap_count"],
            "max_gap_days": round(lc.metadata["max_gap_days"], 4),
            "overlaps_predicted_transit": overlap["overlaps_transit"],
            "n_predicted_transit_windows": overlap["n_predicted_transits"],
            "n_windows_with_cadences": overlap["n_windows_with_cadences"],
            "n_windows_full_coverage": overlap["n_windows_full_coverage"],
            "n_windows_zero_cadence": overlap["n_windows_zero_cadence"],
            "n_observed_transits": overlap["n_windows_with_cadences"],  # Legacy alias
            "is_visually_apparent": is_visually_apparent,
            "algorithmic_recovery": algo_recovery_status,
            "fits_filename": lc.metadata["fits_filename"],
            "file_size_bytes": lc.metadata["file_size_bytes"],
            "sha256": lc.metadata["sha256"],
            "download_source": lc.metadata["download_source"],
            "retrieval_date": lc.metadata["retrieval_date"],
            "qa_passed": qa_passed
        })

        processed_lightcurves[str(tic_id)] = lc


    # 10. Save processed objects
    processed_pkl_path = processed_dir / "pilot_light_curves.pkl"
    with open(processed_pkl_path, "wb") as f:
        pickle.dump(processed_lightcurves, f)
    print(f"\nSaved processed light curves to: {processed_pkl_path}")

    # 11. Save CSV manifests
    inventory_df = pd.DataFrame(target_inventory_records)
    inventory_path = results_dir / "target_inventory.csv"
    inventory_df.to_csv(inventory_path, index=False)
    print(f"Saved target inventory to: {inventory_path}")

    manifest_df = pd.DataFrame(observation_manifest_records)
    manifest_path = results_dir / "observation_manifest.csv"
    manifest_df.to_csv(manifest_path, index=False)
    print(f"Saved observation manifest to: {manifest_path}")

    # 12. Save QA Summary JSON
    qa_path = results_dir / "qa_summary.json"
    with open(qa_path, "w") as f:
        json.dump({
            "pilot_execution_date": datetime.date.today().isoformat(),
            "cohort_size": len(TARGET_COHORT),
            "confirmed_host_count": sum(1 for t in TARGET_COHORT if t["category"] == TargetCategory.CONFIRMED_PLANET_HOST),
            "control_target_count": sum(1 for t in TARGET_COHORT if t["category"] == TargetCategory.CONTROL_STAR),
            "qa_all_passed": all(q["qa_passed"] for q in qa_summary_list),
            "targets": qa_summary_list
        }, f, indent=2)
    print(f"Saved QA summary JSON to: {qa_path}")

    return {
        "inventory_path": inventory_path,
        "manifest_path": manifest_path,
        "qa_path": qa_path,
        "processed_pkl_path": processed_pkl_path,
        "target_count": len(TARGET_COHORT),
        "qa_all_passed": all(q["qa_passed"] for q in qa_summary_list)
    }


if __name__ == "__main__":
    run_pilot()
