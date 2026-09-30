# Scientific and Architectural Decision Log: Real TESS Benchmark Protocol

**Project**: TESS Transit Detection Benchmark  
**Document ID**: `docs/benchmark_decision_log.md`  
**Date**: 2026-09-28  
**Scope**: Protocol Design Decisions for Real TESS Known-Transit Recovery Benchmark  
**Protocol Reference**: `docs/real_data_benchmark_protocol.md` (Version 1.3.2)  
**Status**: **ACTIVE — DECISIONS RECORDED & DECISION GATES FLAGGED (VERSION 1.3.2)**  

---

## Revision History

| Version | Date | Author | Summary of Changes |
| :--- | :---: | :--- | :--- |
| **v1.0** | 2026-09-28 | Research Group | Initial draft recording decisions BDR-001 through BDR-007. |
| **v1.1** | 2026-09-28 | Research Group | Added BDR-008 through BDR-011 covering comparison-star non-representativeness, CNN dual validation gate, segment-wise detrending, and ML task definition. |
| **v1.2** | 2026-09-28 | Research Group | Added BDR-012 through BDR-016 covering BLS frequency grid resolution, circular phase distance, in-transit cadence coverage, pre-detrending flare flagging, and formal attrition accounting; expanded gate registry to GATE-01 through GATE-12. |
| **v1.3** | 2026-09-28 | Research Group | Mathematical audit: transit-depth variance $\operatorname{Var}(\delta) = (\sum_{\text{in}} w_i)^{-1} + (\sum_{\text{out}} w_j)^{-1}$, WLS regression covariance matrix, SDE vs SNR decoupling, general ephemeris variance, BLS grid dimensional terms, five-tier event coverage, detrending attenuation risk, ML candidate-vetting role. |
| **v1.3.1** | 2026-09-28 | Research Group | Consistency audit: BDR-013 ephemeris segregation and covariance limit, BDR-014 continuous temporal coverage via Lebesgue measure, BDR-007 detrending validation fit procedure, BDR-012 BLS spacing and Astropy pinning, GATE-11 SDE background options. |
| **v1.3.2** | 2026-09-28 | Research Group | **Methodological Consistency & Reproducibility Audit**: <br>• **BDR-013 & GATE-12**: Corrected covariance error direction to depend on $\operatorname{sgn}(E_k \cdot \operatorname{Cov}(T_0, P))$; clarified Option C $0.25 T_{\text{dur}}$ is detector resolution (synthetic calibration needed) or scoring convention; affirmed $0.50 T_{\text{dur}}$ cap is scoring convention, not confidence bound.<br>• **BDR-014 & GATE-03**: Defined exposure boundary baseline $[t_{\text{base},\min}, t_{\text{base},\max}]$; defined partial exposure overlap measure $\mu(I_i \cap W_{\text{event}, k})$; designated categorical exclusion of partial events as a PROPOSED choice awaiting approval.<br>• **BDR-007 & GATE-05**: Defined local baseline normalization $C_{\text{out}}$; specified Box, Trapezoid, Limb-Darkened model options; mandated failure rate diagnostic $f_{\text{fail}} = N_{\text{failed}} / N_{\text{total}}$ with dual reporting (omnibus and convergent); kept thresholds pending.<br>• **BDR-012 & GATE-09**: Corrected Astropy versioning from exact pin to dependency constraint; mandated recording exact runtime version, lockfile, arguments, and serialized grid.<br>• **GATE-11**: Detailed identification of fundamental peak, harmonics ($2f_0, 3f_0$), subharmonics ($f_0/2, f_0/3$), aliases, composite union $\mathcal{E}$, invalid bins, and $<50$ degeneracy rule.<br>• **Proposed Defaults vs Pending Gates**: Audited all 12 gates and entries to ensure every unresolved choice is visibly marked `[PROPOSED]` and `AWAITING RESEARCHER APPROVAL`. |

---

## BDR-001: Staged Cohort Design (Feasibility vs Frozen Production Cohort)

- **Context**: Evaluating benchmark algorithms directly on a newly expanded 100-star cohort without end-to-end verification risks discovering software crashes, memory bottlenecks, or scoring bugs midway through execution, creating pressure to patch code and re-run on the test set (data snooping).
- **Alternatives Considered**:
  1. *Immediate 100-Star Run*: Ingest all 100 stars and execute detection algorithms simultaneously.
  2. *Synthetic-Only Calibration*: Calibrate solely on synthetic light curves and jump to real data.
  3. *Two-Stage Architecture (Selected)*: Freeze a feasibility run on the existing 10-star pilot (Sector 1) to verify plumbing, followed by expanding to the frozen 100-star production cohort only after protocol sign-off.
- **Decision**: Adopt the two-stage execution architecture:
  - Stage 1 (Feasibility): Re-use the existing, audited 10-star Sector 1 pilot cohort to verify blind execution, data serialization, and scoring code without altering model hyperparameters.
  - Stage 2 (Production): Ingest and benchmark the frozen 100-star cohort across Sectors 1–5.
- **Consequences**: Designed to reduce data leakage risk and prevents post hoc algorithmic adjustments on the production cohort.

---

## BDR-002: Strict Ephemeris Air-Gap and Blind Scoring Layer

- **Context**: In astronomy ML benchmarks, models frequently suffer subtle leakage when preprocessing functions or period search grids are guided by known ephemerides, or when ground-truth labels are present in the dataframe during feature extraction.
- **Alternatives Considered**:
  1. *Integrated Evaluator*: Pass `LightCurveData` containing metadata like `category` or `known_period` directly to the model pipeline, relying on model code to ignore them.
  2. *Air-Gapped Two-Tier Architecture (Selected)*: Strip all metadata, target identifiers, and ephemerides before light curves enter the search pipeline. The pipeline accepts only opaque IDs and numerical time-series arrays via `BlindLightCurve`. Results are written to a frozen output artifact before the scoring layer reads ground truth.
- **Decision**: Specify an immutable air-gap:
  - Input: Opaque ID (`TARGET_001`), `time`, `flux_norm`, `flux_err_norm`.
  - Output: Frozen detector manifest (`is_detected`, `best_period`, `best_t0`, `best_duration`, `score`).
  - Scoring: Independent evaluator merges frozen outputs with ground-truth table.
- **Consequences**: Eliminates direct programmatic access to period, epoch, duration, or class labels within the search algorithms. Implementation verification required in Stage 1.

---

## BDR-003: Decoupling Target-Level, Event-Level, Period, and Epoch Recovery

