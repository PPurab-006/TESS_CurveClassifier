"""
Unit and Integration Tests for Stage 2 Cohort Selection, Acquisition, and Validation.
"""
from pathlib import Path
import pytest
import numpy as np
import pandas as pd
from astropy.io import fits

from tess_benchmark.data.protocol import TargetCategory, LightCurveData
from tess_benchmark.data.tess_loader import TESSDataLoader, compute_file_sha256
from tess_benchmark.data.cohort import (
    CandidateTarget,
    ValidationRecord,
    Stage2CohortManager,
    PILOT_S1_HOSTS,
    PILOT_S1_CONTROLS
)

PILOT_DIR = Path("data/raw/real_tess_pilot")
SAMPLE_PILOT_FITS = PILOT_DIR / "mastDownload/TESS/tess2018206045859-s0001-0000000025155310-0120-s/tess2018206045859-s0001-0000000025155310-0120-s_lc.fits"


@pytest.fixture
def cohort_manager(tmp_path):
    raw_dir = tmp_path / "raw_stage2"
    results_dir = tmp_path / "results_stage2"
    return Stage2CohortManager(
        raw_cache_dir=raw_dir,
        pilot_cache_dir=PILOT_DIR,
        results_dir=results_dir
    )


def test_candidate_target_dataclass():
    cand = CandidateTarget(
        target_name="WASP-126",
        tic_id=25155310,
        category=TargetCategory.CONFIRMED_PLANET_HOST,
        sector=1,
        is_confirmed_host=True,
        planet_name="WASP-126 b",
        period_days=3.2887898,
        t0_bjd=2458327.519958,
        duration_hours=3.436772,
        depth_ppm=7005.72
    )
    d = cand.to_dict()
    assert d["target_name"] == "WASP-126"
    assert d["tic_id"] == 25155310
    assert d["category"] == "confirmed_planet_host"
    assert d["is_confirmed_host"] is True
    assert d["period_days"] == pytest.approx(3.2887898)


def test_validation_record_serialization():
    rec = ValidationRecord(
        target_name="TIC 306573321",
        tic_id=306573321,
        category="control_star",
        sector=1,
        cadence_sec=120.0,
        pipeline="SPOC",
        flux_column="pdcsap_flux",
        tstart_btjd=1325.29,
        tstop_btjd=1353.18,
        duration_days=27.88,
        n_raw_cadences=20076,
        n_usable_cadences=18278,
        n_quality_rejected=1798,
        usable_cadence_fraction=0.9104,
        gap_count=1,
        max_gap_days=1.13,
        is_strictly_increasing=True,
        n_nan_time_filtered=0,
        n_nan_flux_filtered=0,
        n_inf_flux_filtered=0,
        overlaps_predicted_transit=False,
        n_predicted_transit_windows=0,
        n_windows_with_cadences=0,
        n_windows_full_coverage=0,
        n_windows_zero_cadence=0,
        is_visually_apparent=False,
        fits_filename="test.fits",
        file_size_bytes=2039040,
        sha256="abcdef123456",
        download_source="NASA MAST",
        retrieval_date="2026-09-30",
        qa_passed=True
    )
    d = rec.to_dict()
    assert d["tic_id"] == 306573321
    assert d["category"] == "control_star"
    assert d["qa_passed"] is True
    assert d["acquisition_status"] == "acquired_and_validated"


@pytest.mark.skipif(not SAMPLE_PILOT_FITS.exists(), reason="Pilot FITS file required for local validation test")
def test_validate_light_curve_on_pilot_data(cohort_manager):
    cand = CandidateTarget(
        target_name="WASP-126",
        tic_id=25155310,
        category=TargetCategory.CONFIRMED_PLANET_HOST,
        sector=1,
        is_confirmed_host=True,
        planet_name="WASP-126 b",
        period_days=3.2887898,
        t0_bjd=2458327.519958,
        duration_hours=3.436772,
        depth_ppm=7005.72
    )
    rec = cohort_manager.validate_light_curve(cand, SAMPLE_PILOT_FITS)
    assert rec.qa_passed is True
    assert rec.duration_days >= 20.0
    assert rec.usable_cadence_fraction >= 0.80
    assert rec.is_strictly_increasing is True
    assert rec.n_nan_time_filtered == 0
    assert rec.n_nan_flux_filtered == 0
    assert rec.overlaps_predicted_transit is True
    assert rec.n_windows_with_cadences == 8


@pytest.mark.skipif(not SAMPLE_PILOT_FITS.exists(), reason="Pilot FITS file required for local reuse test")
def test_pilot_reuse_and_resumability(cohort_manager, tmp_path):
    cand = CandidateTarget(
        target_name="WASP-126",
        tic_id=25155310,
        category=TargetCategory.CONFIRMED_PLANET_HOST,
        sector=1,
        is_confirmed_host=True,
        data_uri="mast:TESS/product/tess2018206045859-s0001-0000000025155310-0120-s_lc.fits"
    )

    # 1. First retrieval should copy from pilot cache
    fits_path = cohort_manager.download_target_fits(cand)
    assert fits_path.exists()
    assert fits_path.stat().st_size == SAMPLE_PILOT_FITS.stat().st_size

    # Verify SHA256 matches
    assert compute_file_sha256(fits_path) == compute_file_sha256(SAMPLE_PILOT_FITS)

    # 2. Second retrieval should be instant (resumable)
    fits_path_2 = cohort_manager.download_target_fits(cand)
    assert fits_path_2 == fits_path


