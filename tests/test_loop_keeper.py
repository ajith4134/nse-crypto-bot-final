"""tests/test_loop_keeper.py — runtime self-heal keeper (2026-07-10)."""
from __future__ import annotations

import importlib
import sys


def _fresh_keeper(monkeypatch, tmp_path):
    import tools.loop_keeper as lk
    importlib.reload(lk)
    # isolate state writes away from the live trading/state dir
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    return lk


def test_all_alive_no_restart(monkeypatch, tmp_path):
    lk = _fresh_keeper(monkeypatch, tmp_path)
    monkeypatch.setattr(lk, "_alive", lambda pat: True)
    ran = []
    monkeypatch.setattr(lk.subprocess, "run",
                        lambda *a, **k: ran.append(a) or (_ for _ in ()).throw(
                            AssertionError("start_all must not run")))
    assert lk.run_once() == 0
    assert ran == []


def test_dead_loop_triggers_start_all(monkeypatch, tmp_path):
    lk = _fresh_keeper(monkeypatch, tmp_path)
    states = {"funnel_nse": [False, True]}          # dead on first check, alive after

    def fake_alive(pat):
        for name, seq in states.items():
            if lk.REQUIRED[name] == pat:
                return seq.pop(0) if seq else True
        return True
    monkeypatch.setattr(lk, "_alive", fake_alive)
    monkeypatch.setattr(lk.time, "sleep", lambda s: None)
    ran = []

    class _R:  # minimal CompletedProcess stand-in
        returncode = 0
    monkeypatch.setattr(lk.subprocess, "run", lambda *a, **k: ran.append(a[0]) or _R())
    assert lk.run_once() == 0                       # revived → healthy exit
    assert any("start_all.sh" in " ".join(map(str, c)) for c in ran)


def test_off_flag_blocks_restart(monkeypatch, tmp_path):
    lk = _fresh_keeper(monkeypatch, tmp_path)
    off = tmp_path / ".loop_keeper_off"
    off.write_text("")
    monkeypatch.setattr(lk, "OFF_FLAG", str(off))
    monkeypatch.setattr(lk, "_alive", lambda pat: False)
    ran = []
    monkeypatch.setattr(lk.subprocess, "run", lambda *a, **k: ran.append(a))
    lk.run_once()
    assert ran == []                                # disabled → observes, never restarts
