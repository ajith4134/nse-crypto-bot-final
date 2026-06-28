"""run_options_t4.py — Trading Phase T4 (Options Intelligence) offline demo + status.

Builds a synthetic single-expiry NIFTY-like options chain (NO network, NO API keys,
fully deterministic) and drives every T4 analytic end to end:

  1. Per-strike Black-76 Greeks (delta/gamma/vega/theta/rho) via chain.greeks_of(...).
  2. Max Pain strike (writers' min-payout settlement).
  3. PCR (OI + volume) — contrarian sentiment.
  4. GEX — total dealer gamma exposure, regime (positive/negative), zero-gamma flip
     level, and the call/put gamma walls.
  5. OI heatmap walls (likely resistance/support).
  6. IV Rank + IV Percentile from an IVHistory seeded with synthetic daily ATM IVs.
  7. A multi-leg payoff (bull call spread) via chain.payoff([...]) — breakevens +
     max profit / max loss + net debit.
  8. The honest chain.status() snapshot as indented JSON (what the dashboard reads).

Everything is pure CPU logic on injected quotes — the same OptionsChain drives the
live NSE/crypto chain once a broker/ccxt feed supplies real OptionQuotes.

Usage:
    .venv/bin/python run_options_t4.py
"""
from __future__ import annotations

import json
import math
import sys

from trading.options.chain import OptionLeg, OptionQuote, OptionsChain
from trading.options.greeks import black76_price
from trading.options.iv import IVHistory

# ── synthetic-chain parameters (NIFTY-like weekly expiry) ───────────────────────
FORWARD = 22_000.0          # index forward/futures price
SPOT = 21_950.0             # cash index (slightly below forward)
T_YEARS = 7.0 / 365.0       # ~1 week to expiry
RATE = 0.065                # risk-free rate
LOT_SIZE = 50               # NIFTY lot
STRIKES = [21_600, 21_800, 22_000, 22_200, 22_400]
# A smile: ATM IV lowest, wings richer — typical index skew.
_IV_BY_STRIKE = {21_600: 0.155, 21_800: 0.143, 22_000: 0.135,
                 22_200: 0.140, 22_400: 0.150}
# OI/volume concentrated where writers sit: puts below spot, calls above.
_CALL_OI = {21_600: 18_000, 21_800: 30_000, 22_000: 72_000, 22_200: 95_000, 22_400: 60_000}
_PUT_OI = {21_600: 88_000, 21_800: 110_000, 22_000: 70_000, 22_200: 25_000, 22_400: 12_000}


def _hdr(title: str) -> None:
    print(f"\n=== {title} ===")


def build_demo_chain() -> OptionsChain:
    """Construct the deterministic synthetic OptionsChain used by the demo + dashboard.

    Premiums are the exact Black-76 fair values for each strike's smile IV, so every
    analytic downstream (Greeks, GEX, payoff) is a REAL computed number, not a guess.
    """
    quotes: list[OptionQuote] = []
    for k in STRIKES:
        iv = _IV_BY_STRIKE[k]
        ce_ltp = black76_price("c", FORWARD, float(k), T_YEARS, RATE, iv)
        pe_ltp = black76_price("p", FORWARD, float(k), T_YEARS, RATE, iv)
        quotes.append(OptionQuote(strike=float(k), opt_type="CE", expiry="2026-07-02",
                                  oi=_CALL_OI[k], volume=_CALL_OI[k] * 0.6,
                                  ltp=round(ce_ltp, 2), iv=iv))
        quotes.append(OptionQuote(strike=float(k), opt_type="PE", expiry="2026-07-02",
                                  oi=_PUT_OI[k], volume=_PUT_OI[k] * 0.55,
                                  ltp=round(pe_ltp, 2), iv=iv))
    return OptionsChain(quotes, forward=FORWARD, t=T_YEARS, r=RATE,
                        spot=SPOT, lot_size=LOT_SIZE)


