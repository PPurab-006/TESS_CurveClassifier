# Independent Research-Software Audit Report
**Project**: TESS Transit Detection Benchmark  
**Repository**: `/home/purab/Purab/Projects/TESS-Light-curve`  
**Audit Date**: 2026-09-28  
**Auditor**: Independent Computational Astrophysics & Research-Software Auditor  
**Commit Inspected**: `b9602ad` (Branch: `main`)  
**Overall Verification Status**: **PARTIALLY VERIFIED**

---

## 1. Executive Summary

This independent audit evaluated the implementation, reproducibility, scientific validity, test coverage, and claims of the **TESS Transit Detection Benchmark**. 

The repository provides a clean, well-architected computational framework with strict Python packaging, 34 automated unit and integration tests (90% coverage), modular feature extraction, an Astropy Box Least Squares (BLS) baseline, classical scikit-learn classifiers, a PyTorch 1D CNN, and a star-level group-splitting protocol that prevents star ID leakage.

However, the audit identified **four significant scientific and methodological hazards**:
1. **[CRITICAL] Degenerate All-Positive Classifier in CNN1D**: In the saved model comparison, the 1D CNN predicted positive for 100% of test samples (`TP=4, FP=6, TN=0, FN=0`). While this mechanically yields `Recall = 1.000`, its `Precision` is only `0.400`, `FPR = 1.000`, and `Specificity = 0.000`. Presenting this as a 100% detection rate without disclosing the 100% false alarm rate is scientifically invalid.
2. **[HIGH] Nuisance Variable & Mean Flux Shortcut**: Two-sample Kolmogorov-Smirnov tests revealed that raw flux mean differs significantly ($p = 0.00027$) between positive and negative classes due to uncompensated transit integral attenuation. A classifier trained *strictly on non-transit nuisance metadata* achieves a cross-validated ROC-AUC of **0.78** (75% accuracy), demonstrating that synthetic classes can be partially separated without detecting transit morphology.
3. **[HIGH] Generator Parameter Asymmetry**: In the synthetic benchmark generator script, control stars omitted explicit configuration for `flare_amplitude_scale` and sector gap offsets, falling back to configuration defaults that differed from host stars (repaired in this audit).
4. **[HIGH] Historical BLS Metric Discrepancy**: Historical logs contained conflicting reports claiming either 90% period recovery (2028 ms latency, 100% precision) or 100% period recovery (688 ms latency, 69% precision). The audit reconstructed and verified the true empirical performance: **100% period recovery, 68.97% precision (9 false alarms out of 20 control stars), and 688.7 ms latency per star**.

---

## 2. Verified Repository & Environment Facts

- **Operating System**: Ubuntu 26.04.1 LTS (`x86_64`, Kernel `Linux 7.0.0-34-generic`)
- **Processor**: 13th Gen Intel(R) Core(TM) i5-13500H (16 vCPUs, 12 physical cores)
- **Memory**: 14 GiB physical RAM (4.7 GiB available), 4.0 GiB swap
- **Storage**: 137 GB available on `/dev/nvme0n1p2` (468 GB total)
- **GPU Accelerator**: NVIDIA GeForce RTX 3050 Laptop GPU (4096 MiB VRAM, Driver `595.91.07`, CUDA `13.2`). CUDA bindings verified functional in PyTorch (`torch.cuda.is_available() == True`).
- **Python Runtime**: CPython 3.11.15 in an isolated virtual environment at `.venv/` managed via `uv 0.12.0`.
- **Git State**: Clean working tree on commit `b9602ad`.
- **Installed Key Libraries**:
  - `astropy == 8.0.1`
  - `lightkurve == 2.5.1`
  - `astroquery == 0.4.11`
  - `torch == 2.14.0+cu130`
  - `scikit-learn == 1.9.1`
  - `scipy == 1.17.1`
  - `numpy == 2.4.6`
  - `pandas == 3.0.6`
  - `pytest == 9.1.1`
  - `pytest-cov == 7.1.0`

---

## 3. Exact Tests & Commands Executed

### 3.1 Automated Test Suite
- **Command**:
  ```bash
  PYTHONPATH= .venv/bin/pytest tests/ -v --cov=tess_benchmark --cov-report=term-missing
  ```
- **Exit Code**: `0`
- **Results**: **34 passed in 6.90s, 0 failed, 0 warnings, 90% code coverage**.
- **Log File**: `results/audit/test_results.txt`

### 3.2 Environment Variable Conflict Finding
When executed as `pytest tests/` without clearing `PYTHONPATH`, the command fails with exit code `1` or `3` due to system ROS 2 Lyrical environment variables exporting `/opt/ros/lyrical/lib/python3.14/site-packages` into Python's module search path. PyTest attempts to load `launch_testing` entrypoints from Python 3.14, raising `ModuleNotFoundError: No module named 'osrf_pycommon'`.
**Remediation**: Running with `PYTHONPATH= ...` or ensuring virtual environment activation isolates the execution cleanly.

