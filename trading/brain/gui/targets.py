"""trading/brain/gui/targets.py — the dashboards the computer-use agent operates.

A DashboardTarget is a named, addressable surface the agent can SEE and ACT on. Two ship by
default (the two the user picked): our OWN dashboard (the React app + JSON API on :8000) and
Freqtrade/FreqUI (:8080, the crypto bot's native UI). The registry is persisted via
trading.state so targets the user adds from the dashboard survive a restart.

`api_base` is where the agent reads honest state from (the same JSON the panels/charts draw),
and `web_url` is the page a Playwright/OCR layer would open to click pixels. Secrets-free —
only URLs, never tokens (auth, when needed, comes from config.py loaders at call time).
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field

STATE_FILE = "gui_targets.json"


@dataclass
class DashboardTarget:
    """One operable surface: where to read it (api_base) and where to click it (web_url)."""
    name: str                                  # unique id, e.g. "own_dashboard"
    kind: str                                  # "own" | "freqtrade" | "external"
    web_url: str                               # page a human/Playwright opens
    api_base: str = ""                         # JSON API root the agent reads state from
    note: str = ""
    # which read/act paths this target supports honestly
    can_api: bool = True                       # read JSON + drive control endpoints
    can_dom: bool = True                       # Playwright DOM click (when installed)
    can_ocr: bool = True                       # pixel OCR of charts (when installed)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DashboardTarget":
        keep = {k: d[k] for k in d if k in cls.__dataclass_fields__}
        return cls(**keep)


def _own_base() -> str:
    """Our dashboard host:port — honor DASH_HOST/DASH_PORT env, default 127.0.0.1:8000."""
    host = os.environ.get("DASH_HOST", "127.0.0.1")
    port = os.environ.get("DASH_PORT", "8000")
    return f"http://{host}:{port}"


def _freq_base() -> str:
    """Freqtrade/FreqUI host:port — honor FREQTRADE_URL env, default 127.0.0.1:8080."""
    url = os.environ.get("FREQTRADE_URL", "").strip()
    if url:
        return url.rstrip("/")
    host = os.environ.get("FREQTRADE_HOST", "127.0.0.1")
    port = os.environ.get("FREQTRADE_PORT", "8080")
    return f"http://{host}:{port}"


def default_targets() -> list[DashboardTarget]:
    """The two surfaces the user picked: our own dashboard + Freqtrade/FreqUI."""
    own = _own_base()
    freq = _freq_base()
    return [
        DashboardTarget(
            name="own_dashboard", kind="own", web_url=own, api_base=own,
            note="our React trading dashboard + JSON API (the panels/charts the brain reads "
                 "and the control buttons it presses)"),
        DashboardTarget(
            name="freq_ui", kind="freqtrade", web_url=freq, api_base=f"{freq}/api/v1",
            note="Freqtrade bot's native FreqUI — crypto exec surface (start/stop/forceexit)"),
    ]


class TargetRegistry:
    """Persisted set of operable dashboards (lazy-loads defaults on first use)."""

    def __init__(self, *, persist: bool = True):
        self.persist = persist
        self.targets: dict[str, DashboardTarget] = {}
        self._load()

    def _load(self) -> None:
        blob = None
        if self.persist:
            from trading import state
            blob = state.load_json(STATE_FILE, None)
        if blob and blob.get("targets"):
            for d in blob["targets"]:
                t = DashboardTarget.from_dict(d)
                self.targets[t.name] = t
        else:
            for t in default_targets():
                self.targets[t.name] = t
            self._save()

    def _save(self) -> None:
        if not self.persist:
            return
        from trading import state
        state.save_json(STATE_FILE, {"targets": [t.to_dict() for t in self.targets.values()]})

    def add(self, target: DashboardTarget) -> DashboardTarget:
        self.targets[target.name] = target
        self._save()
        return target

    def get(self, name: str) -> DashboardTarget | None:
        return self.targets.get(name)

    def all(self) -> list[DashboardTarget]:
        return list(self.targets.values())

    def to_json(self) -> dict:
        return {"targets": [t.to_dict() for t in self.targets.values()],
                "n": len(self.targets)}
