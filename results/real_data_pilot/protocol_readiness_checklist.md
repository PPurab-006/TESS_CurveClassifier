# Real-Data Benchmark Protocol Readiness Checklist

**Project**: TESS Transit Detection Benchmark  
**Document ID**: `results/real_data_pilot/protocol_readiness_checklist.md`  
**Date**: 2026-09-28  
**Scope**: Implementation Audit and Gap Analysis for Blind Known-Transit Recovery Benchmark  
**Protocol Reference**: `docs/real_data_benchmark_protocol.md` (Version 1.3.2)  
**Status**: **REVISED READINESS AUDIT COMPLETE (VERSION 1.3.2) — GAPS, EVIDENCE & DECISION GATES MAPPED**  

---

## Revision History

| Version | Date | Author | Summary of Changes |
| :--- | :---: | :--- | :--- |
| **v1.0** | 2026-09-28 | Research Group | Initial checklist mapping protocol requirements to code and gaps. |
| **v1.1** | 2026-09-28 | Research Group | Updated mapping for comparison-star rate, CNN dual gate, BLS reproducibility, and detrending lower bound. |
| **v1.2** | 2026-09-28 | Research Group | Refined mapping for BLS duration-dependent frequency grid, circular phase distance, three-tier cadence accounting, and gates GATE-01 through GATE-12. |
| **v1.3** | 2026-09-28 | Research Group | Mapped transit-depth variance $\operatorname{Var}(\delta)$, WLS regression covariance matrix, SDE vs SNR decoupling, general ephemeris variance, BLS grid dimensional terms, five-tier event coverage, detrending attenuation risk, ML candidate-vetting role. |
| **v1.3.1** | 2026-09-28 | Research Group | Consistency Audit & Methodological Reconciliation: Separation of target eligibility from epoch matching; continuous temporal coverage; boundary truncation; detrending subgroup distributions; SDE background options. |
| **v1.3.2** | 2026-09-28 | Research Group | **Comprehensive Scientific Integrity & Reproducibility Audit**: <br>• Mapped covariance cross-term error direction as dependent on $\operatorname{sgn}(E \cdot \operatorname{Cov}(T_0, P))$; prohibited characterizing zero-covariance as universally conservative or underestimating.<br>• Clarified `GATE-12` Option C: $0.25 T_{\text{dur}}$ term is either calibrated detector resolution $\sigma_{\text{det}}$ or scoring convention; $0.50 T_{\text{dur}}$ cap is strictly a scoring convention, NOT a statistical confidence bound.<br>• Defined baseline via exposure boundaries $[t_{\text{base},\min}, t_{\text{base},\max}]$; defined continuous temporal coverage via Lebesgue measure of intersecting exposures; designated categorical exclusion of boundary events as a PROPOSED choice awaiting approval (`GATE-03`).<br>• Mapped detrending validation baseline normalization $C_{\text{out}}$, exact model options (Box, Trapezoid, Limb-Darkened) under `GATE-05`, mandatory $f_{\text{fail}}$ reporting with omnibus and convergent distributions, and edge-affected segregation; kept all thresholds pending.<br>• Mapped Astropy reproducibility: `astropy>=6.0.0` is an inequality dependency constraint, NOT an exact pin; mandated recording runtime version, environment lockfile, API args, and serialized grid array.<br>• Mapped SDE alias exclusion rules (fundamental, harmonics, subharmonics, satellite aliases, composite union mask $\mathcal{E}$, invalid bins, $<50$ degeneracy guard), preserving Options A, B, C, D under `GATE-11`.<br>• Marked all pending defaults as `[PROPOSED]` awaiting approval; explicitly recorded that no empirical validation was performed. |

---

## 1. Executive Readiness Matrix

