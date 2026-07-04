# AI-Scientist idea ledger (compounding — AgentRxiv style)

_Status legend: proposed · approved · done · rejected. Runs append here; nothing is re-proposed._

## Run 2026-07-04 — FULL CAPACITY, unconstrained (money-lens OFF by owner instruction)

Grounded in: state snapshot (132 deps · 31 vendored OSS · 538 files) + independent audit
(417 modules; `dashboard/server.py` 3777-line god-module; 24 unwired endpoints; unused
`DrawdownAdjustedKelly`; possibly-unwired `nodes/*`) + 2026 SOTA frontier scan.
★ = reuse candidate ALREADY vendored in `vendor/` (low integration cost).

| # | Idea | Type | Why it beats what we have | Reuse | Effort/Risk | Pillar | Status |
|---|---|---|---|---|---|---|---|
| 1 | **Node auto-loader** — pkgutil auto-discovers & registers every `nodes/*` module | wire-up | Audit found node capabilities (advanced_ml, automl, symbolic, quant_factor/signal, denoise, detect…) that may never reach the live pool. Free capability recovery. | stdlib pkgutil | S / Low | 7 | proposed |
| 2 | **Wire `DrawdownAdjustedKelly`** + vol-target blend into live sizing | replace | It's imported but unused today; the most capital-protective sizer sits idle. | keeks ★(installed) | S / Low | 4,22 | proposed |
| 3 | **Split `dashboard/server.py` (3777 L)** into `routes/<domain>.py` | refactor | The most-coupled file (51 deps); unblocks honest-wiring + kills silent endpoint drift. | — | M / Low | 12 | proposed |
| 4 | **"Brain Ops" panel** surfacing the 24 unwired endpoints (autonomy/boss/decisions/sizing/predictions) | new UI | Real brain capabilities you currently cannot see. | add-panel skill | M / Low | 3,12 | proposed |
| 5 | **TSFM ensemble upgrade** — add **Moirai-2.0 + TimesFM-2.5 + Time-MoE** to Chronos/TTM/TabPFN heads; ensemble + conformal; promote by CPCV | replace/upgrade | 2026 benchmarks: Moirai-2.0 & TimesFM-2.5 top financial return forecasting; you only run older heads. | uni2ts ★ · granite_tsfm ★ · lag_llama ★ + TimesFM/Time-MoE | M / Med | 7,17 | proposed |
| 6 | **LiT — Limit Order Book Transformer** for crypto short-horizon direction | new/replace | SOTA (Oct-2025), beats DL baselines on LOB, robust to regime shift; replaces hand-crafted microprice/OBI heuristics. | lob_deep_learning ★ + LiT | M / Med | 7,25 | proposed |
| 7 | **Regime-conditioned MoE router** over the node network (Time-MoE-style gating) | upgrade | Routes to the best model *per detected regime*, learned end-to-end — upgrades CORTEX routing. | Time-MoE + CORTEX | M-L / Med | 7,22,26 | proposed |
| 8 | **RL execution agent** (hierarchical RL order-slicing) | new | Learns to minimize slippage beyond closed-form Almgren-Chriss; execution cost is often the whole edge. | FinRL/ElegantRL + muzero ★ | L / Med-High | 21 | proposed |
| 9 | **GAN/VAE synthetic factor + scenario generator** | new | VAE latent factors avoid crowding; GAN synthetic regimes stress-test strategies & feed sleep-replay. | VAE/GAN + avalanche ★ | M-L / Med | 20,23 | proposed |
| 10 | **Intermarket Graph Neural Net** (PyG) over NSE↔crypto↔macro | new | Models lead-lag/contagion (BTC→NSE IT, funding→spot) as a graph, feeding the causal layer. | PyTorch-Geometric | L / Med | 15,19 | proposed |
| 11 | **On-chain whale + news-NLP alt-data lane** (live features) | new/wire | Free alt-data the goal says IS in scope; whale-flow repo already vendored. | crypto_whale_watching ★ | M / Low-Med | 2,15 | proposed |

Sources: TSFM finance benchmark (arxiv 2606.27100), 2026 TS toolkit (machinelearningmastery.com), LiT LOB transformer (frontiersin.org/…/frai.2025.1616485), latency-efficient LOB (arxiv 2606.25986), FinRL (arxiv 2111.09395), TradeR hierarchical RL execution (arxiv 2104.00620), AlphaEvolve (arxiv 2103.16196), Alpha-R1 (arxiv 2512.23515).
