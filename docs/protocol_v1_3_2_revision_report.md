# Methodological and Reproducibility Audit Report: Protocol v1.3.2

**Project**: TESS Transit Detection Benchmark  
**Document ID**: `docs/protocol_v1_3_2_revision_report.md`  
**Date**: 2026-09-28  
**Scope**: Documentation-Only v1.3.2 Scientific Integrity and Reproducibility Audit of Benchmark Protocol  
**Protocol Reference**: `docs/real_data_benchmark_protocol.md` (Version 1.3.2)  
**Status**: **COMPLETED AUDIT REPORT — SUBMITTED FOR RESEARCHER REVIEW**  

---

## Executive Summary

This report documents the documentation-only **v1.3.2 audit** of the **TESS Transit Detection Benchmark** protocol. The audit resolves eight technical, mathematical, and procedural ambiguities across the protocol specification, decision log, readiness checklist, and machine-readable configuration.

All mathematical definitions, operational constraints, and decision gates have been updated and synchronized across all four documents without silently approving any gates, without modifying data or code, and without claiming empirical validation.

### Strict Change-Control Boundaries Maintained
In strict accordance with researcher instructions:
1. **No code implementation**: No runner scripts, scoring engines, wrapper classes (`BlindLightCurve`), or detector models were implemented.
2. **No data manipulation**: No TESS observations or exoplanet catalog records were downloaded, altered, or re-ingested.
3. **No model execution**: No models were trained, evaluated, tuned, or benchmarked.
4. **No metric alteration**: No historical metrics, plots, predictions, or scientific results were modified.
5. **No gate approvals**: All 12 formal researcher decision gates remain strictly flagged as `AWAITING RESEARCHER APPROVAL`.
6. **No empirical claims**: The protocol and its safeguards are documented as engineering specifications; **no empirical validation was performed**.

---

## Technical Audit Findings and Reconciliations

### 1. Ephemeris Covariance and Propagated Uncertainty
- **Previous Ambiguity**: Earlier protocol iterations characterized the zero-covariance assumption ($\operatorname{Cov}(T_0, P) = 0$) as either an unverified limitation or implied that it is "not always conservative" without explaining the exact directional dependency on epoch offset and covariance signs.
- **Mathematical Correction in v1.3.2**:
  The full linear propagation of uncertainty for transit midtime $t_{\text{mid}}(E_k) = T_0 + E_k P$ is:
  $$\operatorname{Var}(t_{\text{mid}}(E_k)) = \sigma_{T_0}^2 + E_k^2 \sigma_P^2 + 2 E_k \operatorname{Cov}(T_0, P)$$
  When $\operatorname{Cov}(T_0, P)$ is omitted (approximated as zero), the error in propagated variance is:
  $$\Delta \operatorname{Var} = \operatorname{Var}_{\text{omitted}} - \operatorname{Var}_{\text{true}} = -2 E_k \operatorname{Cov}(T_0, P)$$
  Because the orbit epoch index $E_k = (t_{\text{mid}, k} - T_0) / P$ can be positive (observations after $T_0$) or negative (observations before $T_0$), the direction of the error depends strictly on the sign of $E_k \cdot \operatorname{Cov}(T_0, P)$:
  - If $E_k \cdot \operatorname{Cov}(T_0, P) > 0$, omitting covariance **underestimates** transit midtime uncertainty ($\operatorname{Var}_{\text{omitted}} < \operatorname{Var}_{\text{true}}$).
  - If $E_k \cdot \operatorname{Cov}(T_0, P) < 0$, omitting covariance **overestimates** transit midtime uncertainty ($\operatorname{Var}_{\text{omitted}} > \operatorname{Var}_{\text{true}}$), which is conservative.
  - In exoplanet transit timing fits, $\operatorname{Cov}(T_0, P)$ is commonly negative when $T_0$ is defined near the start of the discovery baseline, meaning forward extrapolation ($E_k > 0$) yields $E_k \operatorname{Cov}(T_0, P) < 0$. However, when $T_0$ is defined at the center of the baseline (where $\operatorname{Cov}(T_0, P) \approx 0$) or for backward extrapolation ($E_k < 0$), the sign flips.
- **Protocol Policy**: The protocol strictly forbids characterizing the zero-covariance approximation as either "always conservative" or "always underestimating uncertainty." Where catalog covariance is unavailable, it is documented as an unverified catalog limitation whose sign and magnitude must be reported.

