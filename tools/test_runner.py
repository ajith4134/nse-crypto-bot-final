#!/usr/bin/env python3
"""Parallel sharded test runner — runs each tests/test_*.py module in its OWN subprocess, N in
parallel, with a per-module timeout so one slow/hanging module can't stall the suite.

Why: the serial `unittest discover` is ~40-60 min (slow Darts DL-node training + test_cortex_b7
spawning run_network.py) and its shared interpreter leaks state across modules (the "9 errors that
pass in isolation" flakiness). Per-module subprocesses fix BOTH: wall-time ≈ slowest module, and
every module runs isolated. Honors ML_NETWORK_SKIP_HEAVY + single-threads BLAS (tests/__init__.py).

Usage:
  python tools/test_runner.py [--jobs N] [--timeout S] [--fast] [--exclude m1,m2] [--only m1,m2]
    --fast     skip the known-slow modules (Darts DL training, run_network subprocess)
    --jobs N   parallel workers (default: cpu-2)
Pairs with /cpu-solo — run it on freed cores.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# --fast skips these known-heavy modules (each minutes-long; run them separately with a big
# --timeout). test_multihead/phase3/robust exceed 8 min (candidates for optimization — likely a
# grow-cascade / heavy-fit hot loop; see /hot-path).
SLOW = {"test_dl_nodes", "test_cortex_b7",            # Darts DL training · spawns run_network.py
        "test_multihead", "test_phase3", "test_robust", "test_pipeline_t8",
        "test_rl_execution"}                         # SB3-PPO training (~30k steps, ~28s)


def run_module(mod: str, timeout: int):
    # pytest, NOT unittest: this repo mixes unittest.TestCase with pytest-style test functions,
    # and `unittest discover` silently skips the function-style ones (whole modules never ran).
    # pytest runs BOTH. Single-threaded BLAS (see tests/__init__.py) + heavy-skip via env.
    env = dict(os.environ, ML_NETWORK_SKIP_HEAVY="1", OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    t = time.time()
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", f"tests/{mod}.py",
                            "-q", "--no-header", "-p", "no:cacheprovider"],
                           cwd=str(ROOT), capture_output=True, text=True,
                           timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return mod, "TIMEOUT", 0, float(timeout), f">{timeout}s"
    dt = time.time() - t
    out = (p.stdout or "") + (p.stderr or "")

    def _n(pat):
        m = re.search(pat, out)
        return int(m.group(1)) if m else 0

    passed, failed, errored = _n(r"(\d+) passed"), _n(r"(\d+) failed"), _n(r"(\d+) error")
    nt = passed + failed + errored
    if p.returncode == 0:
        return mod, "OK", passed, dt, ""
    if p.returncode == 5 and not failed and not errored:  # pytest: no tests collected
        return mod, "OK", 0, dt, "empty"
    last = next((ln for ln in reversed(out.strip().splitlines())
                 if ln.strip() and re.search(r"failed|[Ee]rror", ln)), "see output")
    return mod, "FAIL", nt, dt, last[:90]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--exclude", default="")
    ap.add_argument("--only", default="")
    a = ap.parse_args()

    mods = sorted(p.stem for p in (ROOT / "tests").glob("test_*.py"))
    if a.only:
        want = {x.strip() for x in a.only.split(",") if x.strip()}
        mods = [m for m in mods if m in want]
    excl = set(SLOW) if a.fast else set()
    excl |= {x.strip() for x in a.exclude.split(",") if x.strip()}
    mods = [m for m in mods if m not in excl]

    print(f"[test_runner] {len(mods)} modules · {a.jobs} parallel · {a.timeout}s/module"
          + (f" · skip {sorted(excl)}" if excl else ""))
    t0 = time.time()
    results = []
    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for r in ex.map(lambda m: run_module(m, a.timeout), mods):
            results.append(r)
            tag = {"OK": "  ok", "FAIL": "FAIL", "TIMEOUT": "TIME"}[r[1]]
            print(f"  {tag}  {r[0]:36s} {r[2]:4d}t {r[3]:6.1f}s  {r[4]}")

    dt = time.time() - t0
    okc = [r for r in results if r[1] == "OK"]
    failc = [r for r in results if r[1] == "FAIL"]
    toc = [r for r in results if r[1] == "TIMEOUT"]
    tot = sum(r[2] for r in results)
    print(f"\n=== {len(okc)}/{len(results)} modules OK · {tot} tests · {dt:.0f}s wall ===")
    if failc:
        print("FAILED:", [r[0] for r in failc])
    if toc:
        print("TIMEOUT:", [r[0] for r in toc])
    sys.exit(0 if not failc and not toc else 1)


if __name__ == "__main__":
    main()