- **Context**: Many transit literature studies report a single "detection accuracy" metric. This conflates whether an algorithm identified a planet host, whether it identified the true physical period, whether epoch phase was aligned, and whether individual transit dips were covered.
- **Alternatives Considered**:
  1. *Single Binary Metric*: Label a target 1 if detected, 0 if missed.
  2. *Period-Only Metric*: Score based only on matching $P_{\text{true}}$.
  3. *Decoupled Tri-Level Metric (Selected)*: Separately evaluate and report:
     - Target-level classification (Precision, Recall, F1).
     - Period recovery fraction (Fundamental vs Harmonic vs Misidentified).
     - Epoch recovery fraction (Phase alignment within $\Delta t_{0,\text{tol}}$).
     - Event-level recovery fraction (Adequately covered transit windows vs Downlink gaps).
- **Decision**: Formally decouple the four levels. Harmonic recoveries ($\mathcal{H} = \{1/3, 1/2, 2, 3\}$) must never be silently counted as fundamental period recoveries. Epoch mismatch is explicitly distinguished from full physical orbit recovery.
- **Consequences**: Provides nuanced, astronomically meaningful diagnostic metrics and prevents misleading claims of high detection accuracy.

---

## BDR-004: Dual Validation Gate on Probation for 1D CNN

- **Context**: During the synthetic benchmark repair, `TransitCNN1DNet` suffered complete all-positive collapse (TP=4, FP=6, TN=0, FN=0, Specificity = 0.0, FPR = 1.0) because uncalibrated sigmoid outputs on imbalanced data triggered positive predictions on every sample. An earlier draft gate required only Specificity $\ge 0.85$, which an all-negative degenerate classifier (predicting 0 on everything) could trivially satisfy.
- **Alternatives Considered**:
  1. *Include Unmodified*: Benchmark the existing CNN model as-is for transparency.
  2. *Single Specificity Gate*: Require Specificity $\ge 0.85$ only (flawed: all-negative model passes).
  3. *Dual Validation Gate (Selected)*: Place 1D CNN on conditional probation. Require BOTH:
     - Specificity $\ge 0.85$ (or $\text{FPR} \le 0.15$).
     - Sensitivity / Recall $\ge \text{MIN\_SENSITIVITY}$ (`GATE-02` `REQUIRES_RESEARCHER_APPROVAL`, proposed candidate: $\ge 0.75$).
     - Full confusion matrix review on an independent validation set.
     - Threshold selection performed on validation split, never on the real-TESS benchmark test cohort.
- **Decision**: Adopt the dual validation gate. The 1D CNN remains excluded from the primary benchmark comparison until the gate is approved and verified.
- **Consequences**: Protects benchmark integrity from degenerate baselines while providing a rigorous, scientifically defensible remediation standard.

---

## BDR-005: Comparison-Star Interpretation and Cohort Non-Representativeness

- **Context**: In an artificially balanced 50:50 cohort (50 hosts, 50 comparison stars), computing precision or false alarm rates directly creates severe distortion if interpreted as representative of natural space telescope surveys (where exoplanet occurrence is $\sim 1\%$). Furthermore, catalog null records do not prove a star is planet-free.
- **Alternatives Considered**:
  1. *Label Comparison Detections as False Positives*: Assume catalog ground truth is complete.
  2. *Claim Population Precision*: Calculate precision directly from the 50:50 confusion matrix.
  3. *Explicit Non-Representativeness and Terminology Guard (Selected)*:
     - Terminology: Use "comparison-star detection rate" or "catalog-inconsistent detection rate".
     - Expressly prohibit claiming survey precision, PPV, or population false-positive rates from the balanced cohort.
     - Explicitly document comparison stars as non-detection controls, not proven planet-free.
- **Decision**: Formally adopt terminology and non-representativeness guards. Document that comparison-star detections evaluate algorithm vulnerability to stellar variability and systematics, not true survey reliability.
- **Consequences**: Prevents deceptive extrapolation to full TESS survey yields and preserves strict astronomical accuracy.

---

## BDR-006: Local Gap Rule and Disambiguation of Telemetry Discontinuities

- **Context**: A preliminary draft rule stated that "transits near telemetry gaps $> 6\text{ hours}$ are lost." This risked disqualifying transits that occurred during continuous, high-quality data simply because a downlink gap occurred elsewhere in the sector.
- **Alternatives Considered**:
  1. *Global Gap Invalidation*: Any target with a gap $> 6$ hours in its light curve is disqualified.
  2. *Binary In-Window Cadence Count*: Count any transit with $\ge 1$ cadence as observed.
  3. *Local Window Inspection with Dual Adequacy (Selected)*:
     - Primary criterion: The in-transit window $W_{\text{event}, k}$ must meet the dual adequacy rule: temporal coverage fraction $f_{\text{temporal}} \ge 50\%$ AND valid cadence count $N_{\text{valid}} \ge 5$.
     - The 6-hour gap rule applies strictly to the local baseline interval $I_{\text{local}, k} = [t_{\text{mid}, k} - T_{\text{dur}}, t_{\text{mid}, k} + T_{\text{dur}}]$.
     - If a gap overlaps $I_{\text{local}, k}$ but the transit itself satisfies dual adequacy, the event remains eligible and is tagged with `gap_affected = True`.
     - An event is classified as "Not Observed / Downlink Lost" only if the gap directly causes the transit window to fail adequate coverage.
- **Decision**: Restrict the 6-hour gap rule to local intervals and treat gap proximity as an event attribute rather than automatic exclusion.
- **Consequences**: Prevents penalizing algorithms for spacecraft telemetry loss while ensuring that "covered" windows contain sufficient signal to be physically detectable.

---

## BDR-007: Detrending Window, Transit Preservation Risk, and Synthetic Validation

- **Context**: Protocol draft v1.0 specified detrending window $W_{\text{detrend}} \ge 3 \times T_{\text{dur, max}}$ and $W_{\text{detrend}} \ge 1.0\text{ day}$. However, maximum duration was $T_{\text{dur, max}} = 8.4\text{ hours}$ ($0.35\text{ days}$), giving $3 \times 8.4\text{ h} = 25.2\text{ hours} = 1.05\text{ days} > 1.0\text{ day}$. Furthermore, unmasked running medians can attenuate transit signals during stellar variability, and detrending across gaps causes edge distortion.
- **Alternatives Considered**:
  1. *Global Continuous Detrending with Naive 1-Day Window*: Fails duration condition for long transits and distorts across telemetry gaps.
  2. *Ephemeris-Masked Running Median*: Requires known transit windows, violating blind detection air-gap.
  3. *Segment-Wise Detrending with Synthetic Validation Gate (Selected)*:
     - Standardize proposed window to $W_{\text{detrend}} = 1.25\text{ days}$ ($30.0\text{ hours}$), satisfying $W_{\text{detrend}} \ge \max(3 T_{\text{dur, max}}, 1.05\text{ d})$.
     - Execute independently on continuous segments separated by gaps $> 6.0\text{ hours}$.
     - Short segments ($< 1.25\text{ d}$) detrended by scalar median subtraction and tagged `short_segment: bool`.
     - Cadences within $W/2$ of segment edges tagged `edge_affected: bool`.
     - Transit masking is strictly prohibited/unavailable at detection time.
     - Acknowledge the risk of unmasked running median transit attenuation.
     - Mandate synthetic-injection detrending validation experiment measuring $R_{\text{depth}} = \hat{\delta}_{\text{post}} / \delta_{\text{inj}}$. Local out-of-transit baseline flux $C_{\text{out}}$ must be estimated in $[t_{\text{mid}} - 3 T_{\text{dur}}, t_{\text{mid}} + 3 T_{\text{dur}}] \setminus [t_{\text{mid}} - T_{\text{dur}}/2, t_{\text{mid}} + T_{\text{dur}}/2]$.
     - Depth fitting models (Box, Trapezoid, Limb-Darkened) are candidate options under `GATE-05`.
     - Failed fits (singular matrix, $<3$ in-transit points, non-finite, $\hat{\delta}_{\text{post}} \le 0$) must not be silently omitted; report explicit failure rate $f_{\text{fail}} = N_{\text{failed}} / N_{\text{total}}$ and provide both omnibus ($R_{\text{depth}}=0$ on fail) and convergent distributions, with edge-affected transits segregated.
     - Acceptance thresholds (proposed candidate: median $R_{\text{depth}} \ge 0.95, f_{\text{fail}} \le 0.02$) remain strictly pending researcher approval under `GATE-05`.
