"""
Public TESS Data Acquisition Interface, Provenance Loader, and Quality Assurance.

Integrates with Lightkurve, Astropy, and Astroquery to interface with NASA MAST
and the NASA Exoplanet Archive, enforcing local caching, provenance validation,
strict download protocols, and offline FITS parsing.
"""
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import hashlib
import datetime
import numpy as np

from astropy.io import fits

try:
    import lightkurve as lk
except ImportError:
    lk = None

from .protocol import LightCurveData, TargetCategory


REQUIRED_FITS_COLUMNS: List[str] = [
    "TIME",
    "TIMECORR",
    "CADENCENO",
    "SAP_FLUX",
    "SAP_FLUX_ERR",
    "PDCSAP_FLUX",
    "PDCSAP_FLUX_ERR",
    "QUALITY"
]


def compute_file_sha256(filepath: Path | str, chunk_size: int = 65536) -> str:
    """Compute SHA256 hexadecimal hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


class TESSDataLoader:
    """
    Interface for querying, downloading, and loading public TESS light curves.

    Parameters
    ----------
    cache_dir : Path | str
        Directory where downloaded FITS files and metadata will be stored.
    """

    def __init__(self, cache_dir: Path | str = "data/raw"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def search_target(
        self,
        target_name: str,
        mission: str = "TESS",
        author: str = "SPOC"
    ) -> Any:
        """
        Search for available light curves in NASA MAST via Lightkurve.

        Parameters
        ----------
        target_name : str
            Target identifier (e.g. 'TIC 25155310' or 'TOI-700' or 'WASP-126').
        mission : str
            Mission name (default 'TESS').
        author : str
            Pipeline author (default 'SPOC' for Science Processing Operations Center).

        Returns
        -------
        SearchResult
            Lightkurve SearchResult object.
        """
        if lk is None:
            raise ImportError("lightkurve is required for TESSDataLoader operations.")
        return lk.search_lightcurve(target_name, mission=mission, author=author)

    def download_fits(
        self,
        target_name: str,
        sector: Optional[int] = None,
        author: str = "SPOC"
    ) -> Path:
        """
        Download original FITS product from NASA MAST to cache directory without modification.

        Parameters
        ----------
        target_name : str
            Target identifier (e.g., 'TIC 25155310').
        sector : Optional[int]
            Observation sector number.
        author : str
            Pipeline provenance author (default 'SPOC').

        Returns
        -------
        Path
            Path to the downloaded FITS file on local disk.
        """
        if lk is None:
            raise ImportError("lightkurve is required to download TESS data.")

        search = self.search_target(target_name, author=author)
        if sector is not None:
            search = search[search.table["sequence_number"] == sector]

        if len(search) == 0:
            raise ValueError(
                f"No TESS light curve found for {target_name} (sector={sector}, author={author})."
            )

        downloaded = search.download(download_dir=str(self.cache_dir))
        if downloaded is None:
            raise RuntimeError(f"Download returned None for {target_name} from MAST.")

        fits_path = Path(downloaded.filename)
        if not fits_path.exists():
            raise FileNotFoundError(f"Expected downloaded FITS file not found at: {fits_path}")

        return fits_path

    def load_fits_file(
        self,
        fits_path: Path | str,
        flux_column: str = "pdcsap_flux",
        category: TargetCategory = TargetCategory.CONTROL_STAR,
        has_transit: bool = False,
        target_name: Optional[str] = None,
        retrieval_date: Optional[str] = None
    ) -> LightCurveData:
        """
        Ingest and validate a TESS light curve directly from a local FITS file.

        Parameters
        ----------
        fits_path : Path | str
            Path to the local TESS light curve FITS file.
        flux_column : str
            Photometric column to extract ('pdcsap_flux' or 'sap_flux').
        category : TargetCategory
            Astronomical classification category.
        has_transit : bool
            Binary ground-truth label.
        target_name : Optional[str]
            Optional target name override.
        retrieval_date : Optional[str]
            Optional retrieval date string.

        Returns
        -------
        LightCurveData
            Standardized LightCurveData object with comprehensive provenance metadata.
        """
        fits_path = Path(fits_path)
        if not fits_path.exists():
            raise FileNotFoundError(f"FITS file does not exist: {fits_path}")

        file_size_bytes = fits_path.stat().st_size
        sha256_hash = compute_file_sha256(fits_path)

        upper_flux_col = flux_column.upper()

        with fits.open(fits_path) as hdul:
            if len(hdul) < 2:
                raise ValueError(f"FITS file {fits_path} contains fewer than 2 HDUs.")

            primary_hdr = hdul[0].header
            lc_hdu = hdul[1]
            lc_hdr = lc_hdu.header
            col_names = [col.name.upper() for col in lc_hdu.columns]

            # Verify required columns
            missing_cols = [c for c in REQUIRED_FITS_COLUMNS if c not in col_names]
            if missing_cols:
                raise ValueError(
                    f"FITS file {fits_path} is missing required light curve columns: {missing_cols}"
                )

            if upper_flux_col not in col_names:
                raise ValueError(
                    f"Requested flux column '{upper_flux_col}' not found in FITS columns: {col_names}"
                )

            table_data = lc_hdu.data
            time_raw = np.array(table_data["TIME"], dtype=np.float64)
            flux_raw = np.array(table_data[upper_flux_col], dtype=np.float64)
            err_col = f"{upper_flux_col}_ERR"
            flux_err_raw = (
                np.array(table_data[err_col], dtype=np.float64)
                if err_col in col_names
                else np.full_like(flux_raw, np.nan)
            )
            quality_raw = np.array(table_data["QUALITY"], dtype=np.int32)

            # Column units
            time_unit = ""
            flux_unit = ""
            for i, col in enumerate(lc_hdu.columns, start=1):
                if col.name.upper() == "TIME":
                    time_unit = lc_hdr.get(f"TUNIT{i}", "")
                elif col.name.upper() == upper_flux_col:
                    flux_unit = lc_hdr.get(f"TUNIT{i}", "")

            # Primary metadata
            tic_id = primary_hdr.get("TICID")
            sector = primary_hdr.get("SECTOR")
            camera = primary_hdr.get("CAMERA")
            ccd = primary_hdr.get("CCD")
            author = primary_hdr.get("ORIGIN", "SPOC")
            telescope = primary_hdr.get("TELESCOP", "TESS")
            instrument = primary_hdr.get("INSTRUME", "TESS Photometer")
            tstart = primary_hdr.get("TSTART", np.nanmin(time_raw[np.isfinite(time_raw)]) if np.any(np.isfinite(time_raw)) else 0.0)
            tstop = primary_hdr.get("TSTOP", np.nanmax(time_raw[np.isfinite(time_raw)]) if np.any(np.isfinite(time_raw)) else 0.0)
            ra = primary_hdr.get("RA_OBJ")
            dec = primary_hdr.get("DEC_OBJ")
            tess_mag = primary_hdr.get("TESSMAG")

        # Quality mask: SPOC standard quality flags
        # Quality flag 0 indicates clean cadence without known instrumental anomalies
        quality_mask = (quality_raw == 0)

        # Counting missingness, NaNs, and infinities
        n_raw = len(time_raw)
        nan_flux_raw = int(np.sum(np.isnan(flux_raw)))
        inf_flux_raw = int(np.sum(np.isinf(flux_raw)))
        nan_time_raw = int(np.sum(np.isnan(time_raw)))
        quality_rejected = int(np.sum(~quality_mask))

        valid_cadences = quality_mask & np.isfinite(time_raw) & np.isfinite(flux_raw) & np.isfinite(flux_err_raw)
        n_usable = int(np.sum(valid_cadences))

        # Check time monotonicity and finiteness on valid cadences
        valid_times = time_raw[valid_cadences]
        nan_time_filtered = int(np.sum(np.isnan(valid_times)))
        nan_flux_filtered = int(np.sum(np.isnan(flux_raw[valid_cadences])))
        inf_flux_filtered = int(np.sum(np.isinf(flux_raw[valid_cadences])))
        time_diffs = np.diff(valid_times) if len(valid_times) > 1 else np.array([])
        is_strictly_increasing = bool(np.all(time_diffs > 0)) if len(time_diffs) > 0 else True
        median_cadence_sec = float(np.median(time_diffs) * 86400.0) if len(time_diffs) > 0 else 120.0

        # Gap identification (gaps > 0.5 days, e.g. momentum dumps or mid-sector downlink)
        gap_threshold_days = 0.5
        gap_count = int(np.sum(time_diffs > gap_threshold_days)) if len(time_diffs) > 0 else 0
        max_gap_days = float(np.max(time_diffs)) if len(time_diffs) > 0 else 0.0

        # Unsupervised, label-blind continuum normalization
        # Computed strictly as the median of valid, unflagged cadences
        flux_norm = flux_raw.copy()
        flux_err_norm = flux_err_raw.copy()
        if n_usable > 0:
            median_flux = float(np.nanmedian(flux_raw[valid_cadences]))
            if median_flux > 0:
                flux_norm = flux_raw / median_flux
                flux_err_norm = flux_err_raw / median_flux
        else:
            median_flux = 1.0

        target_id_str = f"TIC {tic_id}" if tic_id is not None else (target_name or "UNKNOWN")
        eff_target_name = target_name or target_id_str

        metadata: Dict[str, Any] = {
            "target_name": eff_target_name,
            "tic_id": tic_id,
            "sector": int(sector) if sector is not None else None,
            "camera": int(camera) if camera is not None else None,
            "ccd": int(ccd) if ccd is not None else None,
            "telescope": telescope,
            "instrument": instrument,
            "author": author,
            "flux_column": flux_column.lower(),
            "time_unit": time_unit,
            "flux_unit": flux_unit,
            "cadence_sec": median_cadence_sec,
            "tstart": float(tstart),
            "tstop": float(tstop),
            "duration_days": float(tstop - tstart) if np.isfinite(tstop) and np.isfinite(tstart) else 0.0,
            "ra": ra,
            "dec": dec,
            "tess_mag": tess_mag,
            "synthetic": False,
            "fits_path": str(fits_path.resolve()),
            "fits_filename": fits_path.name,
            "file_size_bytes": file_size_bytes,
            "sha256": sha256_hash,
            "retrieval_date": retrieval_date or datetime.date.today().isoformat(),
            "download_source": "NASA MAST (SPOC Pipeline)",
            "n_raw_cadences": n_raw,
            "n_usable_cadences": n_usable,
            "n_nan_flux_raw": nan_flux_raw,
            "n_inf_flux_raw": inf_flux_raw,
            "n_nan_time_raw": nan_time_raw,
            "n_nan_flux": nan_flux_raw,
            "n_inf_flux": inf_flux_raw,
            "n_nan_time": nan_time_raw,
            "n_nan_time_filtered": nan_time_filtered,
            "n_nan_flux_filtered": nan_flux_filtered,
            "n_inf_flux_filtered": inf_flux_filtered,
            "n_quality_rejected": quality_rejected,
            "usable_cadence_fraction": float(n_usable / n_raw) if n_raw > 0 else 0.0,
            "is_strictly_increasing": is_strictly_increasing,
            "gap_count": gap_count,
            "max_gap_days": max_gap_days,
            "median_raw_flux": median_flux,
            "normalization_method": "median_valid_continuum (label_blind)",
            "quality_mask_policy": "QUALITY == 0 (standard SPOC clean bitmask)"
        }


        return LightCurveData(
            time=time_raw,
            flux=flux_norm,
            flux_err=flux_err_norm,
            target_id=target_id_str,
            category=category,
            has_transit=has_transit,
            metadata=metadata,
            quality_mask=quality_mask,
            raw_flux=flux_raw,
            raw_flux_err=flux_err_raw
        )

    def download_sector_lightcurve(
        self,
        target_name: str,
        sector: Optional[int] = None,
        author: str = "SPOC",
        flux_column: str = "pdcsap_flux",
        category: TargetCategory = TargetCategory.TOI_CANDIDATE,
        has_transit: bool = True
    ) -> LightCurveData:
        """
        Download or load cached TESS light curve for a target and sector.

        Parameters
        ----------
        target_name : str
            Target name / TIC identifier.
        sector : Optional[int]
            TESS observation sector number.
        author : str
            Pipeline provenance author (default 'SPOC').
        flux_column : str
            Photometric flux column ('pdcsap_flux' recommended).
        category : TargetCategory
            Target classification category.
        has_transit : bool
            Label indicating transit presence.

        Returns
        -------
        LightCurveData
            Standardized LightCurveData object.
        """
        fits_path = self.download_fits(target_name=target_name, sector=sector, author=author)
        return self.load_fits_file(
            fits_path=fits_path,
            flux_column=flux_column,
            category=category,
            has_transit=has_transit,
            target_name=target_name
        )

    @staticmethod
    def calculate_transit_overlap(
        time: np.ndarray,
        period_days: float,
        t0_bjd: float,
        duration_hours: float,
        period_err: float = 0.0,
        t0_err: float = 0.0,
        duration_err_hours: float = 0.0
    ) -> Dict[str, Any]:
        """
        Calculate whether predicted transit windows overlap the observation time range.

        Accounts for orbital ephemeris uncertainty propagation and strictly distinguishes
        between predicted transit windows with data coverage versus verified observed events.

        Parameters
        ----------
        time : np.ndarray
            Observation time array in BTJD (BJD - 2457000.0).
        period_days : float
            Orbital period in days.
        t0_bjd : float
            Reference transit midpoint in BJD or BTJD.
        duration_hours : float
            Transit duration in hours.
        period_err : float
            1-sigma uncertainty in orbital period (days).
        t0_err : float
            1-sigma uncertainty in reference transit midpoint (days).
        duration_err_hours : float
            1-sigma uncertainty in transit duration (hours).

        Returns
        -------
        Dict[str, Any]
            Detailed breakdown of predicted transits, timing uncertainties, and cadence counts.
        """
        finite_times = time[np.isfinite(time)]
        if len(finite_times) == 0:
            return {
                "overlaps_transit": False,
                "n_predicted_transits": 0,
                "n_windows_with_cadences": 0,
                "n_windows_full_coverage": 0,
                "n_windows_zero_cadence": 0,
                "n_observed_transits": 0,  # Legacy alias for backward compatibility
                "predicted_midtimes_btjd": [],
                "transit_details": []
            }

        t_min = float(np.min(finite_times))
        t_max = float(np.max(finite_times))

        # Convert t0 to BTJD if provided in standard BJD (> 2450000)
        t0_btjd = t0_bjd - 2457000.0 if t0_bjd > 2400000.0 else t0_bjd
        dur_days = duration_hours / 24.0
        half_dur = dur_days / 2.0

        # Epoch range: E such that t_mid(E) falls near or within [t_min - half_dur, t_max + half_dur]
        e_start = int(np.floor((t_min - half_dur - t0_btjd) / period_days)) - 1
        e_end = int(np.ceil((t_max + half_dur - t0_btjd) / period_days)) + 2

        predicted_midtimes: List[float] = []
        transit_details: List[Dict[str, Any]] = []

        for e in range(e_start, e_end):
            t_mid = t0_btjd + e * period_days
            ingress = t_mid - half_dur
            egress = t_mid + half_dur

            # Propagated timing uncertainty at epoch E
            sigma_t_days = float(np.sqrt(t0_err**2 + (e * period_err)**2))
            sigma_t_min = float(sigma_t_days * 24.0 * 60.0)

            # Check if transit window overlaps the observation range
            if egress >= t_min and ingress <= t_max:
                predicted_midtimes.append(float(t_mid))
                # Count cadences within nominal window
                in_window = (finite_times >= ingress) & (finite_times <= egress)
                cadence_count = int(np.sum(in_window))
                is_full = bool(cadence_count >= max(1, int(duration_hours * 30 * 0.7)))
                is_partial = bool(cadence_count > 0)
                is_zero = bool(cadence_count == 0)

                transit_details.append({
                    "epoch": int(e),
                    "t_mid_btjd": float(t_mid),
                    "sigma_t_mid_days": sigma_t_days,
                    "sigma_t_mid_minutes": sigma_t_min,
                    "ingress_btjd": float(ingress),
                    "egress_btjd": float(egress),
                    "cadence_count": cadence_count,
                    "fully_observed": is_full,
                    "partially_observed": is_partial,
                    "zero_cadence": is_zero
                })

        n_predicted = len(transit_details)
        n_with_cadences = sum(1 for td in transit_details if td["partially_observed"])
        n_full = sum(1 for td in transit_details if td["fully_observed"])
        n_zero = sum(1 for td in transit_details if td["zero_cadence"])
        overlaps = n_with_cadences > 0

        return {
            "overlaps_transit": overlaps,
            "n_predicted_transits": n_predicted,
            "n_windows_with_cadences": n_with_cadences,
            "n_windows_full_coverage": n_full,
            "n_windows_zero_cadence": n_zero,
            "n_observed_transits": n_with_cadences,  # Legacy alias
            "predicted_midtimes_btjd": predicted_midtimes,
            "transit_details": transit_details
        }

