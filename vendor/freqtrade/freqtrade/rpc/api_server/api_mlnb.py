# mlnb: brain state endpoints (fork workstream E2, 2026-07-10).
#
# Serves the brain's sidecar state SAME-ORIGIN for the FreqUI "Brain Cockpit":
#   GET /api/v1/mlnb/feed      — recent mind events (the brain narrating itself)
#   GET /api/v1/mlnb/funnel    — last Broker-Sense funnel cycle per market (stages, reasons)
#   GET /api/v1/mlnb/tailgate  — live ratchet locks + the learned trail distances
#   GET /api/v1/mlnb/xray      — entry-time decision snapshot for one trade (pair+segment+open_ts)
#
# READ-ONLY over files the brain processes own (trading.state JSON); this API never
# mutates brain state. Auth rides the same basic/JWT dependency as the rest of /api/v1.
# Everything degrades to an empty-but-honest payload when a sidecar is missing.
from __future__ import annotations

from fastapi import APIRouter, Query

from freqtrade.rpc.api_server.mlnb_sidecar import load_state_json


router = APIRouter()


def _config() -> dict:
    from freqtrade.rpc.api_server.webserver import ApiServer

    return ApiServer._config or {}


@router.get("/mlnb/feed", tags=["mlnb"])
def mlnb_feed(limit: int = Query(40, ge=1, le=200)):
    events = load_state_json(_config(), "mind_events.json", []) or []
    if isinstance(events, dict):                    # tolerate {"events": [...]} shape
        events = events.get("events") or []
    return {"events": events[-limit:], "n": len(events)}


@router.get("/mlnb/funnel", tags=["mlnb"])
def mlnb_funnel():
    return {"status": load_state_json(_config(), "broker_sense_status.json", {}) or {}}


@router.get("/mlnb/tailgate", tags=["mlnb"])
def mlnb_tailgate():
    return {
        "locks": load_state_json(_config(), "profit_tailgate_locks.json", {}) or {},
        "learned": load_state_json(_config(), "profit_tailgate.json", {}) or {},
    }


@router.get("/mlnb/xray", tags=["mlnb"])
def mlnb_xray(
    pair: str,
    segment: str = Query("futures"),
    open_ts: float = Query(..., description="trade open timestamp (seconds or ms)"),
):
    """Entry-time decision context for one trade — what the brain saw when it entered."""
    data = load_state_json(_config(), "crypto_entry_meta.json", {}) or {}
    rows = data.get(f"{(segment or 'futures').lower()}|{pair}") or []
    ts = open_ts / 1000.0 if open_ts > 1e11 else open_ts
    best = min(rows, key=lambda r: abs(r.get("ts", 0) - ts), default=None)
    if best and abs(best.get("ts", 0) - ts) <= 15 * 60:
        return {"found": True, "recorded_ts": best.get("ts"), "meta": best.get("meta")}
    return {"found": False, "meta": None}