---

## 4. Scientific Validity Findings (Ranked by Severity)

### Finding 1: Degenerate All-Positive Prediction by CNN1D on Test Partition
- **Severity**: **CRITICAL**
- **Affected File & Artifact**: `src/tess_benchmark/models/cnn1d.py` (`CNN1DClassifier.predict()`) & `results/metrics/model_comparison.json`
- **Evidence**:
  ```json
  {
    "model_name": "CNN1D",
    "precision": 0.4,
    "recall": 1.0,
    "f1": 0.5714285714285715,
    "specificity": 0.0,
    "fpr": 1.0,
    "tp": 4,
    "fp": 6,
    "tn": 0,
    "fn": 0
  }
  ```
- **Scientific Impact**: On the 10-star test set (4 transiting hosts, 6 control stars), the model predicted positive for all 10 stars. While `Recall = 1.000` is technically computed by $4/(4+0)$, the classifier has zero discriminative capacity on this split, falsely identifying 100% of quiet stars as transits. Presenting this as "100% detection rate" in executive summaries without highlighting `FPR = 1.000` misrepresents the model's actual utility.
- **Root Cause**: Training a 1D CNN on only 30 light curves for 25 epochs with batch size 32 provides only 25 optimization steps. The network weights do not converge to separate the classes, and the decision threshold calibration collapses to the lower boundary.
- **Correction**: Disclose specificity and FPR in all metric tables; expand the CNN training dataset to $\ge 500$ light curves.

### Finding 2: Nuisance Variable & Mean Flux Shortcut in Synthetic Suite
- **Severity**: **HIGH**
- **Affected File & Artifact**: `src/tess_benchmark/data/synthetic.py` & `results/audit/shortcut_diagnostics.json`
- **Evidence**:
  The diagnostic script `scripts/audit_shortcut_diagnostics.py` trained a Logistic Regression model using *only* 8 non-transit nuisance features (cadence length, missingness fraction, raw flux mean, raw flux median, estimated noise).
  - Two-sample Kolmogorov-Smirnov test on `raw_mean`: $\text{KS statistic} = 0.65$, $p\text{-value} = 0.00027$.
  - 5-fold cross-validated ROC-AUC of nuisance-only classifier: **0.78** (accuracy: **75.0%**).
- **Scientific Impact**: Injected transit dips reduce the total integrated flux below 1.0 ($0.99988$ vs $1.00008$). A linear model can predict transit presence with 75% accuracy simply by measuring whether the un-normalized flux integral is slightly depressed, bypassing the need to learn transit periodicity or box morphology.
- **Correction**: Apply median/mean re-normalization to both classes *after* transit injection to ensure the background flux integral is statistically indistinguishable between classes.

### Finding 3: Generator Parameter Asymmetry Between Classes
- **Severity**: **HIGH**
- **Affected File**: `scripts/generate_synthetic_benchmark.py` (lines 80-110)
- **Evidence**:
  In `generate_synthetic_benchmark.py`, the transit host loop explicitly set `flare_amplitude_scale = 6.0` and `sector_gap_start = 13.1`. The control star loop omitted these keyword arguments, causing control stars to default to `flare_amplitude_scale = 8.0` and `sector_gap_start = 13.2`.
- **Scientific Impact**: Control stars experienced systematically higher flare amplitudes ($8\sigma$ vs $6\sigma$) and shifted downlink gap windows, introducing non-astrophysical discriminants between classes.
- **Correction Applied**: Repaired in `scripts/generate_synthetic_benchmark.py` during the audit to guarantee identical background parameter distributions across both classes.

### Finding 4: Small Test Sample Size Masking True Generalization Variance
- **Severity**: **MEDIUM**
- **Affected Files**: `scripts/train_evaluate_models.py` & `results/metrics/model_comparison.csv`
- **Evidence**: The benchmark dataset contains 40 stars. With a 75/25 group split, the test partition contains exactly 10 stars (4 transits, 6 controls).
- **Scientific Impact**: Perfect metrics ($F_1 = 1.000$) for Logistic Regression, Random Forest, Gradient Boosting, and SVM reflect the small test sample size. In a 4-positive test set, a single misclassification changes recall by $25\%$.
- **Correction**: Increase synthetic validation suite size to $N \ge 200\text{--}500$ stars to compute statistically meaningful confidence intervals.

---

## 5. Leakage & Shortcut Analysis

