"""
Tests for classical ML model wrappers and 1D CNN classifier.
"""
import numpy as np
import pytest
from tess_benchmark.models.classical import build_classical_models
from tess_benchmark.models.cnn1d import CNN1DClassifier, TransitCNN1DNet


def test_classical_models_train_and_predict():
    """All classical models must fit, predict binary labels, and output probabilities."""
    rng = np.random.default_rng(42)
    n_samples = 60
    n_features = 10

    # Synthetic binary classification data
    X = rng.normal(0.0, 1.0, size=(n_samples, n_features))
    y = (X[:, 0] + X[:, 1] > 0).astype(int)

    models = build_classical_models(seed=42)

    for name, wrapper in models.items():
        wrapper.fit(X, y)
        assert wrapper.train_time_sec >= 0.0

        preds = wrapper.predict(X)
        assert preds.shape == (n_samples,)
        assert set(np.unique(preds)).issubset({0, 1})

        probs = wrapper.predict_proba(X)
        assert probs.shape == (n_samples, 2)
        assert np.allclose(np.sum(probs, axis=1), 1.0)
        assert wrapper.last_inference_latency_ms >= 0.0


def test_cnn1d_classifier_train_and_predict():
    """Compact 1D CNN must train with backprop and produce valid probabilities."""
    rng = np.random.default_rng(42)
    n_samples = 40
    seq_len = 50

    X = rng.normal(1.0, 0.01, size=(n_samples, seq_len))
    # Make class 1 have a dip at index 25
    y = np.zeros(n_samples, dtype=int)
    y[n_samples // 2:] = 1
    X[y == 1, 23:28] -= 0.05

    clf = CNN1DClassifier(sequence_length=seq_len, epochs=3, batch_size=16, lr=1e-3, seed=42)
    clf.fit(X, y)

    assert clf.train_time_sec > 0.0
    assert len(clf.loss_history) == 3

    probs = clf.predict_proba(X)
    assert probs.shape == (n_samples, 2)
    assert np.allclose(np.sum(probs, axis=1), 1.0, atol=1e-5)

    preds = clf.predict(X)
    assert preds.shape == (n_samples,)
    assert set(np.unique(preds)).issubset({0, 1})