def test_export_and_load_candidate_manifest(cohort_manager, tmp_path):
    candidates = [
        CandidateTarget(
            target_name="WASP-126",
            tic_id=25155310,
            category=TargetCategory.CONFIRMED_PLANET_HOST,
            sector=1,
            is_confirmed_host=True,
            period_days=3.2887898,
            t0_bjd=2458327.519958,
            duration_hours=3.436772,
            depth_ppm=7005.72
        ),
        CandidateTarget(
            target_name="TIC 306573321",
            tic_id=306573321,
            category=TargetCategory.CONTROL_STAR,
            sector=1,
            is_confirmed_host=False
        )
    ]
    manifest_csv = tmp_path / "test_manifest.csv"
    cohort_manager.export_candidate_manifest(candidates, manifest_csv)
    assert manifest_csv.exists()

    df = pd.read_csv(manifest_csv)
    assert len(df) == 2
    assert df["tic_id"].tolist() == [25155310, 306573321]
    assert df["category"].tolist() == ["confirmed_planet_host", "control_star"]


@pytest.mark.skipif(not SAMPLE_PILOT_FITS.exists(), reason="Pilot FITS file required for mock failure test")
def test_validation_exclusion_on_short_baseline(cohort_manager, tmp_path):
    # Create a truncated FITS file with baseline < 20 days
    truncated_fits = tmp_path / "truncated_lc.fits"
    with fits.open(SAMPLE_PILOT_FITS) as hdul:
        # Truncate to first 5000 rows (approx 7 days)
        hdul[1].data = hdul[1].data[:5000]
        hdul.writeto(truncated_fits)

    cand = CandidateTarget(
        target_name="Truncated Star",
        tic_id=999999999,
        category=TargetCategory.CONTROL_STAR,
        sector=1,
        is_confirmed_host=False
    )
    rec = cohort_manager.validate_light_curve(cand, truncated_fits)
    assert rec.qa_passed is False
    assert rec.acquisition_status == "excluded_qa_failed"
    assert "baseline" in rec.exclusion_reason or "insufficient_usable_cadences" in rec.exclusion_reason


