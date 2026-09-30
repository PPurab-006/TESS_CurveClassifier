# Post-Audit Benchmark Repair: Provenance Note

## 1. Commit Sequence and Audit Manifest Reconciliation

This note documents and resolves the Git commit provenance discrepancy noted between `results/audit/reproducibility_manifest.json` and the repository commit history:

- **Pre-Audit Scaffold Commit (`b9602ad`)**:
  - Commit message: `feat: initial repository scaffold, synthetic validation suite, ML benchmark, and test harness`
  - This commit established the initial codebase, unit tests, model wrappers, and initial benchmark dataset generation scripts.
- **Audit Verification Execution**:
  - During the independent software audit, the auditor executed tests, data verification, and shortcut diagnostics against the working tree of `b9602ad`.
  - The audit script generated `results/audit/reproducibility_manifest.json`, recording `"git_commit": "b9602ad"` as the code state under inspection.
- **Audit Report Commit (`46c0b3b`)**:
  - Commit message: `audit: independent research software audit report, reproducibility manifest, and consistency verification`
  - Committing the audit report, test results (`results/audit/test_results.txt`), consistency report, shortcut diagnostics, and reproducibility manifest produced commit `46c0b3b`.
- **Reconciliation Invariant**:
  - `b9602ad` is the exact commit representing the pre-audit code and historical benchmark artifacts.
  - `46c0b3b` is the Git commit containing the audit evaluation and its findings.
  - In strict compliance with non-rewriting rules for independent audit records, `results/audit/reproducibility_manifest.json` remains unmodified. All post-audit repair activities and manifests are tracked independently starting from commit `46c0b3b`.

## 2. Historical vs. Post-Repair Artifact Separation

To maintain scientific integrity and auditability, all historical artifacts remain untouched:
- Historical synthetic dataset: `data/processed/` (`synthetic_light_curves.pkl`, `features_tabular.csv`, `phase_vectors.npy`)
- Historical benchmark metrics: `results/metrics/` (`model_comparison.csv`, `bls_benchmark.json`, `robustness_suite.csv`)
- Historical audit diagnostics: `results/audit/` (`shortcut_diagnostics.json`, `audit_report.md`, `bls_consistency_report.md`)

All post-audit repaired artifacts are generated into dedicated directories:
- Clean repaired synthetic dataset: `data/processed/post_audit_synthetic/`
- Repaired benchmark results & reports: `results/post_audit_repair/`
- Repaired diagnostic figures: `results/post_audit_repair/plots/`