### 2. Epoch Matching Tolerance and GATE-12 Option C
- **Previous Ambiguity**: In `GATE-12` Option C, $\Delta t_{0,\text{tol}} = \min(0.50 T_{\text{dur}}, \sqrt{(0.25 T_{\text{dur}})^2 + (3\sigma_{t_{\text{mid}}})^2})$, the origin of the $0.25 T_{\text{dur}}$ term and the nature of the $0.50 T_{\text{dur}}$ cap were insufficiently delineated.
- **Technical Clarification in v1.3.2**:
  1. *The $0.25 T_{\text{dur}}$ Term*:
     - Represents either:
       - (a) An empirical detector phase resolution parameter ($\sigma_{\text{det}}$), which accounts for phase discretization and BLS binning uncertainty; OR
       - (b) A scoring convention requiring the detected midpoint to align within the central flat-bottom core of the transit dip.
     - *Calibration Procedure*: If interpreted as detector phase resolution, $\sigma_{\text{det}}$ must be measured via synthetic injection-recovery simulations: injecting synthetic transits across a grid of SNRs, depths, and durations into real TESS noise, fitting BLS periodograms, and computing the empirical standard deviation $\sigma_{\text{det}} = \operatorname{Std}(\hat{t}_{\text{mid}} - t_{\text{true}})$.
  2. *The $0.50 T_{\text{dur}}$ Cap*:
     - The $0.50 T_{\text{dur}}$ upper bound is **strictly a scoring convention**, enforcing that detector credit is never awarded if the proposed transit midpoint falls outside the physical 1st-to-4th contact window $[-T_{\text{dur}}/2, +T_{\text{dur}}/2]$.
     - It is **NOT** a statistical confidence bound.
  3. *Status*: All three options under `GATE-12` (Option A: $0.50 T_{\text{dur}}$, Option B: $0.25 T_{\text{dur}}$, Option C: Bounded Composite) remain strictly `AWAITING RESEARCHER APPROVAL`.

### 3. Event Coverage, Baseline Boundaries, and Partial Events
- **Previous Ambiguity**: Baseline limits were ambiguously referenced as timestamps $t_{\min}$ and $t_{\max}$, exposure overlap measure was not formally defined for partial boundary crossings, and categorical exclusion of boundary events was written as an active default.
- **Mathematical Specification in v1.3.2**:
  1. *Exposure Baseline*: The observational baseline is defined by exposure intervals $I_i = [t_i - \Delta t_{\text{exp}}/2, t_i + \Delta t_{\text{exp}}/2]$, yielding:
     $$[t_{\text{base},\min}, t_{\text{base},\max}] = \left[ \min_i\left(t_i - \frac{\Delta t_{\text{exp}}}{2}\right), \, \max_i\left(t_i + \frac{\Delta t_{\text{exp}}}{2}\right) \right]$$
  2. *Continuous Exposure Overlap*: For each valid cadence $i \in \mathcal{V}$, the exposure interval $I_i$ intersects the transit window $W_{\text{event}, k} = [t_{\text{mid}, k} - T_{\text{dur}}/2, t_{\text{mid}, k} + T_{\text{dur}}/2]$. The temporal coverage fraction is the 1D Lebesgue measure of their union:
     $$f_{\text{temporal}, k} = \frac{\mu\left(W_{\text{event}, k} \cap \bigcup_{i \in \mathcal{V}} I_i\right)}{T_{\text{dur}}}$$
  3. *Cadence Count Ratio*: The ratio $r_{\text{cadence}, k} = N_{\text{valid}, k} / N_{\text{expected}, k}$ is tracked as an independent sampling diagnostic and is never conflated with $f_{\text{temporal}, k}$.
  4. *Partial & Boundary Events*: If an event window crosses a sector or segment boundary ($W_{\text{event}, k} \not\subset [t_{\text{base},\min}, t_{\text{base},\max}]$), categorical exclusion from $N_{\text{adequate}}$ is now explicitly identified as a **[PROPOSED] methodological choice awaiting researcher approval under GATE-03**. Alternative options preserved for researcher decision include:
     - *Option A [PROPOSED]*: Categorical exclusion from $N_{\text{adequate}}$ (routed to $N_{\text{boundary\_excluded}}$).
     - *Option B*: Looser coverage threshold ($f_{\text{temporal}} \ge 30\%$, $N_{\text{valid}} \ge 3$).
     - *Option C*: Partial recovery evaluation (score boundary events if $f_{\text{temporal}} \ge 30\%$).
     - *Option D*: Secondary diagnostic track (retain complete events in primary ledger, report boundary recovery in a separate diagnostic ledger).