| Audit Check | Status | Verification Detail |
| :--- | :---: | :--- |
| **Star-Level Group Isolation** | **VERIFIED** | `StarGroupSplitter` strictly isolates stars by `target_id`. Evaluated: `len(set(train_stars) & set(test_stars)) == 0`. Test `test_star_group_split_raises_on_leakage` confirms `DataLeakageError` is raised if star overlap occurs. |
| **Feature Label Leakage** | **VERIFIED** | Feature extraction in `src/tess_benchmark/features/extractors.py` strictly uses photometric time series (`cleaned.time`, `cleaned.flux`). Ground-truth labels and star IDs are not accessed during feature computation. |
| **Preprocessing Isolation** | **VERIFIED** | `StandardScaler` is wrapped inside `sklearn.pipeline.Pipeline` and fitted exclusively on training fold features. |
| **Nuisance Variable Leakage** | **FLAGGED (HIGH)** | Raw flux mean differs between classes ($p = 0.00027$) due to un-normalized transit integral attenuation, yielding an artificial 75% accuracy shortcut. |

---

## 6. BLS Metric & Runtime Discrepancy Reconciliation

A dedicated audit script recomputed the BLS baseline on the exact saved dataset `data/processed/synthetic_light_curves.pkl`.

```text
Actual Recomputed Metrics:
- True Positives: 20
- False Positives: 9
- True Negatives: 11
- False Negatives: 0
- Recall: 100.0%
- Precision: 68.97%
- F1-Score: 0.8163
- Period Recovery Rate: 100.0%
- Average Search Latency: 688.7 ms / star
```

### Discrepancy Explanation:
1. **The 90% vs 100% Period Recovery**: Historical logs contained an intermediate progress message claiming `Period Recovery: 90.0%` with `Precision: 1.000`. That intermediate log was premature. When the full 40 light curves finished processing, all 20 transiting stars had their periods recovered at the fundamental or a standard harmonic ($P, 0.5P, 2P$) within 3% tolerance.
2. **The 100% vs 68.97% Precision**: The true BLS precision is **68.97%** because 9 out of 20 control stars triggered false positive detections ($\text{SDE} \ge 6.0$, $\text{SNR} \ge 5.0$). This is an expected astrophysical result: quasi-periodic stellar rotation mimics box-like dips in classical BLS periodograms when unaccompanied by vetting tests.
3. **Runtime**: Total execution time was 27.55 seconds across 40 stars (**688.7 ms per star**), refuting the historical ~2000 ms figure.
*Full mathematical analysis is recorded in `results/audit/bls_consistency_report.md`.*

---

## 7. Real TESS Data Status

- **Classification**: **NO REAL OBSERVATIONS PRESENT**
- **Evidence**:
  1. `data/raw/` contains only `.gitkeep`.
  2. No TESS FITS products or sector downloads exist in the repository.
  3. No models have been trained or evaluated on real space-telescope photometry.
- **Architectural Status**:
  The interface for real data acquisition is implemented (`TESSDataLoader` in `src/tess_benchmark/data/tess_loader.py`) and the protocol is documented (`docs/dataset_protocol.md`), but execution remains restricted to synthetic data in accordance with Phase 9 instructions.

---

## 8. Claims Status

### 8.1 Claims Currently Supported by Verified Evidence
- [x] Classical BLS achieves high sensitivity (100% recall on high-SNR transits) and accurately recovers orbital periods.
- [x] Classical BLS suffers from elevated false alarm rates ($FPR = 45\%$) in the presence of quasi-periodic stellar variability.
- [x] Supervised feature-based machine learning (Random Forest, Gradient Boosting, SVM) achieves orders-of-magnitude faster inference ($0.03\text{--}2.4\text{ ms/star}$) than BLS grid search ($688\text{ ms/star}$).
- [x] StarGroupSplitter strictly eliminates star-level data leakage.

### 8.2 Claims NOT Supported / Premature
- [ ] *"1D CNN achieves 100% recall"* — **Unsupported as a performance claim**: The CNN predicted positive for all samples, producing a 100% false positive rate on control stars.
- [ ] *"Supervised models achieve F1 = 1.000 in transit detection"* — **Unsupported for real-world operations**: Tested only on 10 synthetic stars with pronounced, un-blended dips.
- [ ] *"TESS transit detection benchmark validated on space mission observations"* — **Unsupported**: Zero real TESS observations have been evaluated.

---

## 9. Prioritized Next Steps

1. **Re-Normalize Synthetic Baseline Flux (Immediate)**: Update `generate_synthetic_light_curve` to re-normalize flux by its median after transit injection, eliminating the `raw_mean` nuisance shortcut ($p = 0.00027$).
2. **Fix CNN Training Regime & Disclose Specificity (Immediate)**: Increase CNN training epochs, implement cosine annealing learning rates, train on at least 200 stars, and explicitly report specificity and false positive rate alongside recall.
3. **Expand Synthetic Benchmark Sample Size**: Increase benchmark size from 40 to 200–500 stars to reduce binomial test set uncertainty.
4. **Initiate Curated Real TESS Pilot Cohort (Next Milestone)**: Download a verified pilot set of 25 confirmed exoplanet hosts (e.g., TOI-700, WASP-126) and 25 control stars from TESS Sector 1 via `TESSDataLoader` to evaluate real-world domain transfer.
