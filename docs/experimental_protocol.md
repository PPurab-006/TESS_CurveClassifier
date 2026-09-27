# Experimental Protocol: TESS Transit Detection Benchmark

## 1. Experimental Overview

This protocol governs the execution of all comparative experiments between classical signal processing and machine learning for transit detection, ensuring absolute reproducibility, zero data leakage, and rigorous statistical benchmarking.

---

## 2. Star-Level Group Isolation Protocol

### 2.1 The Data Leakage Problem in Astronomy
A common failure mode in astronomical machine learning occurs when multiple sectors, multiple observation segments, or synthetic degraded versions of the same target star are split across training and test sets. When this occurs:
- The classifier memorizes specific stellar properties (mean brightness, starspot morphology, rotation harmonics).
- Test set performance appears artificially inflated.
- The model fails to generalize to unseen stellar fields.

### 2.2 Mathematical Specification of Star Grouping
Let the dataset contain $N$ observations $\mathcal{D} = \{(x_i, y_i, s_i)\}_{i=1}^N$, where:
- $x_i \in \mathbb{R}^D$ is the feature vector or photometric sequence.
- $y_i \in \{0, 1\}$ is the binary transit indicator.
- $s_i \in \mathcal{S}$ is the unique stellar identifier (e.g. `TIC-ID` or `SYNTH-ID`).

We partition the set of stars $\mathcal{S}$ into disjoint subsets:
$$\mathcal{S} = \mathcal{S}_{\text{train}} \cup \mathcal{S}_{\text{test}}, \quad \text{such that } \mathcal{S}_{\text{train}} \cap \mathcal{S}_{\text{test}} = \emptyset$$

The sample partitions are defined strictly by star membership:
$$\mathcal{D}_{\text{train}} = \{(x_i, y_i, s_i) \mid s_i \in \mathcal{S}_{\text{train}}\}$$
$$\mathcal{D}_{\text{test}} = \{(x_i, y_i, s_i) \mid s_i \in \mathcal{S}_{\text{test}}\}$$

The benchmark programmatically verifies this invariant using `StarGroupSplitter` and raises `DataLeakageError` if $|\mathcal{S}_{\text{train}} \cap \mathcal{S}_{\text{test}}| > 0$.

---

## 3. Evaluated Models & Algorithms

### 3.1 Classical Baseline: Box Least Squares (BLS)
- **Library**: `astropy.timeseries.BoxLeastSquares`
- **Period Grid**: Search range $[0.5, 15.0]\text{ days}$ with oversampling frequency factor $\nu_{\text{factor}} = 3.0\text{--}4.0$.
- **Duration Grid**: 8 durations spanning $[0.04, 0.35]\text{ days}$ (~1.0 to 8.4 hours).
- **Detection Criterion**:
  $$\text{Detection} = \left(\text{SDE} \ge 6.0\right) \land \left(\text{SNR} \ge 5.0\right) \land \left(\delta_{\text{BLS}} > 0\right)$$
  where $\text{SDE} = \frac{\text{power}_{\max} - \langle \text{power} \rangle}{\sigma_{\text{power}}}$.
- **Period Recovery Criterion**: Detected period $P_{\text{rec}}$ matches true period $P_{\text{true}}$ if:
  $$\min_{k \in \{1, 0.5, 2, 1/3, 3\}} \left| \frac{P_{\text{rec}} - k P_{\text{true}}}{k P_{\text{true}}} \right| \le 0.03$$

### 3.2 Supervised Classical Machine Learning
- **Input**: 22-dimensional physical, periodogram, and statistical feature vector.
- **Preprocessing**: `StandardScaler` fitted exclusively on training set features.
- **Models**:
  1. **Logistic Regression**: $L_2$ penalty, $C = 1.0$, `class_weight="balanced"`.
  2. **Random Forest**: 100 estimators, max depth 8, `min_samples_split=4`, `class_weight="balanced"`.
  3. **Gradient Boosting**: HistGradientBoostingClassifier, max depth 5, `min_samples_leaf=5`, `class_weight="balanced"`.
  4. **Support Vector Machine (SVM)**: RBF kernel, $C=1.0$, probability calibration via `CalibratedClassifierCV(ensemble=False)`.

### 3.3 Deep Learning: Compact 1D CNN
- **Input**: 200-dimensional phase-folded binned flux vector centered on transit epoch $t_0$.
- **Architecture**:
  - Block 1: $\text{Conv1D}(1 \to 16, k=5, p=2) \to \text{BatchNorm1D} \to \text{ReLU} \to \text{MaxPool1D}(2)$
  - Block 2: $\text{Conv1D}(16 \to 32, k=5, p=2) \to \text{BatchNorm1D} \to \text{ReLU} \to \text{MaxPool1D}(2)$
  - Block 3: $\text{Conv1D}(32 \to 64, k=3, p=1) \to \text{BatchNorm1D} \to \text{ReLU} \to \text{AdaptiveAvgPool1D}(1)$
  - Fully Connected: $\text{Dropout}(0.3) \to \text{Linear}(64 \to 32) \to \text{ReLU} \to \text{Dropout}(0.3) \to \text{Linear}(32 \to 1)$
- **Parameter Count**: ~15,000 parameters (engineered for low-data astrophysical regimes).
- **Optimization**: AdamW, initial learning rate $10^{-3}$, weight decay $10^{-4}$, binary cross-entropy with positive class weighting.

---

## 4. Quantitative Evaluation Metrics

All models are assessed across the following standardized metrics:
1. **Precision**: $\frac{\text{TP}}{\text{TP} + \text{FP}}$ (Positive Predictive Value).
2. **Recall / Detection Rate**: $\frac{\text{TP}}{\text{TP} + \text{FN}}$ (True Positive Rate / Sensitivity).
3. **F1-Score**: Harmonic mean of Precision and Recall: $\frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$.
4. **Specificity**: $\frac{\text{TN}}{\text{TN} + \text{FP}}$ (True Negative Rate).
5. **False Positive Rate (FPR)**: $\frac{\text{FP}}{\text{FP} + \text{TN}}$.
6. **PR-AUC (Average Precision)**: Area under Precision-Recall curve (primary metric for imbalanced astronomical surveys).
7. **ROC-AUC**: Area under Receiver Operating Characteristic curve.
8. **Computational Footprint**:
   - Training Wall-Clock Time (seconds).
   - Inference Latency per Target (milliseconds per light curve).

---

## 5. Controlled Robustness Protocol

To measure performance decay under observational degradation, trained models and the BLS baseline are subjected to controlled sweeps on the test partition:

1. **Gaussian Noise Sweep**: Additive $\sigma_{\text{add}} \in [0.0, 1000, 2000, 4000]\text{ ppm}$.
2. **Transit Depth Attenuation**: Transit depth scaling factor $\alpha \in [1.0, 0.75, 0.5, 0.25]$ (simulating transition from Jovian to sub-Neptune radii).
3. **Extended Gap Insertion**: Simulating spacecraft data downlinks or instrument outages with $\Delta t_{\text{gap}} \in [0, 1, 2, 4]\text{ days}$.
4. **Random Cadence Dropout**: Randomly discarding $f_{\text{drop}} \in [0\%, 15\%, 30\%, 50\%]$ of measurements.

All degradation parameters are tracked and recorded in `results/metrics/robustness_suite.json`.
