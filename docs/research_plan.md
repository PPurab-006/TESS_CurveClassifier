# Research Plan: TESS Transit Detection Benchmark

## 1. Executive Summary & Research Question

**Research Question:**
> *"How do classical signal-processing and machine-learning methods compare in detecting planetary transit signals in TESS light curves, particularly under noisy, incomplete, and low-signal-to-noise observational conditions?"*

The Transiting Exoplanet Survey Satellite (TESS) monitors hundreds of thousands of stars across the sky to detect exoplanetary transits. Classical detection methods rely heavily on the **Box Least Squares (BLS)** periodogram, which cross-correlates photometric time series against periodic box/trapezoid models. While statistically well-grounded for periodic white noise, BLS suffers from computational bottlenecks, sensitivity to stellar variability (spots, flares, pulsations), and elevated false-alarm rates when observational cadences are incomplete or irregular.

Recent advances in machine learning (ML) and 1D Convolutional Neural Networks (CNN) offer complementary strengths: fast inference, learned non-linear morphological representations, and resilience to non-Gaussian systematics. However, rigorous head-to-head comparisons under controlled degradation regimes—with strict star-level grouping to prevent data leakage—are scarce in the literature.

This project delivers a reproducible computational astrophysics benchmark comparing:
1. **Classical Baseline**: Box Least Squares (Astropy implementation).
2. **Supervised Feature-Based ML**:
   - Logistic Regression (L2-regularized linear baseline)
   - Random Forest (ensemble of decision trees)
   - Gradient Boosting (Histogram-based tree boosting)
   - Support Vector Classifier (RBF kernel with calibrated probabilities)
3. **Deep Learning**: Lightweight 1D CNN (~15,000 parameters) trained on phase-folded light curves.

---

## 2. Theoretical Framework & Hypotheses

### Hypothesis 1 (Period Recovery vs. Signal Detection)
*BLS excels at recovering precise orbital periods for high-SNR periodic transits but exhibits steep detection drop-offs and high false-positive rates when transit depth approaches observational noise ($\text{SNR} < 7$).*

### Hypothesis 2 (Morphological Robustness of Feature-Based ML)
*Feature-based ML classifiers that incorporate astrophysical diagnostic features (odd-even transit depth ratios, secondary eclipse depth, Von Neumann ratio, flux skewness) maintain higher precision and lower false-positive rates than BLS in the presence of stellar activity (spots, flares) and eclipsing binary mimics.*

### Hypothesis 3 (Deep Learning Generalization under Data Gaps)
*A compact 1D CNN trained on phase-folded representations demonstrates superior robustness against missing cadences and multi-day observation gaps compared to raw periodograms, provided proper star-level partitioning prevents memorization.*

---

## 3. Project Milestones & Roadmap

| Milestone | Objective | Status | Deliverables |
| :--- | :--- | :--- | :--- |
| **M1: Environment & Foundation** | System audit, repository structure, dependency isolation (`uv`, Python 3.11), CI/test harness | **Complete** | `pyproject.toml`, `.gitignore`, test harness, `src/tess_benchmark` package |
| **M2: Synthetic Validation Suite** | Configurable synthetic light-curve generator with limb darkening, stellar rotation, flares, gaps | **Complete** | `tess_benchmark.data.synthetic`, unit tests |
| **M3: Baseline & Feature Engineering** | Astropy BLS detector, phase folding, 22-dimensional physical and statistical feature extraction | **Complete** | `tess_benchmark.baselines.bls`, `tess_benchmark.features` |
| **M4: Machine Learning Suite** | Classical ML (LR, RF, GBDT, SVM) and compact 1D CNN in PyTorch | **Complete** | `tess_benchmark.models`, `StarGroupSplitter` |
| **M5: Robustness Evaluation Suite** | Controlled degradation suite (noise levels, depth scaling, gap duration, cadence dropouts) | **Complete** | `tess_benchmark.evaluation.robustness`, benchmark runner |
| **M6: Real TESS Observational Pipeline** | Ingestion of NASA MAST SPOC light curves and NASA Exoplanet Archive TOI candidates | **Protocol Defined** | `tess_benchmark.data.tess_loader`, `docs/dataset_protocol.md` |
| **M7: Portfolio & Publication** | Comprehensive benchmark report, comparative figures, ablation studies | **In Progress** | Final research documentation and portfolio artifacts |

---

## 4. Methodological Invariants & Scientific Integrity

1. **Star-Level Group Isolation**: Every target star possesses a unique identifier. All observations, sectors, and degraded variants of a star are strictly assigned to either the training set or the test set—never split across partitions. Overlap is verified algorithmically (`DataLeakageError`).
2. **Synthetic Data Policy**: Synthetic light curves are utilized exclusively for software verification, algorithm sanity testing, and controlled degradation sweeps. Synthetic results are never presented as empirical evidence of real-world TESS detection capability.
3. **No Automated Validation Claims**: Classifiers perform **candidate screening and transit detection**, not exoplanet validation. Rigorous planet validation requires statistical false-positive probability tools (e.g. TRICERATOPS) and radial velocity / high-resolution imaging confirmation.
