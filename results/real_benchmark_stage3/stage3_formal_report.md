# Stage 3 Formal Benchmark Run Report (GATE-11 Option C)

> **FORMAL BENCHMARK EXECUTION**: This execution is the **FORMAL STAGE 3 BENCHMARK** authorized under GATE-11 Option C.
> Cohort: 50 confirmed single-planet hosts (`sy_pnum == 1`) + 50 observational comparison stars (100 unique TICs).
> All gates (G01–G12) enforced without tuning or post-hoc exclusion.

## 1. Execution & Provenance Metadata

- **Execution Timestamp (UTC)**: `2026-10-05T05:44:49.734563+00:00`
- **Run Type**: `FORMAL_STAGE_3_BENCHMARK`
- **SDE Background Method (GATE-11)**: `option_c` (Option C: Peak, harmonic, and alias masked background dispersion)
- **Cohort Manifest**: [`results/real_data_stage2/stage2_corrected_cohort_manifest.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_corrected_cohort_manifest.csv)
- **Protocol Configuration**: [`configs/real_benchmark_protocol.yaml`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml)
- **Total Cohort Size**: `100` (50 Confirmed Hosts, 50 Observational Controls)
- **Single-Planet Host Pool**: `50` targets (`sy_pnum == 1`)
- **Multi-Planet Host Pool**: `0` targets (`sy_pnum > 1`, segregated)
- **Random Seed**: `42`
- **Python Version**: `3.11.15`
- **Astropy Version**: `8.0.1`
- **Scikit-Learn Version**: `1.9.1`
- **Total Benchmark Wall-Clock Runtime**: `47.36 s`

## 2. BLS Primary Baseline Detection Results

The Box Least Squares (BLS) baseline was executed strictly according to approved protocol settings:
- Period search range: $P \in [0.5, \min(15.0, 0.95 \times T_{\text{base}})]$ days
- Adaptive frequency grid: `frequency_factor = 5.0` (GATE-09 Option A)
- Weighting: Inverse-variance weighting $w_i = 1 / \sigma_i^2$ via $dy = \sigma_{\text{flux}}$ (GATE-10)
- SDE Background Dispersion: Option C: Peak, harmonic, and alias masked background dispersion (GATE-11)
- Thresholds: $\text{SDE} \ge 6.0$, $\text{SNR} \ge 5.0$
- Period matching tolerance: $1.0\%$ relative error (GATE-01 Option A)
- Epoch matching tolerance: Bounded composite tolerance $\Delta t_{0,\text{tol}} = \min(0.50 T_{\text{dur}}, \sqrt{(0.25 T_{\text{dur}})^2 + (3 \sigma_{t_{\text{mid}}})^2})$ via circular phase (GATE-12 Option C)
- Harmonic policy: Narrow harmonic set $\mathcal{H} = \{0.5, 1.0, 2.0\}$ (GATE-04 Option B)

| Cohort / Subcohort | Sample Size ($N$) | Candidate Detections (SDE$\ge$6, SNR$\ge$5) | Period Recovered (Tol $\le$ 1%) | Full Recovery ($P + t_0$, GATE-12) | Fundamental Full ($r=1.0$) | Harmonic Full ($r \in \{0.5, 2.0\}$) | Period-Only Match | Median SDE | Median SNR |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Single-Planet Hosts (Strict)** | 50 | 50 (100.0%) | **46 (92.0%)** | **38 (76.0%)** | 38 | 0 | 8 | 71.27 | 91.67 |
| **Multi-Planet Hosts (Segregated)** | 0 | 0 (0.0%) | **0 (0.0%)** | **0 (0.0%)** | 0 | 0 | 0 | 0.00 | 0.00 |
| **All Confirmed Hosts (Omnibus)** | 50 | 50 (100.0%) | **46 (92.0%)** | **38 (76.0%)** | 38 | 0 | 8 | 71.27 | 91.67 |
| **Observational Comparison Stars** | 50 | 45 (90.0%) | N/A (Controls) | N/A | N/A | N/A | N/A | 9.23 | 9.89 |

- **Total BLS Execution Time**: `45.63 s` (`456.3 ms / target`)

### 2.1 GATE-03 Event Coverage Hierarchy (Option 2 Dual Track)

Transit event window coverage was evaluated using continuous Lebesgue interval integration:
- **Total Predicted Events Across Hosts**: `499`
- **Primary Adequate Interior Events** ($f_{\text{temporal}} \ge 0.50, N_{\text{valid}} \ge 5$): `465`
- **Secondary Boundary Diagnostic Events** ($f_{\text{temporal}} \ge 0.30, N_{\text{valid}} \ge 3$): `3`
- **Inadequate / Sparse Events**: `31`
- **Hosts with Primary Adequate Coverage**: `50 / 50` (`100.0%`)

### 2.2 GATE-09 Serialized Frequency Grid Audit

- **Serialization Status**: `SERIALIZED_AND_PERSISTED`
- **Grid Archive File**: [`bls_frequency_grids.npz`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_benchmark_stage3/bls_frequency_grids.npz)
- **Persisted Target Grids**: `100`
- **Oversampling Factor**: `5.0`

## 3. Single-Planet Host Integrity Verification (GATE-06)

All 50 confirmed planet host systems have been verified to have `sy_pnum == 1` in the NASA Exoplanet Archive composite parameters (`ps` table). Exactly 0 multi-planet systems are present in the primary benchmark cohort.


## 4. Tabular Machine Learning Candidate Vetting Baselines

Tabular ML models were trained **strictly on external synthetic data** (zero real-target leakage):
- Feature dimension: 22 astronomical, statistical, and periodogram features
- Decision threshold: 0.50 (predefined; zero test tuning)
- Evaluated on all 100 authentic TESS targets

| Model | Train Time (s) | Inference Latency (ms/target) | Single-Planet Host Recall | Multi-Planet Host Recall | All Hosts Recall | Control Rejection Rate | Control Candidate Flag Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RandomForest** | 0.127 | 0.49 | 90.0% (45/50) | 0.0% (0/1) | 90.0% (45/50) | 74.0% | 26.0% |
| **HistGradientBoosting** | 0.038 | 0.03 | 98.0% (49/50) | 0.0% (0/1) | 98.0% (49/50) | 62.0% | 38.0% |

## 5. Deep Learning (1D CNN) Status

- **Status**: **STRICTLY DISABLED** (`enabled: false`)
- **Protocol Authority**: Approved GATE-02 Option C conditional probation
- **Rationale**: Historical all-positive collapse ($FPR=1.0$) on imbalanced data; formal qualification
  admission gate (specificity $\ge 0.85$, sensitivity $\ge 0.75$) remains deferred pending independent
  validation cohort assembly. Pipeline correctly enforced this gate by withholding CNN execution.

## 6. Leakage & Invariant Audit Checklist

- [x] **Zero Target-Star Leakage**: Preprocessing and normalization ($F / \text{median}(F)$) computed per-star independently.
- [x] **Zero Feature Selection Leakage**: Predefined 22 features extracted without reference to cohort labels.
- [x] **Zero Test Set Tuning**: BLS thresholds (SDE=6.0, SNR=5.0) and ML decision thresholds (0.50) were fixed a priori.
- [x] **Zero Training Contamination**: Supervised classifiers trained exclusively on disjoint synthetic data (`data/processed/features_tabular.csv`).
- [x] **Observational Control Non-Detection**: Controls designated strictly as `control_star` (BDR-005; non-detections, not confirmed planet-free negatives).
- [x] **Multi-Planet Accountability**: Multi-planet systems segregated and explicitly tracked; not silently pooled or concealed.
- [x] **GATE-03 Event Coverage Wire**: Continuous Lebesgue measure evaluated for primary interior and secondary boundary tracks.
- [x] **GATE-12 Bounded Composite Scorer Wire**: Scorer evaluates period, circular epoch residual, and bounded composite tolerance.
- [x] **GATE-09 Frequency Grid Persistence**: Exact frequency arrays serialized to compressed archive.

## 7. Artifact Index

- **BLS Predictions CSV**: [`bls_exploratory_predictions.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_benchmark_stage3/bls_exploratory_predictions.csv)
- **Tabular ML Predictions CSV**: [`tabular_ml_exploratory_predictions.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_benchmark_stage3/tabular_ml_exploratory_predictions.csv)
- **Real Cohort Features CSV**: [`real_cohort_tabular_features.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_benchmark_stage3/real_cohort_tabular_features.csv)
- **BLS Frequency Grids NPZ**: [`bls_frequency_grids.npz`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_benchmark_stage3/bls_frequency_grids.npz)
- **Summary JSON**: [`stage3_exploratory_summary.json`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_benchmark_stage3/stage3_exploratory_summary.json)

## 8. Conclusion & Resumption Safety

This exploratory run successfully established authentic real-data baseline metrics for the TESS Transit
Detection Benchmark under zero-leakage conditions. Outputs are safely isolated in `results/real_benchmark_exploratory/`.
The project is fully safe to resume later for formal benchmarking once the GATE-06 multi-planet cohort
decision is formally resolved by the researcher.