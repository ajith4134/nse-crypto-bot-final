"""tests/test_dream_replay.py — Dream-Trainer phase-2 worldmodel replay (2026-07-10)."""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd


def _df(n=200, drift=0.001, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.006, n)))
    return pd.DataFrame({"open": close, "high": close * 1.003, "low": close * 0.997,
                         "close": close, "volume": rng.uniform(1e3, 5e3, n)})


def test_imagine_replay_pre_entry_only(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    now = dt.datetime.now().isoformat()
    rows = [{"symbol": "AAA/USDT", "direction": "LONG", "r_multiple": 1.2,
             "net_pnl": 5, "entry_datetime": now},
            {"symbol": "BBB/USDT", "direction": "SHORT", "r_multiple": -0.8,
             "net_pnl": -4, "entry_datetime": now}]
    (tmp_path / "journal.json").write_text(json.dumps(rows))
    from trading.brain import dreamer
    monkeypatch.setattr(dreamer, "_candles_before", lambda s, t, tf="5m", limit=400: _df())
    sec = dreamer.imagine_replay(n_trades=2)
    assert sec["n_replayed"] == 2
    assert all(r["wm_action"] in ("HOLD", "ENTER_LONG", "ENTER_SHORT", "EXIT",
                                  "TIGHTEN_STOP", "SCALE_OUT") for r in sec["replays"])
    # persisted beside the phase-1 lessons
    assert tstate.load_json("dream_lessons.json", {}).get("imagination")


def test_old_trades_skipped_never_replayed_on_future_data(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    rows = [{"symbol": "OLD/USDT", "direction": "LONG", "r_multiple": 1.0,
             "net_pnl": 1, "entry_datetime": "2026-01-01T00:00:00"}]
    (tmp_path / "journal.json").write_text(json.dumps(rows))
    from trading.brain import dreamer
    monkeypatch.setattr(dreamer, "_candles_before",
                        lambda s, t, tf="5m", limit=400: None)   # window can't reach back
    sec = dreamer.imagine_replay(n_trades=1)
    assert sec["n_replayed"] == 0 and sec["n_skipped"] == 1
