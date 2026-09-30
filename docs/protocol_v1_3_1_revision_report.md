# Methodological Consistency Audit and Revision Report: Protocol v1.3.1

**Project**: TESS Transit Detection Benchmark  
**Document ID**: `docs/protocol_v1_3_1_revision_report.md`  
**Date**: 2026-09-28  
**Scope**: Documentation-Only Consistency Audit and Methodological Reconciliation of Benchmark Protocol v1.3 $\to$ v1.3.1  
**Status**: **COMPLETED AUDIT REPORT — SUBMITTED FOR RESEARCHER REVIEW**  

---

## Executive Summary

This report documents the rigorous, documentation-only consistency audit and methodological reconciliation of the **TESS Transit Detection Benchmark Protocol**, advancing the specification from **Version 1.3 to Version 1.3.1**.

The audit addresses seven specific methodological tensions identified across the protocol specification, decision log, readiness checklist, and machine-readable YAML configuration. All mathematical definitions, operational constraints, and decision gates have been unified and synchronized without silently making empirical choices.

### Strict Change-Control Boundaries Maintained
In strict accordance with researcher change-control constraints:
1. **No code implementation**: No blind runner, scoring engine, wrapper classes (`BlindLightCurve`), or detector models were implemented.
2. **No data manipulation**: No TESS observations or exoplanet catalog records were downloaded, altered, or re-ingested.
3. **No model execution**: No models were trained, evaluated, tuned, or benchmarked.
4. **No metric alteration**: No historical metrics, plots, predictions, or scientific results were modified.
5. **No gate approvals**: All 12 formal researcher decision gates remain strictly flagged as `AWAITING RESEARCHER APPROVAL`.
6. **No empirical claims**: The protocol and its safeguards are documented as engineering specifications; **no empirical validation was performed**.

---

## Phase 1: Summary of Reconciled Methodological Issues

```
+-------------------------------------------------------------------------------------------------------------+
|                                    SEVEN RECONCILED METHODOLOGICAL DOMAINS                                   |
+-------------------------------------------------------------------------------------------------------------+
| 1. Epoch Matching & Eligibility | Formally segregated target ephemeris eligibility (sigma_tmid <= 0.25 Tdur)|
|                                 | from detected-epoch matching (Delta t0 <= tol); resolved tolerance       |
|                                 | options under GATE-12 without silently selecting a value.                  |
| 2. Event Coverage Formulation   | Defined continuous temporal coverage fraction f_temporal in [0, 1] via 1D |
|                                 | Lebesgue measure of valid exposure intervals; kept cadence count ratio    |
|                                 | R_cadence as a discrete diagnostic; prohibited cadence-only adequacy.     |
| 3. Sector-Boundary Truncation   | Defined boundary truncation by event window relative to [t_min, t_max];   |
|                                 | ruled partial events cannot qualify as adequate; excluded from recovery   |
|                                 | denominator N_adequate.                                                   |
| 4. Ephemeris Provenance & Cov   | Required source-specific proof that T0 is transit midpoint and time       |
|                                 | standard is BTJD; documented Cov(T0,P)=0 as an unverified catalog data    |
|                                 | limitation that is NOT conservative unless proven.                        |
| 5. BLS Grid & API Pinning       | Clarified min(Tdur) sets frequency grid spacing bound; specified exact     |
|                                 | Astropy autoperiod() API call; pinned astropy>=6.0.0; restricted          |
|                                 | oversampling calibration strictly to synthetic injections.                |
| 6. Detrending Validation        | Defined least-squares top-hat/trapezoid fit at injection ephemeris;       |
|                                 | defined uncorrupted denominator N_eval,uncorrupted; isolated edge         |
|                                 | subgroup; required distribution reporting; kept gate GATE-05 pending.     |
| 7. SDE Background Specification | Explicitly detailed peak exclusion window, invalid-bin masking (<50),     |
|                                 | harmonic/alias clipping, and robust MAD dispersion under GATE-11.         |
+-------------------------------------------------------------------------------------------------------------+
```

---

## Phase 2: Detailed Technical Reconciliation

### 1. Epoch Matching, Ephemeris Uncertainty, and Target Eligibility

