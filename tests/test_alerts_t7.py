"""Trading Phase T7 (Telegram Alerts & Automation) acceptance tests — fully offline.

Pins KNOWN-VALUE assertions against the pure-Python alerts package so CI passes with
NO network and NO Telegram credentials: the normalized AlertEvent + builders, the
TTL/critical-bypass deduplicator, the secrets-safe AlertConfig, the Markdown formatter,
the dry-run/injected-transport TelegramChannel, the AlertDispatcher fan-out, the
/positions /pnl /kill command router, and the deterministic ReportScheduler.

CRITICAL: every test is 100% offline. The TelegramChannel is always built with an
INJECTED fake transport (a list-appending recorder) and a dummy-cred AlertConfig — the
live bot (trading.alerts.bot) is never imported and no real HTTP/Telegram call is ever
made. Time is injected everywhere (epoch seconds) so the suite is deterministic.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from trading.alerts.channels import TelegramChannel
from trading.alerts.commands import CommandRouter
from trading.alerts.config import AlertConfig
from trading.alerts.dedup import Deduplicator
from trading.alerts.dispatcher import AlertDispatcher
from trading.alerts.events import (
    AlertEvent,
    circuit_breaker_event,
    daily_pnl_event,
    fill_event,
    kill_event,
    signal_event,
)
from trading.alerts.formatter import to_telegram_markdown
from trading.alerts.scheduler import ReportScheduler

# Dummy credentials — never used against a live endpoint (transport is always injected).
_DUMMY_TOKEN = "123456789:AAdummyTOKENvalueNeverRealABCDEFGHIJKL"
_DUMMY_CHAT = "-1001234567890"


def _disabled_config() -> AlertConfig:
    return AlertConfig(telegram_bot_token=None, telegram_chat_id=None)


def _enabled_config() -> AlertConfig:
    return AlertConfig(telegram_bot_token=_DUMMY_TOKEN, telegram_chat_id=_DUMMY_CHAT)


def _utc(y, mo, d, h=0, mi=0) -> float:
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp()


class _RecordingTransport:
    """Offline fake: records (url, payload) and returns a canned dict. No network."""

    def __init__(self, resp=None, raises: Exception | None = None):
        self.calls: list = []
        self.resp = resp if resp is not None else {"ok": True, "result": {"message_id": 1}}
        self.raises = raises

    def __call__(self, url: str, payload: dict) -> dict:
        self.calls.append((url, payload))
        if self.raises is not None:
            raise self.raises
        return self.resp


class TestEvents(unittest.TestCase):
    def test_builder_kinds_and_severities(self):
        self.assertEqual(fill_event(symbol="X", side="buy", qty=1, price=10).kind, "fill")
        self.assertEqual(fill_event(symbol="X", side="buy", qty=1, price=10).severity, "info")
        self.assertEqual(signal_event(symbol="X", signal="long").kind, "signal")
        # P&L severity flips to warn on a losing day.
        self.assertEqual(daily_pnl_event(net_pnl=100.0, trades=3).severity, "info")
        self.assertEqual(daily_pnl_event(net_pnl=-100.0, trades=3).severity, "warn")
        # circuit breaker and kill are always critical.
        self.assertEqual(circuit_breaker_event(reason="dd").kind, "circuit_breaker")
        self.assertEqual(circuit_breaker_event(reason="dd").severity, "critical")
        self.assertEqual(kill_event(reason="manual").kind, "kill")
        self.assertEqual(kill_event(reason="manual").severity, "critical")

    def test_severity_clamps_to_info(self):
        self.assertEqual(AlertEvent(kind="x", title="t", severity="bogus").severity, "info")
        self.assertEqual(AlertEvent(kind="x", title="t", severity="warn").severity, "warn")

    def test_auto_dedup_key_stable_and_distinct(self):
        a = AlertEvent(kind="signal", title="SIG", symbol="X", fields={"signal": "UP"})
        b = AlertEvent(kind="signal", title="SIG", symbol="X", fields={"signal": "UP"})
        c = AlertEvent(kind="signal", title="SIG", symbol="Y", fields={"signal": "UP"})
        self.assertTrue(a.dedup_key)                 # auto-derived (was blank)
        self.assertEqual(a.dedup_key, b.dedup_key)   # identical events collapse
        self.assertNotEqual(a.dedup_key, c.dedup_key)  # different symbol -> different key

    def test_fill_dedup_key_uses_order_id(self):
        e = fill_event(symbol="RELIANCE", side="buy", qty=10, price=100.0, order_id="OID9")
        self.assertIn("OID9", e.dedup_key)
        self.assertTrue(e.dedup_key.startswith("fill:OID9"))

    def test_circuit_and_daily_keys(self):
        self.assertEqual(circuit_breaker_event(reason="x").dedup_key, "circuit_breaker")
        self.assertEqual(daily_pnl_event(net_pnl=1.0, trades=1, day="2026-06-01").dedup_key,
                         "daily_pnl:2026-06-01")


class TestDedup(unittest.TestCase):
    def test_ttl_window(self):
        d = Deduplicator(ttl_seconds=300, always_send_critical=True)
        e = signal_event(symbol="X", signal="long")
        self.assertTrue(d.should_send(e, now=1000.0))    # first time -> send
        self.assertFalse(d.should_send(e, now=1100.0))   # within ttl -> suppress
        self.assertTrue(d.should_send(e, now=1400.0))    # past ttl (>=300s) -> send again
        self.assertEqual(d.allowed, 2)
        self.assertEqual(d.suppressed, 1)

    def test_critical_always_passes(self):
        d = Deduplicator(ttl_seconds=300, always_send_critical=True)
        cb = circuit_breaker_event(reason="dd")
        self.assertTrue(d.should_send(cb, now=10.0))
        self.assertTrue(d.should_send(cb, now=11.0))   # immediate repeat still passes
        self.assertTrue(d.should_send(cb, now=12.0))
        self.assertEqual(d.allowed, 3)
        self.assertEqual(d.suppressed, 0)

    def test_reset_clears_counters(self):
        d = Deduplicator(ttl_seconds=300)
        e = signal_event(symbol="X", signal="long")
        d.should_send(e, now=0.0)
        d.should_send(e, now=1.0)
        self.assertEqual(d.allowed, 1)
        self.assertEqual(d.suppressed, 1)
        d.reset()
        self.assertEqual(d.allowed, 0)
        self.assertEqual(d.suppressed, 0)
        self.assertTrue(d.should_send(e, now=2.0))  # forgotten -> sends again


class TestConfig(unittest.TestCase):
    def test_enabled_requires_both(self):
        self.assertFalse(_disabled_config().telegram_enabled)
        self.assertFalse(AlertConfig(telegram_bot_token=_DUMMY_TOKEN).telegram_enabled)
        self.assertFalse(AlertConfig(telegram_chat_id=_DUMMY_CHAT).telegram_enabled)
        self.assertTrue(_enabled_config().telegram_enabled)

    def test_status_redacts_token(self):
        st = _enabled_config().as_status()
        self.assertTrue(st["telegram_enabled"])
        self.assertEqual(st["mode"], "live")
        # The raw token must NEVER appear anywhere in the status payload.
        self.assertNotIn(_DUMMY_TOKEN, str(st))
        self.assertNotEqual(st["telegram_token"], _DUMMY_TOKEN)

    def test_status_dry_run_when_disabled(self):
        st = _disabled_config().as_status()
        self.assertFalse(st["telegram_enabled"])
        self.assertIn("dry-run", st["mode"])

    def test_from_env_reads_dict(self):
        cfg = AlertConfig.from_env({"TELEGRAM_BOT_TOKEN": _DUMMY_TOKEN,
                                    "TELEGRAM_CHAT_ID": _DUMMY_CHAT})
        self.assertEqual(cfg.telegram_bot_token, _DUMMY_TOKEN)
        self.assertEqual(cfg.telegram_chat_id, _DUMMY_CHAT)
        self.assertTrue(cfg.telegram_enabled)
        # empty env -> disabled
        self.assertFalse(AlertConfig.from_env({}).telegram_enabled)


class TestFormatter(unittest.TestCase):
    def test_contains_title_and_field_line(self):
        e = fill_event(symbol="RELIANCE", side="buy", qty=10, price=100.0, exchange="NSE")
        text = to_telegram_markdown(e)
        self.assertIn("FILL BUY 10 RELIANCE @ 100.0", text)  # bold title content
        self.assertIn("*", text)                              # markdown bold marker
        self.assertIn("exchange", text)                       # a field line rendered
        self.assertIn("NSE", text)

    def test_none_and_empty_fields_omitted(self):
        e = AlertEvent(kind="x", title="Title", fields={"present": "Y", "blank": "",
                                                        "missing": None, "emptylist": []})
        text = to_telegram_markdown(e)
        self.assertIn("Title", text)
        self.assertIn("present", text)
        self.assertNotIn("blank", text)
        self.assertNotIn("missing", text)
        self.assertNotIn("emptylist", text)

    def test_body_included(self):
        text = to_telegram_markdown(circuit_breaker_event(reason="max drawdown breached"))
        self.assertIn("max drawdown breached", text)


class TestChannel(unittest.TestCase):
    def test_dry_run_makes_no_transport_call(self):
        transport = _RecordingTransport()
        ch = TelegramChannel(config=_disabled_config(), transport=transport)
        self.assertFalse(ch.enabled())
        res = ch.send(signal_event(symbol="X", signal="long"))
        self.assertTrue(res["dry_run"])
        self.assertTrue(res["ok"])
        self.assertEqual(transport.calls, [])          # NEVER touched the transport
        self.assertEqual(len(ch.sent_log), 1)

    def test_live_injected_transport_called_once(self):
        transport = _RecordingTransport(resp={"ok": True, "result": {"message_id": 7}})
        ch = TelegramChannel(config=_enabled_config(), transport=transport)
        self.assertTrue(ch.enabled())
        res = ch.send(fill_event(symbol="X", side="buy", qty=1, price=10.0))
        self.assertFalse(res["dry_run"])
        self.assertTrue(res["ok"])
        self.assertEqual(len(transport.calls), 1)      # exactly one delivery
        url, payload = transport.calls[0]
        self.assertNotIn(" ", url)                      # plausible URL, but offline
        self.assertEqual(payload["chat_id"], _DUMMY_CHAT)
        self.assertEqual(payload["parse_mode"], "Markdown")
        self.assertIn("text", payload)
        self.assertIn("X", payload["text"])

    def test_transport_failure_is_caught(self):
        transport = _RecordingTransport(raises=RuntimeError("boom"))
        ch = TelegramChannel(config=_enabled_config(), transport=transport)
        res = ch.send(signal_event(symbol="X", signal="long"))   # must not raise
        self.assertFalse(res["ok"])
        self.assertFalse(res["dry_run"])
        self.assertIn("RuntimeError", res["detail"])
        self.assertEqual(len(transport.calls), 1)

    def test_ok_false_when_response_not_ok(self):
        transport = _RecordingTransport(resp={"ok": False, "description": "bad"})
        ch = TelegramChannel(config=_enabled_config(), transport=transport)
        res = ch.send(signal_event(symbol="X", signal="long"))
        self.assertFalse(res["ok"])


class TestDispatcher(unittest.TestCase):
    def _enabled_channel(self):
        return TelegramChannel(config=_enabled_config(), transport=_RecordingTransport())

    def test_dedup_suppresses_second_dispatch(self):
        ch = self._enabled_channel()
        disp = AlertDispatcher([ch], deduper=Deduplicator(ttl_seconds=300))
        e = signal_event(symbol="X", signal="long")
        first = disp.dispatch(e, now=0.0)
        self.assertFalse(first["deduped"])
        self.assertEqual(len(first["results"]), 1)
        second = disp.dispatch(e, now=10.0)
        self.assertTrue(second["deduped"])
        self.assertEqual(second["results"], [])

    def test_disabled_channel_skipped(self):
        ch = TelegramChannel(config=_disabled_config(),
                             transport=_RecordingTransport())
        disp = AlertDispatcher([ch])
        res = disp.dispatch(fill_event(symbol="X", side="buy", qty=1, price=1.0), now=0.0)
        self.assertFalse(res["deduped"])
        self.assertEqual(res["results"][0]["skipped"], "disabled")

    def test_status_counts(self):
        ch = self._enabled_channel()
        disp = AlertDispatcher([ch], deduper=Deduplicator(ttl_seconds=300))
        e = signal_event(symbol="X", signal="long")
        disp.dispatch(e, now=0.0)     # delivered
        disp.dispatch(e, now=5.0)     # deduped
        st = disp.status()
        self.assertEqual(st["dispatched"], 2)
        self.assertEqual(st["delivered"], 1)
        self.assertEqual(st["deduped"], 1)
        self.assertEqual(len(st["channels"]), 1)


class TestCommands(unittest.TestCase):
    def test_positions_formats_injected(self):
        router = CommandRouter(positions_fn=lambda: [
            {"symbol": "RELIANCE", "side": "LONG", "open_qty": 10, "entry_price": 100.0}])
        out = router.handle("/positions")
        self.assertIn("RELIANCE", out)
        self.assertIn("LONG", out)
        self.assertIn("10", out)

    def test_pnl_formats_injected_analytics(self):
        router = CommandRouter(pnl_fn=lambda: {
            "analytics": {"net_pnl": 450.0, "total": 5, "win_rate": 60.0,
                          "profit_factor": 4.0}})
        out = router.handle("/pnl")
        self.assertIn("450", out)
        self.assertIn("60", out)
        self.assertIn("P&L", out)

    def test_kill_calls_fn_and_returns_engaged(self):
        calls = []

        def kill_fn(reason):
            calls.append(reason)
            return {"ok": True, "cancelled": 3, "flattened": 2}

        router = CommandRouter(kill_fn=kill_fn)
        out = router.handle("/kill", args="panic")
        self.assertEqual(calls, ["panic"])
        self.assertIn("KILL ENGAGED", out)
        self.assertIn("ok: True", out)

    def test_help_lists_commands(self):
        out = CommandRouter().handle("/help")
        for c in ("/positions", "/pnl", "/kill"):
            self.assertIn(c, out)

    def test_strips_botname_suffix(self):
        router = CommandRouter(positions_fn=lambda: [])
        out = router.handle("/positions@my_trading_bot")
        self.assertIn("No open positions", out)

    def test_unknown_command_handled(self):
        out = CommandRouter().handle("/frobnicate")
        self.assertIn("unknown command", out)

    def test_missing_wiring_is_graceful(self):
        router = CommandRouter()   # nothing wired
        self.assertIn("not wired", router.handle("/positions"))
        self.assertIn("not wired", router.handle("/pnl"))
        self.assertIn("not wired", router.handle("/kill"))


class TestScheduler(unittest.TestCase):
    def test_daily_due_after_at_hour_only(self):
        sched = ReportScheduler().add("eod", "daily", lambda: "ok", at_hour=18)
        self.assertEqual(sched.due(_utc(2026, 6, 1, 17, 0)), [])     # too early
        self.assertEqual(sched.due(_utc(2026, 6, 1, 18, 30)), ["eod"])  # after at_hour

    def test_run_due_fires_once_per_day(self):
        fired = []
        sched = ReportScheduler().add("eod", "daily",
                                      lambda: fired.append("x") or "done", at_hour=18)
        first = sched.run_due(_utc(2026, 6, 1, 18, 30))
        self.assertEqual(len(first), 1)
        self.assertTrue(first[0]["ok"])
        # same day, later -> already ran, no re-fire
        self.assertEqual(sched.run_due(_utc(2026, 6, 1, 22, 0)), [])
        self.assertEqual(len(fired), 1)
        # next day -> fires again
        self.assertEqual(len(sched.run_due(_utc(2026, 6, 2, 18, 5))), 1)
        self.assertEqual(len(fired), 2)

    def test_weekly_respects_weekday(self):
        # 2026-06-01 is a Monday (weekday 0); 2026-06-03 is Wednesday (weekday 2).
        sched = ReportScheduler().add("weekly", "weekly", lambda: "ok",
                                      at_hour=18, weekday=2)
        self.assertEqual(sched.due(_utc(2026, 6, 1, 19, 0)), [])      # Monday != Wed
        self.assertEqual(sched.due(_utc(2026, 6, 3, 19, 0)), ["weekly"])  # Wednesday

    def test_status_reflects_last_run_day(self):
        sched = ReportScheduler().add("eod", "daily", lambda: "ok", at_hour=18)
        sched.run_due(_utc(2026, 6, 1, 18, 30))
        st = sched.status()
        self.assertEqual(st["fired"], 1)
        self.assertEqual(st["reports"][0]["last_run_day"], "2026-06-01")


if __name__ == "__main__":
    unittest.main()
