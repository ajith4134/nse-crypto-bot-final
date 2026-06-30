"""trading/crypto/engine_client.py — thin, honest wrapper over Freqtrade's REST API (T-split B).

Freqtrade is the crypto execution engine (paper=dry-run, live=real), the crypto analogue of
`trading/openalgo_client.py` for NSE. It is a SEPARATE self-hosted process (default
http://127.0.0.1:8080) that must already be running with its `api_server` enabled — this wrapper
does NOT start it (same contract as OpenAlgoClient). See research/trading-engine-split.md.

Design (mirrors OpenAlgoClient exactly):
  • Single source of truth for Freqtrade REST method/param names.
  • Lazy import: the module imports fine even when `freqtrade_client` isn't installed yet, so the
    rest of the crypto package (config, ccxt data, paper sim) stays usable.
  • Honest connectivity: `ping()` actually round-trips to the server and returns a typed result.
  • Live-trade guard: `place_order` refuses a LIVE order unless crypto_config.is_live AND
    `allow_live=True` is explicitly passed.
  • Reuses the `ConnState` dataclass from openalgo_client (one connectivity type across engines).

Usage:
    from trading.crypto.engine_client import CryptoEngineClient
    cli = CryptoEngineClient()
    health = cli.ping()                       # -> ConnState(connected=..., detail=...)
    cli.place_order(symbol="BTC/USDT", action="BUY", side="long")
"""
from __future__ import annotations

from typing import Any

from trading.crypto.config import CryptoConfig, crypto_config
# Reuse the honest connectivity type + error from the NSE engine wrapper (one shape per engine).
from trading.openalgo_client import ConnState


class FreqtradeError(RuntimeError):
    """Raised for Freqtrade API / transport failures with a clear message."""


