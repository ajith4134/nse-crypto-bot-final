"""Tests for the UI-TARS GUI grounder (adopt-plan item 1) — behind GROUNDER=uitars, with an
honest fallback to OmniParser when the model isn't pulled. Coordinate parse + normalized→pixel
scaling must be exact; a 'not visible' answer must yield None; failures must never raise."""
import io
import os
import unittest

from PIL import Image

from trading.brain.vision import uitars_grounder as u


def _png(w=1600, h=900):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, "PNG")
    return buf.getvalue()


class _Base(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.get(k) for k in
                     ("GROUNDER", "UITARS_MODEL", "UITARS_LAST_RESORT")}
        self._avail = u._AVAIL
        u._AVAIL = None

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        u._AVAIL = self._avail


class TestFlag(_Base):
    def test_default_grounder_is_omniparser(self):
        os.environ.pop("GROUNDER", None)
        self.assertFalse(u.enabled())

    def test_flag_enables_uitars(self):
        os.environ["GROUNDER"] = "uitars"
        self.assertTrue(u.enabled())

    def test_last_resort_flag(self):
        os.environ.pop("GROUNDER", None)
        os.environ.pop("UITARS_LAST_RESORT", None)
        self.assertFalse(u.last_resort())               # off by default
        os.environ["UITARS_LAST_RESORT"] = "1"
        self.assertTrue(u.last_resort())                # its own flag
        self.assertFalse(u.enabled())                   # last-resort != aggressive-first

    def test_aggressive_implies_last_resort(self):
        os.environ.pop("UITARS_LAST_RESORT", None)
        os.environ["GROUNDER"] = "uitars"
        self.assertTrue(u.last_resort())                # GROUNDER=uitars also grounds late


class TestLocate(_Base):
    def test_unavailable_model_returns_none(self):
        u._AVAIL = False
        self.assertIsNone(u.locate("Buy button", _png()))

    def test_normalized_coords_scaled_to_pixels(self):
        u._AVAIL = True
        import requests
        orig = requests.post
        requests.post = lambda url, json, timeout: type(
            "R", (), {"json": lambda self: {"message": {"content": "(500,250)"}}})()
        try:
            xy = u.locate("Buy", _png(1600, 900))
        finally:
            requests.post = orig
        self.assertEqual(xy, (800, 225))         # 500/1000*1600, 250/1000*900

    def test_not_visible_returns_none(self):
        u._AVAIL = True
        import requests
        orig = requests.post
        requests.post = lambda url, json, timeout: type(
            "R", (), {"json": lambda self: {"message": {"content": "(-1,-1)"}}})()
        try:
            self.assertIsNone(u.locate("ghost", _png()))
        finally:
            requests.post = orig

    def test_network_error_never_raises(self):
        u._AVAIL = True
        import requests
        orig = requests.post

        def _boom(*a, **k):
            raise ConnectionError("down")
        requests.post = _boom
        try:
            self.assertIsNone(u.locate("Buy", _png()))
        finally:
            requests.post = orig


if __name__ == "__main__":
    unittest.main()
