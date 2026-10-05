# Stage 4 Real-Data Evaluation Report: Transit-Specific Candidate Vetting

**Evaluation Status:** AUTHORIZED ONE-TIME OUT-OF-SAMPLE EVALUATION COMPLETED  
**Timestamp:** `2026-10-05T10:37:47Z`  
**Git HEAD Commit:** `fc795a71391129ae59219fb52e88b9a967fd4ca8`  
**Model / Threshold:** `RandomForest (52 features)` | `tau = 0.55`  
**Cohort Manifest:** `results/real_data_stage2/stage2_corrected_cohort_manifest.csv`  
**Stage 3 BLS Ledger:** `results/real_benchmark_stage3/bls_formal_predictions.csv`  

---

## 1. Cohort Verification

The evaluation was conducted on the frozen 100-target authentic TESS cohort with zero modifications:
- **Total Targets Evaluated:** 100
- **Confirmed Single-Planet Host Systems:** 50
- **Observational Comparison Stars:** 50
- **Manifest SHA-256:** `4231af3c6141c45fd352133d976db956474a4bb42eb47ed21a3703da25e400fb` (verified exact match)
- **Target Load Integrity:** 100/100 FITS files located and loaded from `data/raw/real_tess_stage2/`

## 2. Frozen-Model Provenance

The candidate vetters and feature schemas were frozen prior to evaluation:
- **Champion Vetter:** `RandomForest` (52 features, median imputation)
  - Model File: `results/stage4_candidate_vetting/frozen_candidate_vetter.joblib`
  - Model SHA-256: `a9b19086d84c10e42b434bcbd235c348bca72083908213d16db1d16931244c67`
  - Calibrated Decision Threshold: `tau = 0.55` (calibrated on synthetic OOF data, F1-max subject to Recall >= 0.92)
- **Baseline A Vetter:** `RandomForest` (22 tabular features)
  - Model File: `results/stage4_candidate_vetting/frozen_baseline_vetter_22feats.joblib`
  - Model SHA-256: `75dcd40eef228773fe28cd90e10d7ba91ff6a973a30d9548821dcfffc8274fe3`
  - Decision Threshold: `tau = 0.55`
- **Feature Schema SHA-256:** `b8f69874faf9ab2327ade47857110411fab0f11ca6e25896d35e5915e56132ba` (52 deterministic features)
- **Firewall Guarantee:** No retraining, refitting, feature selection, or threshold tuning occurred on real data.

## 3. Number of Real Candidates Evaluated

Stage 4 operates strictly as a downstream vetting stage on the frozen Stage 3 BLS predictions:
- **BLS Execution on Real Data:** None (BLS was NOT rerun).
- **Total Candidates Evaluated:** Exactly 100 candidate signals (one per target, inherited directly from Stage 3).
- **Candidate Sources:** 50 candidates from confirmed planet hosts, 50 candidates from observational comparison stars.

## 4. Stage 4 Host Retention

- **Total Confirmed Hosts:** 50
- **Retained by Champion Vetter (Score >= 0.55):** **15/50 (30.0%)**
- **Rejected by Champion Vetter (Score < 0.55):** **35/50 (70.0%)**

## 5. Stage 4 Comparison-Star Rejection

- **Total Comparison Stars:** 50
- **Rejected by Champion Vetter (Score < 0.55):** **50/50 (100.0%)**
- **Retained / Triggered as Candidates (Score >= 0.55):** **0/50 (0.0%)**

> **Terminology Note:** Observational comparison stars are field stars observed in the same cadence without known planet records. They are NOT certified planet-free negative controls. Rejection of a comparison star is designated 'comparison-star rejection', and retention is designated 'candidate trigger rate', NOT false-positive rate.

## 6. Baseline A Host Retention / Rejection Comparison

| Metric | Champion RF (52 Features) | Baseline A RF (22 Features) | Delta (Champion - Baseline) |
| :--- | :---: | :---: | :---: |
| **Host Retention Rate** | **30.0%** (15/50) | **14.0%** (7/50) | +16.0% (+8 hosts) |
| **Control Rejection Rate** | **100.0%** (50/50) | **98.0%** (49/50) | +2.0% (+1 controls) |
| **Control Trigger Rate** | **0.0%** (0/50) | **2.0%** (1/50) | -2.0% (-1 controls) |

The 52-feature morphology vetter yields an improvement in comparison-star rejection of **+2.0%** while maintaining **30.0%** host retention.

## 7. Stage 4 vs Stage 3 Comparison

Stage 3 BLS alone without vetting yielded:
- Stage 3 Host Detections: 50/50 (100.0%) hosts triggered the raw BLS SDE threshold.
- Stage 3 Control Triggers: 45/50 (90.0%) comparison stars triggered the raw BLS SDE threshold (only 5 rejected).

