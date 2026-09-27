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


def test_compute_metrics_all_negative():
    """Verify metrics calculation when all samples belong to negative class without divide-by-zero."""
    y_true = np.array([0, 0, 0, 0])
    y_pred = np.array([0, 0, 0, 0])
    report = compute_metrics(y_true, y_pred, model_name="AllNegModel")
    assert report.tp == 0
    assert report.fp == 0
    assert report.tn == 4
    assert report.fn == 0
    assert report.precision == 0.0
    assert report.recall == 0.0
    assert report.specificity == 1.0


def test_compute_metrics_serialization():
    """Verify EvaluationReport converts to JSON-serializable dictionary."""
    import json
    y_true = np.array([0, 1])
    y_pred = np.array([0, 1])
    report = compute_metrics(y_true, y_pred, model_name="JSONModel", train_time_sec=1.5, inference_latency_ms=0.5)
    d = report.to_dict()
    json_str = json.dumps(d)
    recovered = json.loads(json_str)
    assert recovered["model_name"] == "JSONModel"
    assert recovered["train_time_sec"] == 1.5
    assert recovered["inference_latency_ms"] == 0.5

