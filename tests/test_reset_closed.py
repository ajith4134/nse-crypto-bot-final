"""tests/test_reset_closed.py — closed-trade reset is brain-safe + isolated.

Isolates state: monkeypatches trading.state.STATE_DIR to a temp dir so the real journal.json and
the live paper history are NEVER touched. A fake Freqtrade client verifies delete-via-REST without
a running bot.
"""
from __future__ import annotations

import json

import pytest

from trading import state
from trading.journal.reset import reset_closed_trades


class _FakeRest:
    def __init__(self, closed):
        self._closed = closed
        self.deleted = []

    def delete_trade(self, tid):
        self.deleted.append(tid)
        return {"result": f"deleted {tid}"}


class _FakeClient:
    def __init__(self, closed):
        self._closed = closed
        self._rest = _FakeRest(closed)

    def closed_trades(self):
        return self._closed

    def _client(self):
        return self._rest


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "STATE_DIR", tmp_path)      # never touch the real journal/backups
    return tmp_path


def test_bad_confirm_deletes_nothing(isolated_state):
    state.save_json("journal.json", [{"trade_id": "x", "entry_price": 1}])
    client = _FakeClient([{"trade_id": 7}])
    out = reset_closed_trades(confirm="nope", client=client)
    assert out["ok"] is False
    assert state.load_json("journal.json", []) == [{"trade_id": "x", "entry_price": 1}]  # intact
    assert client._rest.deleted == []                       # no freqtrade deletes


def test_reset_clears_journal_and_freqtrade_and_backs_up(isolated_state):
    state.save_json("journal.json", [{"trade_id": "a"}, {"trade_id": "b"}])
    closed = [{"trade_id": 1}, {"trade_id": 2}, {"trade_id": 3}]
    client = _FakeClient(closed)
    out = reset_closed_trades(confirm="RESET", client=client)

    assert out["ok"] is True
    assert out["journal_cleared"] == 2
    assert out["freqtrade_deleted"] == 3
    assert out["freqtrade_failed"] == 0
    assert client._rest.deleted == [1, 2, 3]                # all closed trades deleted via REST
    assert state.load_json("journal.json", None) == []      # journal emptied

    # backups written + recoverable
    assert len(out["backups"]) == 2
    backups = sorted((isolated_state / "backups").glob("*.bak.json"))
    assert len(backups) == 2
    journal_bak = next(b for b in backups if b.name.startswith("journal"))
    assert json.loads(journal_bak.read_text()) == [{"trade_id": "a"}, {"trade_id": "b"}]


def test_case_insensitive_confirm(isolated_state):
    state.save_json("journal.json", [{"trade_id": "a"}])
    out = reset_closed_trades(confirm="  reset  ", client=_FakeClient([]))
    assert out["ok"] is True
    assert out["journal_cleared"] == 1


def test_empty_journal_no_backup_no_crash(isolated_state):
    state.save_json("journal.json", [])
    out = reset_closed_trades(confirm="RESET", client=_FakeClient([]))
    assert out["ok"] is True
    assert out["journal_cleared"] == 0
    assert out["freqtrade_deleted"] == 0
    assert out["backups"] == []                             # nothing to back up
