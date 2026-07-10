"""tools/gen_upstox_census.py — compile the Upstox discovered-features inventory.

Owner ask 2026-07-10: beyond the named data goals, show EVERYTHING the App School found
on Upstox — every API endpoint (function/data source) with its shape, every page, every
link, the learned routes, and the built-in pickers. Pure state-file reads; run anytime.

    python3 tools/gen_upstox_census.py [out_md]
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

STATE = Path("/home/karan18190164/trading/state")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else
           "/home/karan18190164/research/upstox-feature-census-2026-07-10.md")


def _load(name, default):
    try:
        return json.loads((STATE / name).read_text())
    except Exception:
        return default


def main() -> int:
    endpoints = (_load("broker_endpoints.json", {}) or {}).get("upstox", {})
    school = _load("app_school_map.json", {}) or {}
    routes = (school.get("routes") or {}).get("upstox", {})
    pages = (school.get("pages") or {}).get("upstox", {})
    links = (school.get("links") or {}).get("upstox", {})

    by_kind: dict[str, list] = {}
    for pat, r in endpoints.items():
        by_kind.setdefault(r.get("kind", "unknown"), []).append((pat, r))

    lines = [
        "# Upstox — discovered features, functions & data census",
        f"_Generated {datetime.datetime.now().isoformat(timespec='seconds')} from the App "
        "Driving School's live captures (read-only exploration of the logged-in app)._",
        "",
        "## Learned market-data routes (the named goals)",
        "| goal | page (route) | data endpoint |",
        "|---|---|---|",
    ]
    for g, r in sorted(routes.items()):
        lines.append(f"| {g} | {r.get('url', '')} | `{r.get('endpoint', '')}` |")
    lines += [
        "",
        f"## Every API function/data source captured ({len(endpoints)} endpoints)",
        "_kind = what the classifier grounds it as; `unknown` = an app function we "
        "recorded but don't map to a trading data-kind (yet) — each row lists the "
        "payload's top-level fields so future features can use it._",
        "",
    ]
    for kind in sorted(by_kind):
        rows = sorted(by_kind[kind], key=lambda pr: -pr[1].get("n_seen", 0))
        lines.append(f"### {kind} ({len(rows)})")
        lines.append("| endpoint | seen | payload fields |")
        lines.append("|---|---|---|")
        for pat, r in rows:
            keys = ", ".join((r.get("sample_keys") or [])[:8]) or "—"
            lines.append(f"| `{pat[:100]}` | {r.get('n_seen', 0)}× | {keys} |")
        lines.append("")
    lines += [f"## Pages mapped ({len(pages)})", ""]
    for u, meta in sorted(pages.items()):
        t = (meta.get("title") or "")[:60] if isinstance(meta, dict) else ""
        lines.append(f"- {u} — {t}")
    lines += ["", f"## Links saved ({len(links)})", ""]
    for u, meta in sorted(links.items()):
        t = (meta.get("text") or "")[:50] if isinstance(meta, dict) else ""
        lines.append(f"- {u[:110]} — {t}")
    lines += [
        "",
        "## Built-in pickers (filters) already wired as candidate sources",
        "_From trading/broker_sense/broker_features.py — Upstox's own screening filters "
        "(momentum 1m/3m/5m, top gainers/losers, trending, trending<₹500 …) feed the "
        "funnel as ranked candidate lists._",
    ]
    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT} ({len(endpoints)} endpoints, {len(pages)} pages, {len(links)} links)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
