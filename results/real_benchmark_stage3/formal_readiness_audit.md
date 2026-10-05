# Formal Stage 3 Readiness Audit: TESS Transit Detection Benchmark

**Date**: 2026-10-03  
**Auditor**: Lead Research Agent  
**Repository**: `/home/purab/Purab/Projects/TESS-Light-curve`  
**Git Branch**: `main`  
**Commit SHA**: `fc795a71391129ae59219fb52e88b9a967fd4ca8`  
**Protocol References**:
- `docs/real_data_benchmark_protocol.md` (Version 1.3.2)
- `docs/benchmark_decision_log.md` (Version 1.3.3)
- `configs/real_benchmark_protocol.yaml` (Version 1.3.2)
- `docs/protocol_gate_decision_worksheet_v1_3_2.md`

---

## 1. Executive Summary & Readiness Verdict

### **Readiness Verdict: FORMAL BENCHMARK EXECUTION BLOCKED**

A comprehensive pre-execution audit of the repository state, protocol decision gates, data splits, and scoring implementation was conducted prior to launching formal Stage 3 real-data benchmarking.

The audit identified **four material blockers** that preclude immediate execution of the formal benchmark without compromising protocol fidelity or substituting unvalidated heuristics for approved gates:

1. **GATE-06 Cohort Purity Violation (9 Multi-Planet Systems)**: The validated cohort contains 9 host systems with `sy_pnum > 1` in the NASA Exoplanet Archive (admitted via TOI table candidate-row `pl_pnum=1`). GATE-06 mandates that the primary benchmark cohort consist strictly of single-planet hosts. While 5 qualified single-planet host replacements already exist locally in `results/real_data_stage2/stage2_expansion_validated.csv`, 4 additional single-planet hosts would need to be acquired to complete a 50-star single-planet primary cohort, or the user must formally approve admitting the 9 systems into an approved segregated fallback cohort.
2. **GATE-12 Formal Scoring Gap (Epoch/Phase Matching Unimplemented)**: Approved GATE-12 Option C specifies bounded composite epoch matching ($\Delta t_{0,\text{tol}} = \min(0.50 T_{\text{dur}}, \sqrt{(0.25 T_{\text{dur}})^2 + (3 \sigma_{t_{\text{mid}}})^2})$) via circular phase distance. The current codebase only implements period matching (`match_period_to_harmonics`). Substituting period recovery for full orbit recovery is explicitly prohibited by protocol.
3. **GATE-11 Production Method Prerequisite Unmet (Experiment 2 Unexecuted)**: Option C (alias-aware union mask $\mathcal{E}$ + robust normalized MAD) was approved as the Stage 2/3 production candidate *strictly conditional on Experiment 2 comparison*. Experiment 2 has not been conducted. The current code implements Stage 1 baseline Option A. Formal sign-off is required to either promote Option C via Experiment 2 or authorize Option A for formal Stage 3.
4. **GATE-03 Event-Level Coverage Hierarchy Unimplemented**: Primary interior event coverage ($f_{\text{temporal}} \ge 0.50, N_{\text{valid}} \ge 5$) and secondary boundary diagnostic event tracking are not implemented in the Stage 3 benchmark scoring layer.

Per explicit protocol mandate, **formal benchmark execution is paused at this readiness checkpoint**, and no changes to cohort membership, source data, or protocol decisions have been made.

---

## 2. Decision Gate Compliance Audit

