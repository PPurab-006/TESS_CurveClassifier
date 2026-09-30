#!/usr/bin/env python3
"""
Paired Exploratory Comparison for GATE-04: Harmonic Set Definition.

Evaluates both candidate harmonic sets on identical BLS detections from the
authentic TESS Sector 1 pilot cohort under the approved GATE-01 1.0% tolerance:
- Option A (Broad):   {1/3, 1/2, 1, 2, 3}
- Option B (Narrow):  {1/2, 1, 2}

Outputs:
- Per-target comparison table
- Summary table across eligible confirmed planet hosts
- Structured CSV and JSON exports in results/real_data_pilot/
"""
import json
from pathlib import Path
import pickle
from typing import Dict, Any, List
import pandas as pd
import numpy as np

from tess_benchmark.baselines.bls import BLSDetector, match_period_to_harmonics
from tess_benchmark.data.protocol import TargetCategory

OPTION_A_RATIOS = (1.0 / 3.0, 0.5, 1.0, 2.0, 3.0)
OPTION_B_RATIOS = (0.5, 1.0, 2.0)
TOLERANCE = 0.01  # Approved GATE-01 fixed 1% relative tolerance


def ratio_label(ratio: float) -> str:
    """Format harmonic ratio cleanly as fraction or multiplier."""
    if ratio is None or np.isnan(ratio):
        return "N/A"
    if abs(ratio - 1.0 / 3.0) < 1e-4:
        return "1/3x"
    if abs(ratio - 0.5) < 1e-4:
        return "1/2x"
    if abs(ratio - 1.0) < 1e-4:
        return "1x (fund)"
    if abs(ratio - 2.0) < 1e-4:
        return "2x"
    if abs(ratio - 3.0) < 1e-4:
        return "3x"
    return f"{ratio:.4f}x"