- **Decision**: Adopt segment-wise processing with proposed $W_{\text{detrend}} = 1.25\text{ days}$ and require synthetic validation with explicit failure accounting before claiming transit preservation.
- **Consequences**: Eliminates gap-crossing artifacts while establishing a formal validation requirement for filter fidelity without silent failure dropouts.

---

## BDR-008: Supervised ML Task Specification as BLS-Candidate Vetting Classifiers

- **Context**: Random Forest and HistGradientBoosting operate on a 22-dimensional feature space containing `bls_sde`, `bls_snr`, `bls_period`, `bls_depth`, etc. If described as "transit search algorithms," this implies they independently scan raw light curves and discover periods, which is false.
- **Alternatives Considered**:
  1. *Describe as Independent Detectors*: Misleading representation of algorithm capabilities.
  2. *Discard Supervised ML*: Restrict benchmark to BLS only.
  3. *Explicitly Formulate as BLS-Candidate Vetting (Selected)*: Document that tree ensembles are candidate vetting classifiers conditioned on the blind BLS periodogram output. They evaluate whether the primary BLS candidate is an exoplanet transit vs false alarm, inheriting the period, epoch, and duration from BLS.
- **Decision**: Define supervised tabular models strictly as BLS-Candidate Vetting Classifiers. Prohibit direct comparisons between vetting models and BLS search as equivalent search tools.
- **Consequences**: Establishes complete methodological transparency and accurately reflects the computational role of feature-based ML in exoplanet pipelines.

---

## BDR-009: Strict Feasibility Boundary for Stage 1 Pilot Cohort

- **Context**: In pilot studies, researchers are frequently tempted to tweak detection thresholds, search grids, or feature definitions after observing pilot target outcomes, compromising the integrity of the frozen protocol.
- **Alternatives Considered**:
  1. *Allow Iterative Tuning*: Tune thresholds on the 10 pilot stars.
  2. *Strict Freeze (Selected)*: The 10 pilot stars are evaluated strictly to test software plumbing, serialization, determinism, and scorer arithmetic. No threshold or hyperparameter may be tuned on them.
- **Decision**: Enforce a strict freeze on Stage 1. Any parameter change requires a formal protocol revision recorded in this log before re-running.
- **Consequences**: Guarantees that Stage 1 serves purely as a feasibility and quality gate without contaminating test outcomes.

---

## BDR-010: Handling of Multi-Planet Systems and Single-Sector Scope

- **Context**: In multi-planet systems, overlapping transit signals can confuse single-peak BLS periodograms unless iterative pre-whitening is implemented. Furthermore, stars observed in multiple sectors raise questions about light curve concatenation.
- **Alternatives Considered**:
  1. *Allow Multi-Planet Systems Freely*: Risk penalizing algorithms when BLS recovers a secondary planet rather than the primary.
  2. *Multi-Sector Stitching*: Concatenate multiple sectors into a single light curve (introduces cross-sector systematic step-discontinuities).
  3. *Single-Planet Primary Scope with Single-Sector Baseline (Selected)*: Restrict primary benchmark cohort to single confirmed planet hosts observed in single sectors. Multi-planet and multi-sector evaluations are deferred to secondary exploratory tracks.
- **Decision**: Primary benchmark cohort is restricted to single-planet systems and single-sector light curves. Multi-planet systems require explicit researcher approval (`GATE-06`) before inclusion.
- **Consequences**: Ensures clean, unambiguous ground truth for period and event recovery.

---

## BDR-011: Transit-Depth Uncertainty, WLS Regression Covariance, and SDE Decoupling

- **Context**: Literature implementations occasionally report transit-depth uncertainty without taking the square root of the variance, or conflate periodogram Signal Detection Efficiency (SDE) with physical Signal-to-Noise Ratio (SNR).
- **Alternatives Considered**:
  1. *Heuristic SNR*: Define SNR based on SDE or peak-to-peak amplitude.
  2. *Uncalibrated Depth Variance*: Omit square root or assume unweighted points.
  3. *Rigorous Mathematical Formulation (Selected)*:
     - Difference of independent weighted means:
       $$\operatorname{Var}(\delta) = \frac{1}{\sum_{i \in \text{in}} w_i} + \frac{1}{\sum_{j \in \text{out}} w_j}$$
       $$\sigma_\delta = \sqrt{\operatorname{Var}(\delta)}, \quad \text{SNR} = \frac{\delta}{\sigma_\delta}$$
     - Equivalent WLS regression covariance matrix $\operatorname{Cov}(\mathbf{\beta}) = (\mathbf{X}^T \mathbf{W} \mathbf{X})^{-1}$ yielding identical depth variance $\operatorname{Var}(\beta_1) = \operatorname{Var}(\delta)$.
     - Decouple SNR (physical transit dip significance) from SDE (periodogram spectral peak prominence).
- **Decision**: Formally document exact mathematical definitions for $\operatorname{Var}(\delta), \sigma_\delta, \text{SNR}$, and $\text{SDE}$, and prohibit treating SDE and SNR as interchangeable.
- **Consequences**: Eliminates mathematical error and standardizes reporting across all baseline detectors.

---

## BDR-012: BLS Frequency Grid Resolution, Dimensional Formulation, and Astropy Reproducibility