| Domain | Protocol Mandate (v1.3.2) | Existing Code / Artifact | Implementation Gap | Evidence Needed Before Execution | Readiness Status |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Data Ingestion** | SPOC FITS acquisition, checksumming, metadata tracking | `src/tess_benchmark/data/tess_loader.py` | None for Sector 1 pilot ($N=10$). Expansion to Sectors 1–5 ($N=100$) requires batch download script. | SHA256 verification and byte-level check on all files. | **READY FOR PILOT** / Batch script needed for expansion |
| **Cadence QA** | Quality mask (`QUALITY==0`), NaN/Inf isolation, monotonicity check | `tess_loader.py:load_tess_fits_file()`, `cadence_reconciliation.csv` | None. Reconciled across 10 pilot files with zero double-counting. | Automated test assertion for monotonicity and zero NaN. | **VERIFIED & READY** |
| **Ephemeris Ground Truth** | Accurate $P, T_0, T_{\text{dur}}$, units, BTJD scale; mid-transit verification; target eligibility bound $\sigma_{t_{\text{mid}}} \le 0.25 T_{\text{dur}}$; error direction of omitting $\operatorname{Cov}(T_0, P)$ governed by $\operatorname{sgn}(E \cdot \operatorname{Cov}(T_0, P))$ | `ephemeris_validation.csv`, `target_inventory.csv` | None for pilot cohort. Need verified TOI table ingest with mid-transit and BTJD verification for expanded cohort. | Source-specific transit midpoint and time-scale verification report; $\sigma_{t_{\text{mid}}} \le 0.25 T_{\text{dur}}$ verification. | **VERIFIED & READY** |
| **Ephemeris Air-Gap** | Strip all labels and ephemerides before search algorithms | Existing `scripts/run_bls_benchmark.py` accesses `lc.category` | Need dedicated `BlindLightCurve` dataclass and air-gapped runner script (`scripts/run_blind_benchmark.py`). | Unit test verifying algorithm receives only opaque ID and numeric flux arrays. | **GAP: IMPLEMENTATION REQUIRED** |
| **Classical BLS** | Duration-dependent frequency grid (`GATE-09`), exact API arguments, runtime version & grid serialization mandate (`astropy>=6.0.0` is dependency constraint, not exact pin), formal $\sigma_\delta = \sqrt{\operatorname{Var}(\delta)}$ and $\text{SNR} = \delta / \sigma_\delta$, inverse-variance weighting (`GATE-10`), SDE background specification (`GATE-11`), deterministic tie-breaking | `src/tess_benchmark/baselines/bls.py` (`BLSDetector`) | Need standardized CLI runner recording `astropy.__version__`, environment lockfile, serialized grid array, exact $\sigma_\delta$, SDE alias union mask $\mathcal{E}$, and deterministic tie-breaking. | Automated test verifying grid density, runtime version recording, formal SNR vs SDE decoupling, and runtime profiling. | **GAP: RUNNER & GRID WIRING REQUIRED** |
| **Tabular ML** | Blind feature extraction and model inference as BLS-candidate vetting classifier | `src/tess_benchmark/features/extractors.py`, `models/classical.py` | Need training script on disjoint external dataset (synthetic/out-of-sector). | Feature vector unit test proving zero label access and disjoint training verification. | **GAP: TRAINING SCRIPT NEEDED** |
| **1D CNN** | Deep CNN on phase-folded light curves | `src/tess_benchmark/models/cnn1d.py` | Model on probation due to all-positive collapse. Must satisfy dual gate: Specificity $\ge 0.85$ AND Sensitivity $\ge \text{MIN}$ (`GATE-02`). | Validation test report demonstrating dual gate compliance on independent validation split. | **ON PROBATION — CONDITIONAL GAP** |
| **Scoring Layer** | Decoupled fundamental, harmonic, circular phase epoch alignment under `GATE-12` (Options A, B, C; $0.50 T_{\text{dur}}$ scoring cap), and target-level metrics; Wilson CIs | Evaluator logic in `metrics.py` and `bls.py` | Need unified `RealDataBenchmarkScorer` class implementing decoupled tri-level metrics, circular phase distance, and attrition ledger. | Unit test verifying circular phase distance, confusion matrix, and Wilson CI arithmetic. | **GAP: IMPLEMENTATION REQUIRED** |
| **Event Adequacy** | Five-tier event hierarchy; baseline via exposure boundaries $[t_{\text{base},\min}, t_{\text{base},\max}]$; continuous temporal coverage $f_{\text{temporal}} \in [0, 1]$ via Lebesgue measure; dual adequacy ($f_{\text{temporal}} \ge 50\%$ AND $N_{\text{valid}} \ge 5$); categorical exclusion of boundary events is PROPOSED under `GATE-03` | `calculate_transit_overlap()` in `tess_loader.py` | Need pre-screening manifest generator calculating continuous temporal coverage, evaluating dual adequacy, and tagging boundary truncations. | Manifest logging excluded events prior to search execution. | **GAP: IMPLEMENTATION REQUIRED** |
| **Detrending & Outliers** | Segment-wise detrending ($W=1.25\text{ d}$), edge tagging, pre-detrending flare flagging; synthetic injection validation measuring $R_{\text{depth}}$ via local baseline $C_{\text{out}}$, exact model options (Box, Trapezoid, Limb-Darkened) under `GATE-05`, mandatory $f_{\text{fail}}$ reporting with omnibus and convergent distributions, and edge-affected segregation. Threshold pending under `GATE-05`. | `src/tess_benchmark/features/extractors.py` | Ensure detrending filter operates independently per segment without crossing gaps $> 6\text{ h}$; add edge and flare masks; execute synthetic validation reporting $f_{\text{fail}}$ and subgroup distributions. | Test asserting no interpolation across gaps $> 6\text{ hours}$, raw flux immutability, and synthetic validation report across subgroups. | **GAP: IMPLEMENTATION REQUIRED** |

