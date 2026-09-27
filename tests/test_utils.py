"""
Tests for utilities: seed setting, logging, and configuration loading.
"""
from pathlib import Path
import pytest
import numpy as np
import torch
from tess_benchmark.utils.seed import set_seed
from tess_benchmark.utils.logging import get_logger
from tess_benchmark.utils.config import load_config


def test_set_seed():
    """Verify seed sets deterministic random states."""
    set_seed(42)
    val1 = np.random.rand()
    t1 = torch.rand(1).item()

    set_seed(42)
    val2 = np.random.rand()
    t2 = torch.rand(1).item()

    assert val1 == val2
    assert t1 == t2


def test_get_logger(tmp_path: Path):
    """Verify logger creation and file output."""
    log_file = tmp_path / "test.log"
    logger = get_logger("test_logger", log_file=log_file)
    logger.info("Test message for log")

    assert log_file.exists()
    content = log_file.read_text()
    assert "Test message for log" in content


def test_load_config():
    """Verify configuration loading from existing YAML."""
    config = load_config("configs/default.yaml")
    assert "project" in config
    assert config["project"]["name"] == "tess-transit-benchmark"
    assert config["project"]["seed"] == 42


def test_load_config_missing():
    """Missing config file must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("configs/nonexistent.yaml")
