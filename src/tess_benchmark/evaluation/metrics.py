"""
Comprehensive Evaluation Metrics for Transit Detection and Candidate Vetting.

CRITICAL ASTROPHYSICAL DISTINCTIONS:
1. Transit Detection: Determining whether a periodic flux dip consistent with an occultation exists in the time series.
2. Candidate Classification: Distinguishing planetary transit candidates from false positives (e.g., eclipsing binaries, background blends, stellar variability).
3. Planet Validation: Rigorous statistical ruling out of all astrophysical false-positive scenarios (e.g. using TRICERATOPS, VESPA, high-resolution imaging, and radial velocity follow-up).
NO MACHINE LEARNING CLASSIFIER ALONE CAN INDEPENDENTLY VALIDATE AN EXOPLANET.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import numpy as np
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    average_precision_score,
    roc_auc_score,
    confusion_matrix,
)


@dataclass
class EvaluationReport:
    """
    Standardized metrics container for a model evaluation run.

    Attributes
    ----------
    model_name : str
        Name of the evaluated model or baseline.
    precision : float
        TP / (TP + FP)
    recall : float
        TP / (TP + FN) (Sensitivity / Transit Detection Rate)
    f1 : float
        Harmonic mean of precision and recall.
    specificity : float
        TN / (TN + FP)
    fpr : float
        FP / (FP + TN) (False Positive Rate)
    pr_auc : float
        Average Precision / Area under Precision-Recall curve.
    roc_auc : float
        Area under Receiver Operating Characteristic curve.
    tp : int
        True positives count.
    fp : int
        False positives count.
    tn : int
        True negatives count.
    fn : int
        False negatives count.
    train_time_sec : float
        Model training time in seconds.
    inference_latency_ms : float
        Average inference time per sample in milliseconds.
    """
    model_name: str
    precision: float
    recall: float
    f1: float
    specificity: float
    fpr: float
    pr_auc: float
    roc_auc: float
    tp: int
    fp: int
    tn: int
    fn: int
    train_time_sec: float = 0.0
    inference_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return asdict(self)


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray] = None,
    model_name: str = "Model",
    train_time_sec: float = 0.0,
    inference_latency_ms: float = 0.0
) -> EvaluationReport:
    """
    Compute rigorous binary classification and astrophysical detection metrics.

    Parameters
    ----------
    y_true : np.ndarray
        Ground-truth binary labels (0 or 1).
    y_pred : np.ndarray
        Predicted binary labels (0 or 1).
    y_proba : Optional[np.ndarray]
        Predicted probability of the positive class (1).
    model_name : str
        Name of the model.
    train_time_sec : float
        Training time in seconds.
    inference_latency_ms : float
        Inference latency per light curve in ms.

    Returns
    -------
    EvaluationReport
        Populated report instance.
    """
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    if y_proba is not None and len(np.unique(y_true)) > 1:
        pr_auc = float(average_precision_score(y_true, y_proba))
        roc_auc = float(roc_auc_score(y_true, y_proba))
    else:
        # Fall back to discrete prediction estimates if probabilities not provided
        pr_auc = float(prec)
        roc_auc = 0.5 * (rec + spec)

    return EvaluationReport(
        model_name=model_name,
        precision=prec,
        recall=rec,
        f1=f1,
        specificity=spec,
        fpr=fpr,
        pr_auc=pr_auc,
        roc_auc=roc_auc,
        tp=int(tp),
        fp=int(fp),
        tn=int(tn),
        fn=int(fn),
        train_time_sec=train_time_sec,
        inference_latency_ms=inference_latency_ms
    )