---

## 2. Detailed Verification and Implementation Mapping

### Requirement 1: Data Ingestion & Quality Cleaning
- **Protocol Mandate**: Load SPOC FITS, retain strictly `QUALITY == 0`, strip non-finite values, verify strictly monotonic timestamps.
- **Existing Implementation**:
  - `tess_loader.py:load_tess_fits_file()`: Reads `PDCSAP_FLUX`, applies `QUALITY == 0` mask, removes NaNs/Infs, sorts by time, checks monotonicity.
  - Pilot artifact: `results/real_data_pilot/cadence_reconciliation.csv` proves 100% finite, monotonic retention with zero duplicates across all 10 pilot files.
- **Missing Implementation**:
  - Batch downloader for Stage 2 ($N=100$), ensuring retry logic, rate limiting, and automated checksum validation.
- **Evidence Required**:
  - Ingestion QA report for any newly acquired files matching the format of `pilot_report.md`.

### Requirement 2: Ephemeris Ground-Truth, Midpoint Verification, and Target Eligibility
- **Protocol Mandate**: Ground truth must include source-specific verification that $T_0$ is the transit midpoint and time standard is $\text{BTJD}$ ($\text{BJD}_{\text{TDB}}$). Target eligibility requires:
  $$\sigma_{t_{\text{mid}}}(E) = \sqrt{\sigma_{T_0}^2 + E^2 \sigma_P^2 + 2 E \operatorname{Cov}(T_0, P)} \le 0.25 \times T_{\text{dur}}$$
  Setting $\operatorname{Cov}(T_0, P) = 0$ omits cross-term $2 E \operatorname{Cov}(T_0, P)$. Since $E$ can be positive ($t_{\text{mid}} > T_0$) or negative ($t_{\text{mid}} < T_0$), the propagated variance error direction depends strictly on $\operatorname{sgn}(E \cdot \operatorname{Cov}(T_0, P))$. If $E \cdot \operatorname{Cov}(T_0, P) > 0$, the zero-covariance approximation underestimates uncertainty; if $< 0$, it overestimates uncertainty. It must NOT be described as universally conservative or underestimating. Target eligibility is strictly separate from detected-epoch matching.
