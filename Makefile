# ML Network Brain — build tasks (CPU-only). OSS stack lives in .venv.
.PHONY: index test phase1 oss dev multi multi-crypto phase3 dash all crypto ci trading crypto-trade trading-t3 options-t4 journal-t5 alerts-t7 strategy-t8 brain-t8 advintel online

index:        ## regenerate INDEX.md from source (never hand-edit it)
	python3 tools/gen_index.py

test:         ## run acceptance tests
	python3 -m unittest discover -s tests -v

trading:      ## T1 NSE smoke test against a running OpenAlgo server (paper mode)
	python3 run_trading.py

crypto-trade: ## T2 crypto smoke test against live ccxt public data (paper sim)
	python3 run_crypto_trading.py

trading-t3:   ## T3 execution-engine offline demo (order SM, trailing, ladder, circuit breaker, kill switch)
	python3 run_trading_t3.py

options-t4:   ## T4 options-intelligence offline demo (Greeks, max pain, PCR, GEX, OI walls, IV rank, payoff)
	python3 run_options_t4.py

journal-t5:   ## T5 trade-journal offline demo (charges->net P&L, MAE/MFE/R, analytics, behaviour, confidence, tearsheet)
	python3 run_journal_t5.py

alerts-t7:    ## T7 Telegram alerts offline demo (events, dedup, dispatcher, /positions /pnl /kill, scheduler)
	python3 run_alerts_t7.py

strategy-t8:  ## T8.1 strategy-evolution offline demo (GP genome, mutate/crossover, walk-forward OOS leaderboard)
	python3 run_strategy_t8.py

brain-t8:     ## T8.4 experience-bank + semantic-memory offline demo (CBR recall biases decisions; LanceDB + mem0 dry-run)
	python3 run_brain_t8.py

advintel:     ## T8-deferred advanced-intelligence offline demo (Riskfolio VaR/CVaR/Kelly/HRP, stress, FII/DII, on-chain, liquidations, arb, autonomous research, RL exit)
	python3 run_advintel.py

online:       ## ONLINE (O1-O5) always-on bot offline demo (session LIVE/REPLAY, per-market state gate, editable paper wallet, supervisor, Start/Stop/Pause/Halt + paper/real switch via dashboard + Telegram)
	python3 run_online.py

phase1:       ## train the ensemble and write state.json
	python3 run_phase1.py

oss:          ## train the OSS-backed node layer (sklearn/xgb/lgbm/reservoirpy/...) -> state.json
	. .venv/bin/activate && python run_oss.py

dev:          ## train the growing brain on synthetic data (stdlib pool)
	. .venv/bin/activate && python run_dev.py

multi:        ## train the MULTI-OUTPUT network on synthetic data -> state.json
	. .venv/bin/activate && python run_multi.py mackey_glass

multi-crypto: ## train the MULTI-OUTPUT network on REAL crypto (per-coin walk-forward)
	. .venv/bin/activate && python run_multi.py crypto

multi-rich:   ## MULTI-OUTPUT with ALL node families (physics/chaos/signal/quant/math/control)
	. .venv/bin/activate && python run_multi.py mackey_glass rich

phase3:       ## Phase-3 learned routing: Hellsemble + deep L2/L3, all acceptance bars -> phase3.json
	. .venv/bin/activate && python run_phase3.py

trainable:    ## build the P3.5-3.7 trainable network -> state.json (gate/cascade/bus)
	. .venv/bin/activate && python run_trainable.py

active:       ## P3.8 per-input active subnetwork (top-k MoE + communities + firing) -> state.json
	. .venv/bin/activate && python run_active.py

full:         ## FULL trainable network over the entire node catalog (structure-search prune per head)
	. .venv/bin/activate && python run_full_network.py

dash-build:   ## compile the React dashboard (vite) into dashboard/static
	cd dashboard/web && npm run build

dash:         ## serve the dashboard at http://localhost:8000 (venv python = chat/LLM works)
	. .venv/bin/activate && python dashboard/server.py 8000

all: phase1 index test

crypto:       ## fetch real crypto data and train
	python3 run_crypto.py

ci:           ## local CI: regenerate index + run full test suite (skips heavy backends)
	python3 tools/gen_index.py
	ML_NETWORK_SKIP_HEAVY=1 python3 -m unittest discover -s tests -v
