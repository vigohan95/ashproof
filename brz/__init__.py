"""Ashproof: containment-first agent execution on Vultr."""

from __future__ import annotations

import sys
from pathlib import Path

__version__ = "0.1.0"

# ``brz_runner`` (the in-VM runner, kept in sandbox/runner so it ships as a standalone stdlib package)
# is installed as a top-level package by pyproject's package-dir mapping. When running from a plain
# checkout without `pip install -e .`, make it importable too.
try:
    import brz_runner  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - exercised only in un-installed checkouts
    _runner_dir = Path(__file__).resolve().parent.parent / "sandbox" / "runner"
    if (_runner_dir / "brz_runner").is_dir():
        sys.path.append(str(_runner_dir))
