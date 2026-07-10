# mlnb: decision inbox (fork workstream E3, 2026-07-10).
#
# PUSH instead of poll: the brain's funnel appends entry/exit decisions to
# <state>/decisions_inbox.jsonl (one JSON object per line, single-writer append-only);
# each segment bot consumes new lines at the top of its own process() iteration and
# executes them through the SAME RPC force-entry/force-exit machinery the REST API uses
# — so every engine guard (max trades, tradability, duplicate position) still applies.
#
# Why: REST /forceenter polling couples trade placement to HTTP availability and burns
# a round-trip per decision; the inbox survives API hiccups and keeps ordering.
#
# Idempotency/safety:
#  - per-segment byte-offset cursor (decisions_cursor_<segment>.json) — a line is
#    consumed exactly once, even across restarts;
#  - decisions carry ts; anything older than MAX_AGE_S is skipped as stale (a decision
#    made before downtime must not execute into a different market);
#  - never raises into the bot loop.
#
# Config flag: "mlnb_decision_inbox": true (default OFF — REST stays the driver until
# this path has soaked; the funnel side is gated by CRYPTO_DECISION_INBOX=1).
from __future__ import annotations

import json
import logging
from typing import Any


logger = logging.getLogger(__name__)

INBOX_FILE = "decisions_inbox.jsonl"
MAX_AGE_S = 900.0                       # stale-decision guard
_MAX_LINE = 65536


def _cursor_path(config: dict, segment: str):
    from freqtrade.rpc.api_server.mlnb_sidecar import state_dir

    return state_dir(config) / f"decisions_cursor_{segment}.json"


def _rpc(bot) -> Any:
    cached = getattr(bot, "_mlnb_rpc", None)
    if cached is None:
        from freqtrade.rpc.rpc import RPC

        cached = bot._mlnb_rpc = RPC(bot)
    return cached


def consume(bot) -> int:
    """Execute this segment's queued decisions. Returns how many were executed."""
    import time

    from freqtrade.rpc.api_server.mlnb_sidecar import state_dir

    config = bot.config
    segment = (config.get("mlnb_segment") or "futures").lower()
    inbox = state_dir(config) / INBOX_FILE
    try:
        size = inbox.stat().st_size
    except OSError:
        return 0
    cur_path = _cursor_path(config, segment)
    try:
        offset = int(json.loads(cur_path.read_text()).get("offset", 0))
    except (OSError, ValueError):
        offset = 0
    if offset > size:                    # inbox rotated/truncated → start over honestly
        offset = 0
    if offset == size:
        return 0

    executed, skipped = 0, 0
    now = time.time()
    with inbox.open("r") as fh:
        fh.seek(offset)
        for line in fh:
            if not line.endswith("\n") and len(line) < _MAX_LINE:
                break                    # partial tail write — leave for next iteration
            offset += len(line.encode())
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if (rec.get("segment") or "futures").lower() != segment:
                continue
            if now - float(rec.get("ts") or 0) > MAX_AGE_S:
                skipped += 1             # stale: decided before downtime — do not execute
                continue
            try:
                _execute(bot, rec)
                executed += 1
            except Exception as exc:     # noqa: BLE001 — one bad decision never kills the loop
                skipped += 1
                logger.warning("mlnb inbox: decision %s failed: %r", rec.get("id"), exc)
    try:
        cur_path.write_text(json.dumps({"offset": offset}))
    except OSError:
        logger.warning("mlnb inbox: cursor write failed for %s", segment)
    if executed or skipped:
        logger.info(
            "mlnb inbox[%s]: executed=%d skipped=%d (offset=%d)", segment, executed, skipped, offset
        )
    return executed


def _execute(bot, rec: dict) -> None:
    from freqtrade.enums import SignalDirection

    rpc = _rpc(bot)
    action = (rec.get("action") or "").lower()
    pair = rec.get("pair") or ""
    if action == "enter":
        side = SignalDirection.SHORT if (rec.get("side") or "").lower() == "short" \
            else SignalDirection.LONG
        rpc._rpc_force_entry(
            pair,
            None,
            order_type="market",
            order_side=side,
            stake_amount=rec.get("stake") or None,
            enter_tag=rec.get("enter_tag") or "mlnb_inbox",
        )
    elif action == "exit":
        # resolve open trade(s) for this pair inside THIS bot's segment scope.
        # trade_id semantics mirror the REST path: a specific id closes that trade,
        # "all"/absent closes EVERY open trade on the pair (2026-07-10 review fix —
        # first-match-only silently left multi-position pairs half-open).
        from freqtrade.persistence import Trade

        tid = str(rec.get("trade_id") or "all")
        if tid != "all":
            rpc._rpc_force_exit(tid)
        else:
            for trade in Trade.get_open_trades():
                if trade.pair == pair:
                    rpc._rpc_force_exit(str(trade.id))
    else:
        raise ValueError(f"unknown inbox action: {action!r}")
