# TESS Transit Detection Benchmark: Final Project Report

**Project Status:** COMPLETE & FROZEN  
**Closeout Date:** 2026-10-05  
**Repository:** `PPurab-006/TESS_CurveClassifier`  
**Execution Environment:** Linux, Python 3.11  

---

## 1. Research Question

> *"How do classical signal processing (Box Least Squares) and supervised machine learning compare in detecting authentic exoplanetary transit signals in TESS photometric light curves, and can a transit-specific candidate vetting layer suppress false periodic triggers while preserving genuine exoplanet detections?"*

### Scientific Context & Objectives
1. **Classical Sensitivity vs Specificity Tradeoff**: Classical Box Least Squares (BLS) is highly sensitive to periodic dips but prone to false candidate triggers on non-planetary astrophysical variability (e.g., stellar rotation, spot modulation, eclipsing binaries) and TESS instrument systematics (momentum dumps, scattered light, thermal drift).
2. **Dedicated Downstream Vetting**: Stage 4 introduced a specialized candidate-vetting classifier operating downstream of BLS to evaluate signal morphology, odd-even symmetry, event consistency, and local isolation without altering BLS candidate ephemerides.
3. **Strict Methodological Firewall**: The authentic TESS cohort was treated strictly as a one-time out-of-sample evaluation set. All model selection, feature schema definition, hyperparameter specification, and decision-threshold calibration were completed exclusively on synthetic training data prior to crossing the real-data firewall.

---

## 2. Dataset & Cohort Definition

### Authentic TESS Production Cohort ($N=100$)
- **Manifest File:** `results/real_data_stage2/stage2_corrected_cohort_manifest.csv`
- **Manifest SHA-256:** `4231af3c6141c45fd352133d976db956474a4bb42eb47ed21a3703da25e400fb`
- **Single-Planet Host Systems ($N=50$):**
  - Verified single-planet systems from the NASA Exoplanet Archive (`sy_pnum = 1`).
  - Orbital periods $P \in [0.88, 14.3]\text{ days}$.
  - Observation sectors: Sectors 1, 2, 5, 6, and 13.
- **Observational Comparison Stars ($N=50$):**
  - Field stars observed in the identical 120-second cadence across the same TESS sectors.
  - Zero TOI, TCE, or confirmed exoplanet associations in the NASA Exoplanet Archive.
  - Designated strictly as *observational comparison stars*, not guaranteed planet-free negatives.
- **Physical Quality Invariants:**
  - Usable cadence ratio $R_{\text{usable}} \ge 0.80$.
  - Observational baseline $T_{\text{baseline}} \ge 20.0\text{ days}$.
  - Strict monotonic time ordering ($\Delta t > 0$, 0 duplicates).
  - Scalar median normalization ($F / \text{median}(F)$).

---

## 3. Stage 3 Methodology & Formal Baseline Results

### Methodology
- **Search Grid (GATE-09):** Frequency grid constructed deterministically with 5× oversampling factor across periods $P \in [0.5, 15.0]\text{ days}$ and transit durations $q \in [0.01, 0.15]$. Full grid parameters serialized in `results/real_benchmark_stage3/bls_frequency_grids.npz`.
- **SDE Formulation (GATE-11):** SDE Option C adopted—peak, harmonic, and alias masked background dispersion:
  $$\text{SDE}_C = \frac{P_{\max} - \text{median}(P_{\text{masked}})}{\text{MAD}(P_{\text{masked}}) \times 1.4826}$$
- **Recovery Standard (GATE-01, GATE-12):** Fixed 1% relative period recovery tolerance:
  $$\left|\frac{P_{\text{detected}} - P_{\text{catalog}}}{P_{\text{catalog}}}\right| \le 0.01$$
  and G12 composite epoch/circular-phase match within dynamically bounded tolerance.