#### The Inconsistency in v1.3
In Protocol v1.3, the epoch matching tolerance was stated in Section 6.2.3 as:
$$\Delta t_{0, \text{tol}} = \max(0.50 \times T_{\text{dur}}, 3 \sigma_{t_{\text{mid}}})$$
However, `GATE-12` in the Decision Log offered discrete alternatives of $0.50 \times T_{\text{dur}}$ and $0.25 \times T_{\text{dur}}$, while the a priori target eligibility rule in Section 3.3 mandated:
$$\sigma_{t_{\text{mid}}} \le 0.25 \times T_{\text{dur}}$$
If a target is eligible with $\sigma_{t_{\text{mid}}} = 0.25 \times T_{\text{dur}}$, then $3 \sigma_{t_{\text{mid}}} = 0.75 \times T_{\text{dur}}$. If $\Delta t_{0, \text{tol}} = \max(0.50 T_{\text{dur}}, 3\sigma_{t_{\text{mid}}})$, the tolerance expands to $0.75 \times T_{\text{dur}}$, which exceeds the physical transit half-duration ($0.50 \times T_{\text{dur}}$). This would allow a detector whose proposed epoch falls completely outside the physical transit dip (past 4th contact) to be scored as a True Positive.

#### Technical Reconciliation in v1.3.1
1. **Explicit Conceptual Segregation**:
   - **Target Ephemeris Eligibility** (A Priori Catalog Filter): A property of the ephemeris ground truth evaluated before blind benchmark ingestion. An observation is eligible if and only if:
     $$\sigma_{t_{\text{mid}}}(E) = \sqrt{\sigma_{T_0}^2 + E^2 \sigma_P^2 + 2 E \operatorname{Cov}(T_0, P)} \le 0.25 \times T_{\text{dur}}$$
     This guarantees that the catalog transit midpoint is known with sufficient precision that ground-truth scoring is physically meaningful.
   - **Detected-Epoch Matching** (Scoring Evaluation): An empirical match criterion between the detector's proposed epoch $t_{0, \text{det}}$ and the catalog midpoint $t_{\text{mid}}$, evaluated via circular phase distance:
     $$\Delta t_0 = \left| \left( t_{0, \text{det}} - t_{\text{mid}} + \frac{P}{2} \right) \bmod P - \frac{P}{2} \right| \le \Delta t_{0, \text{tol}}$$
2. **Preservation of GATE-12 Options Without Silent Selection**:
   The protocol explicitly preserves the unresolved choice among three candidate formulations under `GATE-12`:
   - **Option A ($0.50 \times T_{\text{dur}}$)**: The detector's proposed transit midpoint must fall within the physical 1st-to-4th contact duration of the true transit dip.
   - **Option B ($0.25 \times T_{\text{dur}}$)**: The detector's proposed midpoint must fall within the central core (flat bottom) of the transit dip.
   - **Option C (Bounded Composite)**:
     $$\Delta t_{0, \text{tol}} = \min\left( 0.50 \times T_{\text{dur}},\, \sqrt{(0.25 \times T_{\text{dur}})^2 + (3 \sigma_{t_{\text{mid}}})^2} \right)$$
     This accounts for detector phase-discretization uncertainty ($0.25 T_{\text{dur}}$) and catalog ephemeris uncertainty ($3 \sigma_{t_{\text{mid}}}$), while strictly capping the tolerance at $0.50 T_{\text{dur}}$ so that an epoch match can never be awarded outside the physical transit event.
   - **Status**: Flagged as `AWAITING RESEARCHER APPROVAL` in `docs/benchmark_decision_log.md` and `configs/real_benchmark_protocol.yaml`.

---

### 2. Event Coverage: Cadence Count Ratio vs Continuous Temporal Coverage Fraction

#### The Inconsistency in v1.3
Earlier text interchangeably used "coverage ratio" to mean the discrete count of valid cadences divided by expected cadences ($N_{\text{valid}} / N_{\text{expected}}$) and "temporal coverage fraction." In irregular cadences, gaps, or rapid data gaps, a light curve can have 15 cadences clustered in a 20-minute window of a 3-hour transit, yielding $N_{\text{valid}} \ge 5$ and even a high cadence ratio, despite 85% of the physical transit duration missing observations.