- **Context**: A uniform frequency step $\Delta f = 1 / (5 \times 27.4\text{ d}) \approx 0.00730\text{ d}^{-1}$ produces only $\approx 266$ points. Across a 27.4-day baseline, a period error of $10.6\text{ minutes}$ at $P=1\text{ d}$ induces an accumulated phase drift of $\approx 4.8\text{ hours}$, completely smearing narrow transits ($T_{\text{dur}} \approx 1\text{--}2\text{ h}$).
- **Alternatives Considered**:
  1. *Fixed 266-Point Linear Grid*: Computationally fast, but misses narrow transits due to phase smearing.
  2. *Arbitrary Oversampling*: Set $f_{\text{factor}} = 50$ without physical justification.
  3. *Duration-Dependent Grid Construction (Selected)*: Adopt Astropy's `BoxLeastSquares.autoperiod()` physics-based formulation:
     $$\Delta f(P) \le \frac{\min(T_{\text{dur}})}{P \cdot f_{\text{factor}} \cdot T_{\text{usable}}}$$
     with dimensionally explicit terms: $T_{\text{usable}}$ in days [T], $P$ in days [T], $T_{\text{dur}}$ in days [T], dimensionless $f_{\text{factor}}$ and duty cycle $q = T_{\text{dur}} / P$.
     - *Astropy Versioning & Recording Mandate*: The environment specification `astropy>=6.0.0` is an inequality dependency constraint, **not an exact version pin**. To guarantee exact scientific reproducibility, implementation must record `astropy.__version__` (e.g. `8.0.1` in verification environment), generate an environment lockfile, log exact API arguments, and serialize the complete generated frequency grid array.
- **Decision**: Formally document phase-drift physics, dimensional definitions, and Astropy recording requirements. Record choice between adaptive `autoperiod` and high-density fixed grid under `GATE-09` (`REQUIRES_RESEARCHER_APPROVAL`). Calibration of proposed $f_{\text{factor}} = 5.0$ must be performed on synthetic injections, never on benchmark test targets.
- **Consequences**: Prevents artificial detector failure caused by inadequate periodogram frequency resolution.

---

## BDR-013: Ephemeris Uncertainty Propagation, Covariance Limits, and Epoch Matching Reconciliation

- **Context**: Conflating a priori target eligibility with detected-epoch matching creates confusion. Furthermore, reference epochs $T_0$ from discovery literature can be years older than TESS observations, requiring variance propagation across integer epoch cycles $E_k$, but public archive tables omit covariance.
- **Alternatives Considered**:
  1. *Linear Time Subtraction*: Fails across orbit cycles and near phase edges.
  2. *Single Phase Modulo*: Discontinuous at 0/1 boundary.
  3. *Reconciled Ephemeris Propagation and Circular Phase Distance (Selected)*:
     - **Source-Specific Verification**: Must verify that catalog $T_0$ is defined as transit midpoint, and that time scale is $\text{BTJD}$ ($\text{BJD}_{\text{TDB}}$).
     - **Target Eligibility**: A priori filter $\sigma_{t_{\text{mid}}}(E) \le 0.25 \times T_{\text{dur}}$ ensuring ground truth is sharp.
     - **Mathematical Covariance Limitation**: Setting $\operatorname{Cov}(T_0, P) = 0$ is an unverified catalog limitation. The cross-term is $2 E_k \operatorname{Cov}(T_0, P)$, whose sign depends strictly on $\operatorname{sgn}(E_k \cdot \operatorname{Cov}(T_0, P))$. If $E_k \operatorname{Cov}(T_0, P) > 0$, omitting covariance underestimates uncertainty; if $E_k \operatorname{Cov}(T_0, P) < 0$, omitting covariance overestimates uncertainty. Because $E_k$ can be positive or negative and the covariance sign is unknown, **the zero-covariance approximation must NOT be characterized as universally conservative or universally underestimating uncertainty**.
     - **Detected-Epoch Matching**: Evaluated via circular phase distance $\Delta \phi$ and physical offset $\Delta t_0 = \Delta \phi \cdot P_{\text{true}} \le \Delta t_{0,\text{tol}}$. Tolerance formula is governed strictly by `GATE-12` (`REQUIRES_RESEARCHER_APPROVAL`), presenting Option A ($0.50 T_{\text{dur}}$), Option B ($0.25 T_{\text{dur}}$), and Option C (bounded composite). In Option C, $0.25 T_{\text{dur}}$ is an empirical detector resolution term requiring synthetic calibration (or a core-dip scoring convention), while the $0.50 T_{\text{dur}}$ cap is strictly a scoring convention, not a statistical confidence bound.
- **Decision**: Separate target eligibility from epoch matching, document covariance error directions mathematically, and enforce circular phase distance matching under `GATE-12`.
- **Consequences**: Eliminates boundary discontinuity errors in epoch scoring and accurately accounts for ephemeris age without silent parameter choices.

---

## BDR-014: Continuous Temporal Coverage Fraction, Baseline Boundaries, and Sector-Boundary Truncation Policy

- **Context**: Treating a cadence count ratio as a coverage fraction allows values $> 1.0$, while treating a point count alone as adequate coverage risks accepting events where points are bunched in a small fraction of the transit dip. Furthermore, partially observed events at sector edges lack transit morphology.
- **Alternatives Considered**:
  1. *Cadence-Only Adequacy*: Any transit with $\ge 5$ cadences counts as adequate coverage.
  2. *Allowing Partial Edge Transits into Denominator*: Scored partial events as detector failures or recoveries.
  3. *Continuous Temporal Coverage with Dual Adequacy and Methodological Boundary Policy (Selected)*:
     - Formally define observation baseline using **exposure boundaries**: $t_{\text{base},\min} = \min_{i}(t_i - \Delta t_{\text{exp}}/2)$ and $t_{\text{base},\max} = \max_{i}(t_i + \Delta t_{\text{exp}}/2)$.
     - Partially overlapping exposures contribute their exact 1D Lebesgue intersection measure: $\mu(I_i \cap W_{\text{event}, k})$.
     - Define continuous temporal coverage fraction $f_{\text{temporal}, k} = \Delta T_{\text{covered}, k} / T_{\text{dur}} \in [0, 1]$.
     - Separate discrete cadence count diagnostic $N_{\text{valid}, k}$ and count ratio $R_{\text{cadence}, k}$.
     - Dual adequacy rule: Requires BOTH $f_{\text{temporal}} \ge 50\%$ AND $N_{\text{valid}} \ge 5$ [PROPOSED CANDIDATE]. Cadence count alone is strictly insufficient.
     - Sector-boundary truncation: Events crossing $t_{\text{base},\min}$ or $t_{\text{base},\max}$ are classified as "Sector-Boundary Truncated". Categorical exclusion from the event-recovery denominator ($N_{\text{adequate}}$) is a **PROPOSED METHODOLOGICAL CHOICE awaiting researcher approval under `GATE-03`**, alongside alternatives of partial recovery evaluation and secondary diagnostic tracking.
