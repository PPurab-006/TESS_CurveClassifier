"""
CLI Script to execute Stage 2 Cohort Selection, Acquisition, and Validation.

Usage:
    python scripts/run_stage2_acquisition.py [--candidates-only] [--workers 4]
"""
import argparse
import logging
import sys
from pathlib import Path

from tess_benchmark.data.cohort import Stage2CohortManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("run_stage2_acquisition")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 2 Cohort Acquisition and Validation Runner")
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="data/raw/real_tess_stage2",
        help="Directory to cache raw Stage 2 FITS files"
    )
    parser.add_argument(
        "--pilot-dir",
        type=str,
        default="data/raw/real_tess_pilot",
        help="Directory containing pilot FITS files for potential reuse"
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="results/real_data_stage2",
        help="Directory for manifests and reports"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of concurrent download/validation workers"
    )
    parser.add_argument(
        "--candidates-only",
        action="store_true",
        help="Generate candidate manifest only without downloading FITS data"
    )
    parser.add_argument(
        "--expand",
        action="store_true",
        help="Execute Option 1 cohort expansion on cleaner sectors (Sectors 2, 5, 6)"
    )
    parser.add_argument(
        "--consolidate",
        action="store_true",
        help="Consolidate initial and expansion qualified targets into final 100-star cohort"
    )

    args = parser.parse_args()

    manager = Stage2CohortManager(
        raw_cache_dir=args.raw_dir,
        pilot_cache_dir=args.pilot_dir,
        results_dir=args.results_dir
    )

    if args.candidates_only:
        logger.info("Generating candidate manifest only...")
        candidates = manager.select_candidate_cohort()
        manifest_path = manager.export_candidate_manifest(candidates)
        logger.info(f"Candidate manifest generated at: {manifest_path}")
        return 0

    if args.expand:
        logger.info("Executing Stage 2 Cohort Expansion Workflow (Option 1: Cleaner Sectors)...")
        df_exp, exp_summary = manager.execute_expansion_workflow(max_workers=args.workers)
        logger.info("=" * 60)
        logger.info("Stage 2 Cohort Expansion Complete!")
        logger.info(f"Expansion Searched: {exp_summary['target_expansion_counts']['candidates_searched']}")
        logger.info(f"Expansion Acquired: {exp_summary['target_expansion_counts']['candidates_acquired']}")
        logger.info(f"Expansion Qualified: {exp_summary['target_expansion_counts']['qualified_expansion_total']}")
        logger.info(f"Qualified Expansion Hosts: {exp_summary['target_expansion_counts']['qualified_expansion_hosts']}")
        logger.info(f"Qualified Expansion Controls: {exp_summary['target_expansion_counts']['qualified_expansion_controls']}")
        logger.info("=" * 60)

    if args.consolidate:
        logger.info("Executing Stage 2 Cohort Consolidation...")
        df_final, final_summary = manager.consolidate_final_cohort()
        logger.info("=" * 60)
        logger.info("Stage 2 Final Cohort Consolidation Complete!")
        logger.info(f"Final Total Targets: {final_summary['achieved_counts']['final_total_targets']}")
        logger.info(f"Final Confirmed Single-Planet Hosts: {final_summary['achieved_counts']['final_confirmed_planet_hosts']}")
        logger.info(f"Final Observational Controls: {final_summary['achieved_counts']['final_observational_controls']}")
        logger.info(f"Multi-Planet Fallback Admitted: {final_summary['achieved_counts']['multi_planet_fallback_admitted']}")
        logger.info(f"100 Target Reached: {final_summary['achieved_counts']['target_reached']}")
        logger.info("=" * 60)
        return 0

    if not args.expand and not args.consolidate:
        logger.info("Executing full Stage 2 cohort acquisition and validation workflow...")
        df_validated, summary = manager.execute_cohort_workflow(max_workers=args.workers)

        logger.info("=" * 60)
        logger.info("Stage 2 Cohort Acquisition & Validation Complete!")
        logger.info(f"Total Validated Targets: {summary['actual_counts']['acquired_and_validated_total']}")
        logger.info(f"Qualified Single-Planet Hosts: {summary['actual_counts']['qualified_single_planet_hosts']}")
        logger.info(f"Observational Controls: {summary['actual_counts']['qualified_observational_controls']}")
        logger.info(f"Multi-Planet Fallback: {summary['actual_counts']['multi_planet_fallback_candidates']}")
        logger.info(f"Exclusions/Failures: {summary['actual_counts']['exclusions_and_failures']}")
        logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())