#### Technical Reconciliation in v1.3.1
1. **Mathematical Definition of Continuous Temporal Coverage**:
   Let the physical event window for transit $k$ be the closed interval:
   $$W_{\text{event}, k} = \left[ t_{\text{mid}, k} - \frac{T_{\text{dur}}}{2}, \, t_{\text{mid}, k} + \frac{T_{\text{dur}}}{2} \right]$$
   Each valid cadence $i$ (with timestamp $t_i$, $\text{QUALITY} == 0$, and finite flux) represents an exposure interval:
   $$I_i = \left[ t_i - \frac{\Delta t_{\text{exp}}}{2}, \, t_i + \frac{\Delta t_{\text{exp}}}{2} \right]$$
   where $\Delta t_{\text{exp}} = 120\text{ s} \approx 0.001389\text{ d}$ for TESS SPOC 2-minute cadence. The union of valid exposure intervals is:
   $$\mathcal{I}_{\text{valid}} = \bigcup_{i \in \text{valid}} I_i$$
   The true covered event duration is the 1D Lebesgue measure ($\mu$) of their intersection:
   $$\Delta T_{\text{covered}, k} = \mu\left( W_{\text{event}, k} \cap \mathcal{I}_{\text{valid}} \right)$$
   The continuous temporal coverage fraction is strictly bounded in $[0, 1]$:
   $$f_{\text{temporal}, k} = \frac{\Delta T_{\text{covered}, k}}{T_{\text{dur}}} \in [0, 1]$$
2. **Cadence Count Ratio Kept as Separate Diagnostic**:
   The discrete cadence count ratio is preserved purely as a diagnostic metric of sampling density:
   $$R_{\text{cadence}, k} = \frac{N_{\text{valid}, k}}{N_{\text{expected}, k}}, \quad N_{\text{expected}, k} = \left\lceil \frac{T_{\text{dur}}}{\Delta t_{\text{cadence}}} \right\rceil$$
3. **Prohibition of Cadence-Only Adequacy**:
   A minimum cadence count alone can never qualify an event as adequate. Under `GATE-03`, transit adequacy strictly requires the conjunction of both criteria:
   $$\text{Event is Adequate} \iff f_{\text{temporal}, k} \ge 0.50 \quad \text{AND} \quad N_{\text{valid}, k} \ge 5$$

---

### 3. Sector Boundaries and Partial Transit Events

#### The Inconsistency in v1.3
Protocol v1.3 noted that events truncated by sector edges were excluded, but did not formally define truncation relative to observation timestamps, nor did it explicitly state whether partially observed events could qualify as adequate, or how the event-recovery denominator $N_{\text{adequate}}$ treated them.

#### Technical Reconciliation in v1.3.1
1. **Definition of Sector-Boundary Truncation**:
   Let the usable photometric observation baseline be $[t_{\min}, t_{\max}]$, where $t_{\min} = \min(t_{\text{valid}})$ and $t_{\max} = \max(t_{\text{valid}})$. A predicted transit event $k$ with window $[t_{\text{start}, k}, t_{\text{end}, k}] = [t_{\text{mid}, k} - T_{\text{dur}}/2, t_{\text{mid}, k} + T_{\text{dur}}/2]$ is truncated by a sector boundary if:
   $$t_{\text{start}, k} < t_{\min} \quad \text{or} \quad t_{\text{end}, k} > t_{\max}$$
2. **Strict Inadequacy of Partial Events**:
   Partially observed events lack either ingress or egress. They cannot be reliably characterized by matched filters and cannot be verified as authentic exoplanetary dips without stellar limb-darkening symmetry. Therefore:
   $$\text{Partial Boundary Event} \implies \text{Adequate} = \text{False}$$
3. **Consistency of Event-Recovery Denominator**:
   All partially observed boundary events are strictly excluded from the event-recovery denominator:
   $$\text{Event Recovery Rate} = \frac{N_{\text{recovered}}}{N_{\text{adequate}}}$$
   where $N_{\text{adequate}}$ includes only fully contained events ($t_{\text{start}} \ge t_{\min}$ and $t_{\text{end}} \le t_{\max}$) satisfying $f_{\text{temporal}} \ge 0.50$ and $N_{\text{valid}} \ge 5$. This ensures algorithmic recovery scores are not artificially penalized by orbital geometry relative to satellite observing schedules.

---

### 4. Ephemeris Provenance and Covariance Limitations

