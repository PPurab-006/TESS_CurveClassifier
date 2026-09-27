"""
Public TESS Data Acquisition Interface and Provenance Loader.

Integrates with Lightkurve and Astroquery to interface with NASA MAST and the
NASA Exoplanet Archive, enforcing local caching, provenance validation, and
strict download protocols.
"""
from pathlib import Path
from typing import Optional, List, Dict, Any
import numpy as np

try:
    import lightkurve as lk
except ImportError:
    lk = None

from .protocol import LightCurveData, TargetCategory


class TESSDataLoader:
    """
    Interface for querying and loading public TESS light curves.

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
            Target identifier (e.g. 'TIC 261136679' or 'TOI-700' or 'WASP-126').
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
            TESS observation sector number. If None, retrieves first available.
        author : str
            Pipeline provenance author (e.g. 'SPOC' or 'QLP').
        flux_column : str
            Photometric flux column ('pdcsap_flux' recommended for systematics-corrected).
        category : TargetCategory
            Target classification category.
        has_transit : bool
            Label indicating transit presence.

        Returns
        -------
        LightCurveData
            Standardized LightCurveData object.
        """
        if lk is None:
            raise ImportError("lightkurve is required to download TESS data.")

        search = self.search_target(target_name, author=author)
        if sector is not None:
            search = search[search.table["sequence_number"] == sector]

        if len(search) == 0:
            raise ValueError(f"No TESS light curve found for {target_name} (sector={sector}, author={author}).")

        lc_collection = search.download(download_dir=str(self.cache_dir))
        if lc_collection is None:
            raise RuntimeError(f"Download failed for {target_name}.")

        # Extract time, flux, flux_err, quality mask
        time = np.array(lc_collection.time.value, dtype=float)
        flux_series = getattr(lc_collection, flux_column)
        flux = np.array(flux_series.value, dtype=float)
        flux_err = np.array(lc_collection.flux_err.value, dtype=float)
        quality = np.array(lc_collection.quality.value, dtype=int)
        quality_mask = (quality == 0)

        # Normalize flux by median
        valid = quality_mask & np.isfinite(flux) & np.isfinite(time)
        if np.sum(valid) > 0:
            med_flux = np.nanmedian(flux[valid])
            if med_flux > 0:
                flux = flux / med_flux
                flux_err = flux_err / med_flux

        sec_num = int(lc_collection.sector) if hasattr(lc_collection, "sector") else sector

        metadata: Dict[str, Any] = {
            "target_name": target_name,
            "tic_id": getattr(lc_collection, "tic_id", None) or getattr(lc_collection, "targetid", None),
            "sector": sec_num,
            "camera": getattr(lc_collection, "camera", None),
            "ccd": getattr(lc_collection, "ccd", None),
            "author": author,
            "flux_column": flux_column,
            "cadence_sec": float(getattr(lc_collection, "cadence", 120.0)) if hasattr(lc_collection, "cadence") else 120.0,
            "ra": getattr(lc_collection, "ra", None),
            "dec": getattr(lc_collection, "dec", None),
            "tess_mag": getattr(lc_collection, "tess_mag", None),
            "synthetic": False
        }

        return LightCurveData(
            time=time,
            flux=flux,
            flux_err=flux_err,
            target_id=str(metadata["tic_id"] or target_name),
            category=category,
            has_transit=has_transit,
            metadata=metadata,
            quality_mask=quality_mask
        )
