# Stage 3 Readiness Evidence Audit Report

**Date**: 2026-10-05  
**Repository**: `/home/purab/Purab/Projects/TESS-Light-curve`  
**Purpose**: Pre-Formal Stage 3 Evidence Audit and Gate Verification  
**Scope**: Verification and evidence audit only. **Formal Stage 3 benchmark has NOT been run.**

---

## 1. Repository & Environment Snapshot

### 1.1 Git Status & Branch State
- **Branch**: `main`
- **HEAD Commit**: `fc795a71391129ae59219fb52e88b9a967fd4ca8`
- **Relationship to Remote**: In exact sync with `origin/main` (`fc795a71391129ae59219fb52e88b9a967fd4ca8`; 0 commits ahead, 0 commits behind).
- **Working Tree Status**:
  - Uncommitted modified files:
    - `pyproject.toml` (pytest addopts updated to `-p no:launch_testing -p no:launch_testing_ros` to protect against system ROS test plugin interference).
    - `src/tess_benchmark/baselines/bls.py` (GATE-11 SDE hook integration with `compute_sde` helper and metadata logging).
  - Untracked artifacts & modules:
    - `results/experiment_2_sde_comparison/` (Experiment 2 raw paired predictions and summary).
    - `results/real_benchmark_stage3/` (Readiness audits, evidence logs).
    - `results/real_data_stage2/cohort_replacement_audit.csv`
    - `results/real_data_stage2/replacement_candidates_validated.csv`
    - `results/real_data_stage2/stage2_corrected_cohort_manifest.csv`
    - `results/real_data_stage2/stage2_corrected_cohort_summary.json`
    - `scripts/run_experiment_2_sde.py`
    - `src/tess_benchmark/baselines/sde.py`
    - `src/tess_benchmark/evaluation/recovery.py`
    - `tests/test_recovery.py`
    - `tests/test_sde.py`

### 1.2 Python Environment & Package Versions
- **Python Executable**: `/home/purab/Purab/Projects/TESS-Light-curve/.venv/bin/python`
- **Python Version**: `3.11.15`
- **Active Virtual Environment**: `.venv` (located at repository root `/home/purab/Purab/Projects/TESS-Light-curve/.venv`)
- **Key Package Versions**:
  - `torch`: `2.14.0+cu130`
  - `astropy`: `8.0.1`
  - `lightkurve`: `2.5.1`
  - `pytest`: `9.1.1`
  - `numpy`: `2.4.6`
  - `scipy`: `1.17.1`
  - `pandas`: `3.0.6`

---

## 2. GATE-06: Verification of All 9 Replacement Hosts

Each of the nine replacement single-planet host candidates admitted into the corrected Stage 2 manifest was independently queried against the NASA Exoplanet Archive TAP service (`https://exoplanetarchive.ipac.caltech.edu/TAP/sync`) via the `ps` table (`default_flag=1`) and verified against the official catalog parameters:

| TIC ID | Host Name | Sector | Archive `sy_pnum` | Qualifying Planet | Period (d) | Discovery Method & Archive Evidence | Physical Status | Protocol Sector Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **TIC 170102285** | WASP-23 | 6 | **1** | WASP-23 b | 2.944426 | Transit; NASA ps `default_flag=1`, `pl_controv_flag=0` | **PASS** | Permitted (Cleaner sector expansion) |
| **TIC 52640302** | WASP-64 | 6 | **1** | WASP-64 b | 1.573292 | Transit; NASA ps `default_flag=1`, `pl_controv_flag=0` | **PASS** | Permitted (Cleaner sector expansion) |
| **TIC 306362738** | WASP-49 | 6 | **1** | WASP-49 b | 2.781740 | Transit; NASA ps `default_flag=1`, `pl_controv_flag=0` | **PASS** | Permitted (Cleaner sector expansion) |
| **TIC 47911178** | WASP-101 | 6 | **1** | WASP-101 b | 3.585720 | Transit; NASA ps `default_flag=1`, `pl_controv_flag=0` | **PASS** | Permitted (Cleaner sector expansion) |
| **TIC 59843967** | HATS-4 | 6 | **1** | HATS-4 b | 2.516729 | Transit; NASA ps `default_flag=1`, `pl_controv_flag=0` | **PASS** | Permitted (Cleaner sector expansion) |
| **TIC 290131778** | HD 202772 A | 1 | **1** | HD 202772 A b | 3.308877 | Transit; NASA ps `default_flag=1`, `pl_controv_flag=0` | **PASS** | Permitted (Sector 1 baseline) |
| **TIC 317548889** | TOI-480 | 6 | **1** | TOI-480 b | 6.866196 | Transit; NASA ps `default_flag=1`, `pl_controv_flag=0` | **PASS** | Permitted (Cleaner sector expansion) |
| **TIC 410214986** | DS Tuc A | 1 | **1** | DS Tuc A b | 8.138268 | Transit; NASA ps `default_flag=1`, `pl_controv_flag=0` | **PASS** | Permitted (Sector 1 baseline) |
| **TIC 290348383** | HD 207496 | **13** | **1** | HD 207496 b | 6.441008 | Transit; NASA ps `default_flag=1`, `pl_controv_flag=0` | **PASS** (Physical) | **CONFLICT (Sector 13 not approved)** |

