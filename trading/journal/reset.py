"""trading/journal/reset.py — permanently wipe CLOSED-trade data, brain-safe (operator reset).

One deliberate, type-to-confirm action that clears the two places closed trades live, so the brain
can't keep learning on contaminated paper history:

  1. the brain's journal (`trading/state/journal.json`) — what TradeOutcomeNet trains on, and
  2. Freqtrade's OWN closed paper trades (tradesv3 sqlite) — deleted via Freqtrade's official REST
     `delete_trade` (bot-aware: it won't corrupt the DB or touch OPEN trades).

Before deleting, BOTH stores are backed up to `trading/state/backups/` (timestamped) so the wipe is
recoverable. OPEN trades and every other piece of state are left untouched. Never raises into a caller
beyond the explicit confirm guard.

    from trading.journal.reset import reset_closed_trades
    reset_closed_trades(confirm="RESET")   # anything else → refused, nothing deleted
"""
from __future__ import annotations

import json
import os
import time

from trading import state

CONFIRM_TOKEN = "RESET"


def _backup(name: str, data) -> str:
    backup_dir = state.STATE_DIR / "backups"        # resolved at call time (test-isolatable)
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = backup_dir / f"{name}.{ts}.bak.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return str(path)


def reset_closed_trades(*, confirm: str, journal_file: str = "journal.json",
                        delete_freqtrade: bool = True, client=None) -> dict:
    """Wipe closed-trade data (journal + Freqtrade history). Requires confirm == "RESET".

    Returns a summary {ok, journal_cleared, freqtrade_deleted, freqtrade_failed, backups, ...}.
    On a bad confirm token it deletes NOTHING and returns {ok: False, reason: ...}.
    """
    if str(confirm).strip().upper() != CONFIRM_TOKEN:
        return {"ok": False, "reason": f"confirm must be '{CONFIRM_TOKEN}' (nothing deleted)"}

    backups: list[str] = []
    out: dict = {"ok": True}

    # 1) brain journal.json — back up, then clear to an empty list (NSE + crypto closed rows)
    try:
        prev = state.load_json(journal_file, [])
        n_journal = len(prev) if isinstance(prev, list) else 0
        if n_journal:
            backups.append(_backup("journal", prev))
        state.save_json(journal_file, [])
        out["journal_cleared"] = n_journal
    except Exception as e:
        out["journal_cleared"] = 0
        out["journal_error"] = f"{type(e).__name__}: {e}"

    # 2) Freqtrade's own CLOSED paper trades — delete via the official bot-safe REST endpoint
    deleted = failed = 0
    if delete_freqtrade:
        try:
            if client is None:
                from trading.crypto.engine_client import CryptoEngineClient
                client = CryptoEngineClient()
            closed = client.closed_trades()           # only is_open=False rows (OPEN untouched)
            if closed:
                backups.append(_backup("freqtrade_closed", closed))
            rc = client._client()
            for t in closed:
                tid = t.get("trade_id")
                if tid is None:
                    continue
                try:
                    rc.delete_trade(tid)
                    deleted += 1
                except Exception:
                    failed += 1
        except Exception as e:
            out["freqtrade_error"] = f"{type(e).__name__}: {e}"
    out["freqtrade_deleted"] = deleted
    out["freqtrade_failed"] = failed

    # 3) drop the brain's cached outcome net so it immediately retrains on the now-empty history
    try:
        from trading.brain import trade_features as _tf
        _tf._CACHE["count"] = -1
        _tf._CACHE["net"] = None
        out["brain_cache_reset"] = True
    except Exception:
        out["brain_cache_reset"] = False

    out["backups"] = backups
    return out
