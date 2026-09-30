# Real-Data Ingestion and Quality Assurance Pilot Protocol

**Project**: TESS Transit Detection Benchmark  
**Document ID**: `docs/real_data_pilot_protocol.md`  
**Execution Date**: 2026-09-28  
**Scope**: Ingestion, Data Provenance, and Data-Quality Validation Pilot  
**Author**: Computational Astrophysics Research Engineer  

> [!IMPORTANT]
> **Scientific Integrity & Scope Constraint**:
> This protocol establishes a reproducible, disciplined data acquisition and quality-assurance (QA) pilot for genuine space telescope observations from the Transiting Exoplanet Survey Satellite (TESS).
> **This pilot is strictly an ingestion and photometric data-quality validation study, NOT a model benchmark or transit detection competition.**
> No machine learning models, classical detectors (e.g. BLS), or threshold tuning shall be evaluated for classification performance or detection accuracy in this pilot.

---

## 1. Primary Objectives and Guiding Principles

1. **Verify Flight Data Ingestion**: Demonstrate that the benchmark software environment can acquire, parse, and validate authentic primary TESS FITS products from the NASA Mikulski Archive for Space Telescopes (MAST) without synthetic assumptions or data corruption.
2. **End-to-End Provenance & Traceability**: Guarantee that every downloaded observation retains an unbroken record of its original file path, file size, SHA256 checksum, observation timestamps, pipeline provenance, and retrieval metadata.
3. **Data Quality Assurance (QA)**: Quantify observational artifacts inherent to spaceborne flight photometry—including missing cadences, NaN/infinite values, Earthshine/momentum dump flags, spacecraft downlink gaps, and irregular sampling intervals.
4. **Strict Separation of Target State and Observational Reality**: Explicitly separate whether a star is a cataloged exoplanet host from whether a transit event physically fell within the observation window, whether it is visually distinct, and whether any algorithm detected it.
5. **No Negative Ground-Truth Overclaims**: Enforce that comparison stars are documented as observational non-detection controls, never as "confirmed planet-free."

---

## 2. Target Characterization and Anti-Conflation Schema

In observational astronomy, conflating catalog labels with actual time-series content introduces fatal evaluation biases. To maintain scientific rigor, this pilot enforces strict distinction across **seven mutually independent observational fields**:

```
+-----------------------------------------------------------------------------------------------+
|                                SEVEN INDEPENDENT TARGET FIELDS                                |
+-----------------------------------------------------------------------------------------------+
| 1. Confirmed Host Status    | Catalog confirmation from peer-reviewed literature / NExScI     |
| 2. TESS Target ID           | Unique TESS Input Catalog (TIC) identifier                      |
| 3. Sector & Cadence         | Observing sector (e.g. Sector 1) and sampling rate (120 s)    |
| 4. Product & Pipeline       | Archive product (e.g. SPOC Light Curve, PDCSAP_FLUX)            |
| 5. Ephemeris Overlap Status | Geometric overlap between predicted transit window and data     |
| 6. Visual Apparentness      | Qualitative visual discernibility of transit in raw/flat flux   |
| 7. Algorithmic Recovery     | Output of a detection algorithm (EXCLUDED from this pilot)      |
+-----------------------------------------------------------------------------------------------+
```

### 2.1 The Invariant Rules
- **Rule 5 (Non-universal Transits)**: Do not assume every confirmed planet host has a visible transit in every TESS sector. An observation may coincide with an orbital phase where no transit occurs, or the transit may fall directly into the ~1-day mid-sector spacecraft data downlink gap.
- **Rule 6 (Unconfirmed Negatives)**: Do not label comparison stars as "confirmed planet-free" unless exhaustive radial velocity or imaging evidence proves absence across all parameter spaces. Field comparison stars are classified as `TargetCategory.CONTROL_STAR` (observational controls).
- **Rule 7 (Field Separation)**: An observation can overlap a predicted transit window (Field 5 = Yes) even if the transit is not visually apparent due to shallow depth or high stellar noise (Field 6 = No), and regardless of whether any detector was run (Field 7 = Not Evaluated).

---

## 3. Pilot Target Cohort Specification

The pilot evaluates a balanced cohort of 10 stars observed during TESS Sector 1 (2018-Jul-25 to 2018-Aug-22) at 120-second (2-minute) cadence produced by the NASA Ames Science Processing Operations Center (SPOC) pipeline:

### 3.1 Confirmed Exoplanet Host Targets ($N = 5$)

| Target Name | TIC ID | Host Star | Confirmed Planet | Orbital Period (d) | Reference $T_0$ (BJD) | Transit Duration (hr) | Nominal Depth (ppm) | Ephemeris Source |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **WASP-126** | 25155310 | WASP-126 | WASP-126 b | $3.288830 \pm 3.7 \times 10^{-5}$ | $2458827.2415$ | $3.437 \pm 0.010$ | ~7006 | NExScI `pscomppars` / TOI-114.01 |
| **WASP-46** | 231663901 | WASP-46 | WASP-46 b | $1.430368 \pm 9.3 \times 10^{-7}$ | $2455392.3155$ | $1.617 \pm 0.019$ | ~18961 | NExScI `pscomppars` / TOI-101.01 |
| **WASP-91** | 238176110 | WASP-91 | WASP-91 b | $2.798580 \pm 5.0 \times 10^{-6}$ | $2458327.3200$ | $2.380 \pm 0.020$ | ~16709 | NExScI `pscomppars` / TOI-116.01 |
| **LHS 3844** | 410153553 | LHS 3844 | LHS 3844 b | $0.462930 \pm 4.4 \times 10^{-8}$ | $2460178.6888$ | $0.524 \pm 0.004$ | ~696 | NExScI `pscomppars` / TOI-136.01 |
| **WASP-124** | 97409519 | WASP-124 | WASP-124 b | $3.372877 \pm 1.2 \times 10^{-5}$ | $2458326.6800$ | $2.634 \pm 0.015$ | ~17164 | NExScI `pscomppars` / TOI-113.01 |

