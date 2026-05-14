import logging
import os
from logging.handlers import RotatingFileHandler

from app.config import get_data_dir

_logger = None


def get_logger(name: str = "cloud_training") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    _logger = logging.getLogger(name)
    if _logger.handlers:
        return _logger

    _logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    _logger.addHandler(ch)

    try:
        log_dir = get_data_dir("logs_path")
        log_file = os.path.join(log_dir, "app.log")
        fh = RotatingFileHandler(
            log_file, maxBytes=100 * 1024 * 1024, backupCount=10, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        _logger.addHandler(fh)
    except Exception:
        pass

    return _logger
