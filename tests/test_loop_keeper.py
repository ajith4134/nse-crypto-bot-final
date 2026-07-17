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


# ── wedge detection (2026-07-17): alive-but-unresponsive, the failure pgrep cannot see ──

def _wedge_keeper(monkeypatch, tmp_path, responsive):
    """Keeper whose processes are all ALIVE, with a probe answering `responsive`."""
    lk = _fresh_keeper(monkeypatch, tmp_path)
    monkeypatch.setattr(lk, "_alive", lambda pat: True)
    monkeypatch.setattr(lk, "_responsive", lambda url: responsive)
    monkeypatch.setattr(lk.time, "sleep", lambda s: None)
    killed = []
    monkeypatch.setattr(lk, "_kill_wedged",
                        lambda name, pat: killed.append(name) or True)
    monkeypatch.setattr(lk.subprocess, "run", lambda *a, **k: None)
    return lk, killed


def test_responsive_process_is_never_killed(monkeypatch, tmp_path):
    lk, killed = _wedge_keeper(monkeypatch, tmp_path, responsive=True)
    for _ in range(lk.WEDGE_STRIKES + 2):
        lk.run_once()
    assert killed == []                             # healthy → hands off, no matter how long


def test_wedged_process_survives_early_strikes_then_dies(monkeypatch, tmp_path):
    """The safety property: this box idles at load ~15, so a slow probe is NORMAL. One (or two)
    unresponsive samples must never cost a restart — only sustained silence may."""
    lk, killed = _wedge_keeper(monkeypatch, tmp_path, responsive=False)
    for strike in range(1, lk.WEDGE_STRIKES):
        lk.run_once()
        assert killed == [], f"killed on strike {strike} — premature"
    lk.run_once()                                   # WEDGE_STRIKES reached
    assert "dashboard" in killed and "freqtrade" in killed


def test_strikes_persist_across_runs_and_reset_on_recovery(monkeypatch, tmp_path):
    """Each cron run is a fresh process, so strikes only work if they round-trip through state —
    and a process that comes back must start clean, never carrying a stale strike toward a kill."""
    lk, killed = _wedge_keeper(monkeypatch, tmp_path, responsive=False)
    lk.run_once()
    from trading import state as tstate
    assert tstate.load_json("loop_keeper.json", {})["strikes"]["dashboard"] == 1
    lk.run_once()
    assert tstate.load_json("loop_keeper.json", {})["strikes"]["dashboard"] == 2

    monkeypatch.setattr(lk, "_responsive", lambda url: True)   # recovered before the kill
    lk.run_once()
    assert tstate.load_json("loop_keeper.json", {})["strikes"]["dashboard"] == 0
    assert killed == []


def test_off_flag_blocks_wedge_kill(monkeypatch, tmp_path):
    lk, killed = _wedge_keeper(monkeypatch, tmp_path, responsive=False)
    off = tmp_path / ".loop_keeper_off"
    off.write_text("")
    monkeypatch.setattr(lk, "OFF_FLAG", str(off))
    for _ in range(lk.WEDGE_STRIKES + 1):
        lk.run_once()
    assert killed == []                             # owner kill-switch outranks the wedge path


def test_http_error_counts_as_responsive(monkeypatch, tmp_path):
    """The dashboard answers /api/health with 401. A reply is a reply: the probe asks whether the
    event loop still turns, not whether we are authorized. Treating 401 as dead would SIGKILL a
    perfectly healthy dashboard every 15 minutes."""
    import urllib.error
    lk = _fresh_keeper(monkeypatch, tmp_path)

    def _raise_401(url, timeout=None):
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)
    monkeypatch.setattr(lk.urllib.request, "urlopen", _raise_401)
    assert lk._responsive("http://127.0.0.1:8000/api/health") is True


def test_unreachable_port_counts_as_wedged(monkeypatch, tmp_path):
    """A port nothing listens on is the honest negative control for the probe."""
    import socket
    lk = _fresh_keeper(monkeypatch, tmp_path)
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()                                       # nothing listening now
    monkeypatch.setattr(lk, "PROBE_TIMEOUT", 2)
    assert lk._responsive(f"http://127.0.0.1:{port}/") is False