def main():
    root = Path(__file__).resolve().parent.parent
    pickle_path = root / "data" / "processed" / "real_tess_pilot" / "pilot_light_curves.pkl"
    ephem_path = root / "results" / "real_data_pilot" / "ephemeris_validation.csv"
    output_dir = root / "results" / "real_data_pilot"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pickle_path.exists():
        raise FileNotFoundError(f"Pilot light curves pickle not found at {pickle_path}")

    # Load authentic pilot light curves
    with open(pickle_path, "rb") as f:
        pilot_curves = pickle.load(f)

    # Load verified ephemerides
    if ephem_path.exists():
        ephem_df = pd.read_csv(ephem_path)
        host_ephem = {
            str(row["tic_id"]): {
                "target_name": row["target_name"],
                "planet_name": row["confirmed_planet_name"],
                "catalog_period": float(row["toi_period_days"])
            }
            for _, row in ephem_df.iterrows()
        }
    else:
        # Fallback to verified catalog values from protocol
        host_ephem = {
            "25155310": {"target_name": "WASP-126", "planet_name": "WASP-126 b", "catalog_period": 3.2887898},
            "231663901": {"target_name": "WASP-46", "planet_name": "WASP-46 b", "catalog_period": 1.4303699},
            "238176110": {"target_name": "WASP-91", "planet_name": "WASP-91 b", "catalog_period": 2.7985802},
            "410153553": {"target_name": "LHS 3844", "planet_name": "LHS 3844 b", "catalog_period": 0.4629304},
            "97409519": {"target_name": "WASP-124", "planet_name": "WASP-124 b", "catalog_period": 3.372877},
        }

    # Initialize standard BLS detector (identical parameters for all targets)
    detector = BLSDetector(
        min_period=0.5,
        max_period=15.0,
        frequency_factor=5.0,
        sde_threshold=6.0,
        min_snr=5.0
    )

    per_target_records = []

    # Filter strictly to eligible confirmed planet hosts
    for tic_id, ephem in host_ephem.items():
        lc = pilot_curves.get(tic_id)
        if lc is None:
            continue
        if lc.category != TargetCategory.CONFIRMED_PLANET_HOST:
            continue

        p_catalog = ephem["catalog_period"]
        target_name = ephem["target_name"]

        # Run BLS detection ONCE to guarantee identical input detection for both options
        res = detector.search(lc)
        p_detected = res.best_period

        # Evaluate under Option A: {1/3, 1/2, 1, 2, 3}
        rec_a, ratio_a, err_a = match_period_to_harmonics(
            detected_period=p_detected,
            catalog_period=p_catalog,
            accepted_ratios=OPTION_A_RATIOS,
            tolerance=TOLERANCE
        )

        # Evaluate under Option B: {1/2, 1, 2}
        rec_b, ratio_b, err_b = match_period_to_harmonics(
            detected_period=p_detected,
            catalog_period=p_catalog,
            accepted_ratios=OPTION_B_RATIOS,
            tolerance=TOLERANCE
        )

        per_target_records.append({
            "target_identifier": f"{target_name} (TIC {tic_id})",
            "tic_id": int(tic_id),
            "target_name": target_name,
            "planet_name": ephem["planet_name"],
            "catalog_period_days": p_catalog,
            "detected_bls_period_days": p_detected,
            "bls_sde": res.sde,
            "bls_snr": res.snr,
            "bls_is_detected": res.is_detected,
            "option_a_nearest_ratio": ratio_a,
            "option_a_nearest_ratio_label": ratio_label(ratio_a),
            "option_a_relative_error": err_a,
            "option_a_recovered": rec_a,
            "option_b_nearest_ratio": ratio_b,
            "option_b_nearest_ratio_label": ratio_label(ratio_b),
            "option_b_relative_error": err_b,
            "option_b_recovered": rec_b,
        })

    # Summary calculations
    df_targets = pd.DataFrame(per_target_records)
    n_eligible = len(df_targets)
    n_rec_a = int(df_targets["option_a_recovered"].sum())
    n_rec_b = int(df_targets["option_b_recovered"].sum())
    frac_a = n_rec_a / n_eligible if n_eligible > 0 else 0.0
    frac_b = n_rec_b / n_eligible if n_eligible > 0 else 0.0

    both_recovered = df_targets[df_targets["option_a_recovered"] & df_targets["option_b_recovered"]]["target_name"].tolist()
    only_a = df_targets[df_targets["option_a_recovered"] & ~df_targets["option_b_recovered"]]["target_name"].tolist()
    only_b = df_targets[~df_targets["option_a_recovered"] & df_targets["option_b_recovered"]]["target_name"].tolist()

    summary_data = {
        "analysis": "GATE-04 Paired Harmonic Set Sensitivity Comparison",
        "scope": "Exploratory sensitivity analysis on authentic real TESS Sector 1 pilot cohort",
        "disclaimer": "Pilot cohort is exploratory (N=5 hosts); results are NOT statistically generalizable.",
        "status": "GATE-04 REMAINS PENDING RESEARCHER APPROVAL",
        "gate_01_tolerance": TOLERANCE,
        "eligible_target_count": n_eligible,
        "option_a": {
            "name": "Option A (Broad)",
            "accepted_ratios": [1/3, 0.5, 1.0, 2.0, 3.0],
            "recovered_count": n_rec_a,
            "recovered_fraction": frac_a
        },
        "option_b": {
            "name": "Option B (Narrow)",
            "accepted_ratios": [0.5, 1.0, 2.0],
            "recovered_count": n_rec_b,
            "recovered_fraction": frac_b
        },
        "recovered_both": both_recovered,
        "recovered_only_option_a": only_a,
        "recovered_only_option_b": only_b,
        "additional_recoveries_attributable_to_third_or_triple": len(only_a)
    }

    # Save exports
    csv_path = output_dir / "gate_04_harmonic_comparison.csv"
    json_path = output_dir / "gate_04_harmonic_comparison.json"
    df_targets.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(summary_data, f, indent=2)

    # Print markdown tables
    print("\n" + "=" * 80)
    print("GATE-04 PAIRED EXPLORATORY HARMONIC COMPARISON (REAL TESS PILOT)")
    print("=" * 80)
    print("\n### 1. Per-Target Comparison Table\n")
    print(
        "| Target Identifier | Catalog P (d) | Detected BLS P (d) | Option A Nearest | Option A Rel Err | Option A Rec | Option B Nearest | Option B Rel Err | Option B Rec |"
    )
    print(
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
    )
    for _, r in df_targets.iterrows():
        print(
            f"| **{r['target_identifier']}** | {r['catalog_period_days']:.6f} | {r['detected_bls_period_days']:.6f} | "
            f"{r['option_a_nearest_ratio_label']} | {r['option_a_relative_error'] * 100:.4f}% | {'YES' if r['option_a_recovered'] else 'NO'} | "
            f"{r['option_b_nearest_ratio_label']} | {r['option_b_relative_error'] * 100:.4f}% | {'YES' if r['option_b_recovered'] else 'NO'} |"
        )

    print("\n### 2. Summary Comparison Table\n")
    print("| Metric | Option A (Broad: {1/3, 1/2, 1, 2, 3}) | Option B (Narrow: {1/2, 1, 2}) |")
    print("| :--- | :---: | :---: |")
    print(f"| **Eligible Target Count** | {n_eligible} | {n_eligible} |")
    print(f"| **Recovered Count** | {n_rec_a} | {n_rec_b} |")
    print(f"| **Recovery Fraction** | {frac_a * 100:.1f}% | {frac_b * 100:.1f}% |")
    print(f"| **Recovered Under Both** | {len(both_recovered)} ({', '.join(both_recovered)}) | {len(both_recovered)} ({', '.join(both_recovered)}) |")
    print(f"| **Recovered Only Under Option A** | {len(only_a)} ({', '.join(only_a) if only_a else 'None'}) | N/A |")
    print(f"| **Recovered Only Under Option B** | N/A | {len(only_b)} ({', '.join(only_b) if only_b else 'None'}) |")
    print(f"| **Additional Recoveries from 1/3 or 3** | {len(only_a)} | N/A |")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
