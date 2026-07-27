"""
Structured logging utilities using loguru.

- Console: human-friendly, colored output (stdout)
- File: structured JSON lines for ingestion (logs/monospace.log)
- Integrates standard logging (redirects to loguru)
- Exposes `configure_logging()` to be called at startup and `get_logger(name)` to obtain a bound logger.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger as _logger

from .constants import LOG_DIR, LOG_DEFAULT_LEVEL, LOG_ROTATION, LOG_RETENTION

# Keep a flag so repeated calls to configure_logging() are idempotent.
_CONFIGURED = False


class InterceptHandler(logging.Handler):
    """
    Catch standard logging records and forward them to loguru.
    This preserves existing libraries that use logging.getLogger(...).
    """

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - simple forwarder
        try:
            level = _logger.level(record.levelname).name
        except Exception:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        # Find the first frame that is not part of logging machinery
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        record_dict = record.__dict__.copy()
        # Forward record to loguru with extra fields preserved
        _logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage(), **{"record": record_dict})


def _ensure_log_dir() -> Path:
    path = Path(LOG_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_logging(level: Optional[str] = None) -> None:
    """
    Configure loguru and redirect standard logging into it.

    - idempotent: calling multiple times will not duplicate handlers
    - level: override default level (e.g., "DEBUG")
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = level or LOG_DEFAULT_LEVEL

    # Clear existing handlers added by previous configure runs to avoid duplication.
    _logger.remove()

    # Ensure log directory exists
    log_dir = _ensure_log_dir()
    log_file = log_dir / "monospace.log"

    # Console handler: readable output for developers/operators
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level> "
        "{exception}"
    )
    _logger.add(sys.stdout, colorize=True, format=console_format, level=level, enqueue=True)

    # File handler: structured logs (JSON lines) for ingestion and long-term storage
    # We use rotation/retention settings from constants to manage disk usage.
    try:
        _logger.add(
            str(log_file),
            rotation=LOG_ROTATION,
            retention=LOG_RETENTION,
            level=level,
            serialize=True,
            enqueue=True,
            backtrace=True,
            diagnose=False,
        )
    except Exception:
        # Best-effort fallback to a non-serialized file if serialization fails in some environments
        _logger.add(str(log_file.with_suffix(".txt")), rotation=LOG_ROTATION, retention=LOG_RETENTION, level=level, enqueue=True)

    # Redirect the standard logging module to loguru
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Optionally silence overly verbose third-party loggers here:
    for name in ("asyncio", "aiosqlite", "urllib3", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)
        logging.getLogger(name).propagate = True

    _CONFIGURED = True
    _logger.debug("Logging configured", level=level, log_file=str(log_file))


def get_logger(name: Optional[str] = None):
    """
    Return a loguru logger bound with the module/name.

    Usage:
        LOG = get_logger(__name__)
        LOG.info("Hello", key=value)
    """
    if name:
        return _logger.bind(module=name)
    return _logger