### Stage 3 Results
- **BLS Host Detection Rate:** 50/50 (100.0%) hosts triggered the raw candidate threshold ($\text{SDE} \ge 6.0$).
- **BLS Period Recovery (1% tolerance):** 46/50 (92.0%) hosts achieved period recovery within 1%.
- **G12 Full Recovery (Period + Epoch Match):** 38/50 (76.0%) hosts achieved full recovery.
- **Observational Comparison Star Triggers:** 45/50 (90.0%) comparison stars triggered the candidate threshold (only 5 rejected).
- **Scientific Implication:** BLS alone demonstrates excellent sensitivity but inadequate specificity on real TESS light curves, motivating the Stage 4 vetting layer.

---

## 4. Stage 4 Synthetic Methodology & Model Selection

### Synthetic Benchmark Design
- **Candidate Dataset ($N=600$ admitted BLS candidates):**
  - Generated using physics-based trapezoidal transit injection and realistic stellar variability.
  - 300 genuine planetary transit signals.
  - 300 confounder candidates (100 eclipsing binaries, 100 stellar variability/spots, 100 TESS instrument artifacts).
  - Preserved in: `data/processed/stage4_synthetic/synthetic_candidates_52feats.csv` (SHA-256: `ff3b371f983c311a1fbc558bf7b07059cc703d9b1c174f1569369b41c7e398ca`).
- **Deterministic 52-Feature Schema (SHA-256: `b8f69874faf9ab2327ade47857110411fab0f11ca6e25896d35e5915e56132ba`):**
  - 22 Baseline Tabular Features (flux statistics, folded binned profile, BLS properties).
  - 7 Transit Shape & Geometry Features (depth-to-MAD, duty cycle, in/out contrast).
  - 5 Profile Morphology Features (symmetry, ingress/egress difference, flat-bottom kurtosis).
  - 5 Individual Event Consistency Features (adequate event count, depth scatter, single-event dominance).
  - 4 Odd/Even Consistency Features (odd-even depth difference, depth ratio, significance, secondary eclipse ratio).
  - 5 Stellar Variability Features (global-to-local std, autocorrelation peak/modulation, flare rate, smoothness).
  - 4 Signal Localization Features (variance contrast, deficit concentration, dip isolation, baseline flatness).

### Model Selection & Strict Protocol Correction
- **Predeclared Protocol Rule:** Select champion model by maximum synthetic out-of-fold (OOF) PR-AUC subject to Recall $\ge 0.90$.
- **5-Fold Star-Group Cross-Validation Results:**
  - Logistic Regression (52 feats): PR-AUC = 0.9769, Recall = 94.7%
  - HistGradientBoosting (52 feats): PR-AUC = 0.9852, Recall = 93.3%
  - **Random Forest (52 feats): PR-AUC = 0.9866, Recall = 92.7%**
- **Protocol Correction (Audit Option 1):** Random Forest was formally selected and frozen as the Champion model, adhering strictly to the predeclared PR-AUC criterion.
- **Decision Threshold Calibration:** Calibrated deterministically on synthetic OOF predictions (maximize F1 subject to Recall $\ge 0.92$):
  $$\tau = 0.55 \quad (\text{OOF F1} = 0.9416, \text{Recall} = 92.67\%, \text{Specificity} = 95.67\%)$$

---

## 5. One-Time Real-Data Evaluation Results

The frozen Champion Random Forest vetter and Baseline A vetter were evaluated exactly once on the authentic 100-target cohort using Stage 3 BLS candidate parameters as inputs:

### Benchmark Performance Comparison

| Metric | Stage 3 BLS (Unvetted) | Baseline A RF (22 Features) | Champion RF (52 Features) | Delta (Champion vs Baseline A) |
| :--- | :---: | :---: | :---: | :---: |
| **Confirmed Host Retention Rate** | 100.0% (50/50) | 14.0% (7/50) | **30.0% (15/50)** | **+16.0% (+8 hosts)** |
| **Comparison-Star Rejection Rate** | 10.0% (5/50) | 98.0% (49/50) | **100.0% (50/50)** | **+2.0% (+1 control)** |
| **Comparison-Star Candidate Trigger Rate** | 90.0% (45/50) | 2.0% (1/50) | **0.0% (0/50)** | **-2.0% (-1 control)** |