With Stage 4 Champion Vetter downstream of Stage 3:
- **Net Candidates Removed:** Stage 4 eliminates **45 additional comparison-star candidates** that Stage 3 BLS alone accepted.
- **Comparison-Star Trigger Reduction:** From 90.0% (45/50) in raw BLS down to **0.0% (0/50)** in Stage 4.
- **Host Tradeoff:** Stage 4 retains **15/50 (30.0%)** of known hosts, filtering 35 hosts whose BLS or morphology properties fell below threshold.

## 8. G12-Category Cross-Tabulation

Cross-tabulation of Stage 4 Champion vetting decisions against frozen Stage 3 G12 recovery status:

| G12 Recovery Category | Total Hosts (N) | Champion Retained | Champion Rejected | Retention Rate | Baseline Retained |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **FULL_RECOVERY** | 38 | 14 | 24 | 36.8% | 6 |
| **PERIOD_ONLY** | 8 | 1 | 7 | 12.5% | 1 |
| **EPOCH_ONLY** | 1 | 0 | 1 | 0.0% | 0 |
| **REJECTED** | 3 | 0 | 3 | 0.0% | 0 |

Key Observations:
- **FULL_RECOVERY Targets:** 14/38 (36.8%) retained.
- **PERIOD_ONLY Targets:** 1/8 (12.5%) retained.
- **REJECTED (No Match in Stage 3):** 0/3 retained; Stage 4 correctly rejects 3/3 of these unrecovered signals.

## 9. Host Failure Analysis

A total of **35 confirmed host candidates** were rejected by Stage 4 (score < 0.55):

