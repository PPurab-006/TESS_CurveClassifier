# Stage 3 Formal Benchmark Readiness Report

**Date:** 2026-10-03  
**Protocol Version:** 1.3.2 | **Branch:** main  
**Status: READINESS CLEANUP COMPLETE — AWAITING USER AUTHORIZATION FOR FORMAL BENCHMARK**

---

## Summary

This report documents the completed Stage 3 readiness cleanup. The formal benchmark has **not** been run. No threshold tuning, model training, or BLS benchmarking has been executed.

---

## Phase 1 — Experiment 2 Reconciliation (Complete)

Experiment 2 compared Options A–D across all 110 targets (10 Sector 1 pilot + 100 Stage 2 validated):

| Method | Mean SDE | Median SDE | Std |
|--------|----------|------------|-----|
| Option A | 10.70 | 9.57 | 5.15 |
| Option B | 51.4 | 36.1 | 51.5 |
| Option C | 51.8 | 36.5 | 52.0 |
| Option D | 58.9 | 39.3 | 60.7 |

- Option C (alias-aware union E+robust MAD) is analytically robust; mask fraction ≤ 0.94%
- No degenerate or MAD-zero cases in Option C
- Option B and C numerically very close (mean |B−C| = 0.41)

**GATE-11: USER DECISION REQUIRED — select SDE method (Option C analytically preferred).**

---

## Phase 2 — Protocol Gate Audit (Complete)

| Gate | Status |
|------|--------|
| GATE-01 Period tolerance 1.0% | PASS |
| GATE-02 Frequency grid autoperiod | PASS |
| GATE-03 Event coverage hierarchy | PASS — implemented |
| GATE-04 Narrow harmonic set {0.5,1,2} | PASS |
| GATE-05 Native PDCSAP primary | PASS |
| GATE-06 Single-planet cohort | PASS — corrected (Phase 5) |
| GATE-07 Sector baseline ≥20d | PASS |
| GATE-08 N=100 cohort | PASS |
| GATE-09 Frequency grid serialization | PASS |
| GATE-10 SHA256 provenance | PASS |
| GATE-11 SDE method selection | **AWAITING USER DECISION** |
| GATE-12 Composite epoch/phase matching | PASS — implemented |

---

## Phase 3 — GATE-03 Event Coverage Implementation (Complete)

`evaluate_event_coverage()` in `src/tess_benchmark/evaluation/recovery.py`:

- **Interior:** f_temporal ≥ 0.50 AND N_valid ≥ 5 → `is_adequate_interior = True`
- **Boundary:** f_temporal ≥ 0.30 AND N_valid ≥ 3 → `is_adequate_boundary = True` (diagnostic track only)
- **Gap events:** below both thresholds → `exclusion_reason` recorded
- Each event mutually exclusive: interior XOR boundary

**6 new tests in `tests/test_recovery.py`:** threshold boundary, N_valid-4 rejection, <30% boundary exclusion, mutual exclusivity, empty input guard, invalid period/duration guard.

---

## Phase 4 — GATE-12 Composite Epoch Matching Implementation (Complete)

Tolerance formula (approved GATE-12 Option C bounded composite):

```
t0_tol = min(0.50 * T_dur, sqrt((0.25 * T_dur)^2 + (3 * sigma_tmid)^2))
```

Phase matching: circular phase residual φ in [0, 0.5] via modular arithmetic.

**10 new tests in `tests/test_recovery.py`:** σ=0 degeneration, cap binding, invalid inputs (NaN/0/inf/negative), wraparound, boundary acceptance, just-outside rejection, invalid ephemeris, multi-planet one-to-one, duplicate candidate constraint.

---

## Phase 5 — GATE-06 Primary Host Cohort Correction (Complete)

**Problem:** 9/50 confirmed hosts had sy_pnum > 1 in NASA ps table.

**Removed (multi-planet, sy_pnum > 1):**

| Target | TIC | Sector |
|--------|-----|--------|
| WASP-94 A | 92352620 | 1 |
| TOI-125 | 52368076 | 2 |
| WASP-8 | 183532609 | 2 |
| TOI-178 | 251848941 | 2 |
| GJ 3090 | 262530407 | 2 |
| L 98-59 | 307210830 | 2 |
| TOI-431 | 31374837 | 5 |
| TOI-426 | 189013224 | 5 |
| TOI-469 | 33692729 | 6 |

**Admitted (all sy_pnum=1, all gates pass):**

| Target | TIC | Sector | Usable | Baseline |
|--------|-----|--------|--------|----------|
| WASP-23 | 170102285 | 6 | 0.927 | 21.77d |
| WASP-64 | 52640302 | 6 | 0.932 | 21.77d |
| WASP-49 | 306362738 | 6 | 0.931 | 21.77d |
| WASP-101 | 47911178 | 6 | 0.930 | 21.77d |
| HATS-4 | 59843967 | 6 | 0.932 | 21.77d |
| HD 202772 A | 290131778 | 1 | 0.906 | 27.74d |
| TOI-480 | 317548889 | 6 | 0.932 | 21.77d |
| DS Tuc A | 410214986 | 1 | 0.910 | 27.88d |
| HD 207496 | 290348383 | 13 | 0.841 | 25.33d |

All verified via NASA ps API (sy_pnum=1). 5 local + 4 newly downloaded from MAST.

**Corrected manifest:** `results/real_data_stage2/stage2_corrected_cohort_manifest.csv`  
**Replacement audit:** `results/real_data_stage2/cohort_replacement_audit.csv`

**Corrected cohort: 50 confirmed single-planet hosts (sy_pnum=1) + 50 observational controls = 100 total.**

---

## Test Suite

**98 passed** (protocol-critical, no torch required)  
Tests added this session: **16** (GATE-03: 6, GATE-12: 10)

---

## Remaining Blockers

| Blocker | Required Action |
|---------|----------------|
| **GATE-11 SDE method** | User must select Option A, B, C, or D for formal Stage 3 |
| **Formal benchmark authorization** | Explicit user sign-off required |

---

*Report generated 2026-10-03. Formal Stage 3 benchmark NOT yet authorized.*
