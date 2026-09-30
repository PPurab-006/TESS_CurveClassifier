# Methodological Audit and Revision Report: Protocol v1.3

**Project**: TESS Transit Detection Benchmark  
**Document ID**: `docs/protocol_v1_3_revision_report.md`  
**Date**: 2026-09-28  
**Scope**: Documentation-Only Methodological Audit and Mathematical Correction of Benchmark Protocol v1.2 $\to$ v1.3  
**Status**: **COMPLETED AUDIT REPORT — SUBMITTED FOR RESEARCHER REVIEW**  

---

## Executive Summary

This report documents the rigorous, documentation-only methodological audit and mathematical correction of the **TESS Transit Detection Benchmark Protocol**, incrementing the specification from **Version 1.2 to Version 1.3**.

In accordance with strict research integrity constraints:
- **No code, runners, scorers, wrappers, or models were implemented.**
- **No observational or catalog data were downloaded, modified, or re-ingested.**
- **No models were trained, evaluated, or benchmarked.**
- **No existing metrics, plots, predictions, or scientific outputs were altered.**
- **No researcher decision gates were approved; all 12 formal gates remain strictly marked `AWAITING RESEARCHER APPROVAL`.**
- **No empirical claims of protocol validation, data leakage prevention, or scientific completeness are asserted.**

---

## Phase 1: Inspection of Current Documentation

### 1.1 Files Inspected
1. `docs/real_data_benchmark_protocol.md` (v1.2 base protocol)
2. `docs/benchmark_decision_log.md` (v1.2 decision log)
3. `results/real_data_pilot/protocol_readiness_checklist.md` (v1.2 readiness checklist)
4. `configs/real_benchmark_protocol.yaml` (v1.2 configuration specification)
5. `results/real_data_pilot/pilot_report.md` (pilot ingestion & QA report)
6. `results/real_data_pilot/integrity_audit.md` (Sector 1 data integrity audit)
7. `results/real_data_pilot/cadence_reconciliation.csv` (cadence audit table)
8. `results/real_data_pilot/ephemeris_validation.csv` (ephemeris records)
9. `src/tess_benchmark/baselines/bls.py` (existing BLS wrapper)
10. `src/tess_benchmark/data/tess_loader.py` (TESS FITS loader and overlap calculator)

### 1.2 Current Definitions and Equations Identified in v1.2
- **Transit Depth Uncertainty**: Earlier documentation stated depth uncertainty informally without providing the explicit variance of difference between weighted means, or omitted the square root in standard error representations ($\sigma_\delta = \sqrt{\operatorname{Var}(\delta)}$). Furthermore, Signal Detection Efficiency (SDE) and Signal-to-Noise Ratio (SNR) were occasionally referenced in overlapping diagnostic contexts without strict operational decoupling.
- **Event Coverage**: Coverage ratio in v1.1/v1.2 did not explicitly clamp the ratio $N_{\text{valid}} / N_{\text{expected}}$ to $\le 1.0$, allowing slight cadence timing jitter to produce fractions $> 100\%$. The denominator for event recovery was loosely defined across predicted vs observed transits.
- **Ephemeris Uncertainty**: Previous drafts assumed linear propagation $\sigma_{t_{\text{mid}}} = \sqrt{\sigma_{T_0}^2 + E^2 \sigma_P^2}$, omitting the general covariance term $2 E \operatorname{Cov}(T_0, P)$ and leaving the zero-covariance assumption implicit rather than formally documented as a catalog data limitation.
- **BLS Frequency Grid**: Protocol v1.1 had specified a coarse uniform step ($\Delta f \approx 0.00730\text{ d}^{-1}$), which produced phase smearing ($\sim 4.8\text{ h}$ drift across 27.4 d at $P=1\text{ d}$). While v1.2 introduced the duration-dependent formula, the dimensional definitions, baseline distinction ($T_{\text{usable}}$ vs nominal baseline), and Astropy API pinning remained underspecified.
- **Detrending**: 1.25-day running median detrending was adopted to satisfy $W \ge \max(3 T_{\text{dur, max}}, 1.05\text{ d})$, but the risk of transit attenuation by unmasked running medians was unacknowledged, and no empirical synthetic-injection validation experiment was formalized.