#### The Inconsistency in v1.3
v1.3 noted that $\operatorname{Cov}(T_0, P)$ was omitted from archive tables and asserted that setting $\operatorname{Cov}(T_0, P) = 0$ was "conservative." However, mathematically, if $T_0$ and $P$ have a positive covariance ($\operatorname{Cov}(T_0, P) > 0$), setting covariance to zero underestimates the propagated uncertainty $\sigma_{t_{\text{mid}}}(E)$, which is non-conservative. Furthermore, catalog epochs were assumed to be transit midpoints without mandating source-specific verification.

#### Technical Reconciliation in v1.3.1
1. **Source-Specific Verification Mandate**:
   For every catalog target, the ground-truth ingestion ledger must explicitly verify from the original discovery literature or TOI release:
   - That $T_0$ is the **transit midpoint** (time of minimum light / central conjunction), and not an ingress time, egress time, or periastron passage.
   - That the time standard is strictly **Barycentric TESS Julian Date** ($\text{BTJD} = \text{BJD}_{\text{TDB}} - 2457000.0$), matching the SPOC FITS timestamp standard. Any target with an incompatible time standard (e.g. UTC, HJD) must be explicitly converted using barycentric barycorrpy/Astropy tools or excluded.
2. **Clarification of Covariance Limitations**:
   The protocol text and decision log (BDR-013) now explicitly state:
   > "Assuming $\operatorname{Cov}(T_0, P) = 0$ is an unverified catalog data limitation arising from the omission of full covariance matrices in public archives. It must NOT be described as conservative, because if $\operatorname{Cov}(T_0, P) > 0$, the propagated variance is underestimated."

---

### 5. BLS Grid Spacing, Duration Range, and API Pinning

#### The Inconsistency in v1.3
While v1.3 introduced the frequency spacing criterion $\Delta f \le 1 / (T_{\text{baseline}} \times q_{\max})$, it did not explicitly state how the range of trial transit durations ($T_{\text{dur}} \in [T_{\text{dur, min}}, T_{\text{dur, max}}]$) affects grid construction, nor did it specify the exact Astropy call or version requirements, creating risks of non-reproducible grid spacing across library updates.

#### Technical Reconciliation in v1.3.1
1. **Duration-Dependent Spacing Bound**:
   To prevent phase smearing across the observation baseline $T_{\text{baseline}}$, the frequency step must be fine enough that the accumulated transit phase drift across the baseline does not exceed a fraction of the shortest trial transit duration. The maximum allowable frequency spacing across the grid is governed by the minimum trial duration:
   $$\Delta f \le \frac{1}{T_{\text{baseline}}} \cdot \frac{T_{\text{dur, min}}}{P_{\max}}$$
   For $T_{\text{baseline}} = 27.4\text{ d}$, $P_{\max} = 15.0\text{ d}$, and $T_{\text{dur, min}} = 0.0417\text{ d}$ ($1\text{ h}$), this yields $\Delta f \le 0.000101\text{ d}^{-1}$.
2. **Exact Astropy API Arguments & Version Pinning**:
   The implementation is explicitly tied to Astropy's BoxLeastSquares engine:
   ```python
   # Exact API Call Specification
   from astropy.timeseries import BoxLeastSquares

   bls = BoxLeastSquares(t_valid, y_norm, dy_norm)
   period_grid = bls.autoperiod(
       duration=trial_durations,  # array: [0.0417, ..., 0.3333] days
       minimum_period=0.5,
       maximum_period=15.0,
       frequency_factor=5.0,
       minimum_n_transit=2
   )
   ```
   The software environment must pin `astropy>=6.0.0` to preserve identical autoperiod frequency grid generation across runs.
3. **Oversampling Calibration Restriction**:
   The `frequency_factor` parameter (default 5.0) governs oversampling relative to the nominal Fourier spacing. Protocol v1.3.1 explicitly restricts tuning or calibrating `frequency_factor` to **synthetic light curves only**. Calibrating oversampling on real benchmark targets or labels is strictly prohibited as data snooping.

---

### 6. Detrending Validation Procedure, Uncorrupted Denominator, and Subgroups

#### The Inconsistency in v1.3
v1.3 mandated a synthetic detrending test with an acceptance criterion $R_{\text{depth}} \ge 0.95$, but left unspecified how injected and recovered depths are measured, how numerical fitting failures or edge-affected transits enter the denominator, and what subgroup distributions must be reported.

