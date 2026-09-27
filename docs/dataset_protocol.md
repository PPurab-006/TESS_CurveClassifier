# Scientific Data Protocol: TESS Transit Detection Benchmark

## 1. Public Data Sources & Archival Interfaces

This benchmark interfaces with official NASA astrophysics data repositories using modern Python astronomy libraries (`lightkurve`, `astropy`, `astroquery`).

### 1.1 NASA Mikulski Archive for Space Telescopes (MAST)
- **Primary Data Products**: Calibrated photometric light curves from the Science Processing Operations Center (SPOC) pipeline and Quick-Look Pipeline (QLP).
- **Access Method**: `lightkurve.search_lightcurve(target, mission="TESS", author="SPOC")`.
- **Primary Data Formats**: FITS (Flexible Image Transport System) binary tables containing timestamped flux, background flux, centroids, and quality flags.

### 1.2 NASA Exoplanet Archive (NExScI)
- **Access Method**: `astroquery.ipac.nexsci.nasa_exoplanet_archive.NasaExoplanetArchive`.
- **Target Tables**:
  - `pscomppars`: Confirmed Exoplanet Composite Parameters (ground-truth orbital periods, transit depths, planetary radii $R_p$, transit durations).
  - `toi`: TESS Objects of Interest table (vetting dispositions: PC = Planet Candidate, CP = Confirmed Planet, FP = False Positive, KP = Known Planet).
  - `tce`: Threshold Crossing Events from SPOC transiting planet search runs.

---

## 2. Observational Provenance & Light Curve Properties

### 2.1 Cadence and Observation Modes
- **2-minute Cadence**: Standard SPOC pre-selected targets (~20,000 stars per 27.4-day sector). High temporal resolution optimal for short-duration transits and ingress/egress profile modeling.
- **20-second Cadence**: High-cadence mode introduced in TESS Extended Mission (Sectors 27+) for bright targets and asteroseismology.
- **10-minute / 30-minute Full-Frame Images (FFIs)**: Processed by QLP and community pipelines (e.g., eleanor). Wider coverage, slightly higher scatter and blending risk.

### 2.2 Photometric Flux Columns
- **Simple Aperture Photometry (SAP_FLUX)**: Raw sum of calibrated pixel values inside optimal aperture. Contains spacecraft motion, pointing jitter, thermal drifts, and background contamination.
- **Pre-search Data Conditioning SAP (PDCSAP_FLUX)**: *Recommended baseline.* Uses cotrending basis vectors (CBVs) to remove instrumental systematics while preserving astrophysical variability.

### 2.3 Time Systems & Astrometry
- **Time Standard**: Barycentric TESS Julian Date:
  $$\text{BTJD} = \text{BJD} - 2457000.0$$
  where BJD is Barycentric Julian Date in the Barycentric Dynamical Time (TDB) frame, correcting for the light-travel time to the Solar System barycenter.
- **Coordinates**: International Celestial Reference System (ICRS) Right Ascension and Declination ($\text{J2000}$).

### 2.4 Data Quality Filtering
TESS data products provide 32-bit integer quality flags per cadence. The benchmark requires applying quality filtering before analysis:
- **Bit 1**: Attitude tweak / pointing adjustment.
- **Bit 3**: Coarse pointing / spacecraft loss of fine guidance.
- **Bit 4**: Earth or Moon in camera field of view (high scattered light).
- **Bit 5**: Desaturation event (momentum wheel dump).
- **Bit 8**: Cosmic ray detection in optimal aperture.
- **Protocol Rule**: All cadences with non-zero quality flags in the standard bitmask (`bitmask="default"`) must be masked out and treated as missing data rather than zero flux.

---

## 3. Astronomical Target Categorization Schema

To preserve scientific rigor, all targets ingested into the benchmark are categorized into five mutually exclusive classes:

| Target Category | Code Identifier | Definition | Label Semantics |
| :--- | :--- | :--- | :--- |
| **Confirmed Planet Host** | `CONFIRMED_PLANET_HOST` | Stars possessing one or more confirmed transiting exoplanets published in the NASA Exoplanet Archive with verified orbital solutions. | Positive Class ($y = 1$) |
| **TOI Candidate** | `TOI_CANDIDATE` | TESS Objects of Interest classified as "Planet Candidate" (PC) passing initial pipeline thresholds, pending radial velocity or high-resolution imaging validation. | Positive Class ($y = 1$, Candidate screening) |
| **Astrophysical False Positive** | `FALSE_POSITIVE` | Eclipsing binaries (EBs), background eclipsing binaries (BEBs), Grazing binaries, or variable stars identified by the TESS Follow-up Observing Program (TFOP). | Negative Class ($y = 0$, False Alarm evaluation) |
| **Observational Control Star** | `CONTROL_STAR` | Quiet field stars with no detected transit signals in SPOC or QLP pipelines. | Baseline Class ($y = 0$, Unconfirmed Negative) |
| **Synthetic Injection** | `SYNTHETIC_INJECTION` | Control light curves or synthetic baselines into which a mathematically modeled planetary transit has been injected. | Positive Class ($y = 1$, Validation suite) |

### 3.1 The "Unconfirmed Negative" Invariant
> **CRITICAL SCIENTIFIC INTEGRITY WARNING**:
> In observational astrophysics, stars without detected planets **MUST NOT** be treated as confirmed non-hosts. Planetary transit detection is fundamentally constrained by:
> 1. Geometric transit probability: $\mathcal{P}_{tr} \approx R_* / a \ll 1$ (typically $0.1\%$ to $10\%$).
> 2. Photometric noise floor: Small Earth-sized planets around solar-type stars ($\delta \sim 84 \text{ ppm}$) fall below the single-sector TESS detection threshold ($\sim 500\text{--}1000\text{ ppm}$).
> 3. Orbital period limits: A 27.4-day TESS sector can only detect multi-transit events with $P \le 13.7\text{ days}$.
> 
> Therefore, benchmark evaluations must document that `CONTROL_STAR` represents an *observational non-detection control*, not an absolute negative ground truth.

---

## 4. Large Dataset Acquisition Protocol

Before downloading large batches of observational TESS light curves:

1. **Dry-Run Query**: Execute search metadata queries via `lightkurve.search_lightcurve()` to count available sectors, data volume, and cadence distributions without initiating file downloads.
2. **Bandwidth & Storage Budget**: Each TESS SPOC 2-minute FITS file is $\sim 1.5\text{--}2.5\text{ MB}$. A sample of 1,000 targets across 2 sectors requires $\sim 4\text{ GB}$ of local disk space.
3. **Local Caching Structure**:
   ```
   data/raw/
       mastDownload/
           TESS/
               tess2020...-s0026-.../
                   tess2020..._lc.fits
   ```
4. **Automated Checksums & Integrity**: Verify FITS header integrity (`astropy.io.fits.verify()`) upon download. Corrupt or truncated downloads must be discarded and re-fetched.
5. **Rate Limiting**: Space automated MAST queries to avoid triggering remote API throttling or IP blocks.
