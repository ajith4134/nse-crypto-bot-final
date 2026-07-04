"""Extracted network / state / knowledge HTTP routes (dashboard/server.py split — Wave0-⑤ Group 3).

Same ``_srv(h)`` live-module accessor as dashboard/routes/{brain,trading}_ext.py: ``self.X`` → ``h.X``
and any bare server module-level helper/global (``STATE``, ``PHASE3``, ``ROOT``, ``_SYSMAP_CACHE``,
``_network_state_payload``, ``_network_trust_payload``, ``_network_refresh_start``) → ``_srv(h).X`` so a
moved body reaches the SAME live file paths / caches the inline code did (server runs as ``__main__``;
a plain import would bind a duplicate module copy).
"""
import json
import os
import sys
import time


def _srv(h):
    """The live server module, resolved off the handler instance — see brain_ext._srv for why."""
    return sys.modules[h.__class__.__module__]


def handle_state(h):
    """GET /api/state — the persisted phase-1 network state.json (nodes/edges/history), or an honest
    empty stub if it hasn't been generated yet."""
    srv = _srv(h)
    if os.path.exists(srv.STATE):
        with open(srv.STATE, "rb") as f:
            return h._send(200, f.read(), "application/json")
    return h._send(200, json.dumps(
        {"project": "no state yet — run `make phase1`",
         "nodes": [], "edges": [], "history": []}).encode(),
        "application/json")


def handle_state_routing(h):
    """GET /api/state/routing — the learned-routing / DGMG comparison (Hellsemble circles-of-difficulty
    + L2/L3 deep routers, DESlib KNORA/META-DES, conformal-gated, Caruana, deep-cascade, dynamic-bus,
    structure-search) computed by run_phase3.py into phase3.json."""
    srv = _srv(h)
    if os.path.exists(srv.PHASE3):
        with open(srv.PHASE3, "rb") as f:
            return h._send(200, f.read(), "application/json")
    return h._send(200, json.dumps(
        {"note": "no routing snapshot — run `python -m run_phase3` (writes phase3.json)",
         "results": []}).encode(), "application/json")


def handle_network_state(h):
    """GET /api/network/state — CORTEX B7 unified feed: network_state.json (run_network.py) + freshness."""
    return h._send(200, json.dumps(_srv(h)._network_state_payload()).encode(),
                   "application/json")


def handle_network_trust(h):
    """GET /api/network/trust — raw TrustLedger file (real per-node losses/counts — never fabricated)."""
    return h._send(200, json.dumps(_srv(h)._network_trust_payload()).encode(),
                   "application/json")


def handle_network_system(h):
    """GET /api/network/system — whole-brain system map: every subsystem with working/standby status
    from real evidence + wired edges (core/system_map.py). 20s cache on the server module."""
    srv = _srv(h)
    try:
        hit = srv._SYSMAP_CACHE
        if hit and (time.time() - hit[0]) < 20:
            return h._send(200, hit[1], "application/json")
        from core.system_map import system_map
        body = json.dumps(system_map()).encode()
        srv._SYSMAP_CACHE = (time.time(), body)
        return h._send(200, body, "application/json")
    except Exception as e:
        return h._send(200, json.dumps(
            {"note": f"system map unavailable: {type(e).__name__}: {e}"}).encode(),
            "application/json")


def handle_network_antioverfit(h):
    """GET /api/network/antioverfit — CANON-43 anti-overfit telemetry (backtests / free-params /
    research age)."""
    try:
        from trading.antioverfit import telemetry as _ao_tel
        payload = _ao_tel()
    except Exception as e:
        payload = {"note": f"antioverfit telemetry unavailable: {type(e).__name__}: {e}"}
    return h._send(200, json.dumps(payload).encode(), "application/json")


def handle_knowledge(h):
    """GET /api/knowledge — the persisted knowledge_state.json (knowledge-graph nodes/edges/stats),
    or an honest empty stub."""
    kp = os.path.join(_srv(h).ROOT, "knowledge_state.json")
    if os.path.exists(kp):
        with open(kp, "rb") as f:
            return h._send(200, f.read(), "application/json")
    return h._send(200, b'{"nodes":[],"edges":[],"stats":{}}', "application/json")


def handle_llm_telemetry(h):
    """GET /api/llm/telemetry — real per-provider cloud-LLM call stats (hit-rate / free calls used /
    cooldown), recorded inside core.llm.chat's failover loop. Never fabricated."""
    try:
        from core import llm, llm_telemetry
        try:
            order = llm.configured_order()
        except Exception:
            order = None
        snap = llm_telemetry.snapshot(order)
    except Exception as e:
        snap = {"providers": [], "totals": {}, "error": str(e)[:120]}
    return h._send(200, json.dumps(snap).encode(), "application/json")


def handle_network_refresh(h):
    """GET /api/network/refresh — CORTEX B7: rebuild network_state.json via a niced run_network.py
    SUBPROCESS (throttled; never trains in the dashboard process — the 524-wedge rule)."""
    return h._send(200, json.dumps(_srv(h)._network_refresh_start()).encode(),
                   "application/json")