### 1.3 Contradictions Identified Between Protocol, Report, and Configuration
1. **Nominal vs Usable Baseline**: The configuration referenced a nominal 27.4-day sector duration for frequency grid calculations, whereas genuine TESS light curves exhibit usable spans $T_{\text{usable}} = t_{\max} - t_{\min} \approx 24.5\text{--}26.0\text{ days}$ due to sector-edge truncations and downlink slews.
2. **Coverage Fraction vs Count Ratio**: The configuration and protocol allowed $N_{\text{valid}} / N_{\text{expected}}$ to serve simultaneously as a coverage fraction (which must be bounded in $[0, 1]$) and an unconstrained cadence count ratio.
3. **ML Task Terminology**: Early text referred to Random Forest and HistGradientBoosting as "transit search baselines," while their technical implementation operates on 22 tabular features derived from the BLS periodogram, making them candidate vetting classifiers rather than independent search engines.
4. **Denominator Ambiguity in Event Recovery**: Pilot text occasionally reported recovery percentages over all predicted geometric transits rather than strictly over adequately covered transits, confounding physical detector sensitivity with satellite telemetry downlink loss.

### 1.4 Classification of Changes
- **Purely Mathematical / Documentary Corrections** (Implemented directly in protocol text):
  - Formulating $\operatorname{Var}(\delta) = (\sum_{\text{in}} w_i)^{-1} + (\sum_{\text{out}} w_j)^{-1}$ with standard error $\sigma_\delta = \sqrt{\operatorname{Var}(\delta)}$ and equivalent WLS regression covariance matrix.
  - Decoupling physical SNR ($\delta / \sigma_\delta$) from spectral SDE ($(P_{\max} - \mu) / \sigma$).
  - Clamping coverage fraction $f_{\text{coverage}} = \min(1.0, N_{\text{valid}} / N_{\text{expected}})$ and defining count ratio $R_{\text{cadence}}$.
  - Defining the general ephemeris variance $\operatorname{Var}(t_{\text{mid}}) = \sigma_{T_0}^2 + E^2 \sigma_P^2 + 2 E \operatorname{Cov}(T_0, P)$ and documenting catalog covariance absence.
  - Specifying all dimensional units in the BLS frequency-spacing equation.
  - Formally distinguishing transit search (Task A) from candidate vetting (Task B).
  - Explicitly bounding all pilot claims to $N=10$ feasibility and ingestion verification.
- **Methodological Choices Requiring Researcher Approval** (Preserved as Decision Gates):
  - GATE-01 through GATE-12 (e.g. period matching tolerance, detrending filter algorithm, BLS frequency grid construction, BLS flux weighting, SDE background distribution, cohort size).

---

## Phase 2: Detailed Methodological Corrections and Clarifications

### 1. Transit-Depth Uncertainty, WLS Regression Covariance, and SNR vs SDE Decoupling
- **Difference of Independent Weighted Means**:
  For cadence flux $y_i$ with diagonal weights $w_i = 1 / \sigma_i^2$, weighted in-transit mean $\bar{y}_{\text{in}} = (\sum_{\text{in}} w_i y_i) / (\sum_{\text{in}} w_i)$ and out-of-transit mean $\bar{y}_{\text{out}} = (\sum_{\text{out}} w_j y_j) / (\sum_{\text{out}} w_j)$:
  $$\operatorname{Var}(\bar{y}_{\text{in}}) = \frac{1}{\sum_{i \in \text{in}} w_i}, \quad \operatorname{Var}(\bar{y}_{\text{out}}) = \frac{1}{\sum_{j \in \text{out}} w_j}$$
  $$\operatorname{Var}(\delta) = \operatorname{Var}(\bar{y}_{\text{out}} - \bar{y}_{\text{in}}) = \frac{1}{\sum_{i \in \text{in}} w_i} + \frac{1}{\sum_{j \in \text{out}} w_j}$$
  $$\sigma_\delta = \sqrt{\operatorname{Var}(\delta)} = \sqrt{\frac{1}{\sum_{i \in \text{in}} w_i} + \frac{1}{\sum_{j \in \text{out}} w_j}}$$
  The square root is strictly included.
  $$\text{SNR} = \frac{\delta}{\sigma_\delta} = \frac{\delta}{\sqrt{\operatorname{Var}(\delta)}}$$
