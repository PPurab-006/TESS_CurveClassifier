"""
Offline validation tests for TESS FITS ingestion, provenance, and QA protocols.

Tests execute purely offline using synthetic FITS fixtures and mocks to verify:
- FITS ingestion and HDU parsing
- Required-column validation and schema enforcement
- Quality mask filtering
- NaN and Infinity handling
- Time ordering and monotonicity
- Missing or malformed header metadata
- Label-blind reproducible preprocessing
- Disk file immutability (raw file preservation)
- Transit overlap geometry calculation
- Observation manifest generation
"""
from pathlib import Path
import hashlib
import numpy as np
import pytest
from astropy.io import fits
from astropy.table import Table

from tess_benchmark.data.protocol import LightCurveData, TargetCategory
from tess_benchmark.data.tess_loader import (
    TESSDataLoader,
    REQUIRED_FITS_COLUMNS,
    compute_file_sha256
)


def create_mock_tess_fits(
    filepath: Path,
    n_cadences: int = 100,
    tic_id: int = 12345678,
    sector: int = 1,
    cadence_sec: float = 120.0,
    insert_nans: bool = False,
    insert_infs: bool = False,
    quality_flags: bool = False,
    non_monotonic: bool = False,
    missing_col: str | None = None
) -> Path:
    """Create a mock SPOC-compliant TESS light curve FITS file for offline testing."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    dt_days = cadence_sec / 86400.0
    time = 1325.0 + np.arange(n_cadences) * dt_days
    if non_monotonic and n_cadences > 5:
        time[5] = time[4] - 0.01

    raw_flux = 5000.0 + np.random.RandomState(42).normal(0, 10.0, size=n_cadences)
    raw_flux_err = np.full(n_cadences, 10.0)
    sap_flux = raw_flux * 0.95
    sap_flux_err = raw_flux_err * 0.95
    quality = np.zeros(n_cadences, dtype=np.int32)

    if insert_nans and n_cadences > 10:
        raw_flux[2:4] = np.nan
        time[6] = np.nan
        quality[6] = 8

    if insert_infs and n_cadences > 15:
        raw_flux[12] = np.inf

    if quality_flags and n_cadences > 20:
        quality[15:18] = 32  # cosmic ray

    col_dict = {
        "TIME": time,
        "TIMECORR": np.zeros(n_cadences, dtype=np.float32),
        "CADENCENO": np.arange(1000, 1000 + n_cadences, dtype=np.int32),
        "SAP_FLUX": sap_flux,
        "SAP_FLUX_ERR": sap_flux_err,
        "SAP_BKG": np.full(n_cadences, 100.0, dtype=np.float32),
        "SAP_BKG_ERR": np.full(n_cadences, 5.0, dtype=np.float32),
        "PDCSAP_FLUX": raw_flux,
        "PDCSAP_FLUX_ERR": raw_flux_err,
        "QUALITY": quality
    }

    if missing_col and missing_col in col_dict:
        del col_dict[missing_col]

    table = Table(col_dict)
    bin_table_hdu = fits.BinTableHDU(table, name="LIGHTCURVE")

    # Header units
    bin_table_hdu.header["TUNIT1"] = "BJD - 2457000, days"
    bin_table_hdu.header["TUNIT8"] = "e-/s"

    primary_hdu = fits.PrimaryHDU()
    primary_hdu.header["TICID"] = tic_id
    primary_hdu.header["SECTOR"] = sector
    primary_hdu.header["CAMERA"] = 1
    primary_hdu.header["CCD"] = 2
    primary_hdu.header["ORIGIN"] = "SPOC"
    primary_hdu.header["TELESCOP"] = "TESS"
    primary_hdu.header["INSTRUME"] = "TESS Photometer"
    primary_hdu.header["TSTART"] = float(time[0]) if np.isfinite(time[0]) else 1325.0
    primary_hdu.header["TSTOP"] = float(time[-1]) if np.isfinite(time[-1]) else 1325.0 + n_cadences * dt_days
    primary_hdu.header["RA_OBJ"] = 120.5
    primary_hdu.header["DEC_OBJ"] = -65.2
    primary_hdu.header["TESSMAG"] = 10.5

    hdul = fits.HDUList([primary_hdu, bin_table_hdu])
    hdul.writeto(filepath, overwrite=True)
    return filepath


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_fits_ingestion_valid(tmp_path: Path):
    """Verify clean FITS ingestion, column parsing, and metadata population."""
    fits_file = tmp_path / "valid_lc.fits"
    create_mock_tess_fits(fits_file, n_cadences=50, tic_id=99991111, sector=2)

    loader = TESSDataLoader(cache_dir=tmp_path)
    lc = loader.load_fits_file(
        fits_file,
        flux_column="pdcsap_flux",
        category=TargetCategory.CONFIRMED_PLANET_HOST,
        has_transit=True
    )

    assert isinstance(lc, LightCurveData)
    assert lc.target_id == "TIC 99991111"
    assert lc.category == TargetCategory.CONFIRMED_PLANET_HOST
    assert lc.has_transit is True
    assert len(lc.time) == 50
    assert len(lc.flux) == 50
    assert lc.metadata["sector"] == 2
    assert lc.metadata["camera"] == 1
    assert lc.metadata["ccd"] == 2
    assert lc.metadata["time_unit"] == "BJD - 2457000, days"
    assert lc.metadata["flux_unit"] == "e-/s"
    assert lc.metadata["file_size_bytes"] > 0
    assert len(lc.metadata["sha256"]) == 64
    assert lc.metadata["is_strictly_increasing"] is True


def test_required_column_validation(tmp_path: Path):
    """Loader must reject FITS files missing mandatory columns."""
    for col in ["QUALITY", "PDCSAP_FLUX", "TIME"]:
        bad_fits = tmp_path / f"missing_{col}.fits"
        create_mock_tess_fits(bad_fits, missing_col=col)

        loader = TESSDataLoader(cache_dir=tmp_path)
        with pytest.raises(ValueError, match="missing required light curve columns"):
            loader.load_fits_file(bad_fits)


def test_quality_mask_behavior(tmp_path: Path):
    """Quality filtering must isolate clean (QUALITY=0) cadences."""
    fits_file = tmp_path / "flagged_lc.fits"
    create_mock_tess_fits(fits_file, n_cadences=40, quality_flags=True)

    loader = TESSDataLoader(cache_dir=tmp_path)
    lc = loader.load_fits_file(fits_file)

    assert lc.metadata["n_raw_cadences"] == 40
    assert lc.metadata["n_quality_rejected"] == 3
    assert np.sum(lc.quality_mask) == 37

    # lc.clean() should keep exactly 37 cadences
    clean_lc = lc.clean()
    assert len(clean_lc.time) == 37


def test_nan_and_infinity_handling(tmp_path: Path):
    """Loader must track raw NaNs and ensure cleaned data has zero NaNs/Infs."""
    fits_file = tmp_path / "nan_inf_lc.fits"
    create_mock_tess_fits(fits_file, n_cadences=50, insert_nans=True, insert_infs=True)

    loader = TESSDataLoader(cache_dir=tmp_path)
    lc = loader.load_fits_file(fits_file)

    assert lc.metadata["n_nan_flux_raw"] == 2
    assert lc.metadata["n_inf_flux_raw"] == 1
    assert lc.metadata["n_nan_time_raw"] == 1

    # Filtered valid cadences must have zero NaNs and Infs
    assert lc.metadata["n_nan_time_filtered"] == 0
    assert lc.metadata["n_nan_flux_filtered"] == 0
    assert lc.metadata["n_inf_flux_filtered"] == 0

    clean_lc = lc.clean()
    assert np.all(np.isfinite(clean_lc.time))
    assert np.all(np.isfinite(clean_lc.flux))
    assert np.all(np.isfinite(clean_lc.flux_err))


def test_time_ordering_and_monotonicity(tmp_path: Path):
    """Loader must detect whether time timestamps are strictly monotonically increasing."""
    monotonic_file = tmp_path / "mono.fits"
    create_mock_tess_fits(monotonic_file, n_cadences=20, non_monotonic=False)

    non_mono_file = tmp_path / "non_mono.fits"
    create_mock_tess_fits(non_mono_file, n_cadences=20, non_monotonic=True)

    loader = TESSDataLoader(cache_dir=tmp_path)
    lc_mono = loader.load_fits_file(monotonic_file)
    lc_non_mono = loader.load_fits_file(non_mono_file)

    assert lc_mono.metadata["is_strictly_increasing"] is True
    assert lc_non_mono.metadata["is_strictly_increasing"] is False


def test_missing_or_malformed_metadata(tmp_path: Path):
    """Loader must gracefully handle missing optional primary header keys."""
    fits_file = tmp_path / "minimal_hdr.fits"
    col_dict = {col: np.ones(20) for col in REQUIRED_FITS_COLUMNS}
    col_dict["QUALITY"] = np.zeros(20, dtype=np.int32)
    col_dict["CADENCENO"] = np.arange(20, dtype=np.int32)

    table = Table(col_dict)
    hdul = fits.HDUList([fits.PrimaryHDU(), fits.BinTableHDU(table, name="LIGHTCURVE")])
    hdul.writeto(fits_file)

    loader = TESSDataLoader(cache_dir=tmp_path)
    lc = loader.load_fits_file(fits_file, target_name="CUSTOM_STAR")

    assert lc.target_id == "CUSTOM_STAR"
    assert lc.metadata["sector"] is None
    assert lc.metadata["camera"] is None


def test_reproducible_label_blind_preprocessing(tmp_path: Path):
    """Normalization must be 100% deterministic and strictly blind to class label."""
    fits_file = tmp_path / "norm_test.fits"
    create_mock_tess_fits(fits_file, n_cadences=50)

    loader = TESSDataLoader(cache_dir=tmp_path)

    # Load as confirmed host
    lc_host = loader.load_fits_file(
        fits_file,
        category=TargetCategory.CONFIRMED_PLANET_HOST,
        has_transit=True
    )

    # Load as observational control
    lc_ctrl = loader.load_fits_file(
        fits_file,
        category=TargetCategory.CONTROL_STAR,
        has_transit=False
    )

    # Normalization and fluxes must be bitwise identical regardless of target category or label
    np.testing.assert_array_equal(lc_host.flux, lc_ctrl.flux)
    np.testing.assert_array_equal(lc_host.flux_err, lc_ctrl.flux_err)
    assert lc_host.metadata["median_raw_flux"] == lc_ctrl.metadata["median_raw_flux"]


def test_preservation_of_raw_files(tmp_path: Path):
    """Reading FITS files must never mutate or touch raw data on disk."""
    fits_file = tmp_path / "raw_preserve.fits"
    create_mock_tess_fits(fits_file, n_cadences=30)

    hash_before = compute_file_sha256(fits_file)
    size_before = fits_file.stat().st_size

    loader = TESSDataLoader(cache_dir=tmp_path)
    _ = loader.load_fits_file(fits_file)
    _ = loader.load_fits_file(fits_file)

    hash_after = compute_file_sha256(fits_file)
    size_after = fits_file.stat().st_size

    assert hash_before == hash_after
    assert size_before == size_after


def test_transit_overlap_calculation():
    """Transit overlap geometry calculation must correctly compute midtimes and cadences."""
    # 27-day observation time array
    dt = 120.0 / 86400.0
    time = 1325.0 + np.arange(int(27.0 / dt)) * dt

    # System with P = 3.0 days, T0 = 1326.0 (in BTJD), duration = 3.0 hours
    overlap = TESSDataLoader.calculate_transit_overlap(
        time=time,
        period_days=3.0,
        t0_bjd=1326.0,  # BTJD
        duration_hours=3.0
    )

    assert overlap["overlaps_transit"] is True
    assert overlap["n_predicted_transits"] >= 8
    assert overlap["n_observed_transits"] >= 8

    # Each observed transit should have cadences in window
    for td in overlap["transit_details"]:
        if td["partially_observed"]:
            assert td["cadence_count"] > 50


def test_observation_manifest_schema_consistency(tmp_path: Path):
    """Generated observation manifest must conform to the required schema."""
    fits_file = tmp_path / "manifest_test.fits"
    create_mock_tess_fits(fits_file, n_cadences=50, tic_id=12345)

    loader = TESSDataLoader(cache_dir=tmp_path)
    lc = loader.load_fits_file(fits_file)

    mandatory_keys = [
        "target_name", "tic_id", "sector", "camera", "ccd",
        "author", "flux_column", "time_unit", "flux_unit",
        "n_raw_cadences", "n_usable_cadences", "sha256"
    ]
    for key in mandatory_keys:
        assert key in lc.metadata, f"Missing mandatory metadata key: {key}"
