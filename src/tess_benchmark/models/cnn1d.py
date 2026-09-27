"""
Lightweight 1D Convolutional Neural Network (CNN) for Light-Curve Classification.

Implements a compact, regularized 1D CNN in PyTorch for classifying phase-folded
or fixed-length photometric flux sequences with low parameter count (~15k params)
to prevent overfitting on astrophysical time-series benchmarks.
"""
import time
from typing import Optional, Dict, Any, List, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset


class TransitCNN1DNet(nn.Module):
    """
    Compact 1D Convolutional Neural Network architecture.

    Parameters
    ----------
    input_channels : int
        Number of input channels (1 for flux series).
    sequence_length : int
        Length of the input sequence (e.g. 200 phase bins).
    dropout_rate : float
        Dropout probability.
    """

    def __init__(self, input_channels: int = 1, sequence_length: int = 200, dropout_rate: float = 0.3):
        super().__init__()
        self.features = nn.Sequential(
            # Block 1
            nn.Conv1d(input_channels, 16, kernel_size=5, stride=1, padding=2),
            nn.BatchNorm1d(16),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=2, stride=2),
            # Block 2
            nn.Conv1d(16, 32, kernel_size=5, stride=1, padding=2),
            nn.BatchNorm1d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=2, stride=2),
            # Block 3
            nn.Conv1d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool1d(1),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(p=dropout_rate),
            nn.Linear(64, 32),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout_rate),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Parameters
        ----------
        x : torch.Tensor of shape (B, 1, L)
            Batch of 1D light curve sequences.

        Returns
        -------
        torch.Tensor of shape (B, 1)
            Logits.
        """
        feat = self.features(x)
        logits = self.classifier(feat)
        return logits


class CNN1DClassifier:
    """
    High-level scikit-learn compatible wrapper for TransitCNN1DNet.

    Parameters
    ----------
    sequence_length : int
        Length of input sequences (default 200).
    epochs : int
        Number of training epochs (default 25).
    batch_size : int
        Mini-batch size (default 32).
    lr : float
        Learning rate (default 1e-3).
    device : Optional[str]
        Device identifier ('cuda', 'cpu', or auto-detected).
    seed : int
        Reproducible random seed.
    """

    def __init__(
        self,
        sequence_length: int = 200,
        epochs: int = 25,
        batch_size: int = 32,
        lr: float = 1e-3,
        device: Optional[str] = None,
        seed: int = 42
    ):
        self.name = "CNN1D"
        self.sequence_length = sequence_length
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.seed = seed

        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        torch.manual_seed(seed)
        self.net = TransitCNN1DNet(input_channels=1, sequence_length=sequence_length).to(self.device)
        self.train_time_sec: float = 0.0
        self.last_inference_latency_ms: float = 0.0
        self.loss_history: List[float] = []

    def _prepare_tensor(self, X: np.ndarray) -> torch.Tensor:
        """Convert input array to (N, 1, L) float tensor."""
        arr = np.asarray(X, dtype=np.float32)
        if arr.ndim == 2:
            arr = np.expand_dims(arr, axis=1)
        elif arr.ndim == 1:
            arr = arr.reshape(1, 1, -1)
        return torch.from_numpy(arr)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "CNN1DClassifier":
        """
        Train the 1D CNN on light curve sequences.

        Parameters
        ----------
        X : np.ndarray of shape (N, L)
            Array of photometric sequences.
        y : np.ndarray of shape (N,)
            Binary target labels (0 or 1).

        Returns
        -------
        CNN1DClassifier
            Self.
        """
        t0 = time.perf_counter()
        torch.manual_seed(self.seed)

        X_t = self._prepare_tensor(X)
        y_t = torch.from_numpy(np.asarray(y, dtype=np.float32)).unsqueeze(1)

        dataset = TensorDataset(X_t, y_t)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        # Handle class imbalance via pos_weight
        n_pos = float(torch.sum(y_t == 1.0))
        n_neg = float(torch.sum(y_t == 0.0))
        pos_weight = torch.tensor([n_neg / max(1.0, n_pos)], device=self.device)

        criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        optimizer = optim.AdamW(self.net.parameters(), lr=self.lr, weight_decay=1e-4)

        self.net.train()
        self.loss_history = []

        for epoch in range(self.epochs):
            epoch_loss = 0.0
            n_batches = 0
            for bx, by in loader:
                bx = bx.to(self.device)
                by = by.to(self.device)

                optimizer.zero_grad()
                out = self.net(bx)
                loss = criterion(out, by)
                loss.backward()
                optimizer.step()

                epoch_loss += float(loss.item())
                n_batches += 1

            avg_loss = epoch_loss / max(1, n_batches)
            self.loss_history.append(avg_loss)

        self.train_time_sec = float(time.perf_counter() - t0)

        # Calibrate optimal decision threshold on training predictions
        train_probs = self.score_probability(X)
        best_thresh = 0.5
        best_f1 = -1.0
        for thresh in np.linspace(0.1, 0.9, 17):
            pred = (train_probs >= thresh).astype(int)
            tp = int(np.sum((y == 1) & (pred == 1)))
            fp = int(np.sum((y == 0) & (pred == 1)))
            fn = int(np.sum((y == 1) & (pred == 0)))
            f1 = (2 * tp) / max(1, 2 * tp + fp + fn)
            if f1 > best_f1:
                best_f1 = f1
                best_thresh = float(thresh)
        self.best_threshold = best_thresh

        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict probability distribution [P(y=0), P(y=1)] for each sequence.
        """
        t0 = time.perf_counter()
        self.net.eval()
        X_t = self._prepare_tensor(X).to(self.device)

        with torch.no_grad():
            logits = self.net(X_t).squeeze(1)
            probs_pos = torch.sigmoid(logits).cpu().numpy()

        elapsed = time.perf_counter() - t0
        self.last_inference_latency_ms = float((elapsed / max(1, len(X))) * 1000.0)

        probs_neg = 1.0 - probs_pos
        return np.column_stack([probs_neg, probs_pos])

    def predict(self, X: np.ndarray, threshold: Optional[float] = None) -> np.ndarray:
        """Predict binary class labels using calibrated decision threshold."""
        if threshold is None:
            threshold = getattr(self, "best_threshold", 0.5)
        prob_pos = self.score_probability(X)
        return (prob_pos >= threshold).astype(int)

    def score_probability(self, X: np.ndarray) -> np.ndarray:
        """Return 1D array of positive class probabilities."""
        return self.predict_proba(X)[:, 1]