- **Equivalent Weighted Least-Squares (WLS) Regression Representation**:
  Model: $y_i = \beta_0 + \beta_1 x_i + \epsilon_i$, where $x_i = 1$ (in-transit) and $x_i = 0$ (out-of-transit).
  Here $L = \beta_0$, $\delta = -\beta_1$, and $\mathbf{\epsilon} \sim \mathcal{N}(\mathbf{0}, \mathbf{W}^{-1})$ with diagonal weight matrix $W_{ii} = w_i = 1/\sigma_i^2$.
  Design matrix $\mathbf{X} = [\mathbf{1}, \mathbf{x}]$ gives:
  $$\operatorname{Cov}(\mathbf{\beta}) = (\mathbf{X}^T \mathbf{W} \mathbf{X})^{-1} = \frac{1}{(\sum_{\text{out}} w_j)(\sum_{\text{in}} w_i)} \begin{pmatrix} \sum_{\text{in}} w_i & -\sum_{\text{in}} w_i \\ -\sum_{\text{in}} w_i & \sum_{\text{all}} w_i \end{pmatrix}$$
  The transit depth variance is the lower-right element:
  $$\operatorname{Var}(\delta) = \operatorname{Var}(\beta_1) = \frac{\sum_{\text{all}} w_i}{(\sum_{\text{out}} w_j)(\sum_{\text{in}} w_i)} = \frac{1}{\sum_{i \in \text{in}} w_i} + \frac{1}{\sum_{j \in \text{out}} w_j}$$
  Assumptions: Errors $\epsilon_i$ are independent, zero-mean Gaussian white noise with known variances $\sigma_i^2 = 1/w_i$ (idealized white-noise lower bound; red noise ignored by standard BLS).
- **Decoupling Physical SNR from Spectral SDE**:
  - SNR ($\delta / \sigma_\delta$) measures the physical photometric significance of the transit dip in the time domain.
  - SDE ($(P_{\max} - \mu_{\text{Power}}) / \sigma_{\text{Power}}$) measures the prominence of a periodogram peak relative to the spectral noise floor in the frequency domain.
  - They quantify fundamentally different properties and are never treated as interchangeable.

### 2. Event Coverage and Cadence Accounting
- **Five-Tier Event Hierarchy**:
  1. $N_{\text{predicted}}$: Total predicted geometric transit midtimes across mission timeline.
  2. $N_{\text{baseline}}$: Events whose window intersects observation baseline $[t_{\min}, t_{\max}]$.
  3. $N_{\text{downloaded}}$: Events with $\ge 1$ raw cadences in FITS table.
  4. $N_{\text{valid}}$: Events with $\ge 1$ cadences satisfying $\text{QUALITY}=0$ and finite flux/time.
  5. $N_{\text{adequate}}$: Events satisfying the predeclared adequacy criterion ($N_{\text{valid}} \ge 5$ AND $f_{\text{coverage}} \ge 50\%$).
- **Transit Duration vs Evaluation Window**:
  - Physical Transit Duration ($T_{\text{dur}}$): 1st to 4th contact time ($t_4 - t_1$).
  - Event Evaluation Window ($W_{\text{event}, k}$): Time interval evaluated $[t_{\text{mid}, k} - T_{\text{dur}}/2, t_{\text{mid}, k} + T_{\text{dur}}/2]$.
- **Cadence Calculations**:
  - Nominal cadence duration: $\Delta t_{\text{nominal}} = 120.0\text{ s} = 2.0\text{ min} = 0.001388889\text{ d}$.
  - Expected cadences: $N_{\text{expected}, k} = T_{\text{dur}} / \Delta t_{\text{nominal}}$.
  - Clamped coverage fraction: $f_{\text{coverage}, k} = \min(1.0, N_{\text{valid}, k} / N_{\text{expected}, k})$.
  - Cadence count ratio: $R_{\text{cadence}, k} = N_{\text{valid}, k} / N_{\text{expected}, k}$ (may exceed 1.0).
