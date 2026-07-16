"""Write-only per-candidate VOTE LOG — every lens's simultaneous opinion, one JSONL row.

Why this exists (B1 "Ensemble Delusion" study, 2026-07-16): the truth ledger records each
lens's vote as an independent row at its own moment, so lens-vs-lens correlation can only be
estimated by joining on (symbol, time-bin) — sparse (27/66 pairs observed) and approximate.
The one place the full simultaneous vote vector exists is the executor's ``_reads`` list,
and it was never persisted. This module persists it.

Contract:
  • WRITE-ONLY. Nothing in the decision path reads this file; log() returns None and
    swallows every exception, so it can never alter, delay, or abort a trade.
  • One JSONL row per candidate evaluation: ts, symbol, market, segment, regime, lane,
    and the {source: p_up} vote map exactly as fused.
  • Bounded: rotated like the truth ledger's train log (keep the newest _MAX_KEEP lines).

Readers: research scripts (pairwise phi / effective rank), future diversity dashboards.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from trading import state

_FILE = "direction_votes.jsonl"
_MAX_LINES = 90_000            # rotate above this…
_MAX_KEEP = 60_000             # …keeping the newest 60k rows (~a few days of candidates)
_EST_BYTES_PER_LINE = 200      # cheap size-based rotation trigger, like _append_train


def _path() -> Path:
    return Path(state.STATE_DIR) / _FILE


def _enabled() -> bool:
    return os.environ.get("VOTE_LOG", "1") in ("1", "true", "TRUE", "yes", "on")


def log(*, symbol: str, market: str, segment: str, lane: str,
        reads, regime: str | None = None, decided: str | None = None) -> None:
    """Append one candidate's full vote vector. Best-effort: never raises.

    ``reads`` is the executor's list of ``(source, p_up)`` tuples; ``decided`` is the
    direction the decision path actually settled on (for later selection-bias checks).
    """
    if not _enabled() or not reads:
        return
    try:
        votes = {}
        for src, p in reads:
            try:
                votes[str(src)] = round(float(p), 4)
            except (TypeError, ValueError):
                continue
        if not votes:
            return
        row = json.dumps(
            {"ts": round(time.time(), 3), "symbol": symbol, "market": market,
             "segment": segment, "regime": regime, "lane": lane,
             "decided": decided, "votes": votes},
            separators=(",", ":"))
        p = _path()
        p.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(p, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, (row + "\n").encode())
        finally:
            os.close(fd)
        try:                                   # occasional rotation, cheap size check
            if p.stat().st_size > _MAX_LINES * _EST_BYTES_PER_LINE:
                keep = p.read_text(encoding="utf-8").splitlines()[-_MAX_KEEP:]
                tmp = p.with_suffix(".tmp")
                tmp.write_text("\n".join(keep) + "\n", encoding="utf-8")
                os.replace(tmp, p)
        except OSError:
            pass
    except Exception:
        pass
