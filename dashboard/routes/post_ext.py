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


def handle_chat_stream(h):
    """POST /api/chat/stream — the Brain Chat as an NDJSON stream: each chat_stream event pushed
    immediately (thoughts + reply deltas). Streamed (Connection: close, no Content-Length)."""
    n = int(h.headers.get("Content-Length", 0) or 0)
    try:
        data = json.loads(h.rfile.read(n) or b"{}")
    except Exception:
        data = {}
    h.send_response(200)
    h.send_header("Content-Type", "application/x-ndjson")
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Accel-Buffering", "no")             # disable proxy buffering
    h.send_header("Connection", "close")                 # streamed (no Content-Length)
    h.close_connection = True
    h.end_headers()
    try:
        from core.chat_brain import chat_stream
        for ev in chat_stream(data.get("message", ""), data.get("history")):
            h.wfile.write((json.dumps(ev) + "\n").encode())
            h.wfile.flush()                              # push each event immediately
    except Exception as e:
        try:
            h.wfile.write((json.dumps(
                {"type": "error", "error": f"server error: {type(e).__name__}"}) + "\n").encode())
        except Exception:
            pass
    return


def handle_agui(h):
    """POST /api/agui — P4.6 Stream-of-Mind over the AG-UI protocol (the transport CopilotKit is
    built on). The React panel's @ag-ui/client HttpAgent POSTs a RunAgentInput; we run ONE real
    think cycle and stream its thought-events as AG-UI SSE (RUN_STARTED → per-thought
    TEXT_MESSAGE_START/CONTENT/END + CUSTOM → RUN_FINISHED). Offline-safe."""
    n = int(h.headers.get("Content-Length", 0) or 0)
    try:
        data = json.loads(h.rfile.read(n) or b"{}")
    except Exception:
        data = {}
    try:
        import uuid

        from ag_ui.core import (CustomEvent, EventType, RunFinishedEvent,
                                RunStartedEvent, TextMessageContentEvent,
                                TextMessageEndEvent, TextMessageStartEvent)
        from ag_ui.encoder import EventEncoder
    except Exception as e:
        return h._send(503, json.dumps(
            {"error": f"AG-UI unavailable: {type(e).__name__}: {e}"}).encode(),
            "application/json")
    enc = EventEncoder()
    h.send_response(200)
    h.send_header("Content-Type", enc.get_content_type())   # text/event-stream
    h.send_header("Cache-Control", "no-cache")
    h.send_header("X-Accel-Buffering", "no")
    h.send_header("Connection", "close")                 # SSE stream (no Content-Length)
    h.close_connection = True
    h.end_headers()

    def _emit(ev):
        h.wfile.write(enc.encode(ev).encode())
        h.wfile.flush()

    thread_id = str(data.get("threadId") or uuid.uuid4())
    run_id = str(data.get("runId") or uuid.uuid4())
    # query: last user message from the AG-UI RunAgentInput, if any
    query = ""
    for m in (data.get("messages") or []):
        if m.get("role") == "user" and m.get("content"):
            query = str(m["content"])
    try:
        _emit(RunStartedEvent(type=EventType.RUN_STARTED, thread_id=thread_id, run_id=run_id))
        from run_stream_of_mind import live_stream
        for ev in live_stream(query):
            if ev.get("type") == "thought":
                mid = str(uuid.uuid4())
                _emit(TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START,
                                            message_id=mid, role="assistant"))
                _emit(TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT,
                                              message_id=mid, delta=ev["text"]))
                _emit(TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=mid))
                # non-chat signal: salience/kind/consolidated for the panel to style
                _emit(CustomEvent(type=EventType.CUSTOM, name=ev.get("kind", "thought"),
                                  value={"salience": ev.get("salience"),
                                         "consolidated": ev.get("consolidated")}))
        _emit(RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=thread_id, run_id=run_id))
    except Exception as e:
        try:
            from ag_ui.core import RunErrorEvent
            _emit(RunErrorEvent(type=EventType.RUN_ERROR, message=f"{type(e).__name__}"))
        except Exception:
            pass
    return