#### Technical Reconciliation in v1.3.1
1. **Precise Depth Measurement Procedure**:
   - For an injected synthetic signal with true physical depth $\delta_{\text{inj}}$, the post-detrending light curve is fitted with a fixed-ephemeris top-hat (or limb-darkened trapezoid) template at the known injection midpoint and duration:
     $$m(t; \delta) = 1.0 - \delta \cdot \mathbb{I}_{|t - t_{\text{mid}}| \le T_{\text{dur}}/2}$$
   - The recovered depth $\hat{\delta}_{\text{post}}$ is computed via weighted least squares:
     $$\hat{\delta}_{\text{post}} = \frac{\sum_{i \in \text{in}} w_i (1.0 - y_{i, \text{detrended}})}{\sum_{i \in \text{in}} w_i}$$
   - Depth preservation ratio: $R_{\text{depth}} = \hat{\delta}_{\text{post}} / \delta_{\text{inj}}$.
2. **Uncorrupted Denominator and Edge Handling**:
   - Numerical failures (e.g. non-convergent fits, empty windows) are counted as failed recoveries ($R_{\text{depth}} = 0$) and reported in an attrition ledger.
   - For aggregate summary statistics, the primary denominator is $N_{\text{eval, uncorrupted}}$ (excluding non-convergent edge artifacts).
   - Injections within $W/2$ ($0.625\text{ d}$) of a sector or telemetry gap edge are **isolated in a segregated edge-affected subgroup**, ensuring core detrending efficacy is evaluated without confounding edge distortions.
3. **Mandatory Subgroup Stratification**:
   Distributions (boxplots, histograms, medians, IQR) of $R_{\text{depth}}$ must be reported across:
   - Injected depth: $[100, 300, 1000, 3000, 10000]\text{ ppm}$
   - Transit duration: $[1.0, 2.0, 4.0, 6.0, 8.0]\text{ hours}$
   - Orbital period: $[0.5, 2.0, 5.0, 10.0, 15.0]\text{ days}$
   - Cadence mode: $120\text{ s}$ vs $1800\text{ s}$
   - Downlink gap proximity: $< 1.25\text{ d}$ vs $\ge 1.25\text{ d}$
   - Sector edge position: Core ($|t - t_{\text{edge}}| > W/2$) vs Edge ($|t - t_{\text{edge}}| \le W/2$)
4. **Decision Gate Pending**:
   The $R_{\text{depth}} \ge 0.95$ threshold remains a proposed guideline flagged under `GATE-05` as `AWAITING RESEARCHER APPROVAL`.

---

### 7. SDE Background Specification, Peak Exclusion, and Alias Treatment

#### The Inconsistency in v1.3
While v1.3 decoupled SDE from SNR, the exact computation of the periodogram background mean $\mu_{\text{bg}}$ and dispersion $\sigma_{\text{bg}}$ was underspecified. In presence of strong stellar variability, aliasing, or prominent transit harmonics, including the peak itself or harmonics in $\mu_{\text{bg}}$ artificially suppresses SDE.

#### Technical Reconciliation in v1.3.1
1. **Explicit Operational Definition**:
   $$\text{SDE} = \frac{P_{\max} - \mu_{\text{bg}}}{\sigma_{\text{bg}}}$$
2. **Peak Exclusion Half-Width**:
   Under `GATE-11` (Option B), frequencies within a half-width of the primary peak are masked out:
   $$\Delta f_{\text{excl}} = 2 \Delta f_{\text{peak}} = 2 \times \frac{1}{T_{\text{dur, min}} \times \text{frequency\_factor}}$$
3. **Invalid-Bin Threshold**:
   If after masking the peak, harmonics, and invalid/NaN bins, the remaining periodogram contains fewer than 50 valid frequency bins, the background cannot be reliably estimated and the detector must return $\text{SDE} = \text{NaN}$ (flagging an unresolvable search).
4. **Harmonic & Alias Clipping**:
   Integer harmonics ($2f_0, 3f_0$) and subharmonics ($f_0/2, f_0/3$) of the primary peak are optionally clipped prior to computing the background dispersion to prevent secondary peaks from inflating $\sigma_{\text{bg}}$.
5. **Robust Dispersion Estimator**:
   Background dispersion is computed via Normalized Median Absolute Deviation:
   $$\sigma_{\text{bg}} = 1.4826 \times \operatorname{median}\left( |P(f) - \operatorname{median}(P(f))| \right)$$
