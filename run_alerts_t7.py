"""run_alerts_t7.py — Trading Phase T7 (Alerts + Automation, Telegram-only) offline demo.

Drives the whole Telegram alert pipeline end to end with NO network and NO credentials.
A FAKE recording transport stands in for the Telegram Bot API, so every step shows
exactly what WOULD be sent while staying fully offline and deterministic:

  1. dispatch a sequence of trading events (fill / daily P&L / signal / circuit-breaker
     / kill) through an AlertDispatcher + Deduplicator, printing the Telegram Markdown
     each event WOULD render to (to_telegram_markdown).
  2. demonstrate dedup — re-dispatch a duplicate fill inside the TTL window and show it
     suppressed, then show a critical event always delivered (bypasses dedup).
  3. exercise the CommandRouter — /positions /pnl /kill against small injected callables,
     printing the Telegram-ready replies.
  4. run a ReportScheduler run_due(now) at a known timestamp to show a scheduled daily
     report firing exactly once.
  5. print the honest dispatcher.status() snapshot (what the dashboard reads) as JSON.

Everything is pure CPU logic over an injected transport — the same dispatcher delivers
live once TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are present in `.env`.

Usage:
    .venv/bin/python run_alerts_t7.py            # offline demo (default, no network)
    .venv/bin/python run_alerts_t7.py --live     # send ONE real test message
                                                 # (requires TELEGRAM_BOT_TOKEN +
                                                 #  TELEGRAM_CHAT_ID in env)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from trading.alerts import (
    AlertConfig,
    AlertDispatcher,
    CommandRouter,
    Deduplicator,
    ReportScheduler,
    TelegramChannel,
    circuit_breaker_event,
    daily_pnl_event,
    fill_event,
    kill_event,
    signal_event,
    to_telegram_markdown,
)

# Deterministic clock for the demo: 2026-06-26 18:30:00 UTC. Past the scheduler's
# default 18:00 fire hour so the daily report is due, and a fixed base for dedup TTL.
_BASE_TS = datetime(2026, 6, 26, 18, 30, 0, tzinfo=timezone.utc).timestamp()


def _hdr(title: str) -> None:
    print(f"\n=== {title} ===")


class _FakeTransport:
    """Records (url, payload) instead of hitting the network. Mimics a Telegram OK."""

    def __init__(self) -> None:
        self.calls: list = []

    def __call__(self, url: str, payload: dict) -> dict:
        self.calls.append({"url": url, "payload": payload})
        return {"ok": True, "result": {"message_id": len(self.calls)}}


def build_demo_dispatcher() -> AlertDispatcher:
    """Construct the deterministic offline AlertDispatcher used by the demo + dashboard.

    Builds a TelegramChannel whose config carries FAKE credentials and whose transport
    is a recording stub, so the channel is "enabled" (exercises the live send path) yet
    performs NO network — every send is captured in transport.calls / channel.sent_log.
    Paired with a Deduplicator so repeat events are suppressed honestly.
    """
    fake_cfg = AlertConfig(telegram_bot_token="DEMO:FAKE-TOKEN",
                           telegram_chat_id="DEMO-CHAT")
    channel = TelegramChannel(config=fake_cfg, transport=_FakeTransport())
    return AlertDispatcher([channel], deduper=Deduplicator(ttl_seconds=300.0))


def _demo_positions() -> list:
    return [
        {"symbol": "RELIANCE", "side": "LONG", "open_qty": 100, "entry_price": 2800.0},
        {"symbol": "BTC/USDT", "side": "LONG", "open_qty": 0.5, "entry_price": 64000.0},
    ]


def _demo_pnl() -> dict:
    return {"analytics": {"net_pnl": 18250.75, "total": 9, "win_rate": 66.7,
                          "profit_factor": 2.4}}


def _demo_kill(reason: str) -> dict:
    return {"ok": True, "cancelled": 2, "flattened": 2, "reason": reason}


def _live_message() -> int:
    """--live: send ONE real test message via a real (env-backed) TelegramChannel."""
    cfg = AlertConfig.from_env()
    if not cfg.telegram_enabled:
        print("  --live requested but TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are absent "
              "in env — staying offline, nothing sent.")
        return 0
    print(f"  live mode: {cfg.as_status()}")
    channel = TelegramChannel(config=cfg)   # real requests transport (lazy)
    ev = signal_event(symbol="TEST", signal="ping", source="run_alerts_t7 --live",
                      ts=_BASE_TS)
    rec = channel.send(ev)
    print(f"  sent: ok={rec.get('ok')} dry_run={rec.get('dry_run')} "
          f"detail={rec.get('detail')}")
    return 0 if rec.get("ok") else 1


def main(argv: list | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    print("ML Network Brain — Trading T7 (Alerts + Automation, Telegram-only) offline demo")

    if "--live" in argv:
        _hdr("LIVE: one real Telegram test message")
        return _live_message()

    disp = build_demo_dispatcher()
    channel = disp.channels[0]
    print(f"  built AlertDispatcher (channel='{channel.name}', enabled={channel.enabled()}, "
          f"FAKE transport — no network), dedup ttl={disp.deduper.ttl_seconds:.0f}s")

    events = [
        fill_event(symbol="RELIANCE", side="buy", qty=100, price=2800.0,
                   order_id="OID-1", exchange="NSE", ts=_BASE_TS),
        daily_pnl_event(net_pnl=18250.75, trades=9, win_rate=66.7,
                        day="2026-06-26", ts=_BASE_TS),
        signal_event(symbol="BTC/USDT", signal="long", confidence=0.77,
                     source="brain", ts=_BASE_TS),
        circuit_breaker_event(reason="daily loss limit -5% breached", ts=_BASE_TS),
        kill_event(reason="manual kill", report={"cancelled": 2, "flattened": 2,
                                                 "ok": True}, ts=_BASE_TS),
    ]

    _hdr("1. dispatch event sequence (Telegram Markdown each WOULD render)")
    for ev in events:
        res = disp.dispatch(ev, now=_BASE_TS)
        state = "DEDUPED" if res["deduped"] else "delivered"
        print(f"\n  [{ev.kind}] {state}  (dedup_key={ev.dedup_key})")
        for line in to_telegram_markdown(ev).splitlines():
            print(f"    | {line}")

    _hdr("2. dedup demonstration")
    dup = fill_event(symbol="RELIANCE", side="buy", qty=100, price=2800.0,
                     order_id="OID-1", exchange="NSE", ts=_BASE_TS + 30)
    res = disp.dispatch(dup, now=_BASE_TS + 30)   # 30s < 300s TTL → suppressed
    print(f"  re-dispatch identical fill 30s later → deduped={res['deduped']} "
          f"(within {disp.deduper.ttl_seconds:.0f}s TTL) ✅ suppressed")
    crit = circuit_breaker_event(reason="daily loss limit -5% breached",
                                 ts=_BASE_TS + 30)
    res = disp.dispatch(crit, now=_BASE_TS + 30)
    print(f"  re-dispatch identical circuit-breaker (critical) → deduped={res['deduped']} "
          f"✅ critical bypasses dedup, always delivered")
    print(f"  dedup counters: {disp.deduper.as_dict()}")

    _hdr("3. CommandRouter (/positions /pnl /kill) with injected callables")
    router = CommandRouter(positions_fn=_demo_positions, pnl_fn=_demo_pnl,
                           kill_fn=_demo_kill)
    for cmd, args in (("/positions", ""), ("/pnl", ""), ("/kill", "demo kill")):
        print(f"\n  > {cmd} {args}".rstrip())
        for line in router.handle(cmd, args).splitlines():
            print(f"    | {line}")

    _hdr("4. ReportScheduler run_due(now) at a known timestamp")
    fired_flag = {"n": 0}

    def _daily_report():
        fired_flag["n"] += 1
        ev = daily_pnl_event(net_pnl=18250.75, trades=9, win_rate=66.7,
                             day="2026-06-26", ts=_BASE_TS)
        disp.dispatch(ev, now=_BASE_TS)
        return {"sent": "daily tearsheet", "net_pnl": 18250.75}

    sched = ReportScheduler()
    sched.add("daily_pnl_report", "daily", _daily_report, at_hour=18)
    now_iso = datetime.fromtimestamp(_BASE_TS, tz=timezone.utc).isoformat()
    print(f"  now={now_iso} (UTC hour 18 ≥ at_hour 18 → due)")
    fired = sched.run_due(_BASE_TS)
    print(f"  fired: {[f['report'] for f in fired]} (callback ran {fired_flag['n']}x)")
    again = sched.run_due(_BASE_TS + 60)
    print(f"  run_due again same day → fired={[f['report'] for f in again]} "
          f"✅ once-per-day dedup")
    print(f"  scheduler status: {json.dumps(sched.status(), default=str)}")

    _hdr("5. honest dispatcher.status() snapshot (what the dashboard reads)")
    print(json.dumps(disp.status(), indent=2, default=str))
    print(f"  fake transport recorded {len(channel.transport.calls)} Telegram API "
          f"call(s) — all offline, zero network")

    print("\n✅ T7 alerts + automation demo complete (offline, deterministic, no network).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
