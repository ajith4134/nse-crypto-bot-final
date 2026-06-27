# ML Network Brain — build tasks (CPU-only). OSS stack lives in .venv.
.PHONY: index test phase1 oss dev dash all crypto ci

index:        ## regenerate INDEX.md from source (never hand-edit it)
	python3 tools/gen_index.py

test:         ## run acceptance tests
	python3 -m unittest discover -s tests -v

phase1:       ## train the ensemble and write state.json
	python3 run_phase1.py

oss:          ## train the OSS-backed node layer (sklearn/xgb/lgbm/reservoirpy/...) -> state.json
	. .venv/bin/activate && python run_oss.py

dev:          ## train the growing brain on synthetic data (stdlib pool)
	. .venv/bin/activate && python run_dev.py

dash:         ## serve the dashboard at http://localhost:8000
	python3 dashboard/server.py 8000

all: phase1 index test

crypto:       ## fetch real crypto data and train
	python3 run_crypto.py

ci:           ## local CI: regenerate index + run full test suite (skips heavy backends)
	python3 tools/gen_index.py
	ML_NETWORK_SKIP_HEAVY=1 python3 -m unittest discover -s tests -v