- **Partial and Edge-of-Sector Handling**:
  - Events overlapping $t < t_{\min}$ or $t > t_{\max}$ are classified as "Sector-Boundary Truncation."
  - Events with $0 < N_{\text{valid}} < 5$ or $f_{\text{coverage}} < 50\%$ are classified as "Insufficient Coverage."
  - An event with 1 valid cadence is strictly classified as insufficient and excluded from the event-recovery denominator ($N_{\text{adequate}}$).

### 3. Ephemeris Uncertainty and Epoch Alignment
- **General Ephemeris Variance**:
  $$\operatorname{Var}(t_{\text{mid}}(E_k)) = \sigma_{T_0}^2 + E_k^2 \sigma_P^2 + 2 E_k \operatorname{Cov}(T_0, P)$$
  $$\sigma_{t_{\text{mid}}}(E_k) = \sqrt{\operatorname{Var}(t_{\text{mid}}(E_k))}$$
- **Covariance Limitation**:
  NASA Exoplanet Archive tables omit $\operatorname{Cov}(T_0, P)$. The independence approximation $\operatorname{Cov}(T_0, P) \approx 0$ is adopted out of necessity. Its potential to under- or overestimate timing uncertainty is formally acknowledged.
- **Time Standard & Alignment Mechanics**:
  - Time standard: Barycentric TESS Julian Date ($\text{BTJD} = \text{BJD}_{\text{TDB}} - 2457000.0$).
  - Catalog epoch $T_0$ represents the physical transit midtime (center).
  - $T_0$ is propagated by integer orbital count $E_k$ to the nearest transit midtime within the sector baseline.
  - Circular phase distance formula:
    $$\Delta \phi = \left| \left( \left( \frac{t_{0,\text{det}} - t_{\text{mid}, k}}{P_{\text{true}}} + 0.5 \right) \pmod 1 \right) - 0.5 \right|, \quad \Delta t_0 = \Delta \phi \cdot P_{\text{true}}$$
  - Tolerance condition: $\Delta t_0 \le \Delta t_{0,\text{tol}} \equiv \max(0.5 \times T_{\text{dur}}, 3 \times \sigma_{t_{\text{mid}}})$.
  - Large epoch offsets ($E \gg 1$): Filtered by target eligibility criterion $\sigma_{t_{\text{mid}}} \le 0.25 T_{\text{dur}}$.
  - Ephemerides are air-gapped strictly to the evaluation layer; they are never inputs to detection algorithms.

### 4. BLS Frequency-Grid Reproducibility
- **Physics of Phase Drift**:
  Cumulative phase shift across usable baseline: $\delta \phi = T_{\text{usable}} \cdot \delta f$.
  To prevent smearing beyond transit duty cycle $q = T_{\text{dur}} / P$:
  $$\Delta f(P) \le \frac{q}{f_{\text{factor}} \cdot T_{\text{usable}}} = \frac{T_{\text{dur}}}{P \cdot f_{\text{factor}} \cdot T_{\text{usable}}}$$
- **Dimensional Terms & Units**:
  - $T_{\text{usable}}$: Actual usable baseline ($t_{\max} - t_{\min}$) in days [T].
  - $P$: Trial period in days [T], $P \in [0.5, 15.0]\text{ d}$.
  - $T_{\text{dur}}$: Trial duration in days [T], $T_{\text{dur}} \in [0.0417, 0.3333]\text{ d}$.
  - $q = T_{\text{dur}} / P$: Duty cycle [dimensionless].
  - $f_{\text{factor}}$: Oversampling factor [dimensionless].
  - $\Delta f(P)$: Frequency spacing in $\text{days}^{-1}$ [$\text{T}^{-1}$].
  - $N_{\text{transits, min}} = 2$: Minimum observed transits required for period search eligibility.
- **Astropy Pinning & Calibration**:
  - API: `astropy.timeseries.BoxLeastSquares.autoperiod()`. Pinning requirement: `astropy>=6.0`.
  - Calibration: $f_{\text{factor}}$ must be calibrated on synthetic injection grids with known parameters, never on real benchmark targets.