- **Decision**: Adopt continuous temporal coverage, dual adequacy, and preserve boundary partial-event treatment as a pending decision gate.
- **Consequences**: Guarantees rigorous, mathematically consistent event-level recovery rates without unapproved policy defaults.

---

## BDR-015: Pre-Detrending Asymmetric Outlier Flagging and Raw Data Immutability

- **Context**: Extreme positive stellar flares or cosmic rays can distort running median or spline detrending filters. However, naively clipping or modifying flux values corrupts raw data provenance and risks clipping transit egress.
- **Alternatives Considered**:
  1. *In-Place Flux Modification*: Overwrite raw flux array with clipped values.
  2. *Symmetric Outlier Clipping*: Clip both positive and negative outliers (destructive to transits).
  3. *Pre-Detrending Asymmetric Flagging with Data Immutability (Selected)*:
     - Flag only positive excursions ($y - y_{\text{med}} > +5 \sigma_{\text{MAD}}$) using running median ($W=0.5\text{ d}$) and normalized MAD.
     - Negative excursions ($y < y_{\text{med}}$) are never clipped or altered.
     - Original raw flux arrays remain strictly immutable; flags are stored in derived boolean masks and an audit CSV (`outlier_reconciliation.csv`).
- **Decision**: Adopt asymmetric positive flare flagging and mandate raw data immutability.
- **Consequences**: Protects detrending filters from flare distortion while guaranteeing zero transit attenuation and unbroken data provenance.

---

## BDR-016: Formal Attrition Accounting and Strict Denominator Isolation

- **Context**: Reporting recovery rates without explicit denominator definitions allows unobserved events (e.g. transits in downlink gaps) to be counted as detector failures, artificially depressing recovery metrics.
- **Alternatives Considered**:
  1. *Ad-Hoc Reporting*: Report single percentage without denominator breakdown.
  2. *Full Attrition Ledger (Selected)*:
     - Publish formal target attrition ledger ($N_{\text{candidate}} \to N_{\text{eligible}} \to N_{\text{searched}}$).
     - Publish formal event attrition ledger ($N_{\text{predicted}} \to N_{\text{zero\_cadence}} \to N_{\text{insufficient}} \to N_{\text{adequate}}$).
     - Denominator for event recovery is strictly $N_{\text{adequate}}$ (adequate in-transit coverage).
- **Decision**: Require formal target and event attrition tables in all benchmark reporting.
- **Consequences**: Prevents unobserved physical events from being mislabeled as detector failures.

---

## Formal Registry of Decision Gates Requiring Researcher Approval

The following 12 decision gates represent unresolved methodological choices. **No gate is approved by default. Every gate is marked `AWAITING RESEARCHER APPROVAL`.**

| Gate ID | Topic | Proposed Option | Alternative Options | Synthetic Calibration Feasible? | Status |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **GATE-01** | Period Matching Tolerance | [PROPOSED] Relative tolerance $\epsilon_P = 1.0\%$ ($0.01$) | Fourier resolution limit: $3 \times P^2 / T_{\text{usable}}$ | Yes | **AWAITING APPROVAL** |
| **GATE-02** | CNN Dual Validation Gate | [PROPOSED] Specificity $\ge 0.85$ AND Sensitivity $\ge 0.75$ | Specificity $\ge 0.90$ AND Sensitivity $\ge 0.80$ | Yes | **AWAITING APPROVAL** |
| **GATE-03** | Window Cadence & Coverage Adequacy | [PROPOSED] $N_{\text{valid}} \ge 5$ AND $f_{\text{temporal}} \ge 50\%$; categorical exclusion of partial/boundary events | Option B: $N_{\text{valid}} \ge 3$ AND $f_{\text{temporal}} \ge 30\%$; Option C: evaluate partial events; Option D: secondary diagnostic track | Yes | **AWAITING APPROVAL** |
| **GATE-04** | Harmonic Set Definition | [PROPOSED] $\mathcal{H} = \{1/3, 1/2, 2, 3\}$ | Restrict strictly to $\mathcal{H} = \{1/2, 2\}$ | Yes | **AWAITING APPROVAL** |
| **GATE-05** | Detrending Filter & Threshold | [PROPOSED] Running median ($W=1.25\text{ d}$, proposed $R_{\text{depth}} \ge 0.95$); Box model; mandatory $f_{\text{fail}}$ reporting | Trapezoid or Limb-Darkened model; robust biweight spline ($W=1.25\text{ d}$) | Yes | **AWAITING APPROVAL** |
| **GATE-06** | Multi-Planet Handling | [PROPOSED] Restrict primary cohort to single confirmed hosts | Score against highest-depth planet in system | Partial | **AWAITING APPROVAL** |
| **GATE-07** | Search Range Boundaries | [PROPOSED] Restrict cohort to $P \in [0.5, 15.0]\text{ days}$ | Expand BLS grid to $P_{\max} = 25.0\text{ days}$ | Yes | **AWAITING APPROVAL** |
| **GATE-08** | Production Cohort Size | [PROPOSED] 50 Confirmed Hosts, 50 Comparison Stars | 30 Hosts, 30 Comparison Stars | No (Empirical/Resource) | **AWAITING APPROVAL** |
| **GATE-09** | BLS Frequency Grid Spacing | [PROPOSED] Astropy `autoperiod` adaptive scaling ($f_{\text{factor}}=5.0$); mandate recording runtime version, args, and serialized grid | Fixed uniform frequency grid ($\Delta f \approx 0.00730\text{ d}^{-1}$) | Yes | **AWAITING APPROVAL** |
| **GATE-10** | BLS Flux Weighting Model | [PROPOSED] Inverse-variance weighting ($w_i = 1 / \sigma_i^2$) | Uniform weighting ($w_i = 1$) | Yes | **AWAITING APPROVAL** |
| **GATE-11** | SDE Background Estimation | [PROPOSED] Option A: Unclipped; preserve Options B, C, D with full composite alias mask $\mathcal{E}$ | Option B: Peak-excluded; Option C: Peak+harmonic excluded robust MAD; Option D: Iterative outlier clipping | Yes | **AWAITING APPROVAL** |
| **GATE-12** | Epoch Matching Tolerance | [PROPOSED] Option C: Bounded composite with $0.25 T_{\text{dur}}$ detector resolution / scoring term and $0.50 T_{\text{dur}}$ scoring cap | Option A: $0.50 \times T_{\text{dur}}$; Option B: $0.25 \times T_{\text{dur}}$ | Yes | **AWAITING APPROVAL** |

---

### Detailed Profiles for Reconciled Decision Gates

