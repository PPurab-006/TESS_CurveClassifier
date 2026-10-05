"""
Script to execute approved Experiment 2 for GATE-11:
Periodogram SDE Background & Peak-Exclusion Method Comparison.

Compares:
- Option A: All-finite frequency bins unclipped (parametric mean/std).
- Option B: Fundamental peak-excluded (E_0 = [f_0 - 3*df, f_0 + 3*df]) robust normalized MAD.
- Option C: Composite alias-aware union mask E = E_0 U (U_h E_h) U (U_s E_s) robust normalized MAD.
- Option D: Iterative 3-sigma clipped parametric mean/std.

Executes paired evaluations on:
1. Designated Experiment 2 Sector 1 pilot cohort (5 hosts + 5 comparison stars).
2. Stage 2 validated cohort (100 targets) for full-distribution diagnostic robustness.
"""
import argparse
import hashlib
import json
import logging
import os
import platform
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

import astropy
import numpy as np
import pandas as pd
from astropy.timeseries import BoxLeastSquares

from tess_benchmark.baselines.bls import BLSDetector
from tess_benchmark.baselines.sde import compute_sde, SDEResult
from tess_benchmark.data.tess_loader import TESSDataLoader, compute_file_sha256
from tess_benchmark.data.protocol import TargetCategory, LightCurveData

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("run_experiment_2_sde")


