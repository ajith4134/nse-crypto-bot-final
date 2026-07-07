"""trading/broker_sense/brokers.py — broker-app registry + ROLE ENFORCEMENT in code.

Owner decisions (2026-07-05, research/broker-sense-design.md):
  • screening apps (web, read-only): Angel One, Upstox, Groww, TradingView (NSE) +
    Bybit, Coinbase, Binance, TradingView (crypto) — whichever have working logins;
    TradingView needs none, so screening can never be blocked by a missing account.
  • exec_paper : NSE → Zerodha sandbox (OpenAlgo) · crypto → Binance dry-run (Freqtrade).
  • exec_real  : crypto → Binance · NSE → ONE of angelone/upstox/groww (owner picks at
    go-live; unset until then). Real execution is HARD-GATED off (see exec_adapter.py).

Role enforcement is structural: `assert_can_execute()` raises for any broker not in the
exec role — screening drivers physically cannot place orders. Secrets-free (URLs + field
NAMES only; values live in the encrypted vault).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from trading import state

_FILE = "broker_sense_brokers.json"        # persisted owner overrides (roles only)


@dataclass(frozen=True)
class BrokerApp:
    """One broker/trading web app the brain may open. URLs are entry points the session
    layer navigates from; `chart_url`/`screener_url` may embed {symbol}/{interval}."""
    name: str
    market: str                            # "nse" | "crypto" | "both"
    site: str                              # vault key + allowlist domain
    home_url: str
    screener_url: str = ""
    chart_url: str = ""                    # {symbol} / {interval} placeholders
    book_url: str = ""                     # page showing depth / order book
    login_fields: tuple = ()               # (field, human explanation) pairs for the chat ask
    public_screener: bool = False          # screener readable WITHOUT login
    roles: tuple = ("screening",)          # subset of: screening, exec_paper, exec_real


REGISTRY: dict[str, BrokerApp] = {a.name: a for a in [
    BrokerApp(
        name="tradingview", market="both", site="tradingview.com",
        home_url="https://www.tradingview.com",
        screener_url="https://www.tradingview.com/screener/",
        chart_url="https://www.tradingview.com/chart/?symbol={symbol}&interval={interval}",
        public_screener=True, roles=("screening",),
        login_fields=(("username", "your TradingView username or email"),
                      ("password", "your TradingView password")),
    ),
    BrokerApp(
        name="angelone", market="nse", site="angelone.in",
        # trade.angelone.in = the logged-in web platform (redirects to angelone.in/login/ when
        # logged out). The old /stocks/screener URL 404s — and that 404's footer demat-signup
        # box even false-flagged as a login form.
        home_url="https://trade.angelone.in",
        screener_url="https://trade.angelone.in",
        chart_url="https://www.angelone.in/stocks/{symbol}",
        login_fields=(("username", "your Angel One registered MOBILE NUMBER (10 digits — the web login asks mobile-first)"),
                      ("password", "your Angel One PIN / password"),
                      ("otp", "the one-time password Angel One just sent to your phone/TOTP app")),
        public_screener=True, roles=("screening", "exec_real_candidate"),
    ),
    BrokerApp(
        name="upstox", market="nse", site="upstox.com",
        # pro.upstox.com = the LOGGED-IN web app (QR session lands here); upstox.com redirects to
        # login and drops the session, so the crawl/screen must start on pro.upstox.com.
        home_url="https://pro.upstox.com",
        screener_url="https://pro.upstox.com/discover",
        chart_url="https://pro.upstox.com/stocks/{symbol}",
        login_fields=(("username", "your Upstox registered mobile number"),
                      ("password", "your Upstox 6-digit PIN"),
                      ("otp", "the OTP Upstox just sent by SMS")),
        public_screener=True, roles=("screening", "exec_real_candidate"),
    ),
    BrokerApp(
        name="groww", market="nse", site="groww.in",
        home_url="https://groww.in",
        screener_url="https://groww.in/markets/top-gainers",
        chart_url="https://groww.in/stocks/{symbol}",
        login_fields=(("username", "the email you registered on Groww"),
                      ("password", "your Groww password"),
                      ("otp", "the OTP Groww just sent to your email/phone")),
        public_screener=True, roles=("screening", "exec_real_candidate"),
    ),
    BrokerApp(
        name="binance", market="crypto", site="binance.com",
        home_url="https://www.binance.com",
        screener_url="https://www.binance.com/en/markets/overview",
        chart_url="https://www.binance.com/en/futures/{symbol}",
        book_url="https://www.binance.com/en/futures/{symbol}",
        login_fields=(("username", "your Binance account email"),
                      ("password", "your Binance password"),
                      ("otp", "the Binance 2FA code (authenticator app or email)")),
        public_screener=True, roles=("screening", "exec_paper", "exec_real"),
    ),
    BrokerApp(
        name="bybit", market="crypto", site="bybit.com",
        home_url="https://www.bybit.com",
        screener_url="https://www.bybit.com/en/markets/overview",
        chart_url="https://www.bybit.com/trade/usdt/{symbol}",
        book_url="https://www.bybit.com/trade/usdt/{symbol}",
        login_fields=(("username", "your Bybit account email"),
                      ("password", "your Bybit password"),
                      ("otp", "the Bybit 2FA code")),
        public_screener=True, roles=("screening",),          # owner: screening ONLY
    ),
    BrokerApp(
        name="coinbase", market="crypto", site="coinbase.com",
        home_url="https://www.coinbase.com",
        screener_url="https://www.coinbase.com/explore",
        chart_url="https://www.coinbase.com/price/{symbol}",
        login_fields=(("username", "your Coinbase account email"),
                      ("password", "your Coinbase password"),
                      ("otp", "the Coinbase 2FA code")),
        public_screener=True, roles=("screening",),          # owner: screening ONLY
    ),
]}

# execution routing (paper today; real hard-gated in exec_adapter.py)
EXEC_PAPER = {"nse": "zerodha-sandbox(openalgo)", "crypto": "binance-dry(freqtrade)"}
EXEC_REAL = {"crypto": "binance", "nse": None}     # NSE: owner picks angelone/upstox/groww at go-live


class RoleViolation(RuntimeError):
    """A screening-only broker was asked to execute — structurally forbidden."""


def _overrides() -> dict:
    return state.load_json(_FILE, {})


def set_real_nse_broker(name: str) -> dict:
    """Owner picks the ONE NSE real-money broker (go-live step). Persisted, never implicit."""
    if name not in REGISTRY or "exec_real_candidate" not in REGISTRY[name].roles:
        raise RoleViolation(f"{name!r} is not an approved NSE real-money candidate "
                            f"(angelone/upstox/groww)")
    ov = _overrides()
    ov["exec_real_nse"] = name
    state.save_json(_FILE, ov)
    return {"exec_real_nse": name}


def real_broker(market: str) -> str | None:
    if market == "crypto":
        return EXEC_REAL["crypto"]
    return _overrides().get("exec_real_nse")       # None until the owner picks


def screening_brokers(market: str | None = None) -> list[BrokerApp]:
    return [a for a in REGISTRY.values() if "screening" in a.roles
            and (market is None or a.market in (market, "both"))]


def assert_can_execute(name: str, market: str, *, live: bool) -> None:
    """Structural gate: only the owner-designated execution broker may execute; screening
    apps can never place an order. Raises RoleViolation otherwise."""
    if not live:
        return                                       # paper rides OpenAlgo-sandbox/Freqtrade-dry
    if market == "crypto" and name != EXEC_REAL["crypto"]:
        raise RoleViolation(f"{name!r} may not execute real crypto — owner chose Binance only")
    if market == "nse" and name != real_broker("nse"):
        raise RoleViolation(f"{name!r} may not execute real NSE — owner has "
                            f"{'not picked a broker yet' if not real_broker('nse') else 'picked ' + str(real_broker('nse'))}")


def status() -> dict:
    """Honest role map for the dashboard."""
    return {
        "screening": [a.name for a in screening_brokers()],
        "exec_paper": EXEC_PAPER,
        "exec_real": {"crypto": EXEC_REAL["crypto"], "nse": real_broker("nse")
                      or "UNSET — owner picks angelone/upstox/groww at go-live"},
        "apps": {a.name: {"market": a.market, "roles": list(a.roles),
                          "public_screener": a.public_screener} for a in REGISTRY.values()},
    }
