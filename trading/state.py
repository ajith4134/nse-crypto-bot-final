"""trading/state.py — tiny JSON state persistence for the trading package.

All mutable trading state (watchlist, instrument cache, toggle state) lives under
`trading/state/` as plain JSON so it survives restarts and is human-inspectable.
The directory is gitignored (no secrets, but it IS machine-local runtime state).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

STATE_DIR = Path(__file__).resolve().parent / "state"


def _path(name: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / name


def load_json(name: str, default: Any) -> Any:
    """Load JSON state file `name`, or return `default` if absent/corrupt."""
    p = _path(name)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def save_json(name: str, data: Any) -> None:
    """Atomically write `data` as JSON to state file `name`."""
    p = _path(name)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, p)  # atomic on POSIX
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