def test_duplicate_tic_rejection_in_consolidation(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir(parents=True)
    mgr = Stage2CohortManager(results_dir=results_dir)

    # Create dummy initial validated manifest with 1 host
    df_init = pd.DataFrame([{
        "target_name": "Target A",
        "tic_id": 1001,
        "category": "confirmed_planet_host",
        "sector": 2,
        "cadence_sec": 120.0,
        "pipeline": "SPOC",
        "flux_column": "pdcsap_flux",
        "tstart_btjd": 1354.0,
        "tstop_btjd": 1381.0,
        "duration_days": 27.0,
        "n_raw_cadences": 18000,
        "n_usable_cadences": 16500,
        "n_quality_rejected": 1500,
        "usable_cadence_fraction": 0.9167,
        "gap_count": 1,
        "max_gap_days": 1.0,
        "is_strictly_increasing": True,
        "n_nan_time_filtered": 0,
        "n_nan_flux_filtered": 0,
        "n_inf_flux_filtered": 0,
        "overlaps_predicted_transit": True,
        "n_predicted_transit_windows": 5,
        "n_windows_with_cadences": 5,
        "n_windows_full_coverage": 5,
        "n_windows_zero_cadence": 0,
        "is_visually_apparent": False,
        "fits_filename": "tess_1001.fits",
        "file_size_bytes": 2000000,
        "sha256": "abc1",
        "download_source": "NASA MAST",
        "retrieval_date": "2026-09-30",
        "qa_passed": True,
        "planet_name": "Target A b",
        "toi_id": "TOI-101.01",
        "period_days": 3.0,
        "period_err": 0.0,
        "t0_bjd": 2458300.0,
        "t0_err": 0.0,
        "duration_hours": 2.0,
        "duration_err": 0.0,
        "depth_ppm": 5000.0,
        "ephemeris_source": "TOI",
        "selection_rationale": "Host",
        "acquisition_status": "acquired_and_validated",
        "exclusion_reason": None
    }])
    df_init.to_csv(results_dir / "stage2_validated_manifest.csv", index=False)

    # Create dummy expansion manifest with duplicate TIC 1001
    df_exp = pd.DataFrame([{
        "target_name": "Target A duplicate",
        "tic_id": 1001,  # DUPLICATE!
        "category": "confirmed_planet_host",
        "sector": 2,
        "cadence_sec": 120.0,
        "pipeline": "SPOC",
        "flux_column": "pdcsap_flux",
        "tstart_btjd": 1354.0,
        "tstop_btjd": 1381.0,
        "duration_days": 27.0,
        "n_raw_cadences": 18000,
        "n_usable_cadences": 16500,
        "n_quality_rejected": 1500,
        "usable_cadence_fraction": 0.9167,
        "gap_count": 1,
        "max_gap_days": 1.0,
        "is_strictly_increasing": True,
        "n_nan_time_filtered": 0,
        "n_nan_flux_filtered": 0,
        "n_inf_flux_filtered": 0,
        "overlaps_predicted_transit": True,
        "n_predicted_transit_windows": 5,
        "n_windows_with_cadences": 5,
        "n_windows_full_coverage": 5,
        "n_windows_zero_cadence": 0,
        "is_visually_apparent": False,
        "fits_filename": "tess_1001_dup.fits",
        "file_size_bytes": 2000000,
        "sha256": "abc2",
        "download_source": "NASA MAST",
        "retrieval_date": "2026-09-30",
        "qa_passed": True,
        "planet_name": "Target A b",
        "toi_id": "TOI-101.01",
        "period_days": 3.0,
        "period_err": 0.0,
        "t0_bjd": 2458300.0,
        "t0_err": 0.0,
        "duration_hours": 2.0,
        "duration_err": 0.0,
        "depth_ppm": 5000.0,
        "ephemeris_source": "TOI",
        "selection_rationale": "Host",
        "acquisition_status": "acquired_and_validated",
        "exclusion_reason": None
    }])
    df_exp.to_csv(results_dir / "stage2_expansion_validated.csv", index=False)

    with pytest.raises(RuntimeError, match="Duplicate TIC IDs found"):
        mgr.consolidate_final_cohort(target_hosts=1, target_controls=0)


def test_preservation_of_original_stage2_records():
    """Verify original Stage 2 files remain intact and unmodified."""
    cand_path = Path("results/real_data_stage2/stage2_candidate_manifest.csv")
    val_path = Path("results/real_data_stage2/stage2_validated_manifest.csv")
    rep_path = Path("results/real_data_stage2/stage2_validation_report.json")

    assert cand_path.exists()
    assert val_path.exists()
    assert rep_path.exists()

    df_cand = pd.read_csv(cand_path)
    df_val = pd.read_csv(val_path)

    assert len(df_cand) == 100
    assert len(df_val) == 100
    assert df_val["qa_passed"].sum() == 59
    assert (df_val["qa_passed"] == False).sum() == 41

    # Check that Sector 3 & 4 exclusions are preserved
    s3_passed = df_val[(df_val["sector"] == 3) & df_val["qa_passed"]]
    s4_passed = df_val[(df_val["sector"] == 4) & df_val["qa_passed"]]
    assert len(s3_passed) == 0
    assert len(s4_passed) == 0


def test_final_cohort_count_and_uniqueness():
    """Verify consolidated final cohort satisfies all protocol invariants."""
    final_path = Path("results/real_data_stage2/stage2_final_cohort_manifest.csv")
    assert final_path.exists(), "Final cohort manifest missing"

    df = pd.read_csv(final_path)
    assert len(df) == 100
    assert df["tic_id"].nunique() == 100, "Duplicate TIC IDs found in final cohort"

    hosts = df[df["category"] == "confirmed_planet_host"]
    controls = df[df["category"] == "control_star"]
    assert len(hosts) == 50
    assert len(controls) == 50

    # Invariants
    assert df["qa_passed"].all() is True or (df["qa_passed"] == True).all()
    assert df["duration_days"].min() >= 20.0
    assert df["usable_cadence_fraction"].min() >= 0.80
    assert df["is_strictly_increasing"].all() is True or (df["is_strictly_increasing"] == True).all()
    assert df["n_nan_time_filtered"].sum() == 0
    assert df["n_nan_flux_filtered"].sum() == 0

    # Ephemerides and period range for hosts
    assert hosts["period_days"].min() >= 0.5
    assert hosts["period_days"].max() <= 15.0
    assert hosts["t0_bjd"].notna().all()
    assert hosts["duration_hours"].notna().all()

    # Controls must have control rationale and no planet name
    assert controls["planet_name"].isna().all()


def test_expansion_reporting_and_exclusion():
    """Verify expansion records document exclusions and data provenance."""
    exp_cand_path = Path("results/real_data_stage2/stage2_expansion_candidates.csv")
    exp_val_path = Path("results/real_data_stage2/stage2_expansion_validated.csv")
    exp_rep_path = Path("results/real_data_stage2/stage2_expansion_report.json")

    assert exp_cand_path.exists()
    assert exp_val_path.exists()
    assert exp_rep_path.exists()

    df_exp = pd.read_csv(exp_val_path)
    assert len(df_exp) >= 50
    assert "qa_passed" in df_exp.columns

    # Verify at least 1 exclusion was caught by the 0.80 threshold
    excl = df_exp[df_exp["qa_passed"] == False]
    assert len(excl) >= 1
    assert "usable_fraction" in excl.iloc[0]["exclusion_reason"]

