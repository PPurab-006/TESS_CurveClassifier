# Stage 2 Real-Data Final Cohort Report (100 Qualified Stars)

**Protocol Stage:** Stage 2 Real-Data Production Cohort Finalization  
**Execution Date (UTC):** 2026-09-30T18:14:50.720000+00:00  
**Pipeline Author:** SPOC (Science Processing Operations Center)  
**Primary Data Product:** Native SPOC PDCSAP light curves (120-second cadence)  
**Normalization:** Scalar median normalization only ($F / \text{median}(F)$)  
**Approved Strategy:** Option 1 (Cleaner Sector Expansion)  
**Target Objective:** Exactly 50 Qualified Single-Planet Hosts + 50 Qualified Observational Controls = 100 Stars  
**Target Status:** **REACHED AND VALIDATED (100/100)**  

---

## 1. Executive Summary & Verification of Goals

| Metric | Target Goal | Achieved | Protocol Gate Status |
| :--- | :---: | :---: | :--- |
| **Total Cohort Stars** | **100** | **100** | **100% Qualified against all invariants** |
| **Confirmed Single-Planet Hosts** | **50** | **50** | **100% Verified single-planet systems ($P \in [0.5, 15.0]$ d)** |
| **Observational Comparison Stars** | **50** | **50** | **100% Observational non-detections (BDR-005; zero TOI/planet associations)** |
| **Multi-Planet Fallback Admitted** | **0** | **0** | **GATE-06 single-planet pool was ample; zero multi-planet systems used** |
| **Cadence Ratio Gate ($R_{\text{usable}} \ge 80\%$)** | $\ge 80.0\%$ | **80.78\%\text{--}93.65\%$** | **Strictly enforced; no threshold relaxation** |
| **Baseline Gate ($T_{\text{baseline}} \ge 20.0\text{ d}$)** | $\ge 20.0\text{ d}$ | **21.77\text{--}27.88\text{ d}$** | **Strictly enforced** |
| **Unique TIC IDs** | 100 | **100** | **Zero duplicate targets across final cohort** |

---

## 2. Cohort Assembly and Lineage Accounting

The 100-star production cohort was assembled by combining qualified targets from the initial acquisition run and the Option 1 cleaner-sector expansion run:

1. **Initial Acquisition Run:**
   - 100 candidate stars searched and acquired across Sectors 1–5 (20 per sector).
   - 59 targets passed all protocol gates:
     - 29 confirmed single-planet hosts (Sector 1: 9, Sector 2: 10, Sector 5: 10).
     - 30 observational controls (Sector 1: 10, Sector 2: 10, Sector 5: 10).
   - 41 targets excluded due to usable cadence ratio below 0.80:
     - Sector 3: 20 targets excluded (usable ratio 61.7%–66.1%; Earth/Moon scattered light).
     - Sector 4: 20 targets excluded (usable ratio 77.3%–79.3%; 2.5-day momentum dump frequency).
     - Sector 1: 1 target excluded (WASP-100; usable ratio 79.1%).
   - All original files preserved untouched in `stage2_candidate_manifest.csv` and `stage2_validated_manifest.csv`.

2. **Expansion Run (Option 1):**
   - Searched and acquired 52 additional candidates from cleaner sectors (Sectors 2, 5, 6).
   - 51 passed all protocol gates (26 hosts, 25 controls).
   - Admitted exactly 21 qualified single-planet hosts and 20 qualified observational controls to fulfill the 50 + 50 target.
   - All expansion records preserved in `stage2_expansion_candidates.csv` and `stage2_expansion_validated.csv`.

---

## 3. Final Sector Distribution

| Sector | Confirmed Hosts | Observational Controls | Sector Total | Usable Cadence (Median) | Baseline (Median) |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **Sector 1** | 9 | 10 | **19** | 91.03% | 27.88 d |
| **Sector 2** | 19 | 18 | **37** | 92.71% | 27.41 d |
| **Sector 5** | 18 | 18 | **36** | 90.39% | 26.20 d |
| **Sector 6** | 4 | 4 | **8** | 93.22% | 21.77 d |
| **Total** | **50** | **50** | **100** | **91.04%** | **27.41 d** |

---

## 4. Scientific Invariants & Quality Verification

All 100 final targets satisfy every invariant of the approved benchmark protocol:
1. **Product Authenticity:** 100% native SPOC PDCSAP FITS files retrieved from NASA MAST with verified SHA256 checksums and file sizes recorded.
2. **Quality Filtering:** Strictly `QUALITY == 0` standard clean mask applied; all instrumental artifacts isolated without data alteration.
3. **Temporal Baseline:** Minimum baseline is **21.77 days** (median **27.41 days**), all $\ge 20.0$ days.
4. **Timestamp Monotonicity:** Strictly monotonically increasing timestamps ($\Delta t > 0$, **0 duplicate timestamps**).
5. **Data Finiteness:** Filtered cadences contain **zero NaN or infinite** values in time, flux, or flux uncertainties. All uncertainties are positive and finite.
6. **Unsupervised Normalization:** Normalized strictly by scalar median division ($F / \text{median}(F)$). No filter detrending applied to primary benchmark product (GATE-05 Option 4).
7. **Host Restrictiveness:** 100% single-planet systems with catalogued ephemerides and $P \in [0.5, 15.0]$ days. Zero multi-planet systems admitted (GATE-06).
8. **Observational Control Provenance:** 100% field stars verified to have zero TOI, TCE, or confirmed planet associations. Designated strictly as `control_star` (observational non-detections, not proven planet-free; BDR-005).

---

## 5. Artifact Index and Provenance

- **Consolidated Final Cohort Manifest:** [`stage2_final_cohort_manifest.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_final_cohort_manifest.csv) (100 qualified stars).
- **Consolidated Summary JSON:** [`stage2_final_cohort_summary.json`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_final_cohort_summary.json).
- **Expansion Candidate Manifest:** [`stage2_expansion_candidates.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_expansion_candidates.csv).
- **Expansion Validated Manifest:** [`stage2_expansion_validated.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_expansion_validated.csv).
- **Original Initial Candidate Manifest:** [`stage2_candidate_manifest.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_candidate_manifest.csv) (100 initial candidates).
- **Original Initial Validated Manifest:** [`stage2_validated_manifest.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_validated_manifest.csv) (59 passed, 41 excluded).