### 5. Detrending and Transit Preservation
- **1.25-Day Running Median Specification**:
  - Standardized window: $W_{\text{detrend}} = 1.25\text{ days} = 30.0\text{ hours}$, satisfying $W \ge \max(3 T_{\text{dur, max}}, 1.05\text{ d})$.
  - Segment-wise processing: Filter operates independently per continuous observation segment. Smoothing across telemetry gaps $> 6.0\text{ hours}$ is strictly prohibited.
  - Short segments ($< 1.25\text{ d}$): Detrended by scalar median subtraction and tagged `short_segment: bool`.
  - Edge handling: Cadences within $W/2$ of segment edges tagged `edge_affected: bool`.
  - Transit masking: Strictly unavailable during blind detection due to the ephemeris air-gap.
- **Transit Attenuation Risk & Mandatory Synthetic Validation**:
  - Unmasked running medians can attenuate deep transits ($T_{\text{dur}} = 6\text{--}8\text{ h}$ occupies $20\text{--}27\%$ of the window) during stellar activity or flare recovery.
  - The protocol explicitly refrains from claiming transit preservation until empirical validation has been executed.
  - Validation procedure: Inject limb-darkened transits ($\delta \in [500, 20000]\text{ ppm}, T_{\text{dur}} \in [1, 8]\text{ h}, P \in [0.5, 15]\text{ d}$) into quiet flight light curves. Acceptance requires $R_{\text{depth}} \ge 0.95$ for $T_{\text{dur}} \le 6\text{ h}$ and $R_{\text{depth}} \ge 0.90$ for $T_{\text{dur}} \in [6, 8]\text{ h}$.

### 6. SDE Background and Frequency Exclusions
- **Specification**:
  - Peak: $P_{\max} = \max_f \text{Power}(f)$.
  - Background power statistics $(\mu_{\text{Power}}, \sigma_{\text{Power}})$ computation: Choices between unclipped vs $3\sigma$ iterative clipping / peak exclusion are preserved under `GATE-11` (`REQUIRES_RESEARCHER_APPROVAL`).
  - Invalid bins: Non-finite power points (NaN, Inf) and negative power values are masked. If $< 50$ valid frequency bins remain, SDE is flagged invalid.
  - Pilot outcome isolation: The background method must not be selected based on pilot outcomes.

### 7. Separation of Search vs Candidate Vetting Tasks
- **Task Distinction**:
  - **Task A (Transit Search)**: Blindly scans time series across period-duration space to detect periodic transit dips and estimate $(P, t_0, T_{\text{dur}}, \delta)$ (e.g. BLS).
  - **Task B (Candidate Vetting)**: Takes pre-generated periodic candidate from search step, extracts diagnostic features (e.g. 22 tabular features), and classifies/ranks candidate as transit vs false alarm (e.g. Random Forest, HistGradientBoosting, CNN).
- **Prohibition on Direct Comparison**:
  Vetting classifiers must never be compared directly against BLS search as equivalent search tools.
- **ML Vetting Controls**:
  - Feature provenance: 22 features extracted blind to catalog labels.
  - Training data: Disjoint external data (synthetic or out-of-sector) with zero test target overlap.
  - Grouping: `StarGroupSplitter` ensures all sectors of a target remain in the same split.
  - Comparison stars: Evaluated as non-detection controls, never labeled confirmed false positives.

### 8. Evidence Boundaries and Claims
- **Pilot Scope**: Sector 1 pilot ($N=10$: 5 hosts, 5 controls) is strictly bounded to software feasibility, data ingestion, and FITS QA verification.
- **Astronomical Reality**: Comparison stars are not proven planet-free; detections evaluate sensitivity to stellar variability and systematics.
- **Population Extrapolation Prohibited**: Balanced 50:50 sampling cannot estimate deployment prevalence, PPV, or survey-level false alarm rates.
- **Cadence vs Adequacy**: Valid cadences do not automatically imply adequate transit coverage.
- **Evaluation Independence**: Injection-and-recovery (measuring completeness function $\eta$) and known-planet recovery (testing recovery of catalogued systems) are distinct evaluations.

---

## Phase 3: Comprehensive Decision Gates Table

The formal registry of 12 decision gates is summarized below. **All gates remain unapproved and require explicit researcher sign-off.**

