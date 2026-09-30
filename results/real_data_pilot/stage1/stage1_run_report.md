# Stage 1 Real-Data Feasibility Run Report

**Protocol Stage:** Stage 1 Real-Data Feasibility Run (TESS Transit Detection Benchmark)  
**Execution Date (UTC):** 2026-09-30T17:34:53.346206+00:00  
**Software Environment:** Python 3.11.15, Astropy 8.0.1, NumPy 2.4.6, Pandas 3.0.6  
**Platform:** Linux-7.0.0-34-generic-x86_64-with-glibc2.43  
**Total Execution Wall-Clock Runtime:** 17.82 seconds  

---

## Executive Summary

This report documents the complete Stage 1 real-data feasibility execution for the TESS Transit Detection Benchmark on the authentic Sector 1 pilot cohort ($N=10$).
The run successfully verified the complete pipeline from local offline FITS loading, quality masking (`QUALITY == 0`), scalar median normalization, inverse-variance weighted Astropy Box Least Squares (BLS) period search, harmonic classification, and four-panel diagnostic plotting.

**Key Findings:**
1. **Cohort Processing:** 10/10 targets (100%) successfully loaded from local raw FITS files without network access, errors, or timeouts.
2. **Confirmed Host Period Recovery:** 5/5 confirmed planet hosts successfully recovered:
   - **Fundamental (1.0x):** 4/5 hosts (WASP-126, WASP-46, WASP-91, WASP-124) recovered at their exact catalog periods with relative period errors <= 0.045%.
   - **Harmonic (2.0x):** 1/5 hosts (LHS 3844) recovered at the 2x harmonic (P_det = 0.925350 d vs 2 * P_cat = 0.925861 d, relative error 0.055%) because its true period (P=0.4629 d) lies below the protocol search boundary (P_min = 0.50 d).
   - **Subharmonics / Unmatched:** 0 subharmonic, 0 unmatched.
3. **Observational Comparison Stars:** 4/5 comparison stars returned non-detections with noise SDE below the threshold (SDE 4.33–5.51 < 6.0). One comparison star (TIC 265591866) triggered a high-significance detection (SDE 8.41, SNR ~15600, depth ~59%), which visual and percentile inspection confirms is an astrophysical eclipsing binary / variable star in the field, not an algorithm defect.
4. **Scientific Invariants:** Normalization was strictly scalar median division; time arrays and usable sample counts were identical before and after normalization; timestamps were strictly monotonically increasing; zero duplicate timestamps or non-positive flux uncertainties were present.

---

## Approved Protocol Configuration

| Parameter | Value | Reference / Gate |
| :--- | :--- | :--- |
| **Cohort Size** | N=10 (5 Confirmed Hosts, 5 Observational Controls) | Stage 1 Pilot Definition |
| **Primary Preprocessing** | Native SPOC PDCSAP flux with scalar median normalization only | GATE-05 (Option 4 Primary) |
| **Additional Detrending** | None (Zero filter detrending in primary benchmark) | GATE-05 |
| **Search Period Bounds** | [0.5, 15.0] days (clamped to 0.95 * usable baseline) | GATE-07 |
| **Frequency Grid** | Astropy `autoperiod` adaptive grid (`frequency_factor = 5.0`) | GATE-09 (Option A) |
| **Flux Weighting** | Inverse-variance weighting via `dy=flux_err` | GATE-10 (Option A) |
| **Harmonic Matching Set** | Narrow set: {1/2, 1, 2} with 1.0% relative tolerance | GATE-04 (Option B) & GATE-01 |
| **Epoch Matching Tolerance** | Marked pending formal scoring engine implementation | GATE-12 (Option C) |
| **Quality Mask Policy** | Strictly `QUALITY == 0` | Standard SPOC Clean Bitmask |

---

## Phase 1 & 4: Data Audit and Scientific Sanity Checks

All 10 targets were audited directly from raw FITS files stored in `data/raw/real_tess_pilot/`. Each file contains 20,076 raw cadences spanning ~27.88 days in TESS Sector 1.

### Audit Invariants Verified:
- **Array Lengths & Alignment:** All arrays (`TIME`, `PDCSAP_FLUX`, `PDCSAP_FLUX_ERR`, `QUALITY`) match exactly at 20,076 cadences.
- **SPOC Telemetry Cadences:** Exactly 815 cadences per file have `TIME = NaN` and `QUALITY = 8` (momentum dumps / coarse pointing), correctly filtered by the quality mask.
- **Usable Clean Cadences:** Ranged from 17,477 (87.05%) to 18,278 (91.04%), comfortably exceeding the $\ge 80\%$ protocol threshold.
- **Time Baselines:** Ranged from 27.58 d to 27.88 d, exceeding the $\ge 20.0$ d minimum threshold under GATE-03.
- **Timestamp Monotonicity:** Strictly increasing time arrays ($\Delta t > 0$) for all valid cadences; zero duplicate timestamps.
- **Flux Uncertainty Validity:** All usable flux errors are strictly positive, finite, and non-zero (min error ~6–18 e-/s).
- **Normalization Invariance:** Scalar median normalization altered flux values strictly by $F_{\text{norm}} = F / \text{median}(F)$. Timestamp values, array indices, and usable cadence counts were 100% preserved.