### 4. Detrending Validation, Fitting Models, and Failure Handling
- **Previous Ambiguity**: The recovered-depth estimator did not formally specify the baseline normalization $C_{\text{out}}$, the exact fitting model template was vague, fit failure handling was not defined, and thresholds were written as fixed requirements.
- **Specification in v1.3.2**:
  1. *Baseline Normalization*: Out-of-transit flux $C_{\text{out}}$ must be estimated locally from symmetric buffer windows:
     $$t_i \in \left[t_{\text{mid}} - 1.5 T_{\text{dur}}, \, t_{\text{mid}} - 0.75 T_{\text{dur}}\right] \cup \left[t_{\text{mid}} + 0.75 T_{\text{dur}}, \, t_{\text{mid}} + 1.5 T_{\text{dur}}\right]$$
     using median or biweight location.
  2. *Fitting Model Options under GATE-05*:
     - *Box Model*: Uniform depth $\delta$ within in-transit window $|t_i - t_{\text{mid}}| \le 0.5 T_{\text{dur}}$.
     - *Trapezoid Model*: Linear ingress/egress ramps with free parameter $\tau_{\text{ingress}}$.
     - *Limb-Darkened Mandel-Agol Model*: Analytic quadratic limb-darkened profile.
  3. *Fit Failure Handling*:
     - Fits failing due to $<3$ in-transit cadences, singular design matrices, non-finite values, or negative recovered depths must NOT be silently dropped.
     - Failure rate $f_{\text{fail}} = N_{\text{failed}} / N_{\text{total}}$ must be logged and reported explicitly.
     - Benchmark reporting must present both omnibus distributions (assigning $R_{\text{depth}} = 0$ on failure) and convergent distributions ($N_{\text{converged}}$ only).
     - Transits within $1.5 T_{\text{dur}}$ of segment edges must be segregated into an edge-affected diagnostic cohort.
  4. *Status*: Acceptance thresholds ($R_{\text{depth}} \ge 0.95$ for $T_{\text{dur}} \le 6\text{ h}$, $R_{\text{depth}} \ge 0.90$ for $T_{\text{dur}} \in [6, 8]\text{ h}$, $f_{\text{fail}} \le 1.0\%$) remain strictly `[PROPOSED]` awaiting approval under `GATE-05`.

### 5. Astropy Reproducibility and Grid Serialization
- **Previous Ambiguity**: Earlier protocol documents claimed that `astropy>=6.0.0` was an exact version pin, whereas it is an inequality dependency constraint.
- **Correction in v1.3.2**:
  - The specification `astropy>=6.0.0` in environment manifests is an inequality dependency constraint, NOT an exact version pin. (In the active environment, `astropy==8.0.1` is installed).
  - Protocol v1.3.2 strictly mandates that during benchmark implementation and execution, the runner must:
    1. Log runtime `astropy.__version__` directly in the run manifest.
    2. Export the exact environment lockfile (`pip freeze` or `conda list --export`).
    3. Log the exact dictionary of API arguments passed to `BoxLeastSquares.autoperiod()`.
    4. Serialize the generated frequency grid array to persistent disk (`bls_frequency_grid.npy` or HDF5) to guarantee byte-for-byte reproducibility regardless of upstream Astropy grid algorithmic changes.
  - No synthetic version numbers were invented.

### 6. SDE Alias Exclusion and Composite Union Mask
- **Previous Ambiguity**: Alias exclusion rules under `GATE-11` were only partially sketched, lacking formal mathematical definitions of harmonic sets, satellite aliases, and composite mask combination.
- **Specification in v1.3.2**:
  - *Fundamental Peak*: $f_0 = \operatorname{argmax}_f \operatorname{Power}(f)$, with exclusion window $E_0 = [f_0 - 3\Delta f, f_0 + 3\Delta f]$.
  - *Harmonics and Subharmonics*: Multipliers $h \in \{1/3, 1/2, 2, 3\}$, with exclusion windows $E_h = [h f_0 - 3\Delta f, h f_0 + 3\Delta f]$.
  - *Satellite Aliases*: Orbit/downlink gap aliases $f_{\text{sat}} = f_0 \pm k \cdot \Delta f_{\text{gap}}$, where $\Delta f_{\text{gap}} \approx 0.0730\text{ d}^{-1}$.
  - *Composite Union Mask*: Full set-theoretic union:
    $$\mathcal{E} = E_0 \cup \left( \bigcup_{h \in \mathcal{H}} E_h \right) \cup \left( \bigcup_{s \in \mathcal{S}} E_s \right)$$
    with overlapping intervals automatically merged into contiguous intervals.
  - *Invalid Bins*: Bins with $\operatorname{Power}(f) \le 0$, $\text{NaN}$, or $\pm\infty$ are stripped prior to masking.
  - *Degeneracy Guard*: If valid unmasked bins $N_{\text{valid}} < 50$, background statistics are undefined and SDE must return $\text{NaN}$.
  - *Status*: All four options (Option A: Parametric Unclipped, Option B: Peak-Excluded Parametric, Option C: Peak+Harmonic Excluded Robust MAD, Option D: Iterative Outlier Clipping) are preserved under `GATE-11` awaiting researcher approval. No option was selected based on pilot outcomes.