#### GATE-01: Period Matching Tolerance
- **Decision Requested**: Select the numerical tolerance formula for declaring detected period $P_{\text{det}}$ consistent with true catalog period $P_{\text{true}}$.
- **Available Options**:
  1. *Option A [PROPOSED]*: Relative tolerance $\epsilon_P = 0.01$ ($1.0\%$), $|P_{\text{det}} - P_{\text{true}}| / P_{\text{true}} \le 0.01$.
  2. *Option B (Alternative)*: Grid-dependent Fourier resolution limit: $\Delta P_{\text{tol}} = 3 \times \frac{P^2}{T_{\text{usable}}}$.
- **Methodological Consequences**: Option A provides an intuitive scale-invariant percentage across all periods. Option B reflects physical Fourier peak broadening with $P^2$, being tighter at short periods and looser at long periods.
- **Evidence Needed**: Distribution of peak widths from periodogram simulations across $P \in [0.5, 15.0]\text{ d}$.
- **Synthetic Calibration**: Feasible. Inject synthetic transits at known periods, measure $|P_{\text{recovered}} - P_{\text{true}}|$, and choose tolerance encompassing $\ge 99\%$ of uncontaminated recoveries.
- **Status**: **AWAITING RESEARCHER APPROVAL**

#### GATE-02: 1D CNN Dual Validation Gate
- **Decision Requested**: Establish minimum performance criteria on an independent validation set required to lift the 1D CNN baseline off probation.
- **Available Options**:
  1. *Option A [PROPOSED]*: Specificity $\ge 0.85$ AND Sensitivity $\ge 0.75$, with non-zero counts in all confusion matrix quadrants.
  2. *Option B (Stricter)*: Specificity $\ge 0.90$ AND Sensitivity $\ge 0.80$.
- **Methodological Consequences**: Option A allows evaluating remediated CNNs with moderate sensitivity. Option B requires high discrimination before admission. Both prevent all-positive or all-negative collapse.
- **Evidence Needed**: Validation test report on independent, disjoint synthetic/flight validation split.
- **Synthetic Calibration**: Feasible. Train and evaluate on balanced and imbalanced synthetic splits.
- **Status**: **AWAITING RESEARCHER APPROVAL**

#### GATE-03: Event Window Cadence and Temporal Adequacy Criterion
- **Decision Requested**: Define the minimum valid temporal coverage and cadence threshold required for a predicted transit window to be deemed adequately observed, and define the benchmark policy for partial events and sector-boundary crossing events.
- **Exposure Boundaries & Temporal Coverage**:
  - The observational baseline is defined by exposure intervals $I_i = [t_i - \Delta t_{\text{exp}}/2, t_i + \Delta t_{\text{exp}}/2]$, yielding overall baseline $[t_{\text{base},\min}, t_{\text{base},\max}] = [\min_i(t_i - \Delta t_{\text{exp}}/2), \max_i(t_i + \Delta t_{\text{exp}}/2)]$.
  - Temporal coverage fraction is strictly defined via Lebesgue measure of valid exposure intersection:
    $$f_{\text{temporal}, k} = \frac{\mu\left(W_{\text{event}, k} \cap \bigcup_{i \in \mathcal{V}} I_i\right)}{T_{\text{dur}}}$$
  - Cadence count ratio $r_{\text{cadence}, k} = N_{\text{valid}, k} / N_{\text{expected}, k}$ is recorded as a separate diagnostic and never conflated with $f_{\text{temporal}, k}$.
- **Available Options**:
  1. *Option A [PROPOSED]*: $f_{\text{temporal}} \ge 50\%$ AND $N_{\text{valid}} \ge 5$. Categorical exclusion of boundary-truncated and partial events ($W_{\text{event}, k} \not\subset [t_{\text{base},\min}, t_{\text{base},\max}]$) from $N_{\text{adequate}}$, routing them to $N_{\text{boundary\_excluded}}$ / $N_{\text{insufficient}}$.
  2. *Option B (Looser Coverage)*: $f_{\text{temporal}} \ge 30\%$ AND $N_{\text{valid}} \ge 3$, with categorical exclusion of boundary events.
  3. *Option C (Partial Recovery Evaluation)*: Score boundary-truncated events under a relaxed threshold if in-baseline temporal coverage exceeds a partial threshold (e.g. $\ge 30\%$).
  4. *Option D (Secondary Diagnostic Track)*: Retain primary evaluation on strictly complete events, but report detection rates on boundary/partial events in a separate diagnostic ledger to assess edge-detection sensitivity.
- **Methodological Consequences**: Categorical exclusion (Option A) prevents partial/boundary transits with missing ingress or egress from depressing detector scores, but reduces event sample size. Option C tests partial recovery but penalizes models that require symmetric U-shaped profiles. Option D provides complete visibility without conflating primary metrics.
- **Evidence Needed**: Transit parameter fitting precision and detector recovery as a function of coverage fraction and boundary truncation on synthetic flights.
- **Synthetic Calibration**: Feasible. Subsample synthetic transits to varying coverage fractions and simulate sector-edge truncations.
- **Status**: **AWAITING RESEARCHER APPROVAL**

#### GATE-04: Harmonic Set Definition
- **Decision Requested**: Specify the set of rational frequency multipliers $\mathcal{H}$ recognized as harmonic recoveries.
- **Available Options**:
  1. *Option A [PROPOSED]*: $\mathcal{H} = \{1/3, 1/2, 2, 3\}$.
  2. *Option B (Conservative)*: $\mathcal{H} = \{1/2, 2\}$ (first subharmonic and first harmonic only).
- **Methodological Consequences**: Option A captures 3:1 orbital resonance aliases common in deep transits or eccentric orbits. Option B restricts credit strictly to half-period (e.g. secondary eclipses) and double-period detections.
- **Evidence Needed**: Frequency distribution of secondary BLS peaks from known exoplanet catalogs.
- **Synthetic Calibration**: Feasible. Measure harmonic peak generation rates across period search grids on synthetic data.
- **Status**: **AWAITING RESEARCHER APPROVAL**

#### GATE-05: Detrending Filter Type, Fitting Model, and Acceptance Threshold
- **Decision Requested**: Select the baseline segment-wise detrending filter algorithm, specify the recovered-depth fitting template and baseline normalization, define failure handling, and formalize synthetic validation acceptance thresholds.
- **Fitting Model & Baseline Normalization**:
  - Baseline flux $C_{\text{out}}$ must be estimated locally from out-of-transit buffer cadences $t_i \in [t_{\text{mid}} - 1.5 T_{\text{dur}}, t_{\text{mid}} - 0.75 T_{\text{dur}}] \cup [t_{\text{mid}} + 0.75 T_{\text{dur}}, t_{\text{mid}} + 1.5 T_{\text{dur}}]$ using median or biweight location.
  - Candidate fitting models:
    - *Box Model*: Uniform depth $\delta$ within in-transit window $|t_i - t_{\text{mid}}| \le 0.5 T_{\text{dur}}$.
    - *Trapezoid Model*: Linear ingress/egress ramps with parameter $\tau_{\text{ingress}}$ and flat bottom.
    - *Limb-Darkened Mandel-Agol Model*: Analytic quadratic limb-darkened profile parameterized by $(R_p/R_*, a/R_*, u_1, u_2)$.