def _seed_iv_history(chain: OptionsChain) -> IVHistory:
    """Seed an IVHistory with a synthetic year of daily ATM IVs (deterministic)."""
    hist = IVHistory(lookback=252)
    base = chain.atm_iv() or 0.135
    # A gently oscillating vol path that brackets today's ATM IV.
    for i in range(252):
        hist.push(base * (1.0 + 0.35 * math.sin(i / 14.0)) + 0.01 * (i % 5))
    hist.push(base)   # today's ATM IV is the final/current observation
    return hist


def main() -> int:
    print("ML Network Brain — Trading T4 (Options Intelligence) offline demo")
    chain = build_demo_chain()
    print(f"  synthetic chain: forward={FORWARD:.0f} spot={SPOT:.0f} "
          f"t={T_YEARS*365:.0f}d r={RATE:.3f} lot={LOT_SIZE} "
          f"strikes={[int(k) for k in STRIKES]}")

    _hdr("1. per-strike Black-76 Greeks (ATM + one wing)")
    atm = chain.atm_strike()
    for k in (atm, atm + 400):
        for flag in ("CE", "PE"):
            q = (chain._calls if flag == "CE" else chain._puts).get(k)
            g = chain.greeks_of(q)
            print(f"  {int(k)} {flag}: px={g['price']:8.2f} iv={g['iv']*100:5.2f}%  "
                  f"delta={g['delta']:+.3f} gamma={g['gamma']:.6f} "
                  f"vega={g['vega']:.2f} theta={g['theta']:+.2f} rho={g['rho']:+.2f}")

    _hdr("2. Max Pain")
    mp = chain.max_pain()
    print(f"  max_pain_strike={int(mp['max_pain_strike'])} "
          f"(total call_oi={mp['total_call_oi']:.0f} put_oi={mp['total_put_oi']:.0f})")

    _hdr("3. Put/Call Ratio")
    pcr = chain.pcr()
    print(f"  PCR-OI={pcr['pcr_oi']:.3f}  PCR-Volume={pcr['pcr_volume']:.3f}  "
          f"(>1 = put-heavy/contrarian-bullish)")

    _hdr("4. GEX (dealer gamma exposure, estimate)")
    gex = chain.gex()
    zg = gex["zero_gamma"]
    print(f"  total_gex={gex['total_gex']:,.0f}  regime={gex['regime']}  "
          f"zero_gamma={('%.1f' % zg) if zg is not None else 'n/a'}")
    print(f"  call_wall(+GEX)={int(gex['call_wall'])}  put_wall(-GEX)={int(gex['put_wall'])}")

    _hdr("5. OI heatmap walls")
    heat = chain.oi_heatmap()
    print(f"  call_walls (resistance)={[int(k) for k in heat['call_walls']]}")
    print(f"  put_walls  (support)   ={[int(k) for k in heat['put_walls']]}")

    _hdr("6. IV Rank / IV Percentile")
    hist = _seed_iv_history(chain)
    iv_d = hist.as_dict()
    print(f"  current ATM IV={iv_d['current']*100:.2f}%  "
          f"range=[{iv_d['low']*100:.2f}%, {iv_d['high']*100:.2f}%]  n={iv_d['n']}")
    print(f"  IV Rank={iv_d['iv_rank']:.1f}  IV Percentile={iv_d['iv_percentile']:.1f}")

    _hdr("7. multi-leg payoff — bull call spread (long ATM / short +400)")
    legs = [OptionLeg(strike=atm, opt_type="CE", position="long"),
            OptionLeg(strike=atm + 400, opt_type="CE", position="short")]
    po = chain.payoff(legs)
    be = ", ".join(f"{b:.1f}" for b in po["breakevens"]) or "none"
    print(f"  legs: +{int(atm)}CE / -{int(atm+400)}CE  net_premium={po['net_premium']:+.2f} "
          f"({'credit' if po['net_premium'] >= 0 else 'debit'})")
    print(f"  breakeven(s)={be}  max_profit={po['max_profit']:.2f} @ {po['max_profit_at']:.0f}  "
          f"max_loss={po['max_loss']:.2f} @ {po['max_loss_at']:.0f}  bounded={po['bounded']}")

    _hdr("8. honest chain.status() snapshot (what the dashboard reads)")
    print(json.dumps(chain.status(), indent=2, default=str))

    print("\n✅ T4 options-intelligence demo complete (offline, deterministic).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