### 7. Proposed Defaults versus Pending Gates
- **Audit Action**: Every unresolved parameter, threshold, and operational policy across `docs/real_data_benchmark_protocol.md`, `docs/benchmark_decision_log.md`, `results/real_data_pilot/protocol_readiness_checklist.md`, and `configs/real_benchmark_protocol.yaml` has been audited.
- **Result**: All numeric candidate values are explicitly marked with `[PROPOSED]` or `AWAITING RESEARCHER APPROVAL`. No implementation instructions treat pending choices as active defaults.

### 8. Validation Claims and Formal Distinctions
- **Formal Boundary Distinction**:
  1. *YAML Syntax Validation*: PyYAML `yaml.safe_load()` verifies syntactic correctness and dictionary key hierarchy. (Executed: 10 keys loaded cleanly).
  2. *Existing Automated Test Suite*: 48 unit tests passing with 91% code coverage (`pytest tests/`). These tests validate low-level utility functions, FITS loading routines, and synthetic data structures. **They do NOT validate the scientific protocol or benchmark detection performance.**
  3. *Semantic Consistency Review*: Thorough cross-document alignment ensuring mathematical formulas, gate definitions, and parameters match across protocol, decision log, checklist, and YAML.
  4. *Empirical Validation*: **None performed.** No detection performance metrics, synthetic injection recovery curves, or benchmark runs have been executed.

---

## Change Control and Audit Results

### 1. Files Changed
1. `docs/real_data_benchmark_protocol.md` (Updated to Version 1.3.2)
2. `docs/benchmark_decision_log.md` (Updated to Version 1.3.2)
3. `results/real_data_pilot/protocol_readiness_checklist.md` (Updated to Version 1.3.2)
4. `configs/real_benchmark_protocol.yaml` (Updated to Version 1.3.2)
5. `docs/protocol_v1_3_2_revision_report.md` (Created audit revision report)

### 2. Version Changes
- Specification version incremented uniformly: **`v1.3.1` $\to$ `v1.3.2`**.
- YAML protocol ID updated: **`REAL_TESS_BENCHMARK_v1.3.1` $\to$ `REAL_TESS_BENCHMARK_v1.3.2`**.

### 3. Validation Performed and Exact Results
- **YAML Validation**:
  ```bash
  PYTHONPATH= .venv/bin/python -c "import yaml; data = yaml.safe_load(open('configs/real_benchmark_protocol.yaml')); print('YAML loaded successfully! Keys:', len(data))"
  # Output: YAML loaded successfully! Keys: 10
  ```
- **Automated Test Suite**:
  ```bash
  PYTHONPATH= .venv/bin/pytest tests/ -q
  # Output: 48 passed in 7.91s (91% overall coverage)
  ```
- **Git Status Verification**:
  ```bash
  git status -s
  # Only documentation, configuration, and audit reports modified/created; zero data or scientific outputs touched.
  ```

### 4. Confirmation of Scientific Output Preservation
- **Confirmed**: No raw FITS files, processed pilot light curves, pilot metrics (`pilot_report.md`, `cadence_reconciliation.csv`, `ephemeris_validation.csv`), synthetic benchmark outputs, or model weights were altered, overwritten, or recomputed.

---

## Formal Registry of All 12 Pending Researcher Decision Gates