class CryptoEngineClient:
    """Wraps the `freqtrade-client` FtRestClient. One instance per process is enough."""

    def __init__(self, config: CryptoConfig | None = None):
        self.config = config or crypto_config
        self._sdk: Any | None = None  # lazily constructed FtRestClient

    # ── SDK lifecycle ─────────────────────────────────────────────────────────
    def _client(self) -> Any:
        """Build (once) and return the underlying FtRestClient."""
        if self._sdk is not None:
            return self._sdk
        try:
            from freqtrade_client import FtRestClient  # type: ignore
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise FreqtradeError(
                "The 'freqtrade-client' package is not installed. Run:\n"
                "    .venv/bin/pip install freqtrade-client\n"
                "and start a Freqtrade bot with api_server enabled at "
                f"{self.config.ft_host}."
            ) from exc
        self._sdk = FtRestClient(
            self.config.ft_host,
            username=self.config.ft_username,
            password=self.config.ft_password,
        )
        return self._sdk

    # ── connectivity ──────────────────────────────────────────────────────────
    def ping(self) -> ConnState:
        """Round-trip to the server (ping endpoint). Honest connected/not state."""
        host = self.config.ft_host
        try:
            resp = self._client().ping()
        except FreqtradeError as exc:
            return ConnState(False, host, str(exc))
        except Exception as exc:  # transport / server-down / auth
            return ConnState(False, host, f"{type(exc).__name__}: {exc}")
        status = (resp or {}).get("status") if isinstance(resp, dict) else None
        if status == "pong":
            return ConnState(True, host, "ping endpoint OK", broker="freqtrade")
        if status == "not_running":
            # FtRestClient swallows the connection error and returns this when the bot is down.
            return ConnState(False, host, "Freqtrade server not running / unreachable at " + host)
        return ConnState(False, host, f"unexpected response: {resp!r}")

    # ── dry-run (paper/sandbox) mode ──────────────────────────────────────────
    def show_config(self) -> dict:
        """Return Freqtrade's running config ({'dry_run': bool, 'state': ..., ...})."""
        return self._check(self._client().show_config(), "show_config")

    def dry_run(self) -> bool | None:
        """Read the engine's current dry_run flag (True = paper). None if unknown."""
        try:
            return bool(self.show_config().get("dry_run"))
        except Exception:
            return None

    def sync_mode(self) -> dict:
        """Verify Freqtrade's dry_run matches our TRADING_MODE (paper→dry_run ON). Unlike
        OpenAlgo's analyzer, dry_run is fixed at Freqtrade start, so this REPORTS a mismatch
        rather than toggling it (the operator must restart Freqtrade with the right config)."""
        want_dry = not self.config.is_live           # paper => dry_run should be True
        have_dry = self.dry_run()
        ok = (have_dry is not None) and (bool(have_dry) == want_dry)
        return {"ok": ok, "want_dry_run": want_dry, "have_dry_run": have_dry,
                "detail": ("dry_run matches TRADING_MODE" if ok else
                           f"MISMATCH: TRADING_MODE wants dry_run={want_dry} but Freqtrade "
                           f"reports dry_run={have_dry} — restart Freqtrade with the right config")}

    # ── orders ────────────────────────────────────────────────────────────────
    def _guard_live(self, allow_live: bool) -> None:
        if self.config.is_live and not allow_live:
            raise FreqtradeError(
                "Refusing to place a LIVE crypto order: TRADING_MODE=live but allow_live was "
                "not explicitly set. Pass allow_live=True to confirm real money."
            )

    def place_order(
        self,
        *,
        symbol: str,                 # e.g. "BTC/USDT"
        action: str,                 # "BUY"/"LONG" (forceenter) | "SELL"/"EXIT" (forceexit)
        side: str = "long",          # "long" | "short" (forceenter only)
        price: float | None = None,
        trade_id: str | None = None,  # for an EXIT: the Freqtrade trade id (or "all")
        allow_live: bool = False,
        enter_tag: str | None = None,  # tag the entry (e.g. the brain's chosen strategy per coin)
    ) -> dict:
        """Place a crypto order via Freqtrade. In dry-run this is a paper fill in the engine.

        BUY/LONG  -> POST /forceenter (open a position on `symbol`)
        SELL/EXIT -> POST /forceexit  (close `trade_id`, or all positions on the pair)

        `enter_tag` is carried onto the Freqtrade trade so the chosen strategy is visible on the
        open-trade row (dark dashboard + FreqUI both surface enter_tag) — honest per-coin attribution.
        """
        self._guard_live(allow_live)
        act = (action or "").upper()
        cli = self._client()
        if act in ("BUY", "LONG", "ENTER", "SHORT"):
            entry_side = "short" if act == "SHORT" else (side or "long")
            # enter_tag is optional on older freqtrade-client builds → degrade gracefully.
            try:
                return self._check(cli.forceenter(symbol, entry_side, price=price,
                                                  enter_tag=enter_tag), "forceenter")
            except TypeError:
                return self._check(cli.forceenter(symbol, entry_side, price=price), "forceenter")
        if act in ("SELL", "EXIT", "CLOSE"):
            tid = trade_id if trade_id is not None else "all"
            return self._check(cli.forceexit(tid), "forceexit")
        raise FreqtradeError(f"unknown action {action!r} (expected BUY/LONG or SELL/EXIT)")

    # ── read-only data ────────────────────────────────────────────────────────
    def status(self) -> Any:
        """Open trades (list) per Freqtrade."""
        return self._client().status()

    def open_trade_count(self) -> int:
        """Number of open positions Freqtrade is managing (honest 0 on any failure)."""
        try:
            st = self.status()
            return len(st) if isinstance(st, list) else int((st or {}).get("open_trades", 0))
        except Exception:
            return 0

    # ── bot run-state (maps the dashboard's crypto Start/Stop onto Freqtrade) ──────────
    def start(self) -> dict:
        """Start the Freqtrade trader (resume taking trades)."""
        return self._check(self._client().start(), "start")

    def stop(self) -> dict:
        """Stop the Freqtrade trader (no new trades; existing positions kept)."""
        return self._check(self._client().stop(), "stop")

    def reload_config(self) -> dict:
        return self._check(self._client().reload_config(), "reload_config")

    def whitelist(self) -> list:
        """The bot's LIVE pairlist in its native format (futures → 'BTC/USDT:USDT'), via the
        /whitelist endpoint. Unlike show_config().whitelist this is populated for dynamic
        pairlists (VolumePairList). [] on failure."""
        try:
            resp = self._client().whitelist()
        except Exception:
            return []
        wl = resp.get("whitelist") if isinstance(resp, dict) else resp
        return [p for p in (wl or []) if isinstance(p, str)]

    def open_pairs(self) -> list:
        """Pairs Freqtrade currently has an OPEN trade on (for entry de-dup). [] on failure."""
        try:
            st = self.status()
            return [t.get("pair") for t in st if isinstance(t, dict) and t.get("pair")]
        except Exception:
            return []

    def close_pair(self, pair: str) -> dict:
        """Force-close the open Freqtrade trade on `pair` (by its trade id). Honest no-op if none."""
        try:
            for t in (self.status() or []):
                if isinstance(t, dict) and t.get("pair") == pair:
                    return self._check(self._client().forceexit(t.get("trade_id")), "forceexit")
        except Exception as e:
            raise FreqtradeError(f"close_pair({pair}) failed: {e}") from e
        return {"skipped": f"no open trade for {pair}"}

    def closed_trades(self) -> list:
        """ALL closed trades from Freqtrade (list of dicts), honest empty list on failure.

        Freqtrade's REST /trades caps each response at 500 rows, so a single call hides older
        history (and the reset could never see — let alone delete — trades beyond the newest
        500). We page with limit/offset until a short page signals the end, then keep only the
        closed (is_open=False) rows. Whatever was gathered before any transport error is returned.
        """
        out: list = []
        limit, offset = 500, 0
        client = self._client()
        try:
            while True:
                resp = client.trades(limit=limit, offset=offset)
                trades = resp.get("trades", resp) if isinstance(resp, dict) else resp
                if not isinstance(trades, list) or not trades:
                    break
                out.extend(t for t in trades if isinstance(t, dict) and not t.get("is_open", False))
                if len(trades) < limit:        # last (short) page — no more rows server-side
                    break
                offset += limit
        except Exception:
            pass                                # honest: return whatever we paged before failing
        return out

    def balance(self) -> dict:
        return self._check(self._client().balance(), "balance")

    def profit(self) -> dict:
        return self._check(self._client().profit(), "profit")

    # ── honest status snapshot for the dashboard ───────────────────────────────
    def as_status(self) -> dict:
        """Secrets-safe snapshot the dashboard can show next to the legacy crypto session."""
        conn = self.ping()
        out = {
            "engine": "freqtrade",
            "host": self.config.ft_host,
            "freqtrade_url": self.config.freqtrade_url,   # "Open FreqUI" link target
            "trading_mode": self.config.trading_mode,
            "connected": conn.connected,
            "detail": conn.detail,
        }
        if conn.connected:
            out["dry_run"] = self.dry_run()
            out["open_trades"] = self.open_trade_count()
            out["mode_sync"] = self.sync_mode()
            # crypto balance comes from the engine (exchange/dry-run wallet), NOT the paper sim
            try:
                bal = self.balance()
                out["balance"] = {"total": bal.get("total"), "currency": bal.get("stake"),
                                  "starting_capital": bal.get("starting_capital")}
            except Exception:
                pass
        return out

    # ── helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _check(resp: Any, endpoint: str) -> dict:
        """Validate a Freqtrade response envelope; raise on API-level failure."""
        if resp is None:
            raise FreqtradeError(f"{endpoint}: empty response (server down / bad auth?)")
        if isinstance(resp, dict) and (resp.get("error") or resp.get("status") == "error"):
            raise FreqtradeError(f"{endpoint} failed: {resp.get('error') or resp.get('detail') or resp}")
        return resp if isinstance(resp, dict) else {"data": resp}