- **Failure Handling**:
  - Fits failing due to $<3$ in-transit cadences, singular design matrices, non-finite parameters, or negative recovered depths must NOT be discarded from acceptance statistics.
  - Failure rate $f_{\text{fail}} = N_{\text{failed}} / N_{\text{total}}$ must be reported explicitly.
  - Benchmark must report both omnibus distributions (assigning $R_{\text{depth}} = 0$ on failure) and convergent distributions ($N_{\text{converged}}$ only).
  - Transits within $1.5 T_{\text{dur}}$ of segment edges must be segregated into an edge-affected diagnostic cohort.
- **Available Options**:
  1. *Option A [PROPOSED]*: Segment-wise running median filter ($W = 1.25\text{ days}$), Box fitting model, with candidate acceptance threshold median $R_{\text{depth}} \ge 0.95$ ($T_{\text{dur}} \le 6\text{ h}$) and $R_{\text{depth}} \ge 0.90$ ($T_{\text{dur}} \in [6, 8]\text{ h}$), requiring $f_{\text{fail}} \le 1.0\%$.
  2. *Option B (Spline Filter with Box Model)*: Segment-wise robust biweight spline ($W = 1.25\text{ days}$) with identical acceptance criteria.
  3. *Option C (Trapezoid Model)*: Running median filter ($W = 1.25\text{ days}$) with Trapezoid fitting model.
  4. *Option D (Limb-Darkened Model)*: Running median filter ($W = 1.25\text{ days}$) with Mandel-Agol quadratic limb-darkened profile.
- **Methodological Consequences**: Running median is non-parametric and robust against outliers; spline provides continuous derivatives. Box models are simple and robust; trapezoid and Mandel-Agol account for limb-darkening but require more parameters and have higher failure rates under low SNR.
- **Evidence Needed**: Injected-depth vs recovered-depth distributions and fit failure rates from synthetic validation experiments on quiet flight light curves.
- **Synthetic Calibration**: Feasible.
- **Status**: **AWAITING RESEARCHER APPROVAL**

#### GATE-06: Multi-Planet System Handling
- **Decision Requested**: Determine the eligibility policy for known multi-planet systems in the primary benchmark cohort.
- **Available Options**:
  1. *Option A [PROPOSED]*: Restrict primary cohort strictly to confirmed single-planet systems; defer multi-planet systems.
  2. *Option B (Alternative)*: Include multi-planet systems, scoring detections strictly against the dominant (highest expected SNR / depth) planet.
- **Methodological Consequences**: Option A guarantees clean ground truth for single-peak BLS. Option B expands target sample size but introduces unmodeled secondary dips that degrade periodogram power.
- **Evidence Needed**: Target yield analysis in Sectors 1–5 comparing single vs multi-planet catalog availability.
- **Synthetic Calibration**: Partially feasible (can simulate overlapping multi-planet injections).
- **Status**: **AWAITING RESEARCHER APPROVAL**

#### GATE-07: Search Range Boundaries
- **Decision Requested**: Define the maximum period boundary for the primary benchmark search grid.
- **Available Options**:
  1. *Option A [PROPOSED]*: Restrict cohort to $P \in [0.5, 15.0]\text{ days}$, ensuring $\ge 2$ transits in a 27.4-day sector.
  2. *Option B (Alternative)*: Expand BLS search grid to $P_{\max} = 25.0\text{ days}$, scoring single-transit detections under a dedicated event track.
- **Methodological Consequences**: Option A ensures every evaluated host is physically eligible for period recovery. Option B tests long-period sensitivity but includes systems with only 1 transit, conflating period failure with observational geometry.
- **Evidence Needed**: Cohort size trade-off in NASA Exoplanet Archive for $P \le 15\text{ d}$ vs $P \le 25\text{ d}$.
- **Synthetic Calibration**: Feasible.
- **Status**: **AWAITING RESEARCHER APPROVAL**

#### GATE-08: Production Cohort Size
- **Decision Requested**: Specify the target count for Stage 2 production benchmarking across Sectors 1–5.
- **Available Options**:
  1. *Option A [PROPOSED]*: $N = 100$ (50 Confirmed Hosts, 50 Observational Comparison Stars).
  2. *Option B (Alternative)*: $N = 60$ (30 Confirmed Hosts, 30 Observational Comparison Stars).
- **Methodological Consequences**: Option A narrows Wilson score confidence interval half-widths to $\approx \pm 10\text{--}14\%$. Option B reduces download and compute time by $40\%$ but broadens confidence intervals.
- **Evidence Needed**: Available confirmed hosts meeting all eligibility criteria across Sectors 1–5.
- **Synthetic Calibration**: Not applicable (resource and empirical catalog availability decision).
- **Status**: **AWAITING RESEARCHER APPROVAL**

#### GATE-09: BLS Frequency Grid Spacing Construction
- **Decision Requested**: Select the frequency grid spacing algorithm for the primary BLS baseline, and specify exact reproducibility recording mandates.
- **Reproducibility Mandates**:
  - The specification `astropy>=6.0.0` in environment manifests is an inequality dependency constraint, NOT an exact version pin.
  - During benchmark implementation and execution, the runner must record `astropy.__version__`, export the exact environment lockfile, log all API arguments passed to `autoperiod()`, and serialize the generated frequency grid array to persistent storage (`bls_frequency_grid.npy` or HDF5).
- **Available Options**:
  1. *Option A [PROPOSED]*: Astropy `BoxLeastSquares.autoperiod()` duration-adaptive grid:
     $$\Delta f(P) = \frac{\min(T_{\text{dur}})}{P \cdot f_{\text{factor}} \cdot T_{\text{usable}}}$$
     with candidate proposed oversampling factor $f_{\text{factor}} = 5.0$.
  2. *Option B (Alternative)*: Fixed uniform frequency grid with high oversampling ($N_{\text{freq}} \ge 20,000$).
- **Methodological Consequences**: Option A adaptively allocates grid density where phase drift is steepest, minimizing unnecessary computation while strictly preventing transit smearing. Option B is conceptually simpler but oversamples long periods and risks undersampling short periods unless $N_{\text{freq}}$ is extremely large.
- **Evidence Needed**: Transit recovery completeness vs computation time across trial grid formulations on synthetic injections.
- **Synthetic Calibration**: Feasible. Calibrate $f_{\text{factor}}$ on synthetic injection grid.
- **Status**: **AWAITING RESEARCHER APPROVAL**

#### GATE-10: BLS Flux Weighting Model
- **Decision Requested**: Specify the per-cadence weight model $w_i$ for BLS periodogram optimization.
- **Available Options**:
  1. *Option A [PROPOSED]*: Inverse-variance weighting ($w_i = 1 / \sigma_i^2$, using normalized SPOC flux errors).
  2. *Option B (Alternative)*: Uniform weighting ($w_i = 1$).
