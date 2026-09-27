"""Machine learning and deep learning models for transit detection."""
from .classical import ModelWrapper, build_classical_models
from .cnn1d import TransitCNN1DNet, CNN1DClassifier

__all__ = [
    "ModelWrapper",
    "build_classical_models",
    "TransitCNN1DNet",
    "CNN1DClassifier",
]
