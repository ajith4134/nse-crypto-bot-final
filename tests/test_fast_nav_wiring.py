"""HumanUI.navigate() — the fast_nav wiring (ledger #10): plan → try → record.

Uses a fake Playwright page + a temp STATE_DIR (never the live paper state), and
exercises the three plan methods end-to-end: a goto that honestly lands (target words
visible), a goto that does NOT land (falls through to explore), and the skill replay
prefix handling. Also checks every attempt is recorded into fast_nav_stats.json.
"""
import unittest
from pathlib import Path
from unittest import mock


class _FakeLocator:
    def __init__(self, texts):
        self._texts = texts

    def all_inner_texts(self):
        return self._texts


class _FakePage:
    """Just enough Playwright surface for navigate()'s goto path."""

    def __init__(self, landed_title="Holdings — Upstox"):
        self.url = "https://pro.upstox.com/home"
        self._title = landed_title
        self.gotos = []

    def goto(self, url, **kw):
        self.gotos.append(url)
        self.url = url

    def wait_for_timeout(self, ms):
        pass

    def title(self):
        return self._title

    def locator(self, sel):
        return _FakeLocator([self._title])

    # perceive()/screenshot surface — navigate() must not need these on the goto path
    def screenshot(self, **kw):
        raise AssertionError("goto path must not spend vision")


def _ui(page):
    from trading.brain.vision.human_ui import HumanUI
    ui = HumanUI(page, name="upstox")
    # keep the fake cheap: no modal-dismiss vision passes
    ui.dismiss_modals = lambda **kw: 0
    return ui


class FastNavWiringTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from trading import state
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        from trading import state
        state.STATE_DIR = self._old
        self._tmp.cleanup()

    def test_goto_that_lands_wins_and_is_recorded(self):
        from trading import state
        from trading.brain.vision import fast_nav
        state.save_json("app_school_map.json", {
            "links": {"upstox": {"https://pro.upstox.com/holdings":
                                 {"text": "Holdings", "seen": 5}}}})
        ui = _ui(_FakePage(landed_title="Holdings — Upstox"))
        res = ui.navigate("holdings")
        self.assertTrue(res["done"])
        self.assertEqual(res["method"], "goto")
        stats = state.load_json(fast_nav._STATS_FILE, {})
        rec = stats["upstox"]["holdings"]["goto:https://pro.upstox.com/holdings"]
        self.assertEqual(rec["wins"], 1)
        self.assertEqual(rec["consecutive_fails"], 0)

    def test_goto_that_does_not_land_is_honest_and_falls_through(self):
        from trading import state
        from trading.brain.vision import fast_nav
        state.save_json("app_school_map.json", {
            "links": {"upstox": {"https://pro.upstox.com/somewhere":
                                 {"text": "holdings", "seen": 3}}}})
        page = _FakePage(landed_title="Completely Different Page")
        page.url = "https://pro.upstox.com/other"

        def _goto(url, **kw):
            page.gotos.append(url)
            page.url = "https://pro.upstox.com/other"   # SPA bounced us elsewhere
        page.goto = _goto
        ui = _ui(page)
        with mock.patch.object(ui, "explore",
                               return_value={"done": False}) as exp:
            res = ui.navigate("holdings")
        self.assertFalse(res["done"])                    # never fakes arrival
        exp.assert_called_once()                          # honest fallback was tried
        stats = state.load_json(fast_nav._STATS_FILE, {})
        rec = stats["upstox"]["holdings"]["goto:https://pro.upstox.com/somewhere"]
        self.assertEqual(rec["wins"], 0)
        self.assertEqual(rec["consecutive_fails"], 1)

    def test_skill_key_prefix_is_stripped_for_replay(self):
        from trading import state
        state.save_json("ui_skills.json", {
            "upstox:nav-holdings": {"steps": [{"action": "click", "target": "Holdings"}],
                                    "wins": 3}})
        ui = _ui(_FakePage())
        with mock.patch.object(ui, "_replay_skill", return_value=True) as rep:
            res = ui.navigate("holdings")
        self.assertTrue(res["done"])
        self.assertEqual(res["method"], "skill")
        rep.assert_called_once_with("nav-holdings", {})   # bare key, not "upstox:nav-holdings"

    def test_boss_tool_reports_missing_session_honestly(self):
        from trading.brain import boss
        with mock.patch("trading.broker_sense.account_watchlist._open_ui",
                        return_value=(None, None)), \
             mock.patch("trading.broker_sense.sessions.get_sessions",
                        return_value=object()):
            out = boss.navigate_app("upstox", "holdings")
        self.assertFalse(out["ok"])
        self.assertIn("session", out["error"])


if __name__ == "__main__":
    unittest.main()
