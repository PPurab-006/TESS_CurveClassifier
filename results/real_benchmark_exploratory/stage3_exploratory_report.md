# Stage 3 Exploratory Benchmark Run Report (Provisional Baselines)

> **IMPORTANT PROTOCOL NOTICE**: This execution is a **BOUNDED, EXPLORATORY / PROVISIONAL** benchmark run.
> It does **NOT** claim formal benchmark qualification or establish model superiority.
> An unresolved protocol issue remains: 9/50 host systems have `sy_pnum > 1` in the NASA Exoplanet Archive,
> having been selected under the TOI-row `pl_pnum=1` convention. GATE-06 strict single-planet-host
> requirements are therefore not fully satisfied. Metrics for single-planet and multi-planet systems
> are strictly segregated below.

## 1. Execution & Provenance Metadata

- **Execution Timestamp (UTC)**: `2026-09-30T18:41:05.461123+00:00`
- **Run Type**: `BOUNDED_EXPLORATORY_PROVISIONAL`
- **Cohort Manifest**: [`results/real_data_stage2/stage2_final_cohort_manifest.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_data_stage2/stage2_final_cohort_manifest.csv)
- **Protocol Configuration**: [`configs/real_benchmark_protocol.yaml`](file:///home/purab/Purab/Projects/TESS-Light-curve/configs/real_benchmark_protocol.yaml)
- **Total Cohort Size**: `100` (50 Confirmed Hosts, 50 Observational Controls)
- **Single-Planet Host Pool**: `41` targets (`sy_pnum == 1`)
- **Multi-Planet Host Pool**: `9` targets (`sy_pnum > 1`, segregated)
- **Random Seed**: `42`
- **Python Version**: `3.11.15`
- **Astropy Version**: `8.0.1`
- **Scikit-Learn Version**: `1.9.1`
- **Total Benchmark Wall-Clock Runtime**: `46.25 s`

## 2. BLS Primary Baseline Detection Results

The Box Least Squares (BLS) baseline was executed strictly according to approved protocol settings:
- Period search range: $P \in [0.5, \min(15.0, 0.95 \times T_{\text{base}})]$ days
- Adaptive frequency grid: `frequency_factor = 5.0` (GATE-09 Option A)
- Weighting: Inverse-variance weighting $w_i = 1 / \sigma_i^2$ via $dy = \sigma_{\text{flux}}$ (GATE-10)
- Thresholds: $\text{SDE} \ge 6.0$, $\text{SNR} \ge 5.0$
- Period matching tolerance: $1.0\%$ relative error (GATE-01 Option A)
- Harmonic policy: Narrow harmonic set $\mathcal{H} = \{0.5, 1.0, 2.0\}$ (GATE-04 Option B)

| Cohort / Subcohort | Sample Size ($N$) | Candidate Detections (SDE$\ge$6, SNR$\ge$5) | Period Recovered (Tol $\le$ 1%) | Fundamental Recovery ($r=1.0$) | Harmonic Recovery ($r \in \{0.5, 2.0\}$) | Median SDE | Median SNR |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Single-Planet Hosts (Strict)** | 41 | 40 (97.6%) | **39 (95.1%)** | 39 (95.1%) | 0 (0.0%) | 15.28 | 89.45 |
| **Multi-Planet Hosts (Segregated)** | 9 | 9 (100.0%) | **7 (77.8%)** | 7 (77.8%) | 0 (0.0%) | 14.19 | 30.44 |
| **All Confirmed Hosts (Omnibus)** | 50 | 49 (98.0%) | **46 (92.0%)** | 46 (92.0%) | 0 (0.0%) | 15.09 | 85.58 |
| **Observational Comparison Stars** | 50 | 25 (50.0%) | N/A (Controls) | N/A | N/A | 6.02 | 9.89 |

- **Total BLS Execution Time**: `44.88 s` (`448.8 ms / target`)

## 3. Segregated Audit of the 9 Multi-Planet Host Systems

The following 9 host stars in the Stage 2 cohort were selected using the TOI-row `pl_pnum=1` convention,
but an audit against the NASA Exoplanet Archive composite parameters (`ps` table) revealed `sy_pnum > 1`:

| TIC ID | Hostname | TOI ID | System Planet Count (`sy_pnum`) | Catalog Period (d) | Detected BLS Period (d) | SDE | SNR | Period Recovery Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 262530407 | GJ 3090 | TOI-177.01 | 2 | 2.8531 | 12.0445 | 9.45 | 30.44 | unrecovered |
| 189013224 | TOI-426 | TOI-426.01 | 2 | 1.3205 | 12.2896 | 6.21 | 89.96 | unrecovered |
| 92352620 | WASP-94 A | TOI-107.01 | 2 | 3.9502 | 3.9502 | 14.90 | 299.65 | fundamental |
| 31374837 | TOI-431 | TOI-431.01 | 3 | 12.4610 | 12.4522 | 16.01 | 65.04 | fundamental |
| 183532609 | WASP-8 | TOI-191.01 | 2 | 8.1587 | 8.1524 | 16.30 | 343.85 | fundamental |
| 307210830 | L 98-59 | TOI-175.01 | 5 | 3.6907 | 3.6917 | 20.83 | 28.62 | fundamental |
| 33692729 | TOI-469 | TOI-469.01 | 3 | 13.6308 | 13.5999 | 11.44 | 29.33 | fundamental |
| 52368076 | TOI-125 | TOI-125.01 | 3 | 4.6517 | 4.6506 | 11.32 | 15.09 | fundamental |
| 251848941 | TOI-178 | TOI-178.01 | 6 | 6.5579 | 6.5559 | 14.19 | 15.92 | fundamental |

## 4. Tabular Machine Learning Candidate Vetting Baselines

Tabular ML models were trained **strictly on external synthetic data** (zero real-target leakage):
- Feature dimension: 22 astronomical, statistical, and periodogram features
- Decision threshold: 0.50 (predefined; zero test tuning)
- Evaluated on all 100 authentic TESS targets

| Model | Train Time (s) | Inference Latency (ms/target) | Single-Planet Host Recall ($N=41$) | Multi-Planet Host Recall ($N=9$) | All Hosts Recall ($N=50$) | Control Rejection Rate ($N=50$) | Control Candidate Flag Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **RandomForest** | 0.128 | 0.49 | 90.2% (37/41) | 55.6% (5/9) | **84.0% (42/50)** | **78.0%** | 22.0% (11/50) |
| **HistGradientBoosting** | 0.045 | 0.02 | 92.7% (38/41) | 77.8% (7/9) | **90.0% (45/50)** | **94.0%** | 6.0% (3/50) |

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
- [x] **Multi-Planet Accountability**: 9 multi-planet systems segregated and explicitly tracked; not silently pooled or concealed.

## 7. Artifact Index

- **BLS Predictions CSV**: [`bls_exploratory_predictions.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_benchmark_exploratory/bls_exploratory_predictions.csv)
- **Tabular ML Predictions CSV**: [`tabular_ml_exploratory_predictions.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_benchmark_exploratory/tabular_ml_exploratory_predictions.csv)
- **Real Cohort Features CSV**: [`real_cohort_tabular_features.csv`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_benchmark_exploratory/real_cohort_tabular_features.csv)
- **Summary JSON**: [`stage3_exploratory_summary.json`](file:///home/purab/Purab/Projects/TESS-Light-curve/results/real_benchmark_exploratory/stage3_exploratory_summary.json)

## 8. Conclusion & Resumption Safety

This exploratory run successfully established authentic real-data baseline metrics for the TESS Transit
Detection Benchmark under zero-leakage conditions. Outputs are safely isolated in `results/real_benchmark_exploratory/`.
The project is fully safe to resume later for formal benchmarking once the GATE-06 multi-planet cohort
decision is formally resolved by the researcher.