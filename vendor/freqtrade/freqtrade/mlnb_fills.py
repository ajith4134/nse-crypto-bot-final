# mlnb: fill-time journal stamping (fork workstream E4, 2026-07-10).
#
# The brain's journal used to be reconstructed AFTER the fact by freqtrade_ingest polling
# the REST API — entry-time context risked drifting from fill truth (the 2026-07-07
# label-honesty bug class: live values stamped onto old trades). This module appends one
# JSON line per REAL fill event, at the moment the engine confirms it, to
# <state>/mlnb_fills.jsonl — an append-only, engine-authored record the ingest side can
# trust as ground truth for fill price/time/amount and merge with crypto_entry_meta.json.
#
# Never raises into the bot; kill-switch "mlnb_fill_journal": false.
from __future__ import annotations

import json
import logging
import time


logger = logging.getLogger(__name__)

FILLS_FILE = "mlnb_fills.jsonl"


def record_fill(config: dict, trade, order, event: str) -> None:
    """Append one fill event ('entry' | 'exit'). Best-effort, silent on failure."""
    try:
        if not (config or {}).get("mlnb_fill_journal", True):
            return
        from freqtrade.rpc.api_server.mlnb_sidecar import state_dir

        rec = {
            "ts": time.time(),
            "event": event,
            "trade_id": trade.id,
            "pair": trade.pair,
            "segment": (config or {}).get("mlnb_segment") or "futures",
            "is_short": bool(trade.is_short),
            "fill_price": order.safe_price,
            "amount": order.safe_amount_after_fee,
            "enter_tag": trade.enter_tag,
            "exit_reason": trade.exit_reason if event == "exit" else None,
            "leverage": trade.leverage,
            "stake_amount": trade.stake_amount,
        }
        path = state_dir(config) / FILLS_FILE
        with path.open("a") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
    except Exception:                    # noqa: BLE001 — journaling must never break trading
        logger.debug("mlnb fill journal write failed", exc_info=True)
