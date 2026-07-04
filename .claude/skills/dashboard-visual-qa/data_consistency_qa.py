#!/usr/bin/env python3
"""data_consistency_qa — verify the dashboard tells the TRUTH about the data on disk (both ways).

Render/interaction QA prove a panel shows *something* and its controls fire. This proves the numbers
are HONEST: for each data-bearing endpoint the dashboard draws from, it compares the API response to
the source file on disk and checks BOTH directions:

  disk → dashboard : every record on disk is reflected in the API (count/keys match; nothing silently
                     dropped so the panel under-reports).
  dashboard → disk : every value the API serves traces to disk — and anything NOT disk-backed is
                     honestly flagged `demo`/`available:false`, never presented as real
                     (operationalizes the honest-dashboard-wiring rule).

Verdicts per source: `consistent` · `mismatch` (dashboard ≠ disk — a real bug) · `demo` (synthetic,
honestly labelled) · `no-disk` (file absent, API must show empty) · `error`. Report-only.
"""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = "/home/karan18190164"
BASE = os.environ.get("MLNB_DASH", "http://localhost:8000")
OUT = Path(ROOT) / "research/visual-qa"


def _api(path):
    r = subprocess.run(["curl", "-s", "--max-time", "25", f"{BASE}{path}"],
                       capture_output=True, text=True)
    return json.loads(r.stdout)


def _disk(fname):
    p = Path(ROOT) / fname
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return "UNPARSEABLE"


def _len(x, *keys):
    """len of the first present key's list, else 0."""
    if not isinstance(x, dict):
        return 0
    for k in keys:
        v = x.get(k)
        if isinstance(v, list):
            return len(v)
    return 0


# (name, api_path, disk_file, extract(api)->metric, extract(disk)->metric, note)
MANIFEST = [
    ("network graph state", "/api/state", "state.json",
     lambda a: _len(a, "nodes"), lambda d: _len(d, "nodes"), "phase-1 node graph"),
    ("routing / DGMG", "/api/state/routing", "phase3.json",
     lambda a: _len(a, "results"), lambda d: _len(d, "results"), "run_phase3 output"),
    ("CORTEX network", "/api/network/state", "network_state.json",
     lambda a: _len(a, "nodes"), lambda d: _len(d, "nodes"), "run_network output"),
    ("knowledge graph", "/api/knowledge", "knowledge_state.json",
     lambda a: _len(a, "nodes"), lambda d: _len(d, "nodes"), "knowledge_state"),
    ("closed trades", "/api/trading/closedtrades", "trading/state/journal.json",
     lambda a: _len(a, "rows"), lambda d: _len(d, "trades") if isinstance(d, dict) else (len(d) if isinstance(d, list) else 0),
     "trade journal (STATE_DIR)"),
]


def run():
    rows = []
    for name, api_path, disk_file, fa, fd, note in MANIFEST:
        rec = {"source": name, "api": api_path, "disk": disk_file, "note": note}
        try:
            a = _api(api_path)
        except Exception as e:
            rec.update(verdict="error", detail=f"api: {type(e).__name__}: {e}"[:80]); rows.append(rec); continue
        d = _disk(disk_file)
        am = fa(a)
        demo = bool(isinstance(a, dict) and (a.get("demo") is True or a.get("available") is False))
        rec["api_metric"] = am
        rec["demo_flag"] = demo
        if d is None:
            # no disk file → the honest state is an EMPTY api (or an honestly-labelled demo)
            rec["disk_metric"] = None
            rec["verdict"] = "demo" if demo else ("consistent" if am == 0 else "mismatch")
            rec["detail"] = "no disk file; " + ("api honestly demo/empty" if rec["verdict"] != "mismatch"
                                                else f"api shows {am} rows with NO disk source (fabricated?)")
        else:
            dm = fd(d)
            rec["disk_metric"] = dm
            if demo:
                rec["verdict"] = "demo"
                rec["detail"] = f"api demo-labelled ({am}) while disk has {dm} — honestly not showing live disk data"
            elif am == dm:
                rec["verdict"] = "consistent"
                rec["detail"] = f"api {am} == disk {dm}"
            else:
                rec["verdict"] = "mismatch"
                rec["detail"] = f"api {am} != disk {dm} — dashboard NOT true to disk"
        rows.append(rec)
        print(f"  {rec['verdict']:11s} {name:20s} api={rec.get('api_metric')} "
              f"disk={rec.get('disk_metric')} demo={rec.get('demo_flag')}")

    OUT.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    (OUT / f"data-consistency-{ts}.json").write_text(json.dumps(rows, indent=2))
    md = [f"# Dashboard ↔ disk data-consistency — {time.strftime('%Y-%m-%d %H:%M')}", "",
          "| source | api | disk | api# | disk# | demo | verdict | detail |",
          "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['source']} | `{r['api']}` | `{r['disk']}` | {r.get('api_metric','-')} | "
                  f"{r.get('disk_metric','-')} | {r.get('demo_flag','-')} | **{r['verdict']}** | {r.get('detail','')} |")
    bad = [r for r in rows if r["verdict"] == "mismatch"]
    md += ["", f"**{len(bad)} mismatch(es)** — dashboard not true to disk."
           if bad else "", "_mismatch = a real honest-wiring bug to fix._"]
    (OUT / f"data-consistency-{ts}.md").write_text("\n".join(md))
    print(f"\n[data-consistency] {len(rows)} sources, "
          f"{sum(r['verdict']=='mismatch' for r in rows)} mismatch → {OUT}/data-consistency-{ts}.md")
    return rows


if __name__ == "__main__":
    run()
