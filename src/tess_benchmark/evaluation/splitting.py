"""
Group-Aware Train/Test Data Splitting Protocol.

Enforces star-level isolation to prevent data leakage between training and testing.
Observations, sectors, or synthetic degraded realizations of the same target star
MUST never appear simultaneously in both train and test partitions.
"""
from typing import Tuple, Generator, List, Dict, Any, Set
import numpy as np
from sklearn.model_selection import GroupShuffleSplit, GroupKFold


class DataLeakageError(RuntimeError):
    """Raised when star IDs or target instances overlap across data splits."""
    pass


class StarGroupSplitter:
    """
    Partitions datasets while strictly guaranteeing star-level grouping.

    Parameters
    ----------
    test_size : float
        Fraction of groups reserved for the test split (default 0.25).
    n_splits : int
        Number of cross-validation folds if performing CV (default 5).
    seed : int
        Reproducible random seed.
    """

    def __init__(self, test_size: float = 0.25, n_splits: int = 5, seed: int = 42):
        self.test_size = test_size
        self.n_splits = n_splits
        self.seed = seed

    def train_test_split(
        self,
        X: np.ndarray,
        y: np.ndarray,
        star_ids: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Partition features, labels, and star identifiers into train and test sets.

        Parameters
        ----------
        X : np.ndarray
            Feature matrix (N, D).
        y : np.ndarray
            Binary labels (N,).
        star_ids : np.ndarray
            Star identifier for each sample (N,).

        Returns
        -------
        Tuple[X_train, X_test, y_train, y_test, stars_train, stars_test]

        Raises
        ------
        DataLeakageError
            If any star ID appears in both training and test partitions.
        """
        star_ids = np.asarray(star_ids)
        splitter = GroupShuffleSplit(n_splits=1, test_size=self.test_size, random_state=self.seed)
        train_idx, test_idx = next(splitter.split(X, y, groups=star_ids))

        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        stars_train, stars_test = star_ids[train_idx], star_ids[test_idx]

        # Explicit scientific integrity verification
        train_set = set(stars_train)
        test_set = set(stars_test)
        leakage = train_set.intersection(test_set)
        if len(leakage) > 0:
            raise DataLeakageError(
                f"CRITICAL SCIENTIFIC INTEGRITY VIOLATION: {len(leakage)} stars leaked "
                f"between train and test splits! Leaked IDs: {list(leakage)[:5]}"
            )

        return X_train, X_test, y_train, y_test, stars_train, stars_test

    def kfold_split(
        self,
        X: np.ndarray,
        y: np.ndarray,
        star_ids: np.ndarray
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Generate group-k-fold indices with zero star overlap across folds.
        """
        star_ids = np.asarray(star_ids)
        gkf = GroupKFold(n_splits=self.n_splits)

        for train_idx, val_idx in gkf.split(X, y, groups=star_ids):
            train_stars = set(star_ids[train_idx])
            val_stars = set(star_ids[val_idx])
            leakage = train_stars.intersection(val_stars)
            if len(leakage) > 0:
                raise DataLeakageError(
                    f"Star leakage detected in CV split: {len(leakage)} stars overlap."
                )
            yield train_idx, val_idx
