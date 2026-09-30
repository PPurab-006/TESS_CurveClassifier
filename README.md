# TESS Transit Detection Benchmark

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests: Pytest](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)

A rigorous computational astrophysics benchmark comparing classical signal processing (**Box Least Squares**) against supervised machine learning (**Logistic Regression, Random Forest, Gradient Boosting, SVM, and a compact 1D CNN**) for exoplanet transit detection in TESS (Transiting Exoplanet Survey Satellite) photometric light curves.

---

## 🔬 Research Question

> *"How do classical signal-processing and machine-learning methods compare in detecting planetary transit signals in TESS light curves, particularly under noisy, incomplete, and low-signal-to-noise observational conditions?"*

### Core Objectives:
1. **Classical Baseline**: Evaluate Astropy's Box Least Squares (BLS) transit search algorithm across period recovery accuracy, Signal Detection Efficiency (SDE), and false alarms.
2. **Supervised Machine Learning**: Benchmark Logistic Regression, Random Forest, HistGradientBoosting, and Calibrated Support Vector Machines on a 22-dimensional physical and statistical feature space.
3. **Deep Learning**: Train a lightweight 1D Convolutional Neural Network (~15,000 parameters) on phase-folded flux profiles.
4. **Controlled Robustness Experiments**: Systematically quantify performance decay under increasing Gaussian noise, attenuated transit depths, multi-day observation gaps, and random cadence dropouts.
5. **Leakage Prevention**: Strictly enforce star-level group partitioning (`StarGroupSplitter`) to guarantee zero data leakage between training and testing sets.
6. **Scientific Rigor**: Disentangle transit detection, candidate classification, and exoplanet validation. Synthetic data is used exclusively for software verification and controlled stress testing.

## 📍 Project Status & Milestone Tracking

- **Synthetic Validation Suite (Completed)**: 80 synthetic stellar systems with controlled injection-recovery, 22-D feature extraction, classical ML, and 1D CNN verification.
- **Stage 1 Feasibility Pilot (Completed)**: Verified SPOC PDCSAP loading, scalar median normalization, inverse-variance weighting, and BLS period recovery on 10 Sector 1 targets.
- **Stage 2 Production Cohort Acquisition & Validation (Completed)**:
  - **100 Qualified Targets**: Exactly 50 confirmed single-planet hosts ($P \in [0.5, 15.0]\text{ d}$) and 50 observational comparison stars across TESS Sectors 1, 2, 5, and 6.
  - **Approved Invariant Verification**: All 100 targets strictly satisfy $R_{\text{usable}} \ge 0.80$, $T_{\text{baseline}} \ge 20.0\text{ d}$, strictly increasing timestamps ($\Delta t > 0$, 0 duplicates), zero non-finite cadences, and scalar median normalization ($F / \text{median}(F)$).
  - **Zero Duplicate Stars**: 100 unique TIC IDs across the cohort.
  - **Observational Controls**: Comparison stars are field stars with zero TOI, TCE, or confirmed planet associations in the NASA Exoplanet Archive (observational non-detections, not proven planet-free; BDR-005).
- **Stage 3 Real-Data Benchmarking (Pending)**: No model training, threshold tuning, or BLS detection benchmarking has been run on the production cohort.

---

## 📁 Repository Structure

