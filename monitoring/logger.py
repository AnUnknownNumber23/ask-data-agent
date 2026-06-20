"""Structured logging — file + console, timestamps, request IDs."""
import logging
import os
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(level: str = "INFO", log_dir: str = "./data/logs") -> logging.Logger:
    """Configure root logger with file + console handlers. Returns module logger."""

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("ask-data-agent")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Prevent duplicate handlers on reload
    if root.handlers:
        return root

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — daily rotation by filename
    today = datetime.now().strftime("%Y-%m-%d")
    fh = logging.FileHandler(log_path / f"agent-{today}.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    return root


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a module."""
    return logging.getLogger(f"ask-data-agent.{name}")