---

## Phase 2: Pipeline Execution and Detection Results

### Summary Table

| Target Name | TIC ID | Category | Usable Cadences | Baseline (d) | Detected P (d) | Cat P (d) | BLS SDE | BLS SNR | Recovery Verdict | Rel Err (%) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: |
| WASP-126 | 25155310 | `confirmed_planet_host` | 18278 (91.0%) | 27.88 | 3.28730 | 3.28879 | 15.28 | 129.4 | **RECOVERED (Fundamental)** | 0.0452% |
| WASP-46 | 231663901 | `confirmed_planet_host` | 18276 (91.0%) | 27.88 | 1.43045 | 1.43037 | 16.24 | 95.3 | **RECOVERED (Fundamental)** | 0.0058% |
| WASP-91 | 238176110 | `confirmed_planet_host` | 18276 (91.0%) | 27.88 | 2.79776 | 2.79858 | 17.06 | 187.4 | **RECOVERED (Fundamental)** | 0.0293% |
| LHS 3844 | 410153553 | `confirmed_planet_host` | 18275 (91.0%) | 27.88 | 0.92535 | 0.46293 | 16.80 | 19.0 | **RECOVERED (Harmonic 2x)** | 0.0552% |
| WASP-124 | 97409519 | `confirmed_planet_host` | 17477 (87.1%) | 27.69 | 3.37283 | 3.37288 | 17.08 | 91.1 | **RECOVERED (Fundamental)** | 0.0014% |
| TIC 265591866 | 265591866 | `control_star` | 18274 (91.0%) | 27.88 | 2.28152 | — | 8.41 | 15606.5 | **Control Peak (is_detected=True)** | — |
| TIC 306573321 | 306573321 | `control_star` | 18278 (91.0%) | 27.88 | 0.55340 | — | 5.51 | 5.8 | **Control Peak (is_detected=False)** | — |
| TIC 277891181 | 277891181 | `control_star` | 18276 (91.0%) | 27.88 | 0.69914 | — | 4.33 | 5.7 | **Control Peak (is_detected=False)** | — |
| TIC 370041901 | 370041901 | `control_star` | 18276 (91.0%) | 27.88 | 0.55081 | — | 4.35 | 5.5 | **Control Peak (is_detected=False)** | — |
| TIC 197712257 | 197712257 | `control_star` | 18064 (90.0%) | 27.58 | 0.97624 | — | 5.32 | 5.4 | **Control Peak (is_detected=False)** | — |

---

## Detailed Target-by-Target Analysis

### 1. Confirmed Planet Hosts

1. **WASP-126 (TIC 25155310):**
   - **Catalog:** $P = 3.28879$ d, $T_0 = 1327.51996$ BTJD, duration 3.44 h, depth 7006 ppm.
   - **BLS Result:** Detected $P = 3.28730$ d, $T_0 = 1327.5246$ BTJD, duration 3.07 h, depth 6512 ppm, SDE 15.28, SNR 129.4.
   - **Assessment:** **Fundamental 1x recovered** with relative error 0.0452%. Light curve is highly coherent with 8 clean transits.

2. **WASP-46 (TIC 231663901):**
   - **Catalog:** $P = 1.43037$ d, $T_0 = 1326.00912$ BTJD, duration 1.62 h, depth 18961 ppm.
   - **BLS Result:** Detected $P = 1.43045$ d, $T_0 = 1326.0083$ BTJD, duration 0.96 h, depth 18383 ppm, SDE 16.24, SNR 95.3.
   - **Assessment:** **Fundamental 1x recovered** with relative error 0.0058%. Extremely deep, highly coherent hot Jupiter transits.

3. **WASP-91 (TIC 238176110):**
   - **Catalog:** $P = 2.79858$ d, $T_0 = 1326.68892$ BTJD, duration 2.38 h, depth 16709 ppm.
   - **BLS Result:** Detected $P = 2.79776$ d, $T_0 = 1326.6927$ BTJD, duration 2.02 h, depth 14616 ppm, SDE 17.06, SNR 187.4.
   - **Assessment:** **Fundamental 1x recovered** with relative error 0.0293%. 10 sharp, deep transits clearly visible.

