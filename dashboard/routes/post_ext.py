"""Extracted POST HTTP routes (dashboard/server.py split — Wave0-⑤ Group 4).

do_POST's shared preamble (auth + endpoint-cache-stale marking) STAYS in server.py; only each route
BODY moves here as ``handle_*(h)``. Same ``_srv(h)`` live-module accessor as the other routes/*.py:
``self.X`` → ``h.X`` (incl. ``h.rfile`` / ``h.headers`` / ``h.wfile`` / ``h.send_response`` for the
streaming routes), and bare server globals (``_PRACTICE``, ``ROOT``, ``_brain_agent``, ``_gui_agent``)
→ ``_srv(h).X`` so a moved body reaches the SAME live singletons the inline code did.
"""
import json
import os
import sys
import threading


def _srv(h):
    """The live server module, resolved off the handler instance — see brain_ext._srv for why."""
    return sys.modules[h.__class__.__module__]


def handle_practice_start(h):
    """POST /api/trading/practice/start — start a practice replay (brain trades historic data) as a
    niced SUBPROCESS. One in-flight run at a time, honest busy answer."""
    srv = _srv(h)
    try:
        body_in = json.loads(h.rfile.read(
            int(h.headers.get("Content-Length", 0)) or 0) or b"{}")
    except Exception:
        body_in = {}
    proc = srv._PRACTICE.get("proc")
    if proc is not None and proc.poll() is None:
        return h._send(200, json.dumps(
            {"started": False, "note": "a practice run is already in flight"}).encode(),
            "application/json")
    sym = str(body_in.get("symbol") or "RELIANCE").upper()
    interval = str(body_in.get("interval") or "15m")
    bars = min(5000, max(300, int(body_in.get("bars") or 1200)))
    explore = bool(body_in.get("explore", True))
    code = (
        "from data.downloads import download_nse_history;"
        "from trading.practice import replay;"
        f"df = download_nse_history({sym!r}, {interval!r});"
        f"r = replay(df.tail({bars}).reset_index(drop=True), 'NSE:'+{sym!r},"
        f" warmup_frac=0.6, explore={explore});"
        "print(r['run_id'], r['n_trades'])")
    import subprocess
    kw = {"cwd": srv.ROOT, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    try:
        kw["preexec_fn"] = lambda: os.nice(15)
    except Exception:
        pass
    srv._PRACTICE["proc"] = subprocess.Popen([sys.executable, "-c", code], **kw)
    return h._send(200, json.dumps(
        {"started": True, "symbol": sym, "interval": interval, "bars": bars,
         "explore": explore,
         "note": "practice run started — results appear in the runs list"}).encode(),
        "application/json")


def handle_brain_discovery_run(h):
    """POST /api/trading/brain/discovery/run — trigger a fresh concept-discovery run on REAL recent
    market data (public Binance klines). Body {symbol?, interval?, use_llm?}. Runs the heavy
    encoder+SAE+UMAP in a background thread; the panel's GET poll picks up the saved result."""
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        symbol = str(data.get("symbol", "BTCUSDT")).upper().replace("/", "")
        interval = str(data.get("interval", "1h"))
        use_llm = bool(data.get("use_llm", False))
        from data.binance import fetch_klines, load_klines
        fetch_klines(symbol=symbol, interval=interval, total=800)
        rows = load_klines(symbol=symbol, interval=interval)   # (date, close, volume)
        import numpy as np
        if len(rows) < 60:
            raise ValueError("not enough candles")
        rows = rows[-400:]                                     # bound work for latency
        closes = np.array([float(r[1]) for r in rows], float)
        cv = np.array([[float(r[1]), float(r[2])] for r in rows], float)

        def _run_discovery():
            try:
                from trading.brain.discovery import ConceptDiscoveryEngine
                eng = ConceptDiscoveryEngine(use_llm=use_llm)
                res = eng.discover(series=closes, ohlcv=cv)
                res["symbol"] = symbol
                res["interval"] = interval
                eng.save()
            except Exception:
                pass

        threading.Thread(target=_run_discovery, daemon=True).start()
        return h._send(200, json.dumps(
            {"ok": True, "started": True, "symbol": symbol,
             "note": "discovery running — results appear in a few seconds"}).encode(),
            "application/json")
    except Exception as e:
        return h._send(200, json.dumps({"ok": False, "error": str(e)[:160]}).encode(),
                       "application/json")


def handle_credentials_post(h):
    """POST /api/trading/credentials — credential vault control. Body {op, site, ...}: op=submit
    stores (encrypted) the operator's answer; op=request raises a pending request; op=forget deletes.
    Secret values are accepted but NEVER echoed back (receipt = field names only) or logged."""
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        from trading.brain.credentials import get_vault
        v = get_vault(); op = str(data.get("op", "")).lower()
        if op == "submit":
            out = v.submit(str(data.get("site", "")), data.get("values") or {})
        elif op == "request":
            out = v.request_login(str(data.get("site", "")),
                                  data.get("fields") or ("username", "password"),
                                  str(data.get("note", "")))
        elif op == "forget":
            out = {"site": data.get("site"), "forgotten": v.forget(str(data.get("site", "")))}
        else:
            out = {"error": "op must be submit|request|forget"}
    except Exception as e:
        out = {"error": f"server error: {type(e).__name__}"}
    return h._send(200, json.dumps(out).encode(), "application/json")


def handle_brain_learn(h):
    """POST /api/brain/learn — brain self-learning control. Body {op, ...}: op=topic learns a topic
    (arXiv+web → KnowledgeBrain); op=pdf ingests a PDF; op=self_eval quizzes itself; loop_on/off/
    queue/loop_status drive the continuous learn loop. Slow ops run in a bg thread."""
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        from trading.brain.learner import get_learner
        L = get_learner(); op = str(data.get("op", "")).lower()
        if op in ("loop_on", "loop_off", "queue", "loop_status"):
            from trading.brain.learn_loop import get_learn_loop
            lp = get_learn_loop()
            if op == "loop_on":
                out = lp.enable(True)
            elif op == "loop_off":
                out = lp.enable(False)
            elif op == "queue":
                out = lp.queue_topic(str(data.get("topic", "")))
            else:
                out = lp.status()
        elif op == "self_eval":
            out = L.self_evaluate(data.get("topics"))
        else:
            import threading as _th
            if op == "topic":
                tgt = str(data.get("topic", ""))
                _th.Thread(target=lambda: L.learn_topic(tgt), daemon=True).start()
            elif op == "pdf":
                url = str(data.get("url", ""))
                _th.Thread(target=lambda: L.ingest_pdf(url), daemon=True).start()
            out = {"accepted": op, "note": "learning in background — watch the activity feed",
                   "status": L.status()}
    except Exception as e:
        out = {"error": f"server error: {type(e).__name__}: {e}"[:200]}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_brain_web(h):
    """POST /api/brain/web — autonomous READ-ONLY web screener. Body {op, url|query, site?}:
    op=screen opens a URL read-only (screenshot+OCR+DOM+controls, vault login if walled); op=google
    browses a knowledge-gap query. Emits ephemeral feed events. Never places orders (API-only)."""
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        from trading.brain.gui.web_screener import get_screener
        sc = get_screener(); op = str(data.get("op", "screen")).lower()
        if op == "google":
            out = sc.google_gap(str(data.get("query", "")),
                                max_sites=int(data.get("max_sites", 1)))
        else:
            out = sc.screen(str(data.get("url", "")), site=data.get("site"),
                            want_ocr=bool(data.get("ocr", True)))
        # never echo secrets; trim big fields
        if isinstance(out, dict):
            out.pop("text", None)
    except Exception as e:
        out = {"available": False, "error": f"server error: {type(e).__name__}: {e}"[:200]}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_chat(h):
    """POST /api/chat — the Brain Chat: {message, history?} → core.chat_brain.chat. Lazy import so
    the server starts without it; degrades to an error payload."""
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        from core.chat_brain import chat as brain_chat       # lazy: server starts without it
        out = brain_chat(data.get("message", ""), data.get("history"))
    except Exception as e:
        out = {"reply": "", "sources": [], "thoughts": [],
               "error": f"server error: {type(e).__name__}"}
    return h._send(200, json.dumps(out).encode(), "application/json")


def handle_brain_agent(h):
    """POST /api/brain/agent — P4.1 LangGraph BrainAgent: {message, history?} → recall→respond.
    Mirrors /api/chat — lazy singleton agent (via _srv(h)._brain_agent), degrades to an error payload."""
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        out = _srv(h)._brain_agent().ask(data.get("message", ""),
                                         history=data.get("history"))
    except Exception as e:
        out = {"reply": "", "llm_used": False, "used_memory": False,
               "recalled": [], "error": f"server error: {type(e).__name__}"}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_brain_ultra_remember(h):
    """POST /api/trading/brain/ultra/remember — write a durable Claude-style memory note (one fact
    per file in brain_memory/, indexed + associatively linked). Body {name, description, body, type}."""
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        from trading.brain import ultra
        out = ultra.remember(str(data.get("name", "note")),
                             str(data.get("description", "")),
                             str(data.get("body", "")),
                             type=str(data.get("type", "lesson")))
        body = json.dumps({"ok": True, **out}).encode()
    except Exception as e:
        body = json.dumps({"ok": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")