| Gate ID | Topic | Proposed Option | Alternative Options | Methodological Consequences | Evidence Needed to Choose | Synthetic Calibration Feasible? | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **GATE-01** | Period Matching Tolerance | Relative tolerance $\epsilon_P = 1.0\%$ ($0.01$) | Fourier resolution limit: $3 \times P^2 / T_{\text{usable}}$ | Option A is scale-invariant; Option B scales with physical Fourier peak width ($P^2$). | Peak width distributions from periodogram simulations across $P \in [0.5, 15]\text{ d}$. | Yes | **AWAITING APPROVAL** |
| **GATE-02** | CNN Dual Validation Gate | Specificity $\ge 0.85$ AND Sensitivity $\ge 0.75$ | Specificity $\ge 0.90$ AND Sensitivity $\ge 0.80$ | Prevents degenerate all-positive or all-negative collapse before lifting probation. | Independent validation test report on disjoint flight/synthetic split. | Yes | **AWAITING APPROVAL** |
| **GATE-03** | Window Cadence Adequacy | $N_{\text{valid}} \ge 5$ cadences AND $f_{\text{coverage}} \ge 50\%$ | $N_{\text{valid}} \ge 3$ cadences AND $f_{\text{coverage}} \ge 30\%$ | Option A ensures physical detectability; Option B increases sample size but includes sparse dips. | Transit fitting error vs in-transit cadence count under TESS noise. | Yes | **AWAITING APPROVAL** |
| **GATE-04** | Harmonic Set Definition | $\mathcal{H} = \{1/3, 1/2, 2, 3\}$ | Restrict strictly to $\mathcal{H} = \{1/2, 2\}$ | Option A captures 3:1 orbital resonance aliases; Option B restricts to half/double period. | Frequency distribution of secondary BLS peaks from exoplanet archives. | Yes | **AWAITING APPROVAL** |
| **GATE-05** | Detrending Filter Type | Segment-wise running median ($W=1.25\text{ d}$) | Segment-wise robust biweight spline ($W=1.25\text{ d}$) | Median is non-parametric but risks attenuation; spline is smooth but slower. | Depth preservation ratio $R_{\text{depth}} \ge 0.95$ from synthetic validation. | Yes | **AWAITING APPROVAL** |
| **GATE-06** | Multi-Planet Handling | Restrict primary cohort to single confirmed hosts | Score against highest-depth planet in system | Option A guarantees unambiguous single-peak ground truth; Option B increases sample size. | Target yield analysis in Sectors 1–5 for single vs multi-planet hosts. | Partial | **AWAITING APPROVAL** |
| **GATE-07** | Search Range Boundaries | Restrict cohort to $P \in [0.5, 15.0]\text{ days}$ | Expand BLS grid to $P_{\max} = 25.0\text{ days}$ | Option A guarantees $\ge 2$ transits; Option B tests long periods but includes single transits. | Exoplanet Archive target yield for $P \le 15\text{ d}$ vs $P \le 25\text{ d}$. | Yes | **AWAITING APPROVAL** |
| **GATE-08** | Production Cohort Size | 50 Confirmed Hosts, 50 Comparison Stars | 30 Hosts, 30 Comparison Stars | Option A narrows Wilson CI half-widths ($\pm 10\text{--}14\%$); Option B saves compute. | Available confirmed hosts meeting all eligibility criteria across Sectors 1–5. | No (Resource/Catalog) | **AWAITING APPROVAL** |
| **GATE-09** | BLS Frequency Grid Spacing | Astropy `autoperiod` duration-adaptive scaling | Fixed uniform frequency grid ($\Delta f \approx 0.00730\text{ d}^{-1}$) | Adaptive grid prevents transit phase smearing; uniform grid oversamples or smears. | Completeness vs runtime trade-off on synthetic injection grid. | Yes | **AWAITING APPROVAL** |
| **GATE-10** | BLS Flux Weighting Model | Inverse-variance weighting ($w_i = 1 / \sigma_i^2$) | Uniform weighting ($w_i = 1$) | Option A provides maximum-likelihood weights; Option B is robust to error misestimation. | Empirical photometric error distribution and transit recovery comparison. | Yes | **AWAITING APPROVAL** |
| **GATE-11** | SDE Background Estimation | All frequencies unclipped | Iterative $3\sigma$ clipping of periodogram peaks | Option A is simpler; Option B isolates continuum noise floor from strong harmonics. | False-alarm distribution on comparison stars under Option A vs B. | Yes | **AWAITING APPROVAL** |
| **GATE-12** | Epoch Matching Tolerance | $\Delta t_{0,\text{tol}} = 0.5 \times T_{\text{dur}}$ | $\Delta t_{0,\text{tol}} = 0.25 \times T_{\text{dur}}$ | Option A tests dip overlap; Option B tests flat bottom alignment (fails for V-shapes). | Recovered epoch offset distribution on flight-like synthetic transits. | Yes | **AWAITING APPROVAL** |