def handle_crypto_params(h):
    """POST /api/trading/crypto/params — Phase F+: adjustable Freqtrade params (paper balance /
    max trades / stake / leverage)."""
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        from trading.crypto.freqtrade import control as _ctl
        out = _ctl.set_params(paper_balance=data.get("paper_balance"),
                              max_open_trades=data.get("max_open_trades"),
                              stake_amount=data.get("stake_amount"),
                              leverage=data.get("leverage"))
    except Exception as e:
        out = {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_closedtrades_reset(h):
    """POST /api/trading/closedtrades/reset — permanently wipe CLOSED-trade data (brain journal +
    Freqtrade closed paper trades) so the brain stops learning on contaminated history. Type-to-
    confirm: body {confirm:"RESET"}. Backs up both stores first. OPEN trades untouched."""
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        from trading.journal.reset import reset_closed_trades
        out = reset_closed_trades(confirm=data.get("confirm", ""))
    except Exception as e:
        out = {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_crypto_mode(h):
    """POST /api/trading/crypto/mode — Phase F: guarded crypto paper↔live / spot↔futures switch
    (FreqUI can't flip these). Body {mode?, segment?, paper_balance?, confirm?}. LIVE needs confirm
    + real API keys."""
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        from trading.crypto.freqtrade import control as _ctl
        res = _ctl.switch(mode=data.get("mode"), segment=data.get("segment"),
                          paper_balance=data.get("paper_balance"),
                          confirm=bool(data.get("confirm", False)))
        out = {"ok": True, **res, "status": _ctl.status()}
    except (PermissionError, ValueError) as e:     # refused (real-money guard / bad arg)
        out = {"ok": False, "reason": str(e)}
    except Exception as e:
        out = {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_online_control(h):
    """POST /api/trading/online/control — O5 control endpoint (the SAME persisted control surface
    Telegram uses). Body {action, market, ...}, action ∈ {start,stop,pause,halt,mode,allow_live,
    segments,toggle_segment,set_balance,top_up,reset_wallet,set_strategy,close_all,panic}. Secrets-
    safe; a mode→REAL switch requires explicit confirm:true (deliberate 2-step)."""
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        from trading.online import controls
        action = str(data.get("action", "")).lower()
        market = data.get("market", "")
        # Phase F: CRYPTO start/stop drives the Freqtrade bot (FreqUI's native action),
        # alongside the shared registry flag. Best-effort — engine may be down.
        if str(market).upper() == "CRYPTO" and action in ("start", "stop"):
            try:
                from trading.crypto.engine_client import CryptoEngineClient
                getattr(CryptoEngineClient(), action)()
            except Exception:
                pass
        if action == "start":
            controls.start(market)
        elif action == "stop":
            controls.stop(market)
        elif action == "pause":
            controls.pause(market)
        elif action == "halt":
            controls.halt(market)
        elif action == "mode":
            # accept either "mode" or the UI's "value" key (robust to both clients);
            # surface set_mode's {ok, reason} so a REJECTED real-switch isn't shown green.
            mode = str(data.get("mode") or data.get("value") or "PAPER").upper()
            res = controls.set_mode(market, mode, confirm=bool(data.get("confirm", False)))
            out = {"ok": bool(res.get("ok", True)), "action": action,
                   "reason": res.get("reason"), "status": controls.status()}
            return h._send(200, json.dumps(out, default=str).encode(), "application/json")
        elif action == "allow_live":
            allow = data.get("allow_live", data.get("value", False))
            controls.set_allow_live(market, bool(allow))
        elif action == "segments":           # set the full selected-segment list
            controls.set_segments(market, data.get("segments") or data.get("value") or [])
        elif action == "toggle_segment":      # flip one trade-type on/off
            controls.toggle_segment(market, data.get("segment") or data.get("value") or "")
        # CRYPTO segment changes also reconfigure the multi-segment Freqtrade engine
        # (vendor/freqtrade fork): persist CRYPTO_SEGMENTS + rewrite config + restart.
        if str(market).upper() == "CRYPTO" and action in ("segments", "toggle_segment"):
            try:
                sel = ((controls.status().get("markets") or {})
                       .get("CRYPTO") or {}).get("segments") or []
                from trading.crypto.freqtrade import control as _ctl
                _ctl.set_segments_enabled(sel)
            except Exception as e:
                out = {"ok": True, "action": action, "engine_sync": f"failed: {e}",
                       "status": controls.status()}
                return h._send(200, json.dumps(out, default=str).encode(),
                               "application/json")
        elif action == "set_balance":
            controls.set_balance(market, float(data.get("amount", 0.0)),
                                 data.get("portfolio_id", "default"))
        elif action == "top_up":
            controls.top_up(market, float(data.get("amount", 0.0)),
                            data.get("portfolio_id", "default"))
        elif action == "reset_wallet":
            controls.reset_wallet(market, data.get("portfolio_id", "default"))
        elif action == "set_strategy":        # trailing ATR mult · sizing method/risk/caps
            from trading.online.live_loop import get_loop
            cfg = get_loop().set_config(
                trail_atr_mult=data.get("trail_atr_mult"),
                sizing_method=data.get("sizing_method"),
                max_risk_pct=data.get("max_risk_pct"),
                max_position_pct=data.get("max_position_pct"),
                kelly_fraction=data.get("kelly_fraction"),
                trail_mode=data.get("trail_mode"),
                trail_pct=data.get("trail_pct"),
                take_profit_pct=data.get("take_profit_pct"),
                # auto-open basket + brain-handoff + screener filters
                enter_all=data.get("enter_all"),
                top_n_per_segment=data.get("top_n_per_segment"),
                min_open_per_segment=data.get("min_open_per_segment"),
                min_open_by_segment=data.get("min_open_by_segment"),
                leverage_by_segment=data.get("leverage_by_segment"),
                lot_size_by_segment=data.get("lot_size_by_segment"),
                min_total_open=data.get("min_total_open"),
                min_capital_per_trade=data.get("min_capital_per_trade"),
                brain_handoff_trades=data.get("brain_handoff_trades"),
                brain_unlimited=data.get("brain_unlimited"),
                screen_min_pct=data.get("screen_min_pct"),
                screen_min_quote_volume=data.get("screen_min_quote_volume"))
            out = {"ok": True, "action": action, "config": cfg}
            return h._send(200, json.dumps(out, default=str).encode(), "application/json")
        elif action == "close_all":           # flatten every open position now
            # ALL engines, best-effort: (1) the loop's own paper book, (2) every
            # Freqtrade-owned crypto trade (forceexit per open pair), (3) every
            # OpenAlgo sandbox position (covers trades opened outside the loop).
            from trading.online.live_loop import get_loop
            res = get_loop().close_all()
            ft_closed, ft_err = 0, ""
            try:
                from trading.crypto.engine_client import CryptoEngineClient
                eng = CryptoEngineClient()
                if eng.ping().connected:
                    for pair in list(eng.open_pairs() or []):
                        try:
                            eng.close_pair(pair)
                            ft_closed += 1
                        except Exception as e:
                            ft_err = f"{type(e).__name__}: {e}"[:80]
            except Exception as e:
                ft_err = f"{type(e).__name__}: {e}"[:80]
            oa_res, oa_err = {}, ""
            try:
                from trading.openalgo_client import OpenAlgoClient
                oa = OpenAlgoClient()
                if not oa.config.is_live:      # paper only — never flatten a live book here
                    oa_res = oa._check(oa._client().closeposition(
                        strategy="dashboard-close-all"), "closeposition")
            except Exception as e:
                oa_err = f"{type(e).__name__}: {e}"[:80]
            out = {"ok": True, "action": action, "result": res,
                   "freqtrade": {"closed_pairs": ft_closed, "error": ft_err},
                   "openalgo": {**oa_res, "error": oa_err},
                   "detail": (f"loop closed {res.get('closed', 0)} · Freqtrade closed "
                              f"{ft_closed} pairs · OpenAlgo "
                              f"{oa_res.get('closed_positions', 0)} positions")}
            return h._send(200, json.dumps(out, default=str).encode(), "application/json")
        elif action == "panic":
            controls.panic()
        else:
            out = {"ok": False, "error": f"unknown action {action!r}",
                   "status": controls.status()}
            return h._send(200, json.dumps(out, default=str).encode(),
                           "application/json")
        out = {"ok": True, "action": action, "status": controls.status()}
    except Exception as e:
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_gui_action(h):
    """POST /api/trading/gui/action — drive the computer-use / GUI agent. Body {op, ...}: observe /
    step / practice / experiment / add_target / arm_live. PAPER-FIRST: dry_run defaults TRUE; a real
    action needs op=arm_live(confirm) first."""
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        from trading.brain.gui import register_computer_use_agent
        from trading.brain.gui.targets import DashboardTarget
        agent = _srv(h)._gui_agent()
        op = str(data.get("op", "")).lower()
        if op == "observe":
            # deep:true opens the live page (Playwright) + OCRs the chart (PaddleOCR);
            # default shallow read (api+html) stays cheap for routine polling.
            out = {"ok": True, "op": op,
                   "perception": agent.observe(data.get("target", "own_dashboard"),
                                                deep=bool(data.get("deep", False)))}
        elif op == "step":
            dry = data.get("dry_run", True)
            out = {"ok": True, "op": op, "result": agent.step(
                str(data.get("goal", "")), data.get("target", "own_dashboard"),
                data.get("market", "CRYPTO"),
                dry_run=bool(dry), use_http=bool(data.get("use_http", False)))}
        elif op == "practice":
            out = {"ok": True, "op": op, "result": agent.practice(
                data.get("goals"), int(data.get("rounds", 1)),
                data.get("target", "own_dashboard"))}
        elif op == "experiment":
            out = {"ok": True, "op": op, "result": agent.experiment()}
        elif op == "add_target":
            t = agent.targets.add(DashboardTarget(
                name=str(data["name"]), kind=str(data.get("kind", "external")),
                web_url=str(data.get("web_url", "")),
                api_base=str(data.get("api_base", data.get("web_url", ""))),
                note=str(data.get("note", ""))))
            out = {"ok": True, "op": op, "target": t.to_dict()}
        elif op == "arm_live":
            # deliberate 2-step: arming real-money actions requires confirm:true
            armed = bool(data.get("armed", False))
            if armed and not bool(data.get("confirm", False)):
                out = {"ok": False, "op": op,
                       "reason": "arming live requires confirm:true (deliberate 2-step)"}
            else:
                agent.actions.allow_live = armed
                out = {"ok": True, "op": op, "armed_for_live": armed}
        else:
            out = {"ok": False, "op": op, "error": f"unknown op {op!r}"}
        register_computer_use_agent(agent)        # keep node graph in sync
    except Exception as e:
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_broker_sense_post(h):
    """POST /api/trading/broker_sense — drive the Broker-Sense funnel. Body {op, ...}:
    run_cycle (one funnel cycle in a background thread; market/segment optional),
    set_nse_broker {name} (owner's go-live pick), wipe_screenshots. Paper-first: run_cycle
    never passes allow_live."""
    import threading
    try:
        n = int(h.headers.get("Content-Length", 0) or 0)
        data = json.loads(h.rfile.read(n) or b"{}")
        op = str(data.get("op", "")).lower()
        from dashboard.routes.trading_ext import _bs_funnel
        if op == "run_cycle":
            market = (data.get("market") or "crypto").lower()
            segment = data.get("segment") or ("futures" if market == "crypto" else "equity")
            f = _bs_funnel(market)
            if getattr(f, "_cycle_thread", None) and f._cycle_thread.is_alive():
                out = {"ok": True, "op": op, "running": True,
                       "note": "a cycle is already running — poll GET for the result"}
            else:
                t = threading.Thread(
                    target=lambda: f.run_cycle(segment=segment, allow_live=False),
                    daemon=True, name=f"broker-sense-{market}")
                f._cycle_thread = t
                t.start()
                out = {"ok": True, "op": op, "started": True, "market": market,
                       "segment": segment,
                       "note": "cycle started (paper); GET /api/trading/broker_sense "
                               "shows stages as they land"}
        elif op == "set_nse_broker":
            from trading.broker_sense.brokers import set_real_nse_broker
            out = {"ok": True, "op": op,
                   **set_real_nse_broker(str(data.get("name", "")))}
        elif op == "wipe_screenshots":
            from trading.broker_sense import chart_vision
            out = {"ok": True, "op": op, "deleted": chart_vision.wipe()}
        else:
            out = {"ok": False, "op": op, "error": f"unknown op {op!r}"}
    except Exception as e:
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")