| Gate ID | Topic | Proposed Option | Alternative Options | Status | Decision Still Required |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **GATE-01** | Period Matching Tolerance | [PROPOSED] $\epsilon_P = 1.0\%$ ($0.01$) | Fourier resolution limit ($3 P^2 / T_{\text{usable}}$) | **AWAITING APPROVAL** | Select scale-invariant relative tolerance vs Fourier limit. |
| **GATE-02** | 1D CNN Dual Validation Gate | [PROPOSED] Specificity $\ge 0.85$, Sensitivity $\ge 0.75$ | Stricter (0.90 / 0.80) | **AWAITING APPROVAL** | Select minimum validation thresholds to lift CNN off probation. |
| **GATE-03** | Window Cadence & Coverage Adequacy | [PROPOSED] $f_{\text{temporal}} \ge 50\%$, $N_{\text{valid}} \ge 5$; categorical exclusion of boundary events | Looser (30% / 3); partial event scoring; secondary diagnostic track | **AWAITING APPROVAL** | Select coverage threshold and partial/boundary event handling policy. |
| **GATE-04** | Harmonic Set Definition | [PROPOSED] $\mathcal{H} = \{1/3, 1/2, 2, 3\}$ | Conservative $\mathcal{H} = \{1/2, 2\}$ | **AWAITING APPROVAL** | Select whether 3:1 subharmonics/harmonics receive harmonic credit. |
| **GATE-05** | Detrending Filter, Model & Acceptance | [PROPOSED] Running median ($W=1.25\text{ d}$), Box model, candidate $R_{\text{depth}} \ge 0.95$, $f_{\text{fail}} \le 1.0\%$ | Robust biweight spline; Trapezoid model; Limb-Darkened model | **AWAITING APPROVAL** | Select detrending algorithm, transit fitting model, and acceptance criteria. |
| **GATE-06** | Multi-Planet System Handling | [PROPOSED] Restrict primary cohort to single confirmed hosts | Score against highest-depth planet in system | **AWAITING APPROVAL** | Select primary cohort eligibility for multi-planet hosts. |
| **GATE-07** | Search Range Boundaries | [PROPOSED] $P \in [0.5, 15.0]\text{ days}$ | Expand BLS grid to $P_{\max} = 25.0\text{ days}$ | **AWAITING APPROVAL** | Select maximum search period and single-transit scoring track. |
| **GATE-08** | Production Cohort Size | [PROPOSED] $N = 100$ (50 Hosts, 50 Controls) | $N = 60$ (30 Hosts, 30 Controls) | **AWAITING APPROVAL** | Select production target count based on compute and CI precision. |
| **GATE-09** | BLS Frequency Grid Spacing | [PROPOSED] Astropy `autoperiod` adaptive scaling ($f_{\text{factor}}=5.0$); record runtime version, args, and serialized grid | Fixed uniform frequency grid ($\Delta f \approx 0.00730\text{ d}^{-1}$) | **AWAITING APPROVAL** | Select adaptive vs uniform grid construction and calibrate $f_{\text{factor}}$. |
| **GATE-10** | BLS Flux Weighting Model | [PROPOSED] Inverse-variance weighting ($w_i = 1 / \sigma_i^2$) | Uniform weighting ($w_i = 1$) | **AWAITING APPROVAL** | Select per-cadence flux error weighting model. |
| **GATE-11** | SDE Background Estimation | [PROPOSED] Option A: Unclipped; preserve Options B, C, D with full composite alias mask $\mathcal{E}$ | Peak-excluded; Peak+Harmonic robust MAD; Iterative $3\sigma$ clipping | **AWAITING APPROVAL** | Select background estimation distribution and alias exclusion rule. |
| **GATE-12** | Epoch Matching Tolerance | [PROPOSED] Option C: Bounded composite with $0.25 T_{\text{dur}}$ detector resolution / scoring term and $0.50 T_{\text{dur}}$ scoring cap | Option A ($0.50 T_{\text{dur}}$); Option B ($0.25 T_{\text{dur}}$) | **AWAITING APPROVAL** | Select epoch matching formula, calibrate $\sigma_{\text{det}}$, and confirm $0.50 T_{\text{dur}}$ scoring cap. |

---

## Remaining Implementation Blockers and Next Steps

The following prerequisite items are technical blockers that must be resolved before executing the real-data benchmark:

1. **Researcher Gate Sign-Off**: Formal approval of all 12 decision gates listed above.
2. **Air-Gap Wrapper Implementation**: Construction and verification of `BlindLightCurve` dataclass and air-gapped runner `scripts/run_blind_benchmark.py` ensuring zero metadata exposure.
3. **Disjoint Model Training**: Creation of `scripts/train_external_benchmark_models.py` training Tabular ML baselines on disjoint synthetic/out-of-sector data.
4. **Detrending Synthetic Validation**: Execution of pre-deployment synthetic injection test measuring $R_{\text{depth}}$, $f_{\text{fail}}$, and edge segregation.
5. **Stage 1 Feasibility Certification**: Execution of Stage 1 feasibility run on the 10 pilot targets with strictly frozen parameters to verify software mechanics.

Execution of the benchmark runner, scoring engine, and model evaluation remains halted pending researcher review and formal gate resolution.