6. **Preservation Under GATE-11**:
   Option A (unclipped periodogram) vs Option B (robust MAD with peak exclusion) remains preserved as `AWAITING RESEARCHER APPROVAL`.

---

## Phase 3: Change Control and Document Synchronization Ledger

| File Path | Version | Modification Type | Synchronized Elements |
| :--- | :---: | :---: | :--- |
| `docs/real_data_benchmark_protocol.md` | **1.3.1** | Specification Update | • Sec 3.3: Midpoint verification, BTJD standard, $\sigma_{t_{\text{mid}}} \le 0.25 T_{\text{dur}}$ eligibility segregation.<br>• Sec 4.2: Synthetic detrending validation fit procedure, uncorrupted denominator, subgroup distributions, GATE-05 status.<br>• Sec 5.1.1: $\min(T_{\text{dur}})$ spacing physics, Astropy API call, `astropy>=6.0.0` pinning, synthetic-only calibration.<br>• Sec 5.1.2: SDE peak exclusion, invalid-bin threshold ($<50$), alias clipping, robust MAD under GATE-11.<br>• Sec 6.2.3: Reconciled epoch matching options (A, B, C) under GATE-12.<br>• Sec 6.2.4: Clarified $\operatorname{Cov}(T_0, P) = 0$ is unverified catalog limitation, NOT conservative.<br>• Sec 7.2.3: Defined continuous temporal coverage $f_{\text{temporal}} \in [0, 1]$ via Lebesgue measure; kept $R_{\text{cadence}}$ separate.<br>• Sec 7.2.4: Defined sector-boundary truncation, excluded partial events from recovery denominator $N_{\text{adequate}}$. |
| `docs/benchmark_decision_log.md` | **1.3.1** | Decision Log Update | • BDR-007: Detrending validation WLS fit, uncorrupted denominator, subgroup reporting.<br>• BDR-012: BLS duration spacing impact, Astropy pinning, synthetic-only calibration.<br>• BDR-013: Ephemeris provenance, BTJD verification, $\operatorname{Cov}(T_0, P)=0$ limitation, target eligibility segregation.<br>• BDR-014: Continuous temporal coverage fraction, sector boundary truncation, partial event denominator exclusion.<br>• Gate Registry: Updated profiles for GATE-01 through GATE-12; all 12 marked `AWAITING RESEARCHER APPROVAL`. |
| `results/real_data_pilot/protocol_readiness_checklist.md` | **1.3.1** | Audit Matrix Update | • Executive Matrix: Mapped continuous temporal coverage, BLS autoperiod parameters, Astropy pinning, detrending validation, and GATE-12 options.<br>• Detailed Requirements: Updated Requirements 2, 3, 4, 7, 8 with v1.3.1 reconciled definitions.<br>• Pre-Execution Checklist: Updated verification criteria for all 7 issues. |
| `configs/real_benchmark_protocol.yaml` | **1.3.1** | Configuration Update | • Metadata: Incremented to `REAL_TESS_BENCHMARK_v1.3.1`, version `1.3.1`.<br>• `data_quality_rules`: Added `min_temporal_coverage_fraction: 0.50`, `prohibit_cadence_only_adequacy: true`, `cadence_count_ratio_diagnostic: true`.<br>• `detrending_validation`: Added WLS measurement procedure, uncorrupted denominator flag, edge segregation, and 6 subgroup dimensions.<br>• `ephemeris_provenance`: Added midpoint verification, BTJD scale verification, unverified covariance limitation, target eligibility condition.<br>• `search_methods.bls_primary_baseline`: Added Astropy call string, `astropy>=6.0.0` pinning, duration spacing rule, SDE peak exclusion, $<50$ invalid-bin threshold, synthetic-only oversampling calibration.<br>• `scoring_and_tolerances`: Reconciled GATE-12 options (A: $0.50 T_{\text{dur}}$, B: $0.25 T_{\text{dur}}$, C: Bounded Composite), distinct eligibility flag.<br>• `event_coverage_hierarchy`: Defined Lebesgue measure, boundary truncation rule, partial event exclusion from denominator. |

---

## Phase 4: Researcher Decision Gate Registry (12 Formal Gates)

All 12 decision gates remain strictly **unapproved** and awaiting formal researcher review:

