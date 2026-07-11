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


def update_json(name: str, updates: dict) -> dict:
    """Merge `updates` into dict state file `name` under a cross-process lock.

    load→modify→save from several processes loses keys (last-writer-wins clobbered
    another market's freshly written funnel tile, 2026-07-10) — this serializes the
    read-modify-write via flock on a sidecar .lock so each writer only replaces its
    OWN top-level keys. Returns the merged dict."""
    import fcntl

    lock = _path(f"{name}.lock")
    with open(lock, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            data = load_json(name, {})
            if not isinstance(data, dict):
                data = {}
            data.update(updates)
            save_json(name, data)
            return data
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def mutate_json(name: str, fn, default: Any = None) -> Any:
    """Apply `fn(data) -> data` to state file `name` under the same cross-process lock
    as update_json. For read-modify-write that top-level key merging can't express —
    e.g. INCREMENTING counters that several processes fold into (the direction truth
    ledger's bucket aggregates). `fn` must return the object to persist."""
    import fcntl

    lock = _path(f"{name}.lock")
    with open(lock, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            data = load_json(name, {} if default is None else default)
            data = fn(data)
            save_json(name, data)
            return data
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
