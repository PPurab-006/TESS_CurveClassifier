"""
Logging utilities for TESS benchmark pipeline.
"""
import logging
import sys
from pathlib import Path
from typing import Optional


def get_logger(name: str = "tess_benchmark", log_file: Optional[Path] = None, level: int = logging.INFO) -> logging.Logger:
    """
    Configure and return a structured logger.

    Parameters
    ----------
    name : str
        Logger name.
    log_file : Optional[Path]
        Optional path to write log output to.
    level : int
        Logging level.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    has_console = any(
        type(h) is logging.StreamHandler for h in logger.handlers
    )
    if not has_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file is not None:
        log_path = Path(log_file).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        has_file = any(
            isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_path
            for h in logger.handlers
        )
        if not has_file:
            file_handler = logging.FileHandler(str(log_path))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger
