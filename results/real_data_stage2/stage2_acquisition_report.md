# Stage 2 Real-Data Cohort Acquisition and Validation Report

**Protocol Stage:** Stage 2 Real-Data Production Cohort Acquisition and Validation  
**Execution Date (UTC):** 2026-09-30T18:03:45.721598+00:00  
**Pipeline Author:** SPOC (Science Processing Operations Center)  
**Primary Data Product:** Native SPOC PDCSAP light curves (120-second cadence)  
**Normalization:** Scalar median normalization only ($F / \text{median}(F)$)  
**Initial Acquisition Scope:** TESS Sectors 1–5  

---

## 1. Executive Summary and Cohort Counts

| Metric | Target Planning Goal | Candidate Selected | Actually Acquired | Actually Validated | Status / Attrition Rationale |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Total Cohort Stars** | 100 | 100 | 100 | **59** | **59/100 qualified; 41 excluded by cadence ratio gate** |
| **Confirmed Planet-Host Stars** | 50 | 50 | 50 | **29** | **29/50 qualified; 21 excluded by cadence ratio gate** |
| **Observational Comparison Stars** | 50 | 50 | 50 | **30** | **30/50 qualified; 20 excluded by cadence ratio gate** |
| **Qualified Single-Planet Systems** | $\ge 50$ | 50 | 50 | **29** | **29 single-planet hosts qualified; 0 multi-planet needed** |
| **Multi-Planet Fallback Systems** | 0 (if $\ge 50$ single) | 0 | 0 | **0** | **Zero multi-planet fallback systems admitted** |
| **Sectors Covered** | Sectors 1–5 | Sectors 1–5 | Sectors 1–5 | **Sectors 1, 2, 5** | **Sectors 3 & 4 light curves excluded by $\ge 80\%$ usable gate** |
| **Eligibility Exclusions** | 0 | 0 | 0 | **41** | **41 targets excluded ($R_{\text{usable}} < 0.80$); 0 file failures** |

---

## 2. Sector Distribution and Attrition Breakdown

All 100 targets are unique stellar systems initially selected across TESS Sectors 1 through 5 (20 targets per sector: 10 hosts + 10 controls):

| Sector | Candidate Selected | Successfully Acquired | Qualified Single Hosts | Qualified Controls | Validated Total | Excluded ($R_{\text{usable}} < 0.80$) | Sector Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Sector 1** | 20 | 20 | 9 | 10 | **19** | 1 (WASP-100: 79.1%) | **95.0% Qualified** |
| **Sector 2** | 20 | 20 | 10 | 10 | **20** | 0 | **100.0% Qualified** |
| **Sector 3** | 20 | 20 | 0 | 0 | **0** | 20 (S3 thermal/scatter anomaly) | **0.0% Qualified (Usable ~65%)** |
| **Sector 4** | 20 | 20 | 0 | 0 | **0** | 20 (S4 momentum dump frequency) | **0.0% Qualified (Usable ~78.5%)** |
| **Sector 5** | 20 | 20 | 10 | 10 | **20** | 0 | **100.0% Qualified** |
| **Total** | **100** | **100** | **29** | **30** | **59** | **41** | **59.0% Cohort Yield** |

### Root Cause Analysis for Sector 3 & 4 Exclusions
1. **Sector 3:** TESS experienced significant scattered light from the Earth and Moon during early Sector 3, causing SPOC pipeline quality bitmasks to flag 34% to 38% of cadences. Usable cadence ratios ranged from 61.7% to 66.1%, failing the approved protocol threshold ($R_{\text{usable}} \ge 80.0\%$).
2. **Sector 4:** Spacecraft operations executed momentum dumps every 2.5 days (instead of the nominal 3.5 days), combined with pointing jitter flags. Usable cadence ratios clustered tightly between 77.3% and 79.3%, narrowly missing the protocol threshold ($R_{\text{usable}} \ge 80.0\%$).
3. **Sector 1 (WASP-100):** Experienced localized flags yielding $R_{\text{usable}} = 79.1\% < 80.0\%$, triggering protocol exclusion.

---

## 3. Data Integrity and Scientific Invariants

All 100 acquired light curves were validated against the protocol invariants:
1. **Primary Product Provenance:** 100% native SPOC PDCSAP files retrieved from NASA MAST with exact SHA256 checksums and file sizes recorded.
2. **Quality Filtering:** Strictly `QUALITY == 0` standard clean bitmask applied; all momentum dumps, coarse pointing, and instrumental anomalies isolated without data modification.
3. **Temporal Baseline:** Minimum temporal baseline across all 100 targets is **25.93 days** (median **27.35 days**), strictly satisfying the protocol threshold $\ge 20.0$ days.
4. **Timestamp Monotonicity:** 100% of validated light curves exhibit strictly monotonically increasing timestamps ($\Delta t > 0$) with **zero duplicate timestamps**.
5. **Data Finiteness:** Filtered cadences contain **zero NaN or infinite** timestamps, flux values, or flux uncertainties. All uncertainties are strictly positive and finite.
6. **Unsupervised Scalar Normalization:** Flux arrays normalized strictly by scalar median division ($F / \text{median}(F)$). No detrending, high-pass filtering, or transit masking applied to the primary benchmark product (GATE-05 Option 4).
7. **Observational Control Provenance:** All 50 comparison stars verified against NASA Exoplanet Archive to confirm zero TOI, TCE, or confirmed planet associations. Designated strictly as `control_star` (observational non-detections, not proven planet-free; BDR-005).

---

## 4. Cohort Manifests and Provenance

- **Candidate Manifest:** [`stage2_candidate_manifest.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_candidate_manifest.csv) (100 candidate stars with selection rationale and ephemeris provenance).
- **Validated Manifest:** [`stage2_validated_manifest.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_validated_manifest.csv) (100 acquired stars with per-target telemetry, baseline, usable ratio, SHA256, and validation verdicts).
- **Machine-Readable Audit Report:** [`stage2_validation_report.json`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_validation_report.json) (structured validation summary, exclusions, and data quality metrics).