---

## Phase 4: Validation and Change Control

### 4.1 Mathematical and Dimensional Consistency Verification
1. **Transit Depth Uncertainty**:
   $$\operatorname{Var}(\delta) = \frac{1}{\sum_{i \in \text{in}} w_i} + \frac{1}{\sum_{j \in \text{out}} w_j}$$
   With weights $w_i = 1 / \sigma_i^2$ (units: $\text{flux}^{-2}$), $\sum w_i$ has units $\text{flux}^{-2}$. Thus $\operatorname{Var}(\delta)$ has units $\text{flux}^2$, and $\sigma_\delta = \sqrt{\operatorname{Var}(\delta)}$ has units $\text{flux}$, matching transit depth $\delta$. Dimensionally exact.
2. **Signal-to-Noise Ratio**:
   $$\text{SNR} = \frac{\delta}{\sigma_\delta} \quad \left[\frac{\text{flux}}{\text{flux}} = 1 \text{ (dimensionless)}\right]$$
   Dimensionally exact.
3. **Signal Detection Efficiency**:
   $$\text{SDE} = \frac{P_{\max} - \mu_{\text{Power}}}{\sigma_{\text{Power}}} \quad \left[\frac{\text{power}}{\text{power}} = 1 \text{ (dimensionless)}\right]$$
   Dimensionally exact.
4. **General Ephemeris Variance**:
   $$\operatorname{Var}(t_{\text{mid}}) = \sigma_{T_0}^2 + E^2 \sigma_P^2 + 2 E \operatorname{Cov}(T_0, P) \quad \left[\text{days}^2 + 1 \cdot \text{days}^2 + 1 \cdot \text{days}^2 = \text{days}^2\right]$$
   Standard error $\sigma_{t_{\text{mid}}} = \sqrt{\operatorname{Var}(t_{\text{mid}})}$ has units of days, matching $T_{\text{dur}}$. Dimensionally exact.
5. **BLS Adaptive Frequency Spacing**:
   $$\Delta f(P) = \frac{T_{\text{dur}}}{P \cdot f_{\text{factor}} \cdot T_{\text{usable}}} \quad \left[\frac{\text{days}}{\text{days} \cdot 1 \cdot \text{days}} = \frac{1}{\text{days}} = \text{days}^{-1}\right]$$
   Matches frequency units $\text{days}^{-1}$. Dimensionally exact.
6. **Circular Phase Distance**:
   $$\Delta \phi = \left| \left( \left( \frac{t_{0,\text{det}} - t_{\text{mid}, k}}{P_{\text{true}}} + 0.5 \right) \pmod 1 \right) - 0.5 \right| \quad \left[\frac{\text{days}}{\text{days}} = \text{dimensionless, bounded in } [0, 0.5]\right]$$
   $$\Delta t_0 = \Delta \phi \cdot P_{\text{true}} \quad [1 \cdot \text{days} = \text{days}]$$
   Dimensionally exact.
7. **Event Coverage**:
   $$N_{\text{expected}} = \frac{T_{\text{dur}}}{\Delta t_{\text{nominal}}} \quad \left[\frac{\text{days}}{\text{days}} = 1 \text{ (count)}\right]$$
   $$f_{\text{coverage}} = \min\left(1.0, \frac{N_{\text{valid}}}{N_{\text{expected}}}\right) \quad [\text{dimensionless, strictly bounded in } [0, 1]]$$
   Dimensionally exact.

### 4.2 Terminology Consistency Check
- Terminology standard: Detections on comparison stars are strictly referred to as the **"comparison-star detection rate"** or **"catalog-inconsistent detection rate,"** never "confirmed false positives."
- Task separation: Tabular ML models are formally designated as **"BLS-Candidate Vetting Classifiers,"** never "independent transit search baselines."
- Decoupled scoring: Fundamental period recovery, harmonic recovery, epoch alignment, and target-level classification are strictly segregated.