```text
tess-transit-benchmark/
├── README.md                           # Project overview, quickstart, and benchmark guide
├── pyproject.toml                       # Python package configuration and test settings
├── .gitignore                           # Excludes raw FITS data, checkpoints, and caches
├── configs/
│   ├── default.yaml                     # Global benchmark & model hyperparameters
│   ├── synthetic_benchmark.yaml         # Synthetic validation suite parameters
│   └── real_benchmark_protocol.yaml     # Real-data benchmark protocol & decision records
├── data/
│   ├── raw/                             # Cached TESS FITS files (ignored by git)
│   ├── interim/                         # Intermediate detrended / folded data (ignored by git)
│   └── processed/                       # Processed tabular features and arrays (ignored by git)
├── notebooks/                           # Exploratory astrophysics notebooks
├── src/
│   └── tess_benchmark/
│       ├── __init__.py
│       ├── data/                        # Protocols, schemas, synthetic generator, TESS loader, cohort manager
│       │   ├── protocol.py              # Provenance enums, LightCurveData container
│       │   ├── synthetic.py             # Configurable synthetic light curve generator
│       │   ├── tess_loader.py           # NASA MAST & Exoplanet Archive interface
│       │   └── cohort.py                # Stage 2 candidate selection, acquisition, and validation
│       ├── features/                    # Feature extraction and phase-folding routines
│       │   ├── folding.py               # Phase folding, binning, local/global views
│       │   └── extractors.py            # 22-D tabular physical/statistical feature extractor
│       ├── baselines/                   # Classical signal processing detectors
│       │   └── bls.py                   # Astropy BoxLeastSquares detector with SDE & SNR
│       ├── models/                      # Supervised machine learning algorithms
│       │   ├── classical.py             # Scikit-learn wrappers (LR, RF, GBDT, Calibrated SVM)
│       │   └── cnn1d.py                 # Compact PyTorch 1D CNN for phase sequences
│       ├── evaluation/                  # Group-aware splitting, metrics, robustness suite
│       │   ├── splitting.py             # StarGroupSplitter (strictly isolates stars)
│       │   ├── metrics.py               # Precision, Recall, F1, PR-AUC, ROC-AUC, FPR, Latency
│       │   └── robustness.py            # Controlled degradation transformations
│       └── utils/                       # Reproducibility utilities
│           ├── seed.py                  # Deterministic random seeds (NumPy, PyTorch, Python)
│           ├── logging.py               # Structured logger
│           └── config.py                # YAML configuration parser
├── scripts/
│   ├── generate_synthetic_benchmark.py  # Generates synthetic light curve validation dataset
│   ├── run_bls_benchmark.py             # Executes Astropy BLS baseline benchmark
│   ├── train_evaluate_models.py         # Trains and benchmarks all supervised ML algorithms
│   ├── run_robustness_suite.py          # Runs controlled degradation sweeps (noise, gaps, depth)
│   ├── run_stage1_feasibility.py        # Runs Stage 1 feasibility on Sector 1 pilot
│   └── run_stage2_acquisition.py        # Acquires, validates, and consolidates Stage 2 cohort
├── tests/                               # Comprehensive unit and integration test suite (71 tests)
│   ├── test_synthetic.py
│   ├── test_preprocessing.py
│   ├── test_bls.py
│   ├── test_features.py
│   ├── test_models.py
│   ├── test_metrics.py
│   ├── test_splitting.py
│   ├── test_robustness.py
│   ├── test_utils.py
│   ├── test_loader.py
│   ├── test_stage1_feasibility.py
│   └── test_stage2_acquisition.py
├── results/
│   ├── figures/                         # Diagnostic figures, periodograms, comparison plots
│   ├── metrics/                         # CSV and JSON benchmark results
│   ├── real_data_pilot/                 # Stage 1 pilot artifacts, manifests, and run report
│   └── real_data_stage2/                # Stage 2 production cohort manifests, reports, summaries
└── docs/
    ├── research_plan.md                 # Detailed research questions, hypotheses, roadmap
    ├── real_data_benchmark_protocol.md  # Formal real-data benchmark protocol
    ├── benchmark_decision_log.md        # Protocol decision log (GATE-01 through GATE-12)
    └── protocol_gate_decision_worksheet_v1_3_2.md # Decision brief and options worksheet
```

---

## 🚀 Quickstart & Installation

### 1. Prerequisites
- Python 3.11
- [uv](https://github.com/astral-sh/uv) (recommended) or standard `pip`

### 2. Setup Environment
```bash
# Create virtual environment with Python 3.11
uv venv --python 3.11 .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies and editable benchmark package
uv pip install -e ".[dev]"
```

### 3. Run Test Suite
```bash
env -u PYTHONPATH pytest tests/
```
All 71 tests will execute, verifying synthetic generation, preprocessing, Astropy BLS periodograms, 22-D feature extraction, classical ML models, the PyTorch 1D CNN, group splitting with zero leakage, controlled degradation transformations, and Stage 2 cohort validation invariants.

---

## 📊 Running the Benchmark Suite

### Step 1: Generate Synthetic Validation Suite
```bash
PYTHONPATH= python scripts/generate_synthetic_benchmark.py --n-stars 80
```
Outputs:
- Raw light curves: `data/processed/synthetic_light_curves.pkl`
- 22-D tabular features: `data/processed/features_tabular.csv`
- Phase-folded sequences: `data/processed/phase_vectors.npy`
- Visualization: `results/figures/synthetic_samples.png`

### Step 2: Run Astropy BLS Baseline Benchmark
```bash
PYTHONPATH= python scripts/run_bls_benchmark.py --sde-threshold 6.0
```
Outputs:
- Metrics: `results/metrics/bls_benchmark.json`
- SDE distribution: `results/figures/bls_sde_distribution.png`

### Step 3: Train and Evaluate Supervised Classifiers
```bash
PYTHONPATH= python scripts/train_evaluate_models.py
```
Outputs:
- Metric comparison table: `results/metrics/model_comparison.csv`
- Comparative bar plot: `results/figures/model_comparison.png`

### Step 4: Run Controlled Robustness Degradation Experiments
```bash
PYTHONPATH= python scripts/run_robustness_suite.py
```
Outputs:
- Degradation tables: `results/metrics/robustness_suite.csv`
- Degradation curves (Noise, Depth Scaling, Dropout): `results/figures/robustness_curves.png`

---

## 🛡️ Scientific Integrity & Invariants

1. **Star-Level Group Isolation**: Every target star is keyed by its unique stellar identifier. Multiple observations, sectors, or degraded realizations of the same star are strictly constrained to either training or test partitions—never both.
2. **Synthetic Data Disclaimer**: Synthetic light curves are generated strictly for software verification, unit testing, and controlled stress testing. They are never presented as empirical evidence of real-world survey performance.
3. **Exoplanet Validation Boundary**: Machine learning classifiers are designed for **transit detection and candidate screening**. Planet validation requires statistical false-alarm analysis (e.g. TRICERATOPS, VESPA) and radial velocity / high-resolution imaging confirmation.

---

## 📜 License
This project is licensed under the MIT License - see the LICENSE file for details.
