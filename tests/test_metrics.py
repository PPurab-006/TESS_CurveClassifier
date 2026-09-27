"""
Tests for scientific evaluation metrics and reporting.
"""
import numpy as np
from tess_benchmark.evaluation.metrics import compute_metrics, EvaluationReport


def test_compute_metrics_perfect():
    """Verify metrics calculation for perfect predictions."""
    y_true = np.array([0, 0, 1, 1])
    y_pred = np.array([0, 0, 1, 1])
    y_proba = np.array([0.05, 0.1, 0.9, 0.95])

    report = compute_metrics(y_true, y_pred, y_proba, model_name="PerfectModel")

    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.f1 == 1.0
    assert report.specificity == 1.0
    assert report.fpr == 0.0
    assert report.roc_auc == 1.0
    assert report.tp == 2
    assert report.tn == 2
    assert report.fp == 0
    assert report.fn == 0


def test_compute_metrics_mixed():
    """Verify metrics calculation with known false positives and false negatives."""
    y_true = np.array([0, 0, 1, 1])
    y_pred = np.array([0, 1, 0, 1])
    y_proba = np.array([0.2, 0.7, 0.3, 0.8])

    report = compute_metrics(y_true, y_pred, y_proba, model_name="TestModel")

    assert report.tp == 1
    assert report.fp == 1
    assert report.tn == 1
    assert report.fn == 1
    assert report.precision == 0.5
    assert report.recall == 0.5
    assert report.f1 == 0.5
    assert report.fpr == 0.5

    d = report.to_dict()
    assert d["model_name"] == "TestModel"
    assert "pr_auc" in d
