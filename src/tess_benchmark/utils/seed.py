"""
Reproducibility utilities for random seed management.
"""
import os
import random
import numpy as np
import torch


def set_seed(seed: int = 42) -> None:
    """
    Set random seeds across Python's built-in random, NumPy, PyTorch, and OS environment.

    Parameters
    ----------
    seed : int
        The integer seed to use.
    """
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        # Guarantee determinism where possible
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