| Gate ID | Domain | Issue Requiring Decision | Candidate Options | Current Status |
| :---: | :--- | :--- | :--- | :---: |
| **GATE-01** | Period Matching | Matching tolerance fraction $\Delta P_{\text{tol}} / P$ | 1.0% ($0.01$) vs 0.5% ($0.005$) | `AWAITING APPROVAL` |
| **GATE-02** | CNN Gate | Minimum Sensitivity threshold on validation split | 0.75 vs 0.80 (with Specificity $\ge 0.85$) | `AWAITING APPROVAL` |
| **GATE-03** | Event Adequacy | Minimum continuous temporal coverage $f_{\text{temporal}}$ | 50% vs 70% (conjoined with $N_{\text{valid}} \ge 5$) | `AWAITING APPROVAL` |
| **GATE-04** | Harmonic Scoring | Integer harmonic credit policy | Fundamental-only vs Separate harmonic credit | `AWAITING APPROVAL` |
| **GATE-05** | Detrending Filter | Detrending algorithm and acceptance threshold | Running median vs Biweight spline ($R_{\text{depth}} \ge 0.95$) | `AWAITING APPROVAL` |
| **GATE-06** | Multi-Planet | Multi-transiting planet scoring policy | Exclude multi-planets vs Score primary transit | `AWAITING APPROVAL` |
| **GATE-07** | Period Scope | Maximum orbital period for production cohort | 15.0 days vs 25.0 days | `AWAITING APPROVAL` |
| **GATE-08** | Cohort Size | Production cohort target volume | 100 targets (50/50) vs 60 targets (30/30) | `AWAITING APPROVAL` |
| **GATE-09** | BLS Grid Method | BLS frequency grid generation strategy | Adaptive `autoperiod()` vs Fixed fine uniform | `AWAITING APPROVAL` |
| **GATE-10** | BLS Flux Weights | Photometric measurement error weighting | Inverse-variance ($1/\sigma_i^2$) vs Uniform ($w_i=1$) | `AWAITING APPROVAL` |
| **GATE-11** | SDE Background | Periodogram background dispersion definition | All frequencies unclipped vs Peak-excluded robust MAD | `AWAITING APPROVAL` |
| **GATE-12** | Epoch Tolerance | Detected-epoch matching tolerance $\Delta t_{0, \text{tol}}$ | Option A ($0.50 T_{\text{dur}}$) vs Option B ($0.25 T_{\text{dur}}$) vs Option C (Bounded Composite) | `AWAITING APPROVAL` |

---

## Phase 5: Verification & Change Control Compliance

### 5.1 Machine-Readable YAML Validation
The updated configuration file `configs/real_benchmark_protocol.yaml` was formally validated using Python's YAML parser:
```bash
PYTHONPATH= .venv/bin/python -c "import yaml; data = yaml.safe_load(open('configs/real_benchmark_protocol.yaml')); print('Keys:', list(data.keys()))"
```
**Result**: Valid syntax. Successfully parsed all 10 root sections:
`['protocol_metadata', 'data_quality_rules', 'detrending_validation', 'outlier_handling', 'ephemeris_provenance', 'cohort_specification', 'search_methods', 'scoring_and_tolerances', 'event_coverage_hierarchy', 'metrics_and_reporting']`.

### 5.2 Test Suite Regression Check
The automated unit and integration test suite was executed:
```bash
PYTHONPATH= .venv/bin/pytest tests/ -q
```
**Result**: **48 passed in 5.86s, 91% total code coverage**. Zero regressions introduced.

### 5.3 Scientific Invariants Confirmation
- **No data files touched**: Raw FITS, pilot processed light curves, and synthetic datasets remain identical.
- **No models run**: BLS, Random Forest, HistGradientBoosting, and CNN1D were not executed.
- **No metrics calculated**: No detection statistics, ROC curves, or confusion matrices were generated.
- **No gates approved**: All 12 gates remain explicitly pending researcher approval.
- **Empirical validation status**: **No empirical validation was performed**.

---

## Conclusion & Next Steps

Protocol v1.3.1 provides a fully reconciled, mathematically consistent, and reproducible blueprint for blind exoplanet transit recovery benchmarking on authentic TESS photometry.

The protocol now pauses for **formal researcher review and sign-off** on the 12 decision gates before any implementation or benchmark execution begins.
