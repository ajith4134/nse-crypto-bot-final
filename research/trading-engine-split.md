# Trading Engine Split — NSE→OpenAlgo, Crypto→Freqtrade

**Date:** 2026-06-29
**Status:** Recommendation (no code yet). Phase A+B to be planned next.
**Decision owner ask:** Split the currently-unified dashboard trading into two specialized
engines — NSE Indian stocks on OpenAlgo, crypto on the best of Freqtrade / OctoBot / Jesse.

---

## Key finding: the split already half-exists

NSE already routes through `OpenAlgoClient`; crypto already routes through a ccxt
`ExchangeClient` + home-grown `PaperEngine`. So this is NOT build-two-engines-from-scratch.
It is:
- **(A)** consolidate NSE fully onto OpenAlgo (mostly done), and
- **(B)** replace the hand-rolled crypto paper/live path with a real engine.

## Crypto engine pick: **Freqtrade** (Jesse = documented runner-up)

Weighted on: Python-native fit, strategy-library + trade→NN reuse, all markets/exchanges,
maturity/low-effort.

| Criterion | Freqtrade | Jesse | OctoBot |
|---|---|---|---|
| Python-native fit (ccxt + node net) | ✅ ccxt under the hood (same lib we use); plain Python `IStrategy` | ✅ clean Python, MIT, ccxt for data | ⚠️ GUI/tentacles-first; programmatic control bespoke |
| Strategy-lib + trade→NN reuse | ✅✅ FreqAI = built-in ML retrain loop; REST API + `freqtrade-client` | ⚠️ no built-in ML; wire NN yourself | ⚠️ weakest ML; hardest adapter |
| All markets/exchanges | ✅ spot+perp via ccxt; dry-run↔live parity | ✅ spot+futures, best backtest fidelity, fewer live drivers | ✅ broad via ccxt |
| Maturity/low effort | ✅✅ ~40k★, most active, best docs | ⚠️ smaller community; live = weaker path | ⚠️ mature GUI, code integration costlier |

**Why Freqtrade for this repo:** ccxt-based (matches `CRYPTO_EXCHANGES`/binance defaults);
FreqAI hosts the trade→NN bridge; REST API preserves dashboard-as-control-plane; dry-run/live
parity matches existing `mode + allow_live` guard.

**Jesse** = fallback only if backtest fidelity were #1 (it isn't, given equal maturity+ML weight).

⚠️ **None of the three trade crypto options** (spot + perp futures only). The library's
`crypto_options` segment must stay on the existing ccxt path — do not silently drop it.

## Dashboard relationship: **Control plane** (keep Dark Pro UI as single pane)

Already built this way: per-market endpoints (`/api/trading/status` NSE via `NSESession`,
`/api/trading/crypto/status` crypto), `CCY` map (₹/$), `TradeOutcomeNet` panel. OpenAlgo +
Freqtrade run headless behind REST, feeding existing panels + NN bridge. Link out to FreqUI /
OpenAlgo sandbox only for deep backtest/config (hybrid lean). Keeps honest-dashboard-wiring.

## Target architecture

```
Dashboard (control plane)
   └─ REST ─┬─ OpenAlgo :5000   → NSE  (sandbox=paper, sandbox-off=live)
            └─ Freqtrade :8080  → crypto (dry-run=paper, live=live)
Unified ClosedTrade journal → trade_feature_row() → TradeOutcomeNet / FreqAI
crypto_options → stays on existing ccxt path
```

## Migration plan (grounded in files)

**Phase A — NSE consolidation (small; mostly done)**
- `trading/openalgo_client.py` already does ping/place_order/sync_mode (paper=sandbox).
  Make it the *sole* NSE path; ensure `NSESession` + `live_loop._price()` NSE branch route
  100% through it. OpenAlgo sandbox (₹1cr) = NSE paper; sandbox-off = live via broker.

**Phase B — Stand up Freqtrade as crypto engine**
- Run Freqtrade dry-run, ccxt→binance, REST API enabled. (Install: `freqtrade` + `freqtrade-client`.)
- Add `CryptoEngineClient` mirroring `OpenAlgoClient` (`ping`/`place_order`/`sync_mode`,
  `allow_live`+`config.is_live` guards) talking to Freqtrade REST instead of raw ccxt.
  This is the new integration seam.

**Phase C — Strategy-library adapter (reuse-first)**
- One adapter: `LibraryStrategy` (crypto_spot/crypto_futures) → generated Freqtrade `IStrategy`
  (`populate_indicators/entry/exit`). 17 catalog modules, one translation layer, not 239 rewrites.
- Evolution (`evolve.py`, already `market="CRYPTO"`) stays; survivors emit via same adapter.

**Phase D — Trade→NN bridge continuity**
- Map Freqtrade trade results → 85-col `ClosedTrade` schema (`journal/schema.py`) so
  `trade_feature_row()` + `TradeOutcomeNet.fit_from_journal()` keep working. Optionally host
  the net in FreqAI for live retraining.

**Phase E — Retire home-grown crypto path**
- Decommission crypto side of `live_loop` (`PaperEngine`, crypto `_open`, `PaperWalletBook`
  crypto split) once Freqtrade owns crypto. NSE stays in live_loop / thin loop. `MarketRegistry`
  already keys per-market state. Keep `crypto_options` on the old ccxt path.

**Acceptance criteria:** dashboard shows live OpenAlgo (NSE) + Freqtrade (crypto) over REST;
paper & live both work per-market with `allow_live` guard; library strategies run on Freqtrade
via adapter; `TradeOutcomeNet` trains on unified journal; crypto options still functional.

## Key files / integration seams
- NSE: `trading/openalgo_client.py`, `trading/session.py`, `trading/online/session.py`
- Crypto (to replace): `trading/crypto/exchange_client.py`, `trading/crypto/session.py`,
  `trading/crypto/feed.py`, `trading/crypto/config.py`
- Unified control/state: `trading/online/controls.py`, `state.py`, `live_loop.py` (L226-296, 311-359)
- Journal + NN: `trading/journal/schema.py`, `trading/brain/trade_features.py`
- Dashboard: `dashboard/server.py` (per-market endpoints L542-567, `_candles` L195-224, `CCY` L175)

## Sources
- Freqtrade FreqAI — https://www.freqtrade.io/en/stable/freqai/
- Freqtrade REST API — https://www.freqtrade.io/en/stable/rest-api/
- Jesse — https://github.com/jesse-ai/jesse
- Engine comparison — https://alexbobes.com/crypto/best-freqtrade-alternatives/
- OpenAlgo — https://github.com/marketcalls/openalgo