- **Methodological Consequences**: Option A downweights noisy cadences (e.g. near sector edges, momentum dumps) and yields maximum-likelihood estimates under Gaussian white noise. Option B avoids vulnerability to underestimated error bars but gives equal weight to corrupted cadences.
- **Evidence Needed**: Empirical error bar distribution and transit recovery comparison on flight data.
- **Synthetic Calibration**: Feasible. Inject transits into heteroscedastic flight noise and compare recovery.
- **Status**: **AWAITING RESEARCHER APPROVAL**

#### GATE-11: SDE Background Estimation Distribution
- **Decision Requested**: Define the method for computing periodogram background power statistics $(\mu_{\text{Power}}, \sigma_{\text{Power}})$ for SDE calculation, including formal definitions of fundamental peaks, harmonics, subharmonics, satellite aliases, and invalid bins.
- **Alias & Mask Definitions**:
  - *Fundamental Peak*: $f_0 = \operatorname{argmax}_f \operatorname{Power}(f)$, with primary exclusion region $E_0 = [f_0 - 3 \Delta f, f_0 + 3 \Delta f]$.
  - *Harmonics & Subharmonics*: Multipliers $h \in \{1/3, 1/2, 2, 3\}$, with exclusion regions $E_h = [h f_0 - 3 \Delta f, h f_0 + 3 \Delta f]$.
  - *Satellite Aliases*: Peaks induced by sector baseline or data downlink gaps ($f_{\text{sat}} = f_0 \pm k \cdot \Delta f_{\text{gap}}$, where $\Delta f_{\text{gap}} \approx 0.0730\text{ d}^{-1}$ for TESS orbit resonance).
  - *Composite Exclusion Mask*: Full set-theoretic union $\mathcal{E} = E_0 \cup \left(\bigcup_{h \in \mathcal{H}} E_h\right) \cup \left(\bigcup_{s \in \mathcal{S}} E_s\right)$. Overlapping intervals are automatically merged.
  - *Invalid Bins*: Bins with $\operatorname{Power}(f) \le 0$, $\text{NaN}$, or $\pm\infty$ are stripped prior to masking.
  - *Degeneracy Guard*: If valid unmasked bins $N_{\text{valid}} < 50$, background statistics are undefined and SDE must return $\text{NaN}$.
- **Available Options**:
  1. *Option A [PROPOSED]*: All valid frequencies unclipped (standard parametric mean/std over all finite bins).
  2. *Option B (Peak-Excluded Parametric)*: Exclude primary peak window $E_0$; parametric mean/std over remainder.
  3. *Option C (Peak & Harmonic Excluded Robust MAD)*: Exclude composite mask $\mathcal{E}$; compute robust dispersion using median and normalized MAD ($\sigma_{\text{Power}} = 1.4826 \times \operatorname{MAD}(\text{Power} \setminus \mathcal{E})$).
  4. *Option D (Iterative Outlier Clipping)*: Apply iterative $3\sigma$ clipping until convergence, computing background on unclipped bins.
- **Methodological Consequences**: Option A depresses SDE for strong signals due to peak variance inflation. Option B removes only the primary peak. Option C fully isolates background from all harmonic and satellite artifacts. Option D iteratively clips without requiring explicit alias knowledge. All options are preserved pending researcher approval; no option is selected based on pilot outcomes.
- **Evidence Needed**: SDE stability and false-alarm distribution on comparison stars under Options A, B, C, and D.
- **Synthetic Calibration**: Feasible.
- **Status**: **AWAITING RESEARCHER APPROVAL**

#### GATE-12: Epoch Matching Tolerance
- **Decision Requested**: Specify the mathematical formula and threshold for declaring a detected epoch $t_{0,\text{det}}$ consistent with true transit midtime $t_{\text{mid}}$ (evaluated via circular phase distance $\Delta t_0 = \Delta \phi \cdot P_{\text{true}} \le \Delta t_{0,\text{tol}}$).
- **Distinction Between Eligibility and Matching**:
  - *Target Eligibility* ($\sigma_{t_{\text{mid}}} \le 0.25 T_{\text{dur}}$): Ephemeris quality threshold to ensure catalog ground truth is sufficiently precise.
  - *Detected Epoch Matching Tolerance* ($\Delta t_0 \le \Delta t_{0,\text{tol}}$): Detector scoring threshold to determine whether a detected transit center aligns with ground truth.
- **Available Options**:
  1. *Option A (Physical Dip Overlap)*: $\Delta t_{0,\text{tol}} = 0.50 \times T_{\text{dur}}$ (requires detected center to fall strictly inside physical 1st-to-4th contact window $[-T_{\text{dur}}/2, +T_{\text{dur}}/2]$).
  2. *Option B (Transit Core / Flat Bottom Overlap)*: $\Delta t_{0,\text{tol}} = 0.25 \times T_{\text{dur}}$ (stricter alignment inside central transit core).
  3. *Option C [PROPOSED] (Bounded Composite Formulation)*:
     $$\Delta t_{0,\text{tol}} = \min\left(0.50 \times T_{\text{dur}}, \quad \sqrt{\sigma_{\text{det}}^2 + (3 \times \sigma_{t_{\text{mid}}})^2}\right)$$
     where the candidate default for $\sigma_{\text{det}}$ is $0.25 \times T_{\text{dur}}$.
     - *Nature of the $0.25 T_{\text{dur}}$ Term*: Under this option, $0.25 T_{\text{dur}}$ represents either:
       - (a) A detector phase resolution parameter ($\sigma_{\text{det}}$), which must be measured/calibrated via synthetic injection-recovery simulations measuring the standard deviation of recovered midtimes $(\hat{t}_{\text{mid}} - t_{\text{true}})$ across signal-to-noise ratios; OR
       - (b) An explicit scoring convention requiring detected epoch alignment within the central flat-bottom core of the transit.
     - *Nature of the $0.50 T_{\text{dur}}$ Cap*: The $0.50 \times T_{\text{dur}}$ upper bound is **strictly a scoring convention** (enforcing that credit is never awarded if the detected epoch falls outside the physical 1st-to-4th contact dip window), and is **NOT a statistical confidence bound**.
- **Methodological Consequences**: Option A tests basic dip overlap. Option B tests flat-bottom precision but penalizes V-shaped grazing transits. Option C accounts for catalog ephemeris drift without ever accepting points outside the physical transit. All options remain pending researcher approval.
- **Evidence Needed**: Distribution of recovered epoch offsets from BLS fits across synthetic injections with varying duration and noise.
- **Synthetic Calibration**: Feasible.
- **Status**: **AWAITING RESEARCHER APPROVAL**