Raw JSON TAP response records for each target are preserved in [`results/real_benchmark_stage3/gate06_archive_evidence.json`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_benchmark_stage3/gate06_archive_evidence.json).

---

## 3. Sector-Eligibility Audit & Protocol Conflict

### 3.1 Approved Sector Rules
- **Primary Protocol Specification** ([`configs/real_benchmark_protocol.yaml#L95`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L95)):
  ```yaml
  cohort_specification:
    stage_2_production:
      target_count: 100
      confirmed_hosts: 50
      observational_controls: 50
      sectors: [1, 2, 3, 4, 5]
  ```
- **Fallback Strategy** ([`configs/real_benchmark_protocol.yaml#L101-L103`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L101-L103)):
  `strategy: "expand_sectors_first_then_admit_multiplanet_fallback"`
- **Expansion Workflow Implementation** ([`scripts/run_stage2_acquisition.py#L55`](file:///home/purab/Purab/Projects/TESS-Light-curve/scripts/run_stage2_acquisition.py#L55), [`src/tess_benchmark/data/cohort.py#L860`](file:///home/purab/Purab/Projects/TESS-Light-curve/src/tess_benchmark/data/cohort.py#L860)):
  The approved Stage 2 expansion workflow specifies cleaner sectors: **Sectors 2, 5, and 6**.

### 3.2 Finding for Target #9: HD 207496 (TIC 290348383)
- Target HD 207496 was acquired from **Sector 13** (`tess2019169103026-s0013-0000000290348383-0146-s_lc.fits`).
- Sector 13 is **not** present in `sectors: [1, 2, 3, 4, 5]`, nor was it specified in the cleaner expansion sector list `(2, 5, 6)`.
- **Protocol Conflict**: Admitting Sector 13 represents an unauthorized expansion beyond approved sectors.
- **Protocol Action Taken**:
  - HD 207496 has **NOT** been silently removed or replaced.
  - The protocol has **NOT** been modified.
  - **GATE-06 is marked UNRESOLVED / BLOCKED** pending user decision on whether to formally approve Sector 13 or replace HD 207496 with an eligible single-planet host from approved Sectors 1–6.

---

## 4. Corrected Cohort Integrity

Audit of `results/real_data_stage2/stage2_corrected_cohort_manifest.csv`, `cohort_replacement_audit.csv`, and `stage2_corrected_cohort_summary.json`:

1. **Target Counts & Uniqueness**:
   - Total rows in manifest: exactly **100**
   - Unique TIC IDs: exactly **100** (0 duplicate TICs)
   - Confirmed planet hosts: exactly **50**
   - Observational control stars: exactly **50**
2. **GATE-06 Single-Planet Satisfaction**:
   - All 50 hosts have `sy_pnum == 1` in the NASA Exoplanet Archive (`ps` table with `default_flag=1`).
   - Zero known multi-planet systems exist in the primary host cohort.
3. **Observational Control Integrity**:
   - Exactly 50 control stars are present.
   - All 50 controls are documented with selection rationale: *"Field star observed in SPOC 120s cadence; zero TOI or confirmed exoplanet records"*.
   - Controls retain their strict scientific definition under **BDR-005**: non-detection comparison stars, **not** proven planet-free negatives.
4. **Data Quality Threshold Compliance**:
   - Host baseline duration: min = 21.77 d, max = 27.88 d (all $\ge 20.0$ d threshold).
   - Host usable cadence fraction: min = 0.8407, max = 0.9328 (all $\ge 0.80$ threshold).
   - Control baseline duration: min = 21.77 d, max = 27.88 d (all $\ge 20.0$ d threshold).
   - Control usable cadence fraction: min = 0.8078, max = 0.9105 (all $\ge 0.80$ threshold).
5. **Replacement Audit Log Characterization**:
   - Inspection of [`results/real_data_stage2/cohort_replacement_audit.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/cohort_replacement_audit.csv) reveals that it records the 9 removed multi-planet systems alongside the 9 admitted replacements strictly in sequential row order.
   - **Audit finding**: This file is an **operational replacement log**, not an astrophysical one-to-one matched mapping.

---

## 5. GATE-03 Implementation Audit

### 5.1 Code-Path Inspection
- **Implementation Location**: Function [`evaluate_event_coverage()`](file:///home/purab/Purab/Projects/TESS-Light-curve/src/tess_benchmark/evaluation/recovery.py#L203-L339) in `src/tess_benchmark/evaluation/recovery.py`.
- **Interval Integration**: Continuous-interval Lebesgue exposure measure is implemented:
  ```python
  exp_starts = time_clean - 0.5 * t_exp_days
  exp_ends = time_clean + 0.5 * t_exp_days
  inter_starts = np.maximum(exp_starts, w_start)
  inter_ends = np.minimum(exp_ends, w_end)
  lengths = np.maximum(0.0, inter_ends - inter_starts)
  lebesgue_days = float(np.sum(lengths))
  temporal_frac = min(1.0, float(lebesgue_days / t_dur_days))
  ```
- **Loader Approximation**: `src/tess_benchmark/data/tess_loader.py` lines 451–455 still contains a legacy discrete-cadence approximation in `calculate_transit_overlap()` (`cadence_count >= max(1, int(duration_hours * 30 * 0.7))`). This is documented as preliminary ingestion QA and is decoupled from the formal Lebesgue event coverage evaluation in `recovery.py`.
- **Event Classification**:
  - *Primary interior*: $w_{\text{start}} \ge t_{\text{base,min}}$ and $w_{\text{end}} \le t_{\text{base,max}}$ with $f_{\text{temporal}} \ge 0.50$ and $N_{\text{valid}} \ge 5$ (`is_adequate_interior = True`).
  - *Secondary boundary diagnostic*: boundary-truncated events ($w_{\text{start}} < t_{\text{base,min}}$ or $w_{\text{end}} > t_{\text{base,max}}$) with $f_{\text{temporal}} \ge 0.30$ and $N_{\text{valid}} \ge 3$ (`is_adequate_boundary = True`).
  - *Exclusion logging*: Any event failing adequacy records explicit exclusion reasons.

### 5.2 Formal Runner Integration Status
- **Finding**: While `evaluate_event_coverage()` is implemented and tested in `tests/test_recovery.py` (6 unit tests), it is **NOT** invoked anywhere in the active benchmark runners (`scripts/run_stage3_exploratory.py` or `scripts/run_bls_benchmark.py`).
- Benchmark counts do **not** yet separate or report $N_{\text{primary\_adequate}}$, $N_{\text{boundary\_adequate}}$, or $N_{\text{boundary\_recovered}}$.
- **GATE-03 Status**: **BLOCKED** for formal execution until integrated into the formal benchmark runner.

---

## 6. GATE-12 Implementation Audit

### 6.1 Scoring Engine Implementation
- **Implementation Location**: [`RealDataBenchmarkScorer`](file:///home/purab/Purab/Projects/TESS-Light-curve/src/tess_benchmark/evaluation/recovery.py#L342-L556) in `src/tess_benchmark/evaluation/recovery.py`.
- **Tolerance Formula**: Bounded composite tolerance (GATE-12 Option C):
  $$\Delta t_{0,\text{tol}} = \min\left(0.50 T_{\text{dur}}, \sqrt{(0.25 T_{\text{dur}})^2 + (3 \sigma_{t_{\text{mid}}})^2}\right)$$
- **Phase Folding**: Implements circular phase distance $\Delta \phi \in [0, 0.5]$ via modular wrapping in `compute_circular_epoch_residual()`.
- **Candidate-to-Catalog Matching**: Implements greedy one-to-one matching (`match_candidates_one_to_one()`) preventing a single candidate from recovering multiple planets or multiple candidates from claiming a single planet.
- **Input Guards**: Robust handling of non-finite/NaN values, zero/negative periods, and non-physical durations.

### 6.2 Formal Scoring Path Trace
- **Runner Inspection**: Tracing `scripts/run_stage3_exploratory.py` lines 198–209:
  ```python
  if is_host and catalog_period is not None and catalog_period > 0:
      rec, harmonic, rel_err = match_period_to_harmonics(
          detected_period=bls_res.best_period,
          catalog_period=catalog_period,
          accepted_ratios=(0.5, 1.0, 2.0),
          tolerance=0.01
      )
  ```
- **Finding**: The active runner directly invokes `match_period_to_harmonics()`, evaluating **period-only recovery**. `RealDataBenchmarkScorer` is **not** imported or called in any benchmark execution script.
- **GATE-12 Status**: **BLOCKED** for formal execution until `RealDataBenchmarkScorer` is wired into the formal runner.

---

## 7. GATE-09 Frequency-Grid Serialization Audit

- **Grid Construction**: Astropy adaptive `BoxLeastSquares.autopower()` with `frequency_factor=5.0`, $P \in [0.5, 15.0]\text{ days}$ clamped to $0.95 \times T_{\text{base}}$, and trial duration grid `[0.04, 0.35]` days (1.0 h to 8.4 h).
- **Determinism**: The frequency grid construction in Astropy is deterministic given identical time stamps and duration parameters.
- **Serialization Requirement**: `configs/real_benchmark_protocol.yaml` lines 128–132 mandates:
  ```yaml
  runtime_reproducibility:
    record_installed_version: true
    export_environment_lockfile: true
    serialize_frequency_grid: true
    log_api_arguments: true
  ```
- **Code Inspection**: In [`src/tess_benchmark/baselines/bls.py#L240-L310`](file:///home/purab/Purab/Projects/TESS-Light-curve/src/tess_benchmark/baselines/bls.py#L240-L310), `periodogram = model.autopower(...)` computes the grid in memory. `BLSResult.metadata` records cadences, in-transit count, target ID, and SDE diagnostics, but **does not serialize the generated frequency grid array to disk or record exact grid sample counts**.
- **GATE-09 Status**: **BLOCKED / PENDING** until explicit grid array serialization or exact reconstruction array logging is integrated into the runner.

---

## 8. Test Inventory & Actual Test Status

### 8.1 Environmental Root Cause of Previous Exclusions
In previous sessions, running `pytest` failed or excluded `test_models.py`, `test_utils.py`, and `test_stage3_exploratory.py`. Forensic investigation revealed:
1. **System PYTHONPATH Pollution**: The host environment exported ROS paths (`/opt/ros/lyrical/lib/python3.14/site-packages`). Ambient pytest loaded `launch_testing_ros_pytest_entrypoint.py`, triggering `PluginValidationError: unknown hook 'pytest_launch_collect_makemodule'`.
2. **Virtual Environment Decoupling**: PyTorch (`torch==2.14.0+cu130`) is installed in the project `.venv` (`Python 3.11.15`), but absent from system Python (`Python 3.14`).

Invoking `.venv/bin/pytest` with a clean `PYTHONPATH=src` completely resolves collection errors without modifying global packages.

### 8.2 Full Pytest Suite Execution
- **Command**: `PYTHONPATH=src .venv/bin/pytest tests/ -o addopts="-v"`
- **Result**: **109 passed** in 10.52s. **0 failures, 0 errors, 0 collection issues.**

#### Complete Test Breakdown by File:
| Test File | Passed Tests | Description / Coverage Area |
| :--- | :---: | :--- |
| `tests/test_bls.py` | 5 | BLS detection, pure-noise rejection, harmonics, tolerance, insufficient data |
| `tests/test_features.py` | 4 | Phase folding, binning, tabular feature extractor, phase vector extractor |
| `tests/test_gate_04_harmonics.py` | 7 | GATE-04 harmonic ratios, narrow vs broad set, boundary/tolerance tests |
| `tests/test_loader.py` | 2 | Light curve invariants, loader initialization |
| `tests/test_metrics.py` | 4 | Confusion matrix, perfect/mixed/negative metrics, serialization |
| `tests/test_models.py` | 2 | Random forest, gradient boosting, and 1D CNN training/prediction interfaces |
| `tests/test_preprocessing.py` | 3 | Sigma-clipping, running median detrending, preprocessing pipeline |
| `tests/test_real_tess_loader.py` | 10 | Real FITS ingestion, column checks, QA masks, transit overlap |
| `tests/test_recovery.py` | 24 | GATE-03 event coverage (Lebesgue measure, interior vs boundary), GATE-12 epoch tolerance, circular phase, one-to-one matching |
| `tests/test_robustness.py` | 4 | White noise robustness, red noise injection, extreme outlier stability |
| `tests/test_sde.py` | 9 | GATE-11 SDE methods (Options A, B, C, D), alias masking, MAD zero fallback |
| `tests/test_splitting.py` | 3 | Disjoint train/test split, stratified split, leakage guards |
| `tests/test_stage1_feasibility.py` | 5 | Pilot reproducibility, blind execution, air-gap integrity |
| `tests/test_stage2_acquisition.py` | 10 | Stage 2 candidate selection, MAST queries, manifest generation |
| `tests/test_stage3_exploratory.py` | 5 | Exploratory benchmark execution, manifest validation, score format |
| `tests/test_synthetic.py` | 8 | Synthetic injection generation, transit geometry, noise models |
| `tests/test_utils.py` | 4 | Utility helpers, array operations, hash computation |
| **Total** | **109** | **Full Project Test Suite** |

---

## 9. Experiment 2 Verification (Evidence Only)

Direct verification of `results/experiment_2_sde_comparison/experiment_2_sde_paired_predictions.csv` across all $N=110$ evaluated stars ($N=100$ Stage 2 validated cohort, $N=10$ Sector 1 pilot):

### 9.1 Summary Statistics by Cohort & SDE Method

#### Stage 2 Validated Cohort ($N = 100$)
| SDE Definition | Background Mean ($\mu$) | Background Dispersion ($\sigma$) | Mean SDE | Std SDE | Median SDE | IQR SDE |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **Option A** | Parametric mean of all finite bins | Parametric standard deviation | **10.6404** | 5.0664 | **9.2988** | 9.0391 |
| **Option B** | Median of all finite bins | Normalized MAD ($1.4826 \times \text{MAD}$) | **50.2375** | 50.6696 | **35.0678** | 66.1391 |
| **Option C** | Median excluding union alias mask $\mathcal{E}$ | Normalized MAD of unmasked bins | **50.6433** | 51.1061 | **35.3805** | 66.9454 |
| **Option D** | Median excluding fundamental peak | Normalized MAD excluding peak | **57.6927** | 59.8784 | **37.8567** | 77.5033 |

#### Sector 1 Pilot Cohort ($N = 10$)
| SDE Definition | Mean SDE | Std SDE | Median SDE | IQR SDE |
| :--- | :---: | :---: | :---: | :---: |
| **Option A** | 11.0378 | 5.8787 | 11.8476 | 11.2954 |
| **Option B** | 63.4438 | 55.7015 | 67.1501 | 95.4181 |
| **Option C** | 63.8754 | 56.0829 | 67.5137 | 96.3733 |
| **Option D** | 70.1374 | 63.5303 | 77.2807 | 103.9747 |

### 9.2 Option B vs Option C Concordance & Diagnostic Robustness
- **B vs C Numerical Agreement ($N=100$)**:
  - Mean Difference ($SDE_C - SDE_B$): **+0.4058**
  - Max Absolute Difference: **2.8304**
  - Mean Relative Percentage Difference: **0.6247%**
  - Pearson Correlation Coefficient: **$r = 0.99998590$**
- **Option C Alias Masking**:
  - Mean Frequency Mask Fraction: **0.005198** ($0.52\%$; range $0.32\% - 0.94\%$)
  - Degenerate SDE Count ($N_{\text{unmasked}} < 50$): **0 / 100**
  - MAD-Zero Count ($\text{MAD} = 0$): **0 / 100**

### 9.3 Critical Scientific Rule on SDE Scaling
- **Observed Scale Differences**: SDE values under Options B, C, and D are $\approx 5\times$ higher than Option A because periodogram power distributions are heavy-tailed. The parametric standard deviation in Option A is inflated by peaks and noise tails, dampening SDE. Normalized MAD reflects the genuine local background noise floor.
- **Threshold Calibration Rule**: **An equivalent threshold between Option A and Options B/C/D cannot be mathematically deduced from the ratio of their aggregate means.** SDE thresholds represent empirical operational operating points.
- **Protocol Stance**: **No SDE method or threshold conversion is selected in this audit.** GATE-11 remains undecided pending explicit researcher choice.

---

## 10. Authoritative Gate Status Reconciliation (G01–G12)

The previous preparation report contained arithmetic discrepancies and shifted gate numbering. The table below provides the authoritative, reconciled status of all twelve gates defined in `configs/real_benchmark_protocol.yaml` and `docs/benchmark_decision_log.md`:

| Gate | Canonical Gate Title | Approved Protocol Definition | Verification Evidence & Implementation State | Reconciled Status | Remaining Blocker / Required Action |
| :---: | :--- | :--- | :--- | :---: | :--- |
| **G01** | Period Matching Tolerance | Option A: Fixed $1.0\%$ relative tolerance ($|P_{\text{det}} - P_{\text{cat}}| / P_{\text{cat}} \le 0.01$) with input guards | Implemented in `match_period_to_harmonics` and `RealDataBenchmarkScorer`. Unit tested with ULP precision guards. | **PASS** | None |
| **G02** | 1D CNN Validation & Probation | Option C: Qualification deferred; probation (`enabled: false`) enforced | YAML sets `enabled: false`. Runner raises error on CNN evaluation. Zero models evaluated. | **PASS** | None |
| **G03** | Event Window Cadence & Coverage | Option 2: Dual Adequacy; Primary interior ($f \ge 0.50, N \ge 5$); Boundary ($f \ge 0.30, N \ge 3$) | `evaluate_event_coverage()` implements Lebesgue measure in `recovery.py`. Tested in 6 unit tests. **Not wired into runner.** | **BLOCKED** | Wire `evaluate_event_coverage()` into benchmark runner and segregate boundary reporting metrics. |
| **G04** | Harmonic Set Definition | Option B: Narrow harmonic set $\{0.5, 1.0, 2.0\}$; fundamental scored separately | Implemented in `match_period_to_harmonics` and `RealDataBenchmarkScorer`. Verified in 7 dedicated unit tests. | **PASS** | None |
| **G05** | Detrending Filter & Normalization | Option 4: Native SPOC PDCSAP with scalar median normalization | Primary pipeline applies scalar median normalization only. Secondary running median in diagnostic ledger. | **PASS** | None |
| **G06** | Multi-Planet System Handling | Option C: Primary benchmark restricted strictly to qualified single-planet hosts | All 50 hosts have `sy_pnum=1`. However, replacement #9 HD 207496 is in **Sector 13** (unapproved sector). Iterative recovery unimplemented. | **UNRESOLVED / BLOCKED** | User decision required: approve Sector 13 or replace HD 207496 with host from approved Sectors 1–6. |
| **G07** | Search Range Boundaries | Option A: $P \in [0.5, 15.0]\text{ days}$ clamped to $0.95 \times T_{\text{base}}$ | Implemented in `BLSDetector.search()` and `BoxLeastSquares.autopower()`. Verified in unit tests. | **PASS** | None |
| **G08** | Production Cohort Size & Role | Option A: Balanced $N=100$ (50 hosts, 50 comparison stars); controls are non-detection | Manifest has 50 hosts and 50 comparison stars satisfying baseline/cadence gates. Controls correctly documented. | **PASS** *(conditional on G06)* | Subject to resolving GATE-06 host sector conflict. |
| **G09** | BLS Frequency Grid Spacing | Option A: Astropy autoperiod with $f_{\text{factor}}=5.0$; version & grid serialization | Autoperiod used with $f_{\text{factor}}=5.0$. `astropy==8.0.1` recorded. **Grid array serialization to disk is missing.** | **BLOCKED / PENDING** | Implement frequency grid array serialization (`serialize_frequency_grid: true`) in BLS search/runner. |
| **G10** | BLS Flux Weighting Model | Option A: Inverse-variance weighting $w_i = 1/\sigma_i^2$ via `dy` | Implemented in `BLSDetector.search()` via `dy=err_arr`. Verified in test suite. | **PASS** | None |
| **G11** | SDE Background Estimation | Stage 1 Option A; Stage 2 Option C conditional on Experiment 2 | Experiment 2 executed ($N=110$). Statistics verified. Method and operational threshold pending user choice. | **AWAITING USER DECISION** | User must select formal SDE method (Option A, B, C, or D) and calibrated decision threshold. |
| **G12** | Epoch Matching & Scoring Engine | Option C: Bounded composite tolerance via circular phase; one-to-one matching | `RealDataBenchmarkScorer` fully implemented in `recovery.py` with 10 unit tests. **Not wired into runner.** | **BLOCKED** | Wire `RealDataBenchmarkScorer` into the formal benchmark runner; runner currently runs period-only scoring. |

### Reconciliation Summary:
- **PASS**: **7** (G01, G02, G04, G05, G07, G08, G10)
- **BLOCKED / UNRESOLVED**: **4** (G03, G06, G09, G12)
- **AWAITING USER DECISION**: **1** (G11)
- **Total**: **12 Gates** (100% accounted for, zero arithmetic discrepancies).

---

## 11. Exact Remaining Blockers

Before the Formal Stage 3 Benchmark can be launched, the following four technical and scientific blockers must be resolved:

1. **BLK-01 (GATE-06 Sector Eligibility)**: Target HD 207496 (TIC 290348383) is observed in Sector 13, which is outside the approved protocol sectors `[1, 2, 3, 4, 5]` and expansion sectors `[2, 5, 6]`.  
   *Required Action*: User must decide whether to amend the protocol to admit Sector 13 or acquire an alternative validated single-planet host from approved Sectors 1–6.
2. **BLK-02 (GATE-11 SDE Selection & Calibration)**: Experiment 2 provides paired numerical evidence across Options A, B, C, and D, but formal production deployment requires selecting the SDE background estimator and defining its calibrated operational threshold.  
   *Required Action*: User must select the formal SDE method (Option A, B, C, or D) and confirm the threshold policy.
3. **BLK-03 (GATE-03 & GATE-12 Runner Integration)**: Event coverage (`evaluate_event_coverage`) and bounded composite epoch matching (`RealDataBenchmarkScorer`) exist and pass all unit tests in `src/tess_benchmark/evaluation/recovery.py`, but are not wired into the benchmark execution loop. Active scripts still execute period-only matching.  
   *Required Action*: Integrate `evaluate_event_coverage()` and `RealDataBenchmarkScorer` into the formal Stage 3 benchmark runner.
4. **BLK-04 (GATE-09 Grid Serialization)**: The BLS search does not yet serialize the computed frequency grid array to persistent disk.  
   *Required Action*: Serialize the frequency array to disk and export argument dictionaries during formal execution.

---

## 12. Scientific Integrity Verification

It is explicitly certified that during this evidence audit:
- [x] **No machine learning models were trained.**
- [x] **No detection thresholds were tuned on the real cohort.**
- [x] **Formal Stage 3 benchmark was NOT run.**
- [x] **No approved cohort definitions or eligibility criteria were modified.**
- [x] **No gate definitions were modified or weakened.**
- [x] **The observational control interpretation was preserved strictly as comparison stars (non-detections, not confirmed planet-free negatives).**
- [x] **No real TESS data were used for machine learning training.**
- [x] **No information leakage was introduced.**
- [x] **No files were committed or pushed to Git.**

---

*Report concluded. Repository halted at Pre-Formal Stage 3 Readiness Checkpoint.*