### 4.3 YAML Configuration Syntax Validation
- Validated via Python `yaml.safe_load(open('configs/real_benchmark_protocol.yaml'))`.
- Validation status: **100% Valid (Exit Code 0, Zero Parsing Errors)**.

### 4.4 Data and Results Immutability Check
- Confirmed: No data files under `data/` were modified.
- Confirmed: No model weights or checkpoint files were modified.
- Confirmed: No historical metrics, plots, or results under `results/` were modified (only the readiness checklist was updated).
- Confirmed: Existing pytest test suite passes completely (48 passed, 0 failed, 91% code coverage).

### 4.5 File Modification Ledger

| File Path | Version | Action | Summary of Changes |
| :--- | :---: | :---: | :--- |
| `docs/real_data_benchmark_protocol.md` | v1.3 | Modified | Rewrote protocol to v1.3: transit-depth variance $\operatorname{Var}(\delta) = (\sum_{\text{in}} w_i)^{-1} + (\sum_{\text{out}} w_j)^{-1}$, $\sigma_\delta = \sqrt{\operatorname{Var}(\delta)}$, WLS regression covariance matrix, SDE vs SNR decoupling, general ephemeris variance, BLS grid dimensional terms, five-tier event coverage, detrending attenuation risk & synthetic validation, ML candidate-vetting role, bounded claims. |
| `docs/benchmark_decision_log.md` | v1.3 | Modified | Updated to v1.3: refined BDR-001 through BDR-016 with mathematical corrections, and expanded formal Decision Gate registry for GATE-01 through GATE-12 with complete profiles. |
| `results/real_data_pilot/protocol_readiness_checklist.md` | v1.3 | Modified | Updated to v1.3: mapped all v1.3 mathematical corrections, general ephemeris variance, five-tier event hierarchy, synthetic validation requirements, and synchronized decision gates. |
| `configs/real_benchmark_protocol.yaml` | v1.3.0 | Modified | Updated to v1.3.0: synchronized all configuration parameters, formulas, gate markers, and validated YAML syntax. |
| `docs/protocol_v1_3_revision_report.md` | v1.3 | Created | Created comprehensive methodological audit and revision report documenting all changes, rationale, equations, gates, and validation checks. |

### 4.6 Unresolved Methodological Decisions Requiring Researcher Approval
The following decisions cannot be resolved purely through documentation or mathematics and require explicit researcher approval:
1. **GATE-01**: Period matching relative tolerance ($\epsilon_P = 1.0\%$) vs Fourier limit.
2. **GATE-02**: CNN dual validation gate thresholds (Specificity $\ge 0.85$, Sensitivity $\ge 0.75$).
3. **GATE-03**: Event window cadence adequacy thresholds ($N_{\text{valid}} \ge 5, f_{\text{coverage}} \ge 50\%$).
4. **GATE-04**: Harmonic set definition ($\mathcal{H} = \{1/3, 1/2, 2, 3\}$ vs $\{1/2, 2\}$).
5. **GATE-05**: Detrending filter algorithm (running median vs robust biweight spline).
6. **GATE-06**: Multi-planet system eligibility policy (exclude vs score highest-depth planet).
7. **GATE-07**: Search range maximum period ($P_{\max} = 15.0\text{ d}$ vs $25.0\text{ d}$).
8. **GATE-08**: Production cohort size (50 hosts / 50 controls vs 30 / 30).
9. **GATE-09**: BLS frequency grid construction (adaptive `autoperiod` vs high-density uniform).
10. **GATE-10**: BLS flux weighting model (inverse-variance $w_i = 1/\sigma_i^2$ vs uniform $w_i = 1$).
11. **GATE-11**: SDE background power distribution estimation (unclipped vs $3\sigma$ iterative clipping).
12. **GATE-12**: Epoch matching tolerance ($\Delta t_{0,\text{tol}} = 0.5 \times T_{\text{dur}}$ vs $0.25 \times T_{\text{dur}}$).

### 4.7 Explicit Documentation-Only Statement
**This revision was strictly documentary and methodological. No empirical validation, benchmark execution, model training, or data modification was performed.**