4. **LHS 3844 (TIC 410153553):**
   - **Catalog:** $P = 0.46293$ d, $T_0 = 1325.72413$ BTJD, duration 0.54 h, depth 4507 ppm.
   - **BLS Result:** Detected $P = 0.92535$ d, $T_0 = 1325.7351$ BTJD, duration 0.96 h, depth 2344 ppm, SDE 16.80, SNR 19.0.
   - **Assessment:** **Approved Harmonic 2x recovered** with relative error 0.0552% relative to $2 \times P_{\text{cat}} = 0.92586$ d. Because $P_{\text{cat}} < 0.50$ d, the fundamental is outside the approved search grid $[0.5, 15.0]$ d. Under GATE-04 Option B, detection at the $2\times$ harmonic is an approved recovery mode and correctly booked as a harmonic recovery.

5. **WASP-124 (TIC 97409519):**
   - **Catalog:** $P = 3.37288$ d, $T_0 = 1327.05309$ BTJD, duration 2.63 h, depth 17164 ppm.
   - **BLS Result:** Detected $P = 3.37283$ d, $T_0 = 1327.0549$ BTJD, duration 2.02 h, depth 15312 ppm, SDE 17.08, SNR 91.1.
   - **Assessment:** **Fundamental 1x recovered** with relative error 0.0014%. 8 sharp Jovian transits.

### 2. Observational Comparison Stars

1. **TIC 265591866:**
   - **BLS Result:** Peak period $P = 2.28152$ d, SDE 8.41, SNR 15606.5, depth 590,720 ppm (~59.1% eclipse).
   - **Investigation:** Visual inspection of Panel A and B shows recurring, deep binary eclipses dropping down to ~15% normalized flux. This target is an astrophysical eclipsing binary (EB) or background eclipsing binary blend in Sector 1. This illustrates why observational comparison stars must **never** be labeled as 'proven planet-free' or 'confirmed negatives'.

2. **TIC 306573321:**
   - **BLS Result:** Peak $P = 0.55340$ d, SDE 5.51 (< 6.0), SNR 5.8, depth 64 ppm.
   - **Assessment:** Correctly rejected by SDE threshold; quiet field star.

3. **TIC 277891181:**
   - **BLS Result:** Peak $P = 0.69914$ d, SDE 4.33 (< 6.0), SNR 5.7, depth 53 ppm.
   - **Assessment:** Correctly rejected by SDE threshold; quiet field star.

4. **TIC 370041901:**
   - **BLS Result:** Peak $P = 0.55081$ d, SDE 4.35 (< 6.0), SNR 5.5, depth 89 ppm.
   - **Assessment:** Correctly rejected by SDE threshold; quiet field star.

5. **TIC 197712257:**
   - **BLS Result:** Peak $P = 0.97624$ d, SDE 5.32 (< 6.0), SNR 5.4, depth 1030 ppm.
   - **Assessment:** Correctly rejected by SDE threshold; faint M dwarf field star.

---

## Light Curve Coherence Assessment

- **Coherence Status:** **Coherent Across All 10 Targets.**
- **Evidence:**
  - The scalar median-normalized curves exhibit stable continuum baselines without unphysical normalization artifacts.
  - Confirmed planet host transits phase-fold into clear, distinct box-like dips centered on zero phase.
  - Telemetry gaps (mid-sector momentum dumps and downlink) are cleanly isolated by the quality bitmask without leaving stray NaN or zero-flux values.
  - No artificial smoothing, outlier clipping, or high-pass filtering was applied, preserving authentic transit shapes and depths.

---

## Caveats and Limitations

1. **Feasibility Run Scope:** This run verifies end-to-end software feasibility, data integrity, and protocol mechanics on $N=10$ Sector 1 targets. It does **not** constitute the Stage 2 production benchmark ($N=100$) and must not be used to claim generalized detector performance or final model rankings.
2. **Harmonic Policy:** LHS 3844 demonstrates the necessity of GATE-04 harmonic bookkeeping: when $P < 0.50$ d, recovery at $2\times$ is expected and scientifically meaningful, but must be segregated from fundamental recoveries.
3. **Comparison Star Nature:** The detection on TIC 265591866 underscores that field comparison stars are observational non-detection controls, not verified planet-free stars. In Stage 2, false positive vetting (e.g. depth checks for EBs) must be applied.
4. **Pending Epoch Matching:** Under GATE-12 Option C, epoch matching is defined but remains marked as pending formal scoring engine implementation.

---

## Output Artifacts

All Stage 1 outputs have been saved to `results/real_data_pilot/stage1/`:
- Diagnostic Plots: `results/real_data_pilot/stage1/plots/stage1_diagnostic_TIC_*.png`
- Overview Plot: `results/real_data_pilot/stage1/plots/stage1_overview_all_10.png`
- Summary CSV: `results/real_data_pilot/stage1/stage1_summary.csv`
- Metadata JSON: `results/real_data_pilot/stage1/stage1_metadata.json`
- Run Report: `results/real_data_pilot/stage1/stage1_run_report.md`