# Architecture & Methodology Decision Log: TESS Transit Detection Benchmark

This log documents foundational technical, astrophysical, and methodological decisions made during the design and implementation of the benchmark.

---

## ADR-001: Environment & Virtual Environment Management via `uv` and Python 3.11

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: The project required a clean, isolated Python environment with rapid package resolution, PyTorch CUDA GPU support, Astropy, Lightkurve, and scikit-learn.
- **Decision**: Standardize on Python 3.11 (`cpython-3.11.15`) managed through `uv`.
- **Consequences**: Fast virtual environment creation, reproducible lockfiles, seamless CUDA 13.2 bindings for the local NVIDIA GeForce RTX 3050 GPU, and complete isolation from external system libraries (including ROS 2 environment paths).

---

## ADR-002: Star-Level Group Partitioning Invariant

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: In astronomy surveys, target stars are often observed over multiple sectors or degraded under various noise simulations. Naive random train/test splits cause different observations of the same star to populate both training and test sets, leading to severe feature leakage (memorizing stellar rotation, spot configurations, and mean flux).
- **Decision**: Implement `StarGroupSplitter` wrapping `GroupShuffleSplit` and `GroupKFold` keyed on `target_id`. Require strict programmatic verification ($\mathcal{S}_{\text{train}} \cap \mathcal{S}_{\text{test}} = \emptyset$) with runtime exception `DataLeakageError`.
- **Consequences**: Completely eliminates star-level data leakage. Yields realistic, generalizable generalization metrics.

---

## ADR-003: Scientific Policy on Synthetic Light Curves

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: Synthetic data can easily be tuned to generate unrealistically high machine-learning detection accuracies, risking deceptive claims of survey performance.
- **Decision**: Synthetics are designated *strictly* for software pipeline verification, unit testing, and controlled degradation stress testing (measuring how performance declines as noise or gaps increase).
- **Consequences**: Preserves scientific integrity. Prevents misleading claims that synthetic results validate real-world TESS transit detection.

---

## ADR-004: 22-Dimensional Tabular Astrophysical Feature Space

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: Classical supervised models (Logistic Regression, Random Forest, HistGradientBoosting, SVM) require tabular feature representations that encode both periodogram evidence and astrophysical morphology.
- **Decision**: Engineer a 22-dimensional feature vector spanning:
  1. Periodogram evidence: `bls_sde`, `bls_snr`, `bls_period`, `bls_depth`, `bls_duration`, `bls_duty_cycle`, `bls_max_power`.
  2. Statistical distribution: `flux_std`, `flux_skewness`, `flux_kurtosis`, `flux_mad`, `flux_p1`, `flux_p5`, `flux_iqr`, `flux_min`, `flux_depth_robust`.
  3. Dynamics & Autocorrelation: `von_neumann_ratio`, `outlier_fraction_low`, `outlier_fraction_high`.
  4. Astrophysical vetting diagnostics: `folded_transit_depth`, `odd_even_depth_ratio` (eclipsing binary detector), `secondary_eclipse_depth`.
- **Consequences**: Rich, interpretable feature space that equips tree ensembles and linear models to separate genuine transits from stellar activity and eclipsing binaries.

---

## ADR-005: Lightweight 1D CNN Architecture on Phase-Folded Views

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: Deep learning models with millions of parameters easily overfit on small to medium astronomical datasets.
- **Decision**: Implement `TransitCNN1DNet` in PyTorch with 3 convolutional blocks, batch normalization, adaptive pooling, dropout (0.3), and ~15,000 total parameters operating on 200-bin phase-folded profiles.
- **Consequences**: Rapid training (< 2 seconds), low memory footprint, strong resistance to overfitting, and native GPU acceleration when available.

---

## ADR-006: Calibrated Probability Estimation for Support Vector Classifiers

- **Date**: 2026-09-28
- **Status**: Accepted
- **Context**: Scikit-learn 1.9+ deprecated the `probability=True` parameter on `SVC` in favor of `CalibratedClassifierCV`.
- **Decision**: Wrap `SVC(kernel="rbf", class_weight="balanced")` with `CalibratedClassifierCV(ensemble=False)` inside the model pipeline.
- **Consequences**: Future-proof compatibility, zero deprecation warnings, and properly calibrated posterior probabilities for PR-AUC and ROC-AUC computation.
