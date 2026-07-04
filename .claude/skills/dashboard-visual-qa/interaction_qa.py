#!/usr/bin/env python3
"""interaction_qa — end-to-end INPUT + BUTTON tester for every dashboard view.

Companion to visual_qa.py (a screenshot proves render; this proves the CONTROLS work). For each
view it: enumerates every interactive control, classifies it by safety, drives the safe ones (type
into inputs, pick selects, click buttons/chips/toggles), and captures the real effect — the
network round-trip it fires, the DOM mutation it causes, and any console/page error — then a
verdict per control. Report-only, paper/dry-run only, NEVER clicks a destructive / arm-live control.

Usage:
  python interaction_qa.py                       # all default views
  python interaction_qa.py --views main_trading  # limit
Env: VISUAL_QA_VIEWS (JSON [{name,url,click?}]) overrides; DASH_PASS for basic-auth if set.
"""
import argparse
import json
import os
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/home/karan18190164/research/visual-qa")
D = os.environ.get("MLNB_DASH", "http://localhost:8000")

# name, url, click-text-to-switch-view-first
DEFAULT_VIEWS = [
    {"name": "main_brain", "url": f"{D}/", "click": None},
    {"name": "main_trading", "url": f"{D}/", "click": "📈 Trading"},
    {"name": "crypto_window", "url": f"{D}/?win=crypto", "click": None},
    {"name": "frequi", "url": "http://localhost:8080/", "click": None},
    {"name": "openalgo", "url": "http://localhost:5000/", "click": None},
]

# label substrings that mark a control as DESTRUCTIVE / real-money → enumerate but NEVER click
DESTRUCTIVE = re.compile(
    r"reset|wipe|delete|remove|close\s*all|square.?off|panic|arm|go\s*live|confirm|"
    r"real.?money|liquidat|forceexit|forcesell|stop\s*all|halt|danger", re.I)
# label substrings that SPAWN a heavy background job → skip by default so the test never overloads
# the box (a smoke run just needs cheap controls; heavy triggers can be exercised individually).
HEAVY = re.compile(r"\brun\b|\bstart\b|refresh|rebuild|discover|evolve|practice|backtest|train|"
                   r"learn|research|screen|build|generate|regenerate", re.I)

# JS: enumerate every interactive control with a readable label
ENUMERATE = r"""() => {
  const sel = 'input, select, textarea, button, [role=button], [contenteditable="true"]';
  const nodes = Array.from(document.querySelectorAll(sel));
  const chips = Array.from(document.querySelectorAll('.chip')).filter(c => c.onclick || c.getAttribute('onclick'));
  const all = [...new Set([...nodes, ...chips])];
  const label = (el) => (
    (el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('title') ||
     el.getAttribute('name') || (el.innerText || el.value || '').trim() ||
     (el.closest('section,.card,.panel')?.querySelector('h1,h2,h3')?.innerText || '') + ':' + (el.tagName)
    ) || el.tagName).toString().slice(0, 60).replace(/\s+/g, ' ');
  return all.map((el, i) => {
    el.setAttribute('data-iqa', i);
    return { i, tag: el.tagName.toLowerCase(), type: (el.getAttribute('type') || '').toLowerCase(),
             role: el.getAttribute('role') || '', label: label(el),
             disabled: !!el.disabled, visible: !!(el.offsetParent || el.getClientRects().length) };
  });
}"""

DOM_COUNT = "() => document.querySelectorAll('*').length"