| TIC | Target Name | Planet | G12 Category | S3 Period (d) | Cat Period (d) | S3 SDE | S3 SNR | Vetter Score | Primary Inferred Cause |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| 97409519 | WASP-124 | WASP-124 b | FULL_RECOVERY | 3.373 | 3.373 | 88.9 | 91.1 | 0.467 | Marginal model score across aggregated morphology feature space... |
| 144065872 | WASP-95 | WASP-95 b | FULL_RECOVERY | 2.186 | 2.185 | 117.1 | 374.4 | 0.249 | High odd-even asymmetry (7.38 sigma; EB-like)... |
| 149603524 | WASP-62 | WASP-62 b | FULL_RECOVERY | 4.410 | 4.412 | 67.8 | 340.5 | 0.386 | Marginal model score across aggregated morphology feature space... |
| 231663901 | WASP-46 | WASP-46 b | FULL_RECOVERY | 1.430 | 1.430 | 157.6 | 95.3 | 0.532 | Marginal model score across aggregated morphology feature space... |
| 238176110 | WASP-91 | WASP-91 b | FULL_RECOVERY | 2.798 | 2.799 | 124.0 | 187.4 | 0.472 | Marginal model score across aggregated morphology feature space... |
| 52204645 | TOI-209 | TOI-209 b | PERIOD_ONLY | 4.375 | 4.379 | 16.4 | 9.9 | 0.492 | Period recovered but epoch/phase mismatch in Stage 3 (fundamental_1.0x... |
| 183537452 | WASP-29 | WASP-29 b | FULL_RECOVERY | 3.922 | 3.923 | 72.5 | 166.6 | 0.444 | Marginal model score across aggregated morphology feature space... |
| 230982885 | WASP-97 | WASP-97 b | FULL_RECOVERY | 2.073 | 2.073 | 132.1 | 345.0 | 0.393 | Marginal model score across aggregated morphology feature space... |
| 234523599 | HATS-71 | HATS-71 b | FULL_RECOVERY | 3.795 | 3.796 | 69.4 | 48.0 | 0.515 | Marginal model score across aggregated morphology feature space... |
| 281459670 | HATS-30 | HATS-30 b | FULL_RECOVERY | 3.173 | 3.174 | 85.8 | 99.1 | 0.494 | High odd-even asymmetry (3.71 sigma; EB-like)... |
| 281541555 | HATS-46 | HATS-46 b | FULL_RECOVERY | 4.745 | 4.742 | 31.9 | 26.5 | 0.397 | Shallow depth relative to local scatter (depth/MAD=1.81)... |
| 355703913 | HATS-34 | HATS-34 b | FULL_RECOVERY | 2.106 | 2.106 | 64.6 | 24.2 | 0.472 | Shallow depth relative to local scatter (depth/MAD=1.39)... |
| 441462736 | HD 221416 | HD 221416 b | FULL_RECOVERY | 14.298 | 14.281 | 24.6 | 59.7 | 0.395 | Poor dip isolation / noisy baseline (0.90)... |
| 1528696 | NGTS-6 | NGTS-6 b | FULL_RECOVERY | 0.882 | 0.882 | 61.9 | 25.3 | 0.444 | Shallow depth relative to local scatter (depth/MAD=0.89)... |
| 32499655 | HATS-44 | HATS-44 b | FULL_RECOVERY | 2.743 | 2.744 | 50.3 | 18.1 | 0.481 | Shallow depth relative to local scatter (depth/MAD=1.24)... |
| 43647325 | WASP-35 | WASP-35 b | FULL_RECOVERY | 3.161 | 3.162 | 100.2 | 316.1 | 0.443 | Marginal model score across aggregated morphology feature space... |
| 44647437 | nan | nan | FULL_RECOVERY | 3.351 | 3.353 | 26.4 | 12.2 | 0.444 | Shallow depth relative to local scatter (depth/MAD=0.58); Poor dip iso... |
| 78055054 | HATS-43 | HATS-43 b | FULL_RECOVERY | 4.391 | 4.389 | 66.4 | 82.5 | 0.438 | Marginal model score across aggregated morphology feature space... |
| 139528693 | WASP-78 | WASP-78 b | FULL_RECOVERY | 2.175 | 2.175 | 88.6 | 95.7 | 0.407 | Marginal model score across aggregated morphology feature space... |
| 170634116 | WASP-79 | WASP-79 b | FULL_RECOVERY | 3.663 | 3.662 | 80.2 | 339.5 | 0.350 | High odd-even asymmetry (2.73 sigma; EB-like)... |
| 178284730 | WASP-140 | WASP-140 b | FULL_RECOVERY | 2.235 | 2.236 | 101.0 | 211.2 | 0.448 | Marginal model score across aggregated morphology feature space... |
| 200322593 | TOI-540 | TOI-540 b | EPOCH_ONLY | 0.725 | 1.239 | 115.4 | 106.9 | 0.139 | Shallow depth relative to local scatter (depth/MAD=1.08)... |
| 260708537 | GJ 238 | GJ 238 b | REJECTED | 13.685 | 1.745 | 6.4 | 8.4 | 0.143 | Stage 3 BLS period failed recovery (wrong periodicity candidate); Marg... |
| 452808876 | WASP-82 | WASP-82 b | FULL_RECOVERY | 2.707 | 2.706 | 120.7 | 274.3 | 0.365 | High odd-even asymmetry (5.96 sigma; EB-like)... |
| 4616072 | HATS-45 | HATS-45 b | FULL_RECOVERY | 4.185 | 4.188 | 40.7 | 28.9 | 0.533 | Shallow depth relative to local scatter (depth/MAD=1.75)... |
| 33521996 | HATS-6 | HATS-6 b | FULL_RECOVERY | 3.328 | 3.325 | 65.7 | 68.0 | 0.517 | Marginal model score across aggregated morphology feature space... |
| 170102285 | WASP-23 | WASP-23 b | PERIOD_ONLY | 2.943 | 2.944 | 68.8 | 140.5 | 0.408 | Period recovered but epoch/phase mismatch in Stage 3 (fundamental_1.0x... |
| 52640302 | WASP-64 | WASP-64 b | PERIOD_ONLY | 1.573 | 1.573 | 80.9 | 88.6 | 0.423 | Period recovered but epoch/phase mismatch in Stage 3 (fundamental_1.0x... |
| 306362738 | WASP-49 | WASP-49 b | PERIOD_ONLY | 2.781 | 2.782 | 70.0 | 128.0 | 0.494 | Period recovered but epoch/phase mismatch in Stage 3 (fundamental_1.0x... |
| 47911178 | WASP-101 | WASP-101 b | PERIOD_ONLY | 3.584 | 3.585 | 51.7 | 196.7 | 0.280 | Period recovered but epoch/phase mismatch in Stage 3 (fundamental_1.0x... |
| 59843967 | HATS-4 | HATS-4 b | PERIOD_ONLY | 2.518 | 2.517 | 84.8 | 65.1 | 0.436 | Period recovered but epoch/phase mismatch in Stage 3 (fundamental_1.0x... |
| 290131778 | HD 202772 A | HD 202772 A b | PERIOD_ONLY | 3.302 | 3.309 | 94.5 | 310.4 | 0.453 | Period recovered but epoch/phase mismatch in Stage 3 (fundamental_1.0x... |
| 317548889 | TOI-480 | TOI-480 b | REJECTED | 4.815 | 6.866 | 14.4 | 27.6 | 0.032 | Stage 3 BLS period failed recovery (wrong periodicity candidate); High... |
| 410214986 | DS Tuc A | DS Tuc A b | REJECTED | 2.822 | 8.138 | 483.4 | 2604.6 | 0.111 | Stage 3 BLS period failed recovery (wrong periodicity candidate); High... |
| 402026209 | WASP-4 | WASP-4 b | FULL_RECOVERY | 1.338 | 1.338 | 204.4 | 267.5 | 0.396 | Marginal model score across aggregated morphology feature space... |

Full feature details for all rejected hosts are preserved in: `stage4_host_failure_ledger.csv`.

## 10. Comparison-Star Trigger Analysis

A total of **0 comparison stars** were retained / triggered by Stage 4 as candidate-like (score >= 0.55):

Zero comparison stars were retained as candidates.

## 11. Score Distributions

Summary statistics of model probability scores across the cohort:

| Target Cohort | N | Mean Score | Median Score | Std Dev | Min Score | Max Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Confirmed Hosts** | 50 | 0.4862 | 0.4691 | 0.1850 | 0.0316 | 0.9651 |
| **Comparison Stars** | 50 | 0.1053 | 0.0720 | 0.1032 | 0.0028 | 0.3704 |

A visual comparison of score distributions is saved in: `stage4_score_distributions.png`.

## 12. Unexpected Feature / Edge-Case Behavior

- **Targets with NaN Features:** 91/100 targets had >=1 NaN feature (total NaN feature evaluations: 190).
- **NaN Handling:** All missing/undefined features were processed deterministically by the model's pipeline `SimpleImputer(strategy='median')` using frozen training medians.
- **Data Completeness:** 100/100 light curves had valid cadences; zero targets failed FITS file loading.
- **Numerical Stability:** No infinite or unhandled exception values reached the estimator.

## 13. Integrity / Hash Verification

| Artifact | Expected SHA-256 | Post-Evaluation SHA-256 | Status |
| :--- | :--- | :--- | :---: |
| **Cohort Manifest** | `4231af3c6141c45fd352133d976db956474a4bb42eb47ed21a3703da25e400fb` | `4231af3c6141c45fd352133d976db956474a4bb42eb47ed21a3703da25e400fb` | **VERIFIED UNCHANGED** |
| **Champion Vetter** | `a9b19086d84c10e42b434bcbd235c348bca72083908213d16db1d16931244c67` | `a9b19086d84c10e42b434bcbd235c348bca72083908213d16db1d16931244c67` | **VERIFIED UNCHANGED** |
| **Baseline Vetter** | `75dcd40eef228773fe28cd90e10d7ba91ff6a973a30d9548821dcfffc8274fe3` | `75dcd40eef228773fe28cd90e10d7ba91ff6a973a30d9548821dcfffc8274fe3` | **VERIFIED UNCHANGED** |
| **Feature Schema** | `b8f69874faf9ab2327ade47857110411fab0f11ca6e25896d35e5915e56132ba` | `b8f69874faf9ab2327ade47857110411fab0f11ca6e25896d35e5915e56132ba` | **VERIFIED UNCHANGED** |
| **Synthetic Data** | `ff3b371f983c311a1fbc558bf7b07059cc703d9b1c174f1569369b41c7e398ca` | `ff3b371f983c311a1fbc558bf7b07059cc703d9b1c174f1569369b41c7e398ca` | **VERIFIED UNCHANGED** |
| **Stage 3 Predictions** | `e0f8032247f8887a2eb318ea2a58ce0863af789c2ade44adc69c062ae6652cff` | `e0f8032247f8887a2eb318ea2a58ce0863af789c2ade44adc69c062ae6652cff` | **VERIFIED UNTOUCHED** |

## 14. Full Test Results

- **Full Pytest Suite:** Executed cleanly (`125 passed` across all test files).
- **No Test Modifications:** Zero tests were modified to accommodate real results.

## 15. Clear Limitations

1. **Single Fixed Cohort:** This evaluation is strictly conducted on one fixed 100-target cohort (50 hosts, 50 comparison stars). It does not represent an unselected population survey.
2. **Comparison Stars are Observational Controls:** The comparison stars are field stars observed in the same cadence; they are NOT guaranteed planet-free negatives. A trigger could represent uncataloged astrophysical variability, low-mass companions, or unconfirmed planets.
3. **Frozen Calibration:** The decision threshold (`tau = 0.55`) was calibrated solely on synthetic out-of-fold data. No tuning on real data was performed or is permitted.
4. **Vetting vs Confirmation:** Stage 4 tests whether a periodic BLS signal is consistent with transit-like morphology versus systematic/stellar noise. It does NOT constitute physical confirmation of an exoplanet.
5. **One-Time Evaluation:** In accordance with the protocol firewall, this evaluation is final and immutable.