| Gate | Protocol Parameter | Approved Decision & Options | Current Implementation & Evidence | Audit Status | Code / File Reference |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **GATE-01** | Period Matching Tolerance | **Option A**: Fixed $1.0\%$ relative tolerance ($|P_{\text{det}} - P_{\text{true}}| / P_{\text{true}} \le 0.01$). Guards against non-finite or non-positive inputs. | Aligned in code and YAML. Function `match_period_to_harmonics` checks non-finite values, non-positive periods, and empty harmonic lists, applying a narrow 100-ULP machine precision allowance. | **PASS** | [`src/tess_benchmark/baselines/bls.py#L100-L150`](file:///home/purab/Purab/Projects/TESS-Light-curve/src/tess_benchmark/baselines/bls.py#L100-L150)<br>[`configs/real_benchmark_protocol.yaml#L182`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L182) |
| **GATE-02** | 1D CNN Validation Gate & Probation | **Option C**: Formal qualification deferred; 1D CNN retained on conditional probation (`enabled: false`) for real-data benchmark. Reconsideration requires $N \ge 100$ disjoint validation cohort. | `cnn1d_deep_baseline.enabled: false` strictly enforced in YAML. Runner raises `RuntimeError` if CNN execution is attempted. Zero CNN models evaluated in formal benchmark. | **PASS** | [`configs/real_benchmark_protocol.yaml#L168-L179`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L168-L179)<br>[`scripts/run_stage3_exploratory.py#L76-L84`](file:///home/purab/Purab/Projects/TESS-Light-curve/scripts/run_stage3_exploratory.py#L76-L84) |
| **GATE-03** | Event Window Cadence & Temporal Adequacy | **Option 2**: Dual Adequacy. Target baseline $\ge 20.0$ d, usable ratio $\ge 0.80$. Primary event recovery restricted to fully interior events ($f_{\text{temporal}} \ge 0.50, N_{\text{valid}} \ge 5$). Boundary events ($f_{\text{temporal}} \ge 0.30, N_{\text{valid}} \ge 3$) reported in secondary diagnostic track. | Target-level criteria ($R_{\text{usable}} \ge 0.80$, baseline $\ge 20$ d) verified in Stage 2 cohort. However, transit event-level coverage hierarchy and secondary boundary event reporting are **unimplemented** in the Stage 3 benchmark scoring engine. | **BLOCKED** | [`configs/real_benchmark_protocol.yaml#L204-L229`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L204-L229)<br>[`src/tess_benchmark/data/tess_loader.py#L360-L390`](file:///home/purab/Purab/Projects/TESS-Light-curve/src/tess_benchmark/data/tess_loader.py#L360-L390) |
| **GATE-04** | Harmonic Set Definition | **Option B**: Narrow harmonic set $\mathcal{H} = \{0.5, 1.0, 2.0\}$. Fundamental ($r=1.0$) reported separately from harmonics ($0.5, 2.0$). Broad multipliers $\{1/3, 3\}$ rejected. | Implemented in `BLSDetector` and `match_period_to_harmonics`. Verified in regression tests `test_recovery_counts_exact_mathematical_identity`. | **PASS** | [`src/tess_benchmark/baselines/bls.py#L87-L105`](file:///home/purab/Purab/Projects/TESS-Light-curve/src/tess_benchmark/baselines/bls.py#L87-L105)<br>[`tests/test_stage3_exploratory.py#L97-L135`](file:///home/purab/Purab/Projects/TESS-Light-curve/tests/test_stage3_exploratory.py#L97-L135) |
| **GATE-05** | Detrending Filter & Primary Normalization | **Option 4**: Paired evaluation. Primary path uses native SPOC PDCSAP with scalar median normalization only ($F / \text{median}(F)$). No primary filter detrending. Secondary running median ($W=1.25$ d) in segregated diagnostic ledger. | Primary pipeline applies strictly scalar median division; zero filter detrending applied. Detrending validation failure rate discrepancy ($1\%$ vs $2\%$) remains pending filter promotion. | **PASS** | [`configs/real_benchmark_protocol.yaml#L32-L38`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L32-L38)<br>[`src/tess_benchmark/data/tess_loader.py#L220-L245`](file:///home/purab/Purab/Projects/TESS-Light-curve/src/tess_benchmark/data/tess_loader.py#L220-L245) |
| **GATE-06** | Multi-Planet System Handling | **Option C**: Iterative multi-signal recovery. Primary benchmark restricted strictly to qualified single-planet hosts. If $<50$, expand sectors first before admitting fallback. Multi-planet systems strictly segregated. Iterative details pending. | **AUDIT FAILURE**: 9/50 host stars in the validated cohort have `sy_pnum > 1` in NASA Exoplanet Archive (`ps` table). 5 qualified single-planet replacements exist in local expansion cache, but 4 more are missing. Iterative recovery is not implemented in `bls.py`. | **BLOCKED** | [`configs/real_benchmark_protocol.yaml#L98-L115`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L98-L115)<br>[`results/real_data_stage2/stage2_final_cohort_manifest.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_final_cohort_manifest.csv) |
| **GATE-07** | Search Range Boundaries | **Option A**: $P \in [0.5, 15.0]\text{ days}$, clamped to $0.95 \times T_{\text{base}}$. Single-transit cases separate. LHS 3844 b noted as $2\times$ harmonic detection. | Implemented in `BLSDetector` via `min_period=0.5` and `maximum_period=min(15.0, baseline*0.95)`. | **PASS** | [`src/tess_benchmark/baselines/bls.py#L180-L195`](file:///home/purab/Purab/Projects/TESS-Light-curve/src/tess_benchmark/baselines/bls.py#L180-L195)<br>[`configs/real_benchmark_protocol.yaml#L121-L122`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L121-L122) |
| **GATE-08** | Production Cohort Size & Control Role | **Option A**: Target $N=100$ (50 confirmed hosts, 50 observational comparison stars across Sectors 1–5). Controls are non-detection controls (BDR-005), not proven planet-free. | Exactly 100 targets in manifest. Terminology throughout reports avoids calling controls confirmed negatives. Subject to resolving the 9 host systems under GATE-06. | **PASS** | [`configs/real_benchmark_protocol.yaml#L91-L97`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L91-L97)<br>[`results/real_data_stage2/stage2_final_cohort_report.md`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_final_cohort_report.md) |
| **GATE-09** | BLS Frequency Grid Spacing | **Option A**: Astropy `BoxLeastSquares.autoperiod()` adaptive grid with $f_{\text{factor}}=5.0$. Uniform-frequency grid is a secondary sensitivity comparison. Reproducibility recording required. | Primary baseline uses `frequency_factor=5.0`. Installed runtime version `astropy==8.0.1` recorded. Grid serialization script pending formal runner export. | **PASS** | [`configs/real_benchmark_protocol.yaml#L123-L136`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L123-L136)<br>[`src/tess_benchmark/baselines/bls.py#L240-L246`](file:///home/purab/Purab/Projects/TESS-Light-curve/src/tess_benchmark/baselines/bls.py#L240-L246) |
| **GATE-10** | BLS Flux Weighting Model | **Option A**: Inverse-variance weighting ($w_i = 1/\sigma_i^2$) via `dy = flux_err` passed to Astropy BLS. Uniform weighting ($w_i=1$) retained as secondary sensitivity. | Fully implemented in `BLSDetector.search()`, passing `dy=err_arr`. Verified in test suite. | **PASS** | [`src/tess_benchmark/baselines/bls.py#L237`](file:///home/purab/Purab/Projects/TESS-Light-curve/src/tess_benchmark/baselines/bls.py#L237)<br>[`configs/real_benchmark_protocol.yaml#L137`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L137) |
| **GATE-11** | SDE Background Estimation Distribution | **Stage 1 Baseline Option A** (all finite bins); **Stage 2 Candidate Option C** (composite union mask $\mathcal{E}$ + normalized MAD) *strictly conditional on Experiment 2*. | Experiment 2 has not been conducted. Existing code implements Option A. Option C cannot be deployed to formal production without executing and reviewing Experiment 2. | **BLOCKED** | [`docs/benchmark_decision_log.md#L524-L530`](file:///home/purab/Purab/Projects/TESS-Light-curve/docs/benchmark_decision_log.md#L524-L530)<br>[`configs/real_benchmark_protocol.yaml#L138-L146`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L138-L146) |
| **GATE-12** | Epoch Matching Tolerance & Scoring Engine | **Option C**: Bounded composite tolerance $\Delta t_{0,\text{tol}} = \min(0.50 T_{\text{dur}}, \sqrt{(0.25 T_{\text{dur}})^2 + (3 \sigma_{t_{\text{mid}}})^2})$ via circular phase distance; one-to-one matching rule. | **UNIMPLEMENTED**: Codebase has no epoch matching scorer. `RealDataBenchmarkScorer` is documented as pending in protocol. Period-only matching was used in exploratory run, which cannot substitute for formal recovery. | **BLOCKED** | [`configs/real_benchmark_protocol.yaml#L185-L200`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml#L185-L200)<br>[`docs/benchmark_decision_log.md#L553-L557`](file:///home/purab/Purab/Projects/TESS-Light-curve/docs/benchmark_decision_log.md#L553-L557) |

---

## 3. Cohort Composition & Replacement Inventory

### 3.1 Current Stage 2 Cohort Breakdown ($N=100$)
- **Observational Comparison Stars**: Exactly **50 targets** (all $R_{\text{usable}} \ge 0.80$, baseline $\ge 20.0$ d, zero known TOI/exoplanet records; observational non-detections under BDR-005).
- **Verified Single-Planet Hosts (`sy_pnum == 1`)**: **41 targets** verified against the NASA Exoplanet Archive composite parameters (`ps` table).
- **Multi-Planet Hosts (`sy_pnum > 1`)**: **9 targets** selected under the TOI table candidate-row `pl_pnum=1` convention, but possessing multiple confirmed planets:

| TIC ID | Hostname | TOI ID | Verified System Planet Count (`sy_pnum`) | Catalog Period (d) | Sector |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **262530407** | GJ 3090 | TOI-177.01 | 2 | 2.8531 | Sector 2 |
| **189013224** | TOI-426 | TOI-426.01 | 2 | 1.3205 | Sector 5 |
| **92352620** | WASP-94 A | TOI-107.01 | 2 | 3.9502 | Sector 1 |
| **31374837** | TOI-431 | TOI-431.01 | 3 | 12.4610 | Sector 5 |
| **183532609** | WASP-8 | TOI-191.01 | 2 | 8.1587 | Sector 2 |
| **307210830** | L 98-59 | TOI-175.01 | 5 | 3.6907 | Sector 2 |
| **33692729** | TOI-469 | TOI-469.01 | 3 | 13.6308 | Sector 6 |
| **52368076** | TOI-125 | TOI-125.01 | 3 | 4.6517 | Sector 2 |
| **251848941** | TOI-178 | TOI-178.01 | 6 | 6.5579 | Sector 2 |

### 3.2 Inventory of Locally Available Replacement Single-Planet Hosts
A complete audit of all Stage 2 validated artifacts revealed that **5 qualified confirmed single-planet hosts** from Sector 6 were downloaded and validated during the Stage 2 expansion run ([`stage2_expansion_validated.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_expansion_validated.csv)) but excluded when the cohort was capped at 50:

| TIC ID | Hostname | TOI ID | `sy_pnum` (`ps` Table) | Sector | Usable Cadence Ratio ($R_{\text{usable}}$) | Baseline ($T_{\text{base}}$) | Local FITS Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **170102285** | WASP-23 | TOI-467.01 | **1** | Sector 6 | 92.72% | 21.77 d | Present in `data/raw/real_tess_stage2/` |
| **52640302** | WASP-64 | TOI-472.01 | **1** | Sector 6 | 93.19% | 21.77 d | Present in `data/raw/real_tess_stage2/` |
| **306362738** | WASP-49 | TOI-471.01 | **1** | Sector 6 | 93.15% | 21.77 d | Present in `data/raw/real_tess_stage2/` |
| **47911178** | WASP-101 | TOI-465.01 | **1** | Sector 6 | 93.00% | 21.77 d | Present in `data/raw/real_tess_stage2/` |
| **59843967** | HATS-4 | TOI-473.01 | **1** | Sector 6 | 93.16% | 21.77 d | Present in `data/raw/real_tess_stage2/` |

**Acquisition Implication**:
- If all 5 local Sector 6 stars are admitted as single-planet replacements, the single-planet host count increases from **41 to 46**.
- **4 additional single-planet hosts** would still need to be queried from the NASA Exoplanet Archive and MAST (e.g. from cleaner Sectors 6, 7, or 8) and validated through `Stage2CohortManager` to reach the mandated target of **50 qualified single-planet hosts**.
- Alternatively, if the user explicitly authorizes Option C fallback admission, the 9 multi-planet systems can be retained as an official segregated fallback cohort.

---

## 4. Implementation & Data Leakage Audit

### 4.1 Data Leakage Audit
- **Preprocessing Isolation**: Per-star scalar median division ($F / \text{median}(F)$) relies strictly on local cadences. No global or cross-star statistics exist. **Zero leakage.**
- **Feature Extraction Isolation**: The 22 astronomical and statistical features are computed strictly on individual light curves. **Zero leakage.**
- **Training Separation**: The supervised tabular classifiers (`RandomForest`, `HistGradientBoosting`) were trained exclusively on 40 external synthetic light curves (`data/processed/features_tabular.csv`). **Zero authentic TESS data entered training.**
- **Threshold Integrity**: BLS thresholds ($\text{SDE} \ge 6.0, \text{SNR} \ge 5.0$) and ML classification thresholds ($0.50$) were set a priori by protocol. **Zero test-set tuning.**

### 4.2 Code & Scoring Implementation Gaps
1. **GATE-12 Scoring Engine (`RealDataBenchmarkScorer`)**: Unimplemented. Code currently computes period-only recovery via `match_period_to_harmonics()`. Bounded composite epoch matching $\Delta t_{0,\text{tol}}$ is absent.
2. **GATE-11 Robust MAD Background (Option C)**: Unimplemented in `BLSDetector`. Peak exclusion half-width and alias mask $\mathcal{E}$ are not evaluated.
3. **GATE-03 Event Coverage Hierarchy**: Lebesgue continuous temporal integration and boundary-event diagnostic tracking are not implemented.
4. **GATE-06 Iterative Recovery**: `BLSDetector` extracts only the single global maximum power peak. Iterative signal masking or model pre-whitening is not implemented.

---

## 5. Detailed Blocker Analysis & Action Items

| Blocker ID | Affected Gate | Description | Impact on Formal Benchmark | Minimum Required Action |
| :--- | :--- | :--- | :--- | :--- |
| **BLK-01** | **GATE-06** | 9 host systems in validated cohort have `sy_pnum > 1`. | Primary single-planet cohort requirement ($N=50$) not satisfied. | User decision required: (A) Acquire 4 additional single-planet hosts from cleaner sectors and swap all 9 with single-planet stars (using the 5 local + 4 new); OR (B) Formally approve admitting the 9 systems as a segregated multi-planet fallback cohort under GATE-06 Option C. |
| **BLK-02** | **GATE-12** | Formal epoch matching scoring logic unimplemented. | Evaluating formal recovery using period-matching alone violates protocol. | Implement `RealDataBenchmarkScorer` incorporating circular phase distance $\Delta t_0$ and the approved bounded composite tolerance formula before formal scoring. |
| **BLK-03** | **GATE-11** | Experiment 2 unexecuted; Stage 2 Option C unvalidated. | Protocol leaves Stage 2 production SDE background method unresolved. | User decision required: (A) Authorize Option A (parametric mean/std) as the official formal benchmark baseline; OR (B) Execute Experiment 2 to validate Option C before formal Stage 3. |
| **BLK-04** | **GATE-03** | Transit event coverage hierarchy unimplemented in Stage 3 scorer. | Event-level recovery rate ($N_{\text{recovered, interior}} / N_{\text{adequate, interior}}$) cannot be reported. | Implement interior vs boundary event tracking in the benchmark evaluation pipeline. |

---

## 6. Formal Recommendation

Formal Stage 3 benchmark execution **MUST NOT PROCEED** until the user reviews and provides explicit direction on:
1. **Cohort Resolution (GATE-06)**: Authorize either cohort replacement (using the 5 local candidates + acquiring 4 new cleaner-sector single-planet hosts) or formal admission of the 9 systems into a segregated multi-planet fallback cohort.
2. **SDE Background Resolution (GATE-11)**: Authorize proceeding with Stage 1 baseline Option A for formal BLS benchmarking, or mandate executing Experiment 2 first.
3. **Scoring Implementation (GATE-12 & GATE-03)**: Implement the formal scoring engine (`RealDataBenchmarkScorer`) with bounded composite epoch matching and event coverage hierarchy before recording official benchmark figures.

The repository remains in a clean, reproducible state on commit `fc795a71391129ae59219fb52e88b9a967fd4ca8`, with all exploratory artifacts safely preserved in `results/real_benchmark_exploratory/`.
