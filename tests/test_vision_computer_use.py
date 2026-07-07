"""Tests for the FREE computer-use loop (trading/brain/vision/computer_use) — offline.

The safety-critical property: the read-only guard must REFUSE every order-placing action
(buy/sell/order/confirm/leverage/deposit) at both the decision layer and the DOM layer, no
matter what the vision model returns. Also covers action parsing, the observe→decide→execute
loop with a fake page + fake vision brain, and honest degradation with no vision provider.
STATE_DIR-isolated.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import trading.state as state
from trading.brain.vision import computer_use as cu
from trading.brain.vision.ocular_cortex import OcularCortex


class _IsolatedState(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        state.STATE_DIR = self._old
        self._tmp.cleanup()


class _FakeElement:
    def __init__(self, label, tag="button"):
        self._label = label
        self._tag = tag
        self.clicked = False
        self.filled = None

    def inner_text(self):
        return self._label

    def get_attribute(self, name):
        return None

    def bounding_box(self):
        return {"x": 5, "y": 6, "width": 40, "height": 20}

    def evaluate(self, _js):
        return self._tag.upper()

    def click(self):
        self.clicked = True

    def fill(self, v):
        self.filled = v


class _FakePage:
    def __init__(self, labels):
        self.els = [_FakeElement(l) for l in labels]
        self.scrolled = 0

    def query_selector_all(self, _sel):
        return self.els

    def screenshot(self, **kw):
        return b"PNGSCREENSHOT"

    def wait_for_timeout(self, _ms):
        pass

    class _Mouse:
        def __init__(self, pg):
            self.pg = pg

        def wheel(self, dx, dy):
            self.pg.scrolled += dy

    @property
    def mouse(self):
        return _FakePage._Mouse(self)


class TestActionParsing(unittest.TestCase):
    def test_parse_clean_json(self):
        a = cu._parse_action('{"action":"click","target":"Futures","thought":"open segment"}')
        self.assertEqual(a.kind, "click")
        self.assertEqual(a.target, "Futures")

    def test_parse_with_surrounding_prose(self):
        a = cu._parse_action('Sure! {"action":"scroll","target":"down"} done')
        self.assertEqual(a.kind, "scroll")

    def test_unparseable_becomes_done(self):
        self.assertEqual(cu._parse_action("no json here").kind, "done")

    def test_empty_becomes_noop(self):
        self.assertEqual(cu._parse_action("").kind, "noop")


class TestGuard(_IsolatedState):
    def _agent(self):
        rec = mock.MagicMock(); rec.latest.return_value = None
        return cu.ComputerUseAgent(cortex=OcularCortex(recorder=rec))

    def test_forbidden_click_refused(self):
        ag = self._agent()
        for bad in ["Buy", "Sell BTC", "Place Order", "Confirm Order", "10x Leverage", "Deposit"]:
            with self.assertRaises(cu.GuardViolation):
                ag._execute(_FakePage([bad]), cu.Action("click", bad), "binance")
        self.assertGreaterEqual(ag.blocked, 6)

    def test_forbidden_type_refused(self):
        ag = self._agent()
        with self.assertRaises(cu.GuardViolation):
            ag._execute(_FakePage(["x"]), cu.Action("type", "order qty", "5"), "binance")

    def test_find_control_never_returns_order_button(self):
        page = _FakePage(["Buy", "Sell", "Order Book", "Depth"])
        self.assertIsNone(cu._find_control(page, "Buy"))
        self.assertIsNone(cu._find_control(page, "Place Order"))
        # a safe control resolves fine
        self.assertIsNotNone(cu._find_control(page, "Depth"))

    def test_safe_click_executes(self):
        ag = self._agent()
        page = _FakePage(["Futures", "Spot", "Depth"])
        res = ag._execute(page, cu.Action("click", "Futures"), "binance")
        self.assertTrue(res["ok"])
        self.assertTrue(page.els[0].clicked)

    def test_bare_submit_and_direction_buttons_blocked(self):
        ag = self._agent()
        for bad in ["Submit", "Proceed", "Pay", "Long", "Short", "10x Long"]:
            with self.assertRaises(cu.GuardViolation):
                ag._execute(_FakePage([bad]), cu.Action("click", bad), "binance")

    def test_data_views_are_clickable(self):
        ag = self._agent()
        for good in ["Order Book", "Long/Short Ratio", "Market Depth", "Open Interest",
                     "Order History"]:
            page = _FakePage([good])
            res = ag._execute(page, cu.Action("click", good), "binance")
            self.assertTrue(res["ok"], f"{good!r} should be clickable (data view)")
            self.assertTrue(page.els[0].clicked)

    def test_read_is_never_blocked(self):
        ag = self._agent()
        res = ag._execute(_FakePage(["x"]),
                          cu.Action("read", "long/short ratio and the order book"), "binance")
        self.assertTrue(res["ok"])

    def test_find_control_allows_data_views_blocks_orders(self):
        page = _FakePage(["Order Book", "Buy", "Long/Short Ratio", "Sell"])
        self.assertIsNotNone(cu._find_control(page, "Order Book"))
        self.assertIsNotNone(cu._find_control(page, "Long/Short Ratio"))
        self.assertIsNone(cu._find_control(page, "Buy"))
        self.assertIsNone(cu._find_control(page, "Sell"))


class TestLoop(_IsolatedState):
    def _agent(self, replies):
        rec = mock.MagicMock(); rec.latest.return_value = None
        ag = cu.ComputerUseAgent(cortex=OcularCortex(recorder=rec), max_steps=6)
        self._replies = list(replies)

        def _fake_vision(prompt, screenshot):
            return self._replies.pop(0) if self._replies else '{"action":"done","thought":"end"}'
        ag._vision = _fake_vision
        return ag

    def test_run_navigates_then_done(self):
        ag = self._agent([
            '{"action":"click","target":"Futures","thought":"open futures segment"}',
            '{"action":"scroll","target":"down","thought":"see more symbols"}',
            '{"action":"done","thought":"read the top movers"}',
        ])
        page = _FakePage(["Futures", "Spot", "Depth"])
        out = ag.run(page, "binance", "segment", "open futures and read movers")
        self.assertEqual(out["summary"], "read the top movers")
        kinds = [t["action"] for t in out["trajectory"]]
        self.assertTrue(any("click" in k for k in kinds))
        self.assertTrue(page.els[0].clicked)
        self.assertEqual(out["blocked"], 0)

    def test_loop_refuses_order_action_but_continues(self):
        ag = self._agent([
            '{"action":"click","target":"Buy","thought":"place a long"}',   # MUST be refused
            '{"action":"done","thought":"stopped, never traded in-app"}',
        ])
        page = _FakePage(["Buy", "Sell", "Depth"])
        out = ag.run(page, "binance", "symbol", "look only")
        self.assertEqual(out["blocked"], 1)
        self.assertFalse(page.els[0].clicked)                 # Buy never clicked
        self.assertIn("blocked", out["trajectory"][0])

    def test_vision_unavailable_ends_gracefully(self):
        rec = mock.MagicMock(); rec.latest.return_value = None
        ag = cu.ComputerUseAgent(cortex=OcularCortex(recorder=rec), max_steps=4)
        with mock.patch("core.llm.vision_available", return_value=False):
            out = ag.run(_FakePage(["Spot"]), "binance", "segment", "explore")
        self.assertLessEqual(out["steps"], 1)

    def test_dry_plan_does_not_touch_page(self):
        rec = mock.MagicMock(); rec.latest.return_value = None
        ag = cu.ComputerUseAgent(cortex=OcularCortex(recorder=rec), allow_actions=False)
        page = _FakePage(["Futures"])
        res = ag._execute(page, cu.Action("click", "Futures"), "binance")
        self.assertTrue(res["planned"])
        self.assertFalse(page.els[0].clicked)


class TestPaidBackendOff(unittest.TestCase):
    def test_paid_backend_disabled_by_default(self):
        ag = cu.ComputerUseAgent(backend="anthropic")
        import os
        with mock.patch.dict("os.environ", {}, clear=False):
            os.environ.pop("COMPUTER_USE_PAID", None)
            with self.assertRaises(RuntimeError):
                ag._anthropic_vision("x", b"img")


if __name__ == "__main__":
    unittest.main()
