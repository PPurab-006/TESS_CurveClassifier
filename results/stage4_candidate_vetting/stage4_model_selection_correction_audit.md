# Stage 4 Model Selection Correction Audit

**Correction Date:** 2026-10-05  
**Correction Type:** Protocol enforcement — correcting hardcoded champion model  
**Status:** CORRECTED AND FROZEN  

---

## 1. Discovery

A read-only forensic audit of the Stage 4 synthetic training phase (completed
2026-10-05) identified a genuine implementation/protocol inconsistency.

**The predeclared model-selection rule** (from the approved Stage 4 plan) was:

> Select the model with maximum full-52-feature synthetic OOF PR-AUC,
> subject to the constraint that synthetic OOF Transit Recall >= 0.90.

**The actual implementation** in `scripts/run_stage4_synthetic_phase.py` line 312
contained a hardcoded string:

```python
# INCORRECT (hardcoded, violates protocol)
champion_name = "HistGradientBoosting"
```

This was a literal implementation deviation from the approved rule, regardless of
whether HGB might have had other metrics that were competitive.

---

## 2. Empirical 5-Fold CV Results (Unchanged Synthetic Dataset)

All models evaluated on the same frozen synthetic dataset:

| Model               | Full-52 PR-AUC | Full-52 Recall | Full-52 ROC-AUC | Full-52 F1 |
|---------------------|----------------|----------------|-----------------|------------|
| LogisticRegression  | 0.9769         | 0.9800         | 0.9874          | 0.9719     |
| **RandomForest**    | **0.9866**     | **0.9833**     | 0.9909          | 0.9672     |
| HistGradientBoosting| 0.9852         | 0.9800         | **0.9937**      | **0.9735** |

- All three models satisfy the Recall >= 0.90 constraint.
- **Random Forest has the highest full-52 PR-AUC (0.9866 > 0.9852 for HGB)**.
- HGB has higher ROC-AUC and F1, but those metrics are NOT the declared selection criterion.

---

## 3. Correction Decision

**Option 1 (SELECTED): Strict Protocol Enforcement**

The correction changes the champion selection from hardcoded "HistGradientBoosting"
to a programmatic selection that:

1. Filters all models satisfying full-52 OOF Recall >= 0.90.
2. Ranks by full-52 OOF PR-AUC (descending).
3. Tie-break 1: maximize Recall.
4. Tie-break 2: deterministic alphabetical model name.

Under this rule, **Random Forest is selected** (PR-AUC 0.9866 vs HGB 0.9852).

**The rationale**: The declared rule is the scientific contract for this experiment.
Deviating from it — even in favor of a model with slightly better secondary metrics —
would represent post-hoc model selection, which is a methodological violation
when the real-cohort evaluation is still pending.

---

## 4. No Real Data Used

- The synthetic candidate dataset was **not modified** (SHA-256 confirmed unchanged).
- The 52-feature schema was **not modified**.
- The real 100-target cohort was **not loaded, evaluated, or preprocessed**.
- The real cohort manifest was **not modified** (SHA-256 confirmed unchanged).
- No real predictions were generated.

---

## 5. Corrected Pipeline Changes

### `scripts/run_stage4_synthetic_phase.py`

- Replaced hardcoded `champion_name = "HistGradientBoosting"` (old line 312) with
  programmatic champion selection block applying the approved rule.
- Ablation study now uses `champion_name` (RandomForest) instead of hardcoded HGB.
- Champion hyperparameters in checkpoint now dynamically set per model type.
- Checkpoint records explicit `model_selection_rule` field.
- Step numbering updated to reflect reordering (model selection now precedes ablation).

### `src/tess_benchmark/stage4/vetter.py`

- Changed `CandidateVetter.__init__` default `model_name` from "HistGradientBoosting"
  to "RandomForest" to reflect the corrected champion.

---

## 6. Corrected Frozen Artifacts

| Artifact                                     | SHA-256 |
|----------------------------------------------|---------|
| Synthetic candidate dataset (**unchanged**)  | `ff3b371f983c311a1fbc558bf7b07059cc703d9b1c174f1569369b41c7e398ca` |
| Real cohort manifest (**unchanged**)         | `4231af3c6141c45fd352133d976db956474a4bb42eb47ed21a3703da25e400fb` |
| Feature schema (**unchanged**)               | `b8f69874faf9ab2327ade47857110411fab0f11ca6e25896d35e5915e56132ba` |
| Corrected frozen champion vetter (RF)        | `a9b19086d84c10e42b434bcbd235c348bca72083908213d16db1d16931244c67` |
| Corrected frozen baseline vetter (RF 22-feat)| `75dcd40eef228773fe28cd90e10d7ba91ff6a973a30d9548821dcfffc8274fe3` |

**Previous (superseded) HGB artifact hashes:**
- Champion vetter (HGB): `e1e568a21eca48cd1aa4f4f27f4aaf2a043e046ea29877034fdf82dda0499d81` — superseded
- Baseline vetter (HGB): `6a9fadeece078618691a9a97f1493f38cdc57add984f90f5b407922394aa7052` — superseded
- Previous checkpoint manifest: `f7fcb4d3aa13638227f25d21394126159d777f5ae5f0fd7736a4c1dd881b3084` — superseded

---

## 7. Corrected Calibration Results (Random Forest)

**Champion: RandomForest, 52 features**

| Metric                 | Value  |
|------------------------|--------|
| Full-52 OOF PR-AUC     | 0.9866 |
| Full-52 OOF ROC-AUC    | 0.9909 |
| Decision threshold (t) | 0.55   |
| F1 at t                | 0.9703 |
| Recall at t            | 0.9800 |
| Specificity at t       | 0.9600 |
| Precision at t         | 0.9608 |

**Matched Baseline A (RandomForest, 22 features)**

| Metric                 | Value  |
|------------------------|--------|
| Baseline-22 PR-AUC     | 0.9711 |
| Decision threshold (t) | 0.55   |
| F1 at t                | 0.9605 |
| Recall at t            | 0.9733 |
| Specificity at t       | 0.9467 |
| Precision at t         | 0.9481 |

---

## 8. Test Results

Command: `PYTHONPATH=src .venv/bin/pytest tests/ -o addopts="-v"`

**Result: 125 passed, 2 warnings, 0 failures, 0 errors**

The 2 warnings are pre-existing SciPy RuntimeWarning (catastrophic cancellation in
moment calculation on identically-zero-variance constant flux) from
`test_extract_features_edge_case_zero_transits`. These are intentional edge-case
artifacts and are not new warnings introduced by this correction.

---

## 9. Provenance

- Source git commit: `fc795a71391129ae59219fb52e88b9a967fd4ca8`
- Correction authorized by: User directive "OPTION 1: STRICT PROTOCOL ENFORCEMENT"
- Real-data firewall: **REMAINS CLOSED — NO REAL COHORT ACCESSED**