### 3.2 Observational Comparison Targets ($N = 5$)

| Target Name | TIC ID | Sector | Cadence | Pipeline | Justification & Verification |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **TIC 265591866** | 265591866 | 1 | 120 s | SPOC | Quiet field star in Sector 1; verified 0 entries in TOI, TCE, and `pscomppars` |
| **TIC 306573321** | 306573321 | 1 | 120 s | SPOC | Quiet field star in Sector 1; verified 0 entries in TOI, TCE, and `pscomppars` |
| **TIC 277891181** | 277891181 | 1 | 120 s | SPOC | Quiet field star in Sector 1; verified 0 entries in TOI, TCE, and `pscomppars` |
| **TIC 370041901** | 370041901 | 1 | 120 s | SPOC | Quiet field star in Sector 1; verified 0 entries in TOI, TCE, and `pscomppars` |
| **TIC 197712257** | 197712257 | 1 | 120 s | SPOC | Quiet field star in Sector 1; verified 0 entries in TOI, TCE, and `pscomppars` |

---

## 4. Archival Interface and Directory Isolation

All data operations adhere to strict storage separation:
- **Raw Archive Cache**: Downloaded FITS products are written unmodified into:
  `data/raw/real_tess_pilot/`
  Raw files are read-only and never modified, renamed, or stripped.
- **Processed Products**: Ingested and standardized tabular manifests, quality flags, and serialized representations are stored into:
  `data/processed/real_tess_pilot/`
- **Results and Documentation**:
  - Protocol: `docs/real_data_pilot_protocol.md`
  - Pilot Report: `results/real_data_pilot/pilot_report.md`
  - Target Inventory: `results/real_data_pilot/target_inventory.csv`
  - Observation Manifest: `results/real_data_pilot/observation_manifest.csv`
  - QA Summary: `results/real_data_pilot/qa_summary.json`
  - Light Curve Plots: `results/real_data_pilot/plots/`
  - Offline Test Results: `results/real_data_pilot/test_results.txt`

---

## 5. Ingestion and Quality Assurance Verification Requirements

For every acquired light curve, the ingestion software must execute the following automated validation checks:

1. **FITS Structure and Readability**:
   - Verify HDU 0 (Primary) contains target identifiers (`TICID`), `SECTOR`, `CAMERA`, `CCD`.
   - Verify HDU 1 (BinTableHDU) contains required columns: `TIME`, `TIMECORR`, `CADENCENO`, `SAP_FLUX`, `SAP_FLUX_ERR`, `PDCSAP_FLUX`, `PDCSAP_FLUX_ERR`, `QUALITY`.
2. **Units and Coordinate Standards**:
   - Verify `TIME` is in Barycentric TESS Julian Date ($\text{BTJD} = \text{BJD} - 2457000.0$).
   - Verify flux is in physical electron rate units ($\text{e}^-/\text{s}$).
3. **Quality Mask and Cadence Accounting**:
   - Evaluate standard SPOC 32-bit quality flags.
   - Record total raw cadences $N_{\text{raw}}$, NaN/infinite cadences $N_{\text{nan}}$, quality-rejected cadences $N_{\text{qual}}$, and usable cadences $N_{\text{usable}}$.
4. **Time Series Continuity & Monotonicity**:
   - Verify time timestamps $t_i$ are finite and strictly monotonically increasing: $t_{i+1} > t_i$.
   - Identify gaps $\Delta t > 0.5\text{ days}$ (corresponding to spacecraft orbit turnarounds and momentum dumps).
5. **Label-Agnostic Robust Continuum Normalization**:
   - Preprocessing must normalize flux by its out-of-gap robust median: $F_{\text{norm}}(t) = F(t) / \text{median}(F_{\text{valid}})$.
   - Normalization must not use transit labels, transit masks, or known transit locations.
   - Both raw unnormalized fluxes and normalized fluxes must be accessible in data structures.
6. **Ephemeris Transit Window Calculation**:
   - Where published ephemerides ($T_0, P, T_{\text{dur}}$) exist, compute all transit epoch numbers $E \in \mathbb{Z}$ whose central transit time falls within the observation window:
     $$t_{\text{mid}}(E) = T_0 + E \cdot P \in [t_{\min}, t_{\max}]$$
   - Identify transit ingress and egress times $[t_{\text{mid}} - T_{\text{dur}}/2, t_{\text{mid}} + T_{\text{dur}}/2]$ and determine whether cadences exist during each window.

---

## 6. Stop Condition & Non-Goals

- **No Model Training**: Classical ML models (Logistic Regression, Random Forest, SVM) and deep learning models (1D CNN) must NOT be trained on pilot data.
- **No Performance Metrics**: Do not calculate ROC-AUC, PR-AUC, F1-scores, or precision/recall against target labels.
- **No Detector Benchmarking**: The classical BLS periodogram detector shall NOT be benchmarked for recovery rate or false alarm rate in this pilot.
- **Outcome Requirement**: Upon successful completion of Phase 1-6, the pilot shall deliver a verified data foundation and recommend a distinct, rigorous follow-up experiment.
