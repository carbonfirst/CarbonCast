"""Bridge module for centralized logging utilities.

This module allows code under src/python to import the shared logger helpers
from the repository-level utils package without changing runtime entrypoints.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from utils.logger import configure_root_logging, get_logger  # noqa: E402,F401

__all__ = ["get_logger", "configure_root_logging"]
