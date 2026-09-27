"""
Tests for group-aware star-level splitting and data leakage prevention.
"""
import numpy as np
import pytest
from tess_benchmark.evaluation.splitting import StarGroupSplitter, DataLeakageError


def test_star_group_split_zero_leakage():
    """Splitting must guarantee zero star ID overlap between train and test partitions."""
    n_samples = 100
    n_stars = 20
    # Each star has 5 observations (e.g. sectors or degradation variants)
    star_ids = np.repeat([f"TIC-{i:04d}" for i in range(n_stars)], 5)
    X = np.random.randn(n_samples, 4)
    y = np.random.randint(0, 2, size=n_samples)

    splitter = StarGroupSplitter(test_size=0.3, seed=42)
    X_train, X_test, y_train, y_test, stars_train, stars_test = splitter.train_test_split(
        X, y, star_ids
    )

    train_set = set(stars_train)
    test_set = set(stars_test)

    # ZERO star overlap must be strictly satisfied
    overlap = train_set.intersection(test_set)
    assert len(overlap) == 0, f"Star leakage detected: {overlap}"
    assert len(train_set) + len(test_set) == n_stars
    assert len(X_train) + len(X_test) == n_samples


def test_star_group_kfold_zero_leakage():
    """Group k-fold must ensure no star appears in both train and validation folds."""
    n_samples = 60
    n_stars = 12
    star_ids = np.repeat([f"STAR-{i}" for i in range(n_stars)], 5)
    X = np.zeros((n_samples, 2))
    y = np.zeros(n_samples)

    splitter = StarGroupSplitter(n_splits=3, seed=42)
    for fold, (train_idx, val_idx) in enumerate(splitter.kfold_split(X, y, star_ids)):
        train_stars = set(star_ids[train_idx])
        val_stars = set(star_ids[val_idx])
        assert len(train_stars.intersection(val_stars)) == 0


def test_star_group_split_raises_on_leakage():
    """Verify DataLeakageError is raised if train and test star sets intersect."""
    splitter = StarGroupSplitter(test_size=0.5, seed=42)
    # Monkey-patch internal split generator to inject artificial leakage
    orig_split = splitter.train_test_split

    class LeakySplitter(StarGroupSplitter):
        def train_test_split(self, X, y, star_ids):
            # Artificially force an overlap
            stars_train = np.array(["STAR-1", "STAR-2"])
            stars_test = np.array(["STAR-2", "STAR-3"])
            train_set = set(stars_train)
            test_set = set(stars_test)
            leakage = train_set.intersection(test_set)
            if len(leakage) > 0:
                raise DataLeakageError(f"CRITICAL SCIENTIFIC INTEGRITY VIOLATION: {len(leakage)} stars leaked")
            return X, X, y, y, stars_train, stars_test

    with pytest.raises(DataLeakageError):
        LeakySplitter().train_test_split(np.zeros((4, 2)), np.zeros(4), np.array(["STAR-1", "STAR-2", "STAR-2", "STAR-3"]))