- **Existing Implementation**:
  - `results/real_data_pilot/ephemeris_validation.csv` records verified Sector 1 TOI fits, uncertainties, and predicted window overlaps.
  - `src/tess_benchmark/data/tess_loader.py:calculate_transit_overlap()` propagates $\sigma_P, \sigma_{T_0}$ and counts windows with cadences vs in gaps.
- **Missing Implementation**:
  - Automated eligibility filter script creating `target_eligibility_manifest.csv` before running searches.
- **Evidence Required**:
  - Source-specific mid-transit verification report and pre-registered eligibility manifest signed off before search execution.

### Requirement 3: Strict Ephemeris Air-Gap (Leakage Prevention)
- **Protocol Mandate**: Detection algorithms must not receive catalog period, epoch, duration, depth, host vs control label, or transit window annotations.
- **Existing Implementation**:
  - `BLSDetector.search()` currently accepts `LightCurveData`. While BLS itself does not use `lc.category`, the `LightCurveData` object contains `category`, `known_period`, and `metadata`.
- **Missing Implementation**:
  - Create `tess_benchmark.data.blind.BlindLightCurve`:
    ```python
    @dataclass(frozen=True)
    class BlindLightCurve:
        opaque_id: str
        time: np.ndarray
        flux_norm: np.ndarray
        flux_err_norm: np.ndarray
    ```
  - Create air-gapped runner `scripts/run_blind_benchmark.py` that strips all metadata and outputs a standardized detection results CSV.
- **Evidence Required**:
  - Automated unit test asserting that passing a `BlindLightCurve` with random permutations of opaque IDs produces identical detector results.

### Requirement 4: Classical BLS Baseline Reproducibility & SDE Specification
- **Protocol Mandate**: Run Astropy BLS with duration-dependent frequency grid (`GATE-09`), exact API arguments `BoxLeastSquares.autoperiod(duration, minimum_period=0.5, maximum_period=15.0, frequency_factor=5.0, minimum_n_transit=2)`. Pinned dependency specification `astropy>=6.0.0` is an inequality constraint, NOT an exact version pin; implementation must record runtime `astropy.__version__`, export environment lockfile, and serialize generated frequency grid array to persistent storage (`bls_frequency_grid.npy`). Formal depth variance $\operatorname{Var}(\delta) = (\sum_{\text{in}} w_i)^{-1} + (\sum_{\text{out}} w_j)^{-1}$ with standard error $\sigma_\delta = \sqrt{\operatorname{Var}(\delta)}$ and $\text{SNR} = \delta / \sigma_\delta$, inverse-variance weighting (`GATE-10`), SDE background specification with full composite alias mask $\mathcal{E}$ (`GATE-11`), and deterministic tie-breaking. Oversampling calibration restricted to synthetic injections.
- **Existing Implementation**:
  - `src/tess_benchmark/baselines/bls.py:BLSDetector` supports basic Astropy BLS wrapping.
- **Missing Implementation**:
  - Wire duration-dependent grid construction (`autoperiod`) with explicit parameters.
  - Record runtime `astropy.__version__` and serialize frequency grid array to disk.
  - Ensure $\sigma_\delta$ incorporates the square root and is decoupled from SDE.
  - Implement SDE background exclusion mask $\mathcal{E}$ (Options A, B, C, D pending under `GATE-11`).
  - Implement deterministic tie-breaking (lower period selected on identical power).
  - Add isolated wall-clock runtime profiling around `BLSDetector.search()`.
- **Evidence Required**:
  - Runtime environment lockfile, serialized grid artifact verification, and fixed-grid reproducibility test in `tests/test_bls.py`.

### Requirement 5: Supervised Tabular Machine Learning as BLS-Candidate Vetting
- **Protocol Mandate**: Random Forest and Gradient Boosting evaluated blind on 22-dimensional features as candidate vetting classifiers. Trained strictly on disjoint out-of-sector or synthetic data with zero exposure to benchmark test stars. Direct comparison against BLS as equivalent search tool is prohibited.
- **Existing Implementation**:
  - `src/tess_benchmark/features/extractors.py:extract_features()` extracts 22 blind features.
  - `src/tess_benchmark/models/classical.py:build_classical_models()` instantiates scikit-learn pipelines with calibrated probabilities.