def run_experiment_2(
    pilot_manifest_path: str = "results/real_data_pilot/stage1/stage1_run_summary.json",
    stage2_manifest_path: str = "results/real_data_stage2/stage2_final_cohort_manifest.csv",
    output_dir: str = "results/experiment_2_sde_comparison",
    include_stage2_cohort: bool = True
) -> Dict[str, Any]:
    """Execute Experiment 2 paired comparison."""
    t_start = time.perf_counter()
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    software_versions = {
        "python": platform.python_version(),
        "astropy": astropy.__version__,
        "numpy": np.__version__,
        "platform": platform.platform(),
    }

    # Load pilot manifest / targets
    loader = TESSDataLoader()
    pilot_targets = []
    # Pilot Sector 1 files
    pilot_dir = Path("data/raw/real_tess_pilot")
    pilot_fits = sorted(list(pilot_dir.glob("**/*.fits")))
    logger.info(f"Found {len(pilot_fits)} pilot FITS files in {pilot_dir}")

    # Process targets
    records: List[Dict[str, Any]] = []

    # 1. Evaluate Pilot cohort
    for f in pilot_fits:
        lc = loader.load_fits_file(f)
        cleaned = lc.clean()
        time_arr = cleaned.time
        flux_arr = cleaned.flux
        err_arr = cleaned.flux_err
        file_hash = compute_file_sha256(f)

        # Approved primary BLS settings
        t_base = time_arr[-1] - time_arr[0]
        max_p = min(15.0, t_base * 0.95)
        dur_grid = np.linspace(0.04, 0.35, 8)
        model = BoxLeastSquares(time_arr, flux_arr, dy=err_arr)

        t_search_start = time.perf_counter()
        periodogram = model.autopower(
            duration=dur_grid,
            minimum_period=0.5,
            maximum_period=max_p,
            frequency_factor=5.0
        )
        search_runtime = time.perf_counter() - t_search_start

        power = periodogram.power
        periods = periodogram.period

        # Evaluate SDE under all four options
        res_a = compute_sde(power, periods, method="option_a")
        res_b = compute_sde(power, periods, method="option_b")
        res_c = compute_sde(power, periods, method="option_c")
        res_d = compute_sde(power, periods, method="option_d")

        records.append({
            "cohort": "pilot_sector_1",
            "target_id": lc.target_id,
            "category": lc.category.value if hasattr(lc.category, "value") else str(lc.category),
            "fits_file": f.name,
            "sha256": file_hash,
            "n_cadences": len(time_arr),
            "baseline_days": float(t_base),
            "search_runtime_sec": float(search_runtime),
            "peak_period": float(res_a.peak_period),
            "peak_freq": float(res_a.peak_frequency),
            "max_power": float(res_a.max_power),
            "df": float(res_a.df),
            # Option A
            "sde_opt_a": float(res_a.sde),
            "mean_opt_a": float(res_a.background_mean),
            "disp_opt_a": float(res_a.background_dispersion),
            "deg_opt_a": bool(res_a.sde_degenerate),
            # Option B
            "sde_opt_b": float(res_b.sde),
            "mean_opt_b": float(res_b.background_mean),
            "disp_opt_b": float(res_b.background_dispersion),
            "deg_opt_b": bool(res_b.sde_degenerate),
            "mask_frac_opt_b": float(res_b.mask_fraction),
            # Option C
            "sde_opt_c": float(res_c.sde),
            "mean_opt_c": float(res_c.background_mean),
            "disp_opt_c": float(res_c.background_dispersion),
            "deg_opt_c": bool(res_c.sde_degenerate),
            "mad_zero_opt_c": bool(res_c.mad_zero),
            "mask_frac_opt_c": float(res_c.mask_fraction),
            # Option D
            "sde_opt_d": float(res_d.sde),
            "mean_opt_d": float(res_d.background_mean),
            "disp_opt_d": float(res_d.background_dispersion),
            "deg_opt_d": bool(res_d.sde_degenerate),
            "mask_frac_opt_d": float(res_d.mask_fraction),
        })

    # 2. Evaluate Stage 2 Cohort if available and requested
    if include_stage2_cohort and Path(stage2_manifest_path).exists():
        df_s2 = pd.read_csv(stage2_manifest_path)
        logger.info(f"Evaluating {len(df_s2)} targets from Stage 2 manifest...")
        for _, row in df_s2.iterrows():
            fname = row["fits_filename"]
            # Look for file in raw_dir
            found_paths = list(Path("data/raw/real_tess_stage2").glob(f"**/{fname}"))
            if not found_paths:
                found_paths = list(Path("data/raw/real_tess_pilot").glob(f"**/{fname}"))
            if not found_paths:
                continue

            f = found_paths[0]
            try:
                lc = loader.load_fits_file(f)
            except Exception as e:
                logger.warning(f"Could not load {f}: {e}")
                continue

            cleaned = lc.clean()
            time_arr = cleaned.time
            flux_arr = cleaned.flux
            err_arr = cleaned.flux_err
            file_hash = str(row.get("sha256", ""))

            t_base = time_arr[-1] - time_arr[0]
            max_p = min(15.0, t_base * 0.95)
            dur_grid = np.linspace(0.04, 0.35, 8)
            model = BoxLeastSquares(time_arr, flux_arr, dy=err_arr)

            t_search_start = time.perf_counter()
            periodogram = model.autopower(
                duration=dur_grid,
                minimum_period=0.5,
                maximum_period=max_p,
                frequency_factor=5.0
            )
            search_runtime = time.perf_counter() - t_search_start

            power = periodogram.power
            periods = periodogram.period

            res_a = compute_sde(power, periods, method="option_a")
            res_b = compute_sde(power, periods, method="option_b")
            res_c = compute_sde(power, periods, method="option_c")
            res_d = compute_sde(power, periods, method="option_d")

            records.append({
                "cohort": "stage2_validated",
                "target_id": lc.target_id,
                "category": lc.category.value if hasattr(lc.category, "value") else str(lc.category),
                "fits_file": f.name,
                "sha256": file_hash,
                "n_cadences": len(time_arr),
                "baseline_days": float(t_base),
                "search_runtime_sec": float(search_runtime),
                "peak_period": float(res_a.peak_period),
                "peak_freq": float(res_a.peak_frequency),
                "max_power": float(res_a.max_power),
                "df": float(res_a.df),
                # Option A
                "sde_opt_a": float(res_a.sde),
                "mean_opt_a": float(res_a.background_mean),
                "disp_opt_a": float(res_a.background_dispersion),
                "deg_opt_a": bool(res_a.sde_degenerate),
                # Option B
                "sde_opt_b": float(res_b.sde),
                "mean_opt_b": float(res_b.background_mean),
                "disp_opt_b": float(res_b.background_dispersion),
                "deg_opt_b": bool(res_b.sde_degenerate),
                "mask_frac_opt_b": float(res_b.mask_fraction),
                # Option C
                "sde_opt_c": float(res_c.sde),
                "mean_opt_c": float(res_c.background_mean),
                "disp_opt_c": float(res_c.background_dispersion),
                "deg_opt_c": bool(res_c.sde_degenerate),
                "mad_zero_opt_c": bool(res_c.mad_zero),
                "mask_frac_opt_c": float(res_c.mask_fraction),
                # Option D
                "sde_opt_d": float(res_d.sde),
                "mean_opt_d": float(res_d.background_mean),
                "disp_opt_d": float(res_d.background_dispersion),
                "deg_opt_d": bool(res_d.sde_degenerate),
                "mask_frac_opt_d": float(res_d.mask_fraction),
            })

    df_records = pd.DataFrame(records)
    csv_out = out_path / "experiment_2_sde_paired_predictions.csv"
    df_records.to_csv(csv_out, index=False)
    logger.info(f"Saved paired predictions to {csv_out}")

    # Compute aggregate statistics
    pilot_df = df_records[df_records["cohort"] == "pilot_sector_1"]
    summary: Dict[str, Any] = {
        "execution_date_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "total_runtime_sec": time.perf_counter() - t_start,
        "software_versions": software_versions,
        "n_pilot_targets": len(pilot_df),
        "n_total_evaluated": len(df_records),
        "pilot_summary": {
            "mean_sde_opt_a": float(pilot_df["sde_opt_a"].mean()),
            "mean_sde_opt_b": float(pilot_df["sde_opt_b"].mean()),
            "mean_sde_opt_c": float(pilot_df["sde_opt_c"].mean()),
            "mean_sde_opt_d": float(pilot_df["sde_opt_d"].mean()),
            "median_sde_opt_a": float(pilot_df["sde_opt_a"].median()),
            "median_sde_opt_b": float(pilot_df["sde_opt_b"].median()),
            "median_sde_opt_c": float(pilot_df["sde_opt_c"].median()),
            "median_sde_opt_d": float(pilot_df["sde_opt_d"].median()),
            "mean_mask_fraction_opt_c": float(pilot_df["mask_frac_opt_c"].mean()),
            "degenerate_count_opt_c": int(pilot_df["deg_opt_c"].sum()),
            "mad_zero_count_opt_c": int(pilot_df["mad_zero_opt_c"].sum()),
        },
        "artifacts": {
            "paired_predictions_csv": str(csv_out),
        }
    }

    if len(df_records) > len(pilot_df):
        s2_df = df_records[df_records["cohort"] == "stage2_validated"]
        summary["stage2_summary"] = {
            "n_stage2_targets": len(s2_df),
            "mean_sde_opt_a": float(s2_df["sde_opt_a"].mean()),
            "mean_sde_opt_b": float(s2_df["sde_opt_b"].mean()),
            "mean_sde_opt_c": float(s2_df["sde_opt_c"].mean()),
            "mean_sde_opt_d": float(s2_df["sde_opt_d"].mean()),
            "median_sde_opt_a": float(s2_df["sde_opt_a"].median()),
            "median_sde_opt_b": float(s2_df["sde_opt_b"].median()),
            "median_sde_opt_c": float(s2_df["sde_opt_c"].median()),
            "median_sde_opt_d": float(s2_df["sde_opt_d"].median()),
            "mean_mask_fraction_opt_c": float(s2_df["mask_frac_opt_c"].mean()),
            "degenerate_count_opt_c": int(s2_df["deg_opt_c"].sum()),
            "mad_zero_count_opt_c": int(s2_df["mad_zero_opt_c"].sum()),
        }

    json_out = out_path / "experiment_2_sde_summary.json"
    with open(json_out, "w") as fp:
        json.dump(summary, fp, indent=2)
    logger.info(f"Saved summary JSON to {json_out}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Experiment 2 SDE Comparison")
    parser.add_argument("--outdir", default="results/experiment_2_sde_comparison")
    parser.add_argument("--pilot-only", action="store_true")
    args = parser.parse_args()

    res = run_experiment_2(
        output_dir=args.outdir,
        include_stage2_cohort=not args.pilot_only
    )
    print("Experiment 2 complete!")
    print(json.dumps(res, indent=2))