def _drive(page, ctrl):
    """Interact with one control; return {action, effect, requests, errors_new, verdict}."""
    reqs, before_err = [], list(page._iqa_errors)
    handler = lambda r: reqs.append(f"{r.request.method} {r.url.split('?')[0].split('://')[-1]}"
                                    f" → {r.status}")
    page.on("response", handler)
    dom0 = page.evaluate(DOM_COUNT)
    loc = page.locator(f"[data-iqa='{ctrl['i']}']")
    action = "none"
    try:
        tag, typ = ctrl["tag"], ctrl["type"]
        if tag in ("input", "textarea") and typ not in ("button", "submit", "checkbox", "radio"):
            action = "type"
            loc.fill("7" if typ in ("number", "range") else "qa-test", timeout=3000)
            loc.blur()
        elif tag == "select":
            action = "select"
            opts = loc.locator("option")
            if opts.count() > 1:
                loc.select_option(index=min(1, opts.count() - 1), timeout=3000)
        else:                                   # button / chip / toggle / role=button / checkbox
            action = "click"
            loc.click(timeout=3000, force=False)
        page.wait_for_timeout(900)              # let the fetch + re-render happen
    except Exception as e:
        page.remove_listener("response", handler)
        return {"action": action, "effect": "error", "requests": reqs,
                "errors_new": len(page._iqa_errors) - len(before_err),
                "verdict": "error", "detail": f"{type(e).__name__}: {e}"[:90]}
    page.remove_listener("response", handler)
    dom1 = page.evaluate(DOM_COUNT)
    new_err = len(page._iqa_errors) - len(before_err)
    dom_delta = dom1 - dom0
    api_reqs = [r for r in reqs if "/api/" in r or ":808" in r or ":500" in r]
    if new_err:
        verdict, effect = "error", "console/page error"
    elif api_reqs:
        bad = [r for r in api_reqs if r.rstrip().split("→")[-1].strip()[:1] in ("4", "5")]
        verdict = "error" if bad else "ok"
        effect = f"{len(api_reqs)} request(s)"
    elif abs(dom_delta) > 3:
        verdict, effect = "ok", f"DOM {dom_delta:+d}"
    else:
        verdict, effect = "dead", "no request / no DOM change"
    return {"action": action, "effect": effect, "requests": api_reqs[:4],
            "errors_new": new_err, "verdict": verdict}


def run(only=None):
    env = os.environ.get("VISUAL_QA_VIEWS")
    views = json.loads(env) if env else DEFAULT_VIEWS
    report = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for v in views:
            if only and v["name"] not in only:
                continue
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            page._iqa_errors = []
            page.on("console", lambda m: page._iqa_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: page._iqa_errors.append(str(e)))
            try:
                page.goto(v["url"], wait_until="load", timeout=30000)
            except Exception as e:
                report[v["name"]] = {"error": f"unreachable: {e}"[:120]}
                print(f"  !! {v['name']}: unreachable"); ctx.close(); continue
            page.wait_for_timeout(3500)
            if v.get("click"):
                try:
                    page.get_by_text(v["click"], exact=False).first.click(timeout=5000)
                    page.wait_for_timeout(4000)
                except Exception:
                    pass
            controls = page.evaluate(ENUMERATE)
            controls = [c for c in controls if c["visible"] and not c["disabled"]]
            rows, counts = [], {"ok": 0, "dead": 0, "error": 0, "skipped": 0}
            for c in controls:
                if DESTRUCTIVE.search(c["label"]):
                    rows.append({**c, "verdict": "skipped", "effect": "destructive — not clicked"})
                    counts["skipped"] += 1
                    continue
                if HEAVY.search(c["label"]) and c["tag"] != "input" and c["tag"] != "select":
                    rows.append({**c, "verdict": "skipped", "effect": "heavy job — not clicked"})
                    counts["skipped"] += 1
                    continue
                res = _drive(page, c)
                rows.append({**c, **res})
                counts[res["verdict"]] = counts.get(res["verdict"], 0) + 1
            report[v["name"]] = {"url": v["url"], "n_controls": len(controls),
                                 "counts": counts, "controls": rows}
            print(f"  {v['name']:14s} controls={len(controls):3d}  "
                  f"ok={counts['ok']} dead={counts['dead']} error={counts['error']} "
                  f"skipped={counts['skipped']}")
            ctx.close()
        browser.close()
    OUT.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    (OUT / f"interaction-report-{ts}.json").write_text(json.dumps(report, indent=2))
    _write_md(report, OUT / f"interaction-report-{ts}.md")
    print(f"\n[interaction-qa] report → {OUT}/interaction-report-{ts}.md")
    return report


def _write_md(report, path):
    L = [f"# Dashboard interaction QA — {time.strftime('%Y-%m-%d %H:%M')}", ""]
    for view, d in report.items():
        if d.get("error"):
            L.append(f"## {view} — {d['error']}\n"); continue
        c = d["counts"]
        L.append(f"## {view}  ({d['n_controls']} controls · ok {c['ok']} · dead {c['dead']} · "
                 f"error {c['error']} · skipped {c['skipped']})\n")
        L.append("| label | type | action | effect | verdict |")
        L.append("|---|---|---|---|---|")
        for r in d["controls"]:
            L.append(f"| {r['label']} | {r['tag']}{('/'+r['type']) if r.get('type') else ''} | "
                     f"{r.get('action','-')} | {r.get('effect','-')} | {r['verdict']} |")
        L.append("")
    path.write_text("\n".join(L))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", nargs="*")
    a = ap.parse_args()
    run(only=set(a.views) if a.views else None)