- **Missing Implementation**:
  - Standardized training script `scripts/train_external_benchmark_models.py` that fits models on external/synthetic data and serializes model weights (`models/saved/`).
  - Blind inference runner that loads frozen weights, evaluates `BlindLightCurve`, and outputs prediction CSV.
- **Evidence Required**:
  - Verification that training data contains **zero** stars from the real-data benchmark cohort.

### Requirement 6: 1D CNN Dual Validation Gate on Probation
- **Protocol Mandate**: CNN must not be included in the primary benchmark until it passes the dual validation gate: Specificity $\ge 0.85$ AND Sensitivity $\ge \text{MIN}$ (`GATE-02`) on an independent validation set.
- **Existing Implementation**:
  - `src/tess_benchmark/models/cnn1d.py` implements `TransitCNN1DNet`.
  - Historical output `results/post_audit_repair/model_comparison.csv` documents FPR = 1.0 (all-positive collapse).
- **Missing Implementation**:
  - Remediation branch: Implement focal loss or class-balanced loss, blind candidate phase folding, and threshold calibration.
  - Remediation validation report showing Specificity $\ge 0.85$ and Sensitivity compliance on an independent validation dataset.
- **Evidence Required**:
  - Validation test report verifying non-degenerate predictions before code is merged into the real-data benchmark suite.

### Requirement 7: Decoupled Scoring Layer
- **Protocol Mandate**: Scoring layer evaluates frozen detector predictions against ground truth, computing fundamental-period recovery, harmonic recovery, circular phase epoch alignment under `GATE-12` (Options A, B, C; $0.50 T_{\text{dur}}$ scoring cap), target-level classification metrics, and Wilson score confidence intervals.
- **Existing Implementation**:
  - `src/tess_benchmark/evaluation/metrics.py:compute_metrics()` computes basic classification metrics.
  - `BLSResult.is_period_recovered()` checks basic harmonic ratios.
- **Missing Implementation**:
  - Create `tess_benchmark.evaluation.benchmark_scorer.RealDataBenchmarkScorer` implementing:
    - Exact circular phase distance formula:
      $$\Delta \phi = \left| \left( \left( \frac{t_{0,\text{det}} - t_{\text{mid}, k}}{P_{\text{true}}} + 0.5 \right) \pmod 1 \right) - 0.5 \right|$$
    - Matching condition: $\Delta t_0 = \Delta \phi \cdot P_{\text{true}} \le \Delta t_{0,\text{tol}}$ according to approved GATE-12 option.
    - Propagation of $T_0$ to nearest observed transit midtime $t_{\text{mid}, k}$.
    - Decoupled target-level, fundamental-period, harmonic-period, and event-level evaluation.
    - Separation of comparison-star detection rate from confirmed false positives.
    - Wilson score confidence intervals for binomial metrics.
    - Automated target and event attrition ledger generation.
- **Evidence Required**:
  - Unit tests in `tests/test_benchmark_scorer.py` verifying precision, recall, period recovery, and harmonic matching on synthetic test fixtures.

### Requirement 8: Detrending, Outlier Flagging & Raw Data Immutability
- **Protocol Mandate**: Pre-detrending positive flare flagging ($> 5\sigma_{\text{MAD}}$); raw flux preserved immutably; segment-wise detrending ($W=1.25\text{ d}$) without crossing gaps $> 6\text{ h}$; short segments median-subtracted; edge cadences tagged; synthetic injection validation measuring $R_{\text{depth}} = \hat{\delta}_{\text{post}} / \delta_{\text{inj}}$ using local baseline normalization $C_{\text{out}}$, exact fitting model (Box, Trapezoid, Limb-Darkened) under `GATE-05`, mandatory failure rate reporting ($f_{\text{fail}} = N_{\text{failed}} / N_{\text{total}}$), omnibus and convergent distribution reporting, and segregation of edge-affected transits. All acceptance thresholds remain pending researcher approval under `GATE-05`.
- **Existing Implementation**:
  - `src/tess_benchmark/features/extractors.py` contains basic running median detrending.