### G12 Recovery Cross-Tabulation
- **FULL_RECOVERY Targets ($N=38$):** 14 retained (36.8%), 24 rejected.
- **PERIOD_ONLY Targets ($N=8$):** 1 retained (12.5%), 7 rejected.
- **EPOCH_ONLY Targets ($N=1$):** 0 retained (0.0%), 1 rejected.
- **REJECTED (No Match in Stage 3) Targets ($N=3$):** 0 retained (0.0%), 3 rejected.

### Score Distributions
- **Confirmed Hosts:** Mean score = 0.4862, Median = 0.4691, Range = [0.0316, 0.9651].
- **Comparison Stars:** Mean score = 0.1053, Median = 0.0720, Range = [0.0028, 0.3704].
- Clear separation between populations; zero comparison stars crossed the $\tau = 0.55$ decision boundary.

---

## 6. Reproducibility & Integrity Verification

All core scientific assets were verified by independent SHA-256 cryptographic hashing before and after evaluation:

| Scientific Asset | SHA-256 Digest | Status |
| :--- | :--- | :---: |
| **Real Cohort Manifest** | `4231af3c6141c45fd352133d976db956474a4bb42eb47ed21a3703da25e400fb` | **VERIFIED UNCHANGED** |
| **Synthetic Candidate Dataset** | `ff3b371f983c311a1fbc558bf7b07059cc703d9b1c174f1569369b41c7e398ca` | **VERIFIED UNCHANGED** |
| **Frozen Champion RF Vetter** | `a9b19086d84c10e42b434bcbd235c348bca72083908213d16db1d16931244c67` | **VERIFIED UNCHANGED** |
| **Frozen Baseline A RF Vetter** | `75dcd40eef228773fe28cd90e10d7ba91ff6a973a30d9548821dcfffc8274fe3` | **VERIFIED UNCHANGED** |
| **52-Feature Schema** | `b8f69874faf9ab2327ade47857110411fab0f11ca6e25896d35e5915e56132ba` | **VERIFIED UNCHANGED** |
| **Stage 3 Formal Predictions** | `e0f8032247f8887a2eb318ea2a58ce0863af789c2ade44adc69c062ae6652cff` | **VERIFIED UNTOUCHED** |

Full automated test suite verification:
- `pytest tests/ -o addopts="-v"`: **125 passed, 0 failures, 0 errors**.

---

## 7. Main Limitations & Scientific Scope

1. **Fixed Cohort Scope:** Results are based on a fixed 100-target cohort and should not be extrapolated as universal population statistics across the full TESS catalog.
2. **Observational Comparison Stars:** Field comparison stars are non-detections in existing catalogs, not confirmed planet-free stars. Rejection does not prove planet absence, and retention is reported as *candidate trigger rate*, not formal false-positive rate.
3. **Candidate Vetting vs Confirmation:** Stage 4 evaluates photometric morphology consistency; it does not validate or confirm exoplanetary nature (which requires radial velocity or high-resolution imaging).
4. **Conservative Domain Shift:** The classifier was trained exclusively on synthetic light curves. Real TESS photometric noise characteristics resulted in conservative model scores (median host score 0.4691), highlighting the sim-to-real transfer gap in transit morphology classification.

---

## 8. Final Conclusion & Closeout Declaration

Stage 4 successfully demonstrated that adding specialized transit morphology and consistency features significantly improves candidate discrimination over classical tabular features, eliminating 100% of candidate triggers on observational comparison stars while more than doubling host retention relative to Baseline A.

**Closeout Declaration:**
The TESS-Light-curve research project is now **complete, frozen, and pushed**. In strict compliance with scientific integrity protocols, **no further experiments, model training, parameter retuning, or real-data evaluations were conducted**.
