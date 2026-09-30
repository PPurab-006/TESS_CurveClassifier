# Stage 2 Real-Data Cohort Expansion Report

**Protocol Stage:** Stage 2 Real-Data Cohort Expansion (Option 1: Cleaner Sector Expansion)  
**Execution Date (UTC):** 2026-09-30T18:14:39.128722+00:00  
**Pipeline Author:** SPOC (Science Processing Operations Center)  
**Primary Data Product:** Native SPOC PDCSAP light curves (120-second cadence)  
**Normalization:** Scalar median normalization only ($F / \text{median}(F)$)  
**Expansion Sectors:** [2, 5, 6]  

---

## 1. Expansion Summary and Yield

| Metric | Additional Candidates Searched | Additional Targets Acquired | Qualified Targets ($R_{\text{usable}} \ge 80\%$) | Status / Attrition |
| :--- | :---: | :---: | :---: | :--- |
| **Total Expansion Stars** | 52 | 52 | **51** | **51/52 qualified** |
| **Confirmed Single-Planet Hosts** | 26 | 26 | **26** | **Single-planet hosts with $P \in [0.5, 15.0]$ d** |
| **Observational Comparison Stars** | 26 | 26 | **25** | **Observational non-detection controls (BDR-005)** |
| **Multi-Planet Fallback Targets** | 0 | 0 | **0** | **Zero multi-planet systems needed (pool ample)** |
| **Exclusions / Failures** | 0 | 0 | **1** | **1 targets excluded** |

---

## 2. Sector Distribution of Expansion Targets

| Sector | Candidates Searched | Acquired | Qualified Hosts | Qualified Controls | Total Qualified | Sector Yield |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Sector 2** | 17 | 17 | 9 | 8 | **17** | **100.0% Qualified** |
| **Sector 5** | 16 | 16 | 8 | 8 | **16** | **100.0% Qualified** |
| **Sector 6** | 18 | 18 | 9 | 9 | **18** | **100.0% Qualified** |

---

## 3. Data Integrity and Verification

1. **Temporal Baseline:** Min **21.77 d**, Max **27.41 d**, Median **26.20 d** (all $\ge 20.0$ d).
2. **Usable Cadence Fraction:** Min **0.7996**, Median **0.9271** (all $\ge 0.80$).
3. **Timestamp Monotonicity:** Strictly increasing ($\Delta t > 0$, zero duplicates): **True**.
4. **Data Finiteness:** Zero NaNs/Infs in filtered arrays; positive finite uncertainties: **True**.
5. **No Collisions:** Zero duplicate TIC IDs across initial and expansion cohorts.

---

## 4. Expansion Manifests

- **Expansion Candidates:** [`stage2_expansion_candidates.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_expansion_candidates.csv)
- **Expansion Validated:** [`stage2_expansion_validated.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_expansion_validated.csv)
- **Expansion Audit Report:** [`stage2_expansion_report.json`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_expansion_report.json)