- **Missing Implementation**:
  - Segment partitioner splitting by gaps $> 6.0\text{ hours}$.
  - Pre-detrending asymmetric flare flagging creating derived boolean masks.
  - Edge cadence tagging (`edge_affected: bool`).
  - Short-segment handling ($< 1.25\text{ days}$).
  - Synthetic injection validation script verifying depth and SNR preservation across depth, duration, period, and edge subgroups, with formal failure logging.
- **Evidence Required**:
  - Unit tests asserting that raw flux arrays remain bitwise identical before and after preprocessing.
  - Synthetic injection validation report presenting full empirical distributions and failure rates across subgroups.

---

## 3. Pre-Execution Sign-Off Checklist

Before running any benchmark code on real TESS targets, verify that all 12 researcher decision gates have been formally approved:

```
[ ] GATE-01: Period matching tolerance formally approved [AWAITING APPROVAL]
    (Proposed: relative epsilon_P = 1.0%; Alternative: Fourier resolution limit)
[ ] GATE-02: CNN dual validation gate approved [AWAITING APPROVAL]
    (Proposed: Specificity >= 0.85, Sensitivity >= 0.75; Alternative: 0.90 / 0.80)
[ ] GATE-03: Window temporal & cadence adequacy criterion approved [AWAITING APPROVAL]
    (Proposed: f_temporal >= 50% AND N_valid >= 5; categorical exclusion of boundary events)
[ ] GATE-04: Harmonic set definition approved [AWAITING APPROVAL]
    (Proposed: H = {1/3, 1/2, 2, 3}; Alternative: H = {1/2, 2})
[ ] GATE-05: Detrending filter type, fitting model, and acceptance threshold approved [AWAITING APPROVAL]
    (Proposed: Running median W=1.25 d, Box model, candidate R_depth >= 0.95, mandatory f_fail reporting)
[ ] GATE-06: Multi-planet handling policy approved [AWAITING APPROVAL]
    (Proposed: restrict primary cohort to single confirmed hosts)
[ ] GATE-07: Search range boundaries approved [AWAITING APPROVAL]
    (Proposed: P in [0.5, 15.0] days)
[ ] GATE-08: Stage 2 production cohort size approved [AWAITING APPROVAL]
    (Proposed: 50 hosts, 50 comparison stars)
[ ] GATE-09: BLS frequency grid construction method approved [AWAITING APPROVAL]
    (Proposed: adaptive autoperiod with f_factor=5.0; record runtime version, args, and serialized grid)
[ ] GATE-10: BLS flux weighting model approved [AWAITING APPROVAL]
    (Proposed: inverse-variance weighting; Alternative: uniform weighting)
[ ] GATE-11: SDE background distribution method approved [AWAITING APPROVAL]
    (Proposed: Option A unclipped; preserve Options B, C, D with full composite alias mask E)
[ ] GATE-12: Epoch matching tolerance formula approved [AWAITING APPROVAL]
    (Proposed: Option C bounded composite with 0.25*Tdur detector resolution/scoring term and 0.50*Tdur scoring cap)
[ ] EXEC-01: Air-gap wrapper (BlindLightCurve) implemented and verified leak-free.
[ ] EXEC-02: Stage 1 Feasibility Run executed on existing 10 pilot stars with zero threshold tuning.
[ ] EXEC-03: Stage 1 results reviewed and software execution certified bug-free.
[ ] EXEC-04: Pre-screening eligibility manifest generated and frozen before detector execution.
[ ] EXEC-05: Synthetic injection detrending validation completed with distributions reviewed across subgroups.
```

> [!IMPORTANT]
> **Validation Status Notice**: No empirical validation of detection performance or protocol safeguards has been performed. Existing automated unit tests validate software unit correctness only. All 12 researcher decision gates remain strictly `AWAITING RESEARCHER APPROVAL`. Do not begin benchmark execution or model evaluation until gates are formally resolved.
