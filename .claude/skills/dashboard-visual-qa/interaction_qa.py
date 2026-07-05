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
    # FreqUI is built with base /frequi/ → only mounts via the Caddy gateway :8100/frequi/,
    # NOT direct :8080/ (which serves a blank shell). See memory frequi-blank-gateway-path.
    {"name": "frequi", "url": "http://localhost:8100/frequi/", "click": None},
    {"name": "openalgo", "url": "http://localhost:5000/", "click": None},
]

# label substrings that mark a control as DESTRUCTIVE / real-money → enumerate but NEVER click
DESTRUCTIVE = re.compile(
    r"reset|wipe|delete|remove|close\s*all|square.?off|panic|arm|go\s*live|confirm|"
    r"real.?money|liquidat|forceexit|forcesell|\bstop\b|\bpause\b|\bkill\b|shutdown|"
    r"halt|danger", re.I)  # \bstop\b/\bpause\b: never halt the trading engine during QA
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
    """Interact with one control; return {action, effect, requests, errors_new, verdict}.

    A control WORKS if it fires a good (2xx) request, triggers a file download, sets its own
    value (controlled input), or mutates the DOM. Clicking a nav chip / action button on a live
    React dashboard re-renders the view and DETACHES the located element mid-click → Playwright
    raises; that is SUCCESS (the requests still fired), not an error. Only a genuine new console/
    page error or a 4xx/5xx response is a real "error"; a no-op is "dead"."""
    reqs, fired, before_err = [], [], list(page._iqa_errors)
    before_dlg = len(getattr(page, "_iqa_dialogs", []))
    handler = lambda r: reqs.append(f"{r.request.method} {r.url.split('?')[0].split('://')[-1]}"
                                    f" → {r.status}")
    req_handler = lambda r: fired.append(r.url.split('?')[0].split('://')[-1])
    downloads = []
    dl_handler = lambda d: downloads.append(getattr(d, "suggested_filename", None) or "download")
    page.on("response", handler)
    page.on("request", req_handler)
    page.on("download", dl_handler)
    dom0 = page.evaluate(DOM_COUNT)
    loc = page.locator(f"[data-iqa='{ctrl['i']}']")
    action, raised, typed_ok = "none", None, False
    try:
        tag, typ = ctrl["tag"], ctrl["type"]
        if tag in ("input", "textarea") and typ not in ("button", "submit", "checkbox", "radio"):
            action = "type"
            testval = "7" if typ in ("number", "range") else "qa-test"
            loc.fill(testval, timeout=3000)
            loc.blur()
            try:                                # controlled input that keeps the value = wired
                typed_ok = str(loc.input_value(timeout=1000)) == testval
            except Exception:
                typed_ok = False
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
        raised = f"{type(e).__name__}: {e}"[:90]  # e.g. element detached by an SPA re-render
    page.remove_listener("response", handler)
    page.remove_listener("request", req_handler)
    page.remove_listener("download", dl_handler)
    new_err = len(page._iqa_errors) - len(before_err)
    new_dlg = len(getattr(page, "_iqa_dialogs", [])) - before_dlg
    try:                                        # page may be mid-navigation after a re-render
        dom1 = page.evaluate(DOM_COUNT)
    except Exception:
        dom1 = dom0
    dom_delta = dom1 - dom0
    api_reqs = [r for r in reqs if "/api/" in r or ":808" in r or ":500" in r]
    api_fired = [u for u in fired if "/api/" in u or ":808" in u or ":500" in u]
    bad = [r for r in api_reqs if r.rstrip().split("→")[-1].strip()[:1] in ("4", "5")]
    if new_err or bad:
        verdict = "error"
        effect = "console/page error" if new_err else f"{len(bad)} bad request(s)"
    elif downloads:                             # Export CSV etc. — client-side file download
        verdict, effect = "ok", f"download ({downloads[0]})"
    elif new_dlg:                               # confirm() gate = the control IS wired (dismissed, safe)
        verdict, effect = "ok", "confirm dialog (wired, dismissed)"
    elif api_reqs:                              # fired ≥1 good request (even if it then re-rendered)
        verdict = "ok"
        effect = f"{len(api_reqs)} request(s)" + (" · re-render" if raised else "")
    elif api_fired:                             # request sent but response outran the window (slow ep)
        verdict, effect = "ok", f"request sent ({api_fired[0].split('/api/')[-1][:24]})"
    elif typed_ok:                              # controlled input reflected the typed value
        verdict, effect = "ok", "value set (controlled input)"
    elif abs(dom_delta) > 3:
        verdict, effect = "ok", f"DOM {dom_delta:+d}"
    elif raised:                                # interaction raised but had no observable effect
        verdict, effect = "dead", f"no effect; interaction raised ({raised})"
    else:
        verdict, effect = "dead", "no request / no DOM change"
    return {"action": action, "effect": effect, "requests": api_reqs[:4],
            "errors_new": new_err, "verdict": verdict, "detail": raised}


def _await_app(page, settle=1200):
    """Wait until interactive controls have mounted — heavy views (charts) render slowly under
    load, and a fixed timeout raced them, yielding 0 controls (flaky). Bounded, never hangs."""
    try:
        page.wait_for_selector("button, input, select, textarea, .chip", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(settle)


def _enumerate(page, tries=3):
    """Enumerate visible/enabled controls, retrying if the view hasn't finished rendering yet."""
    controls = []
    for _ in range(tries):
        controls = [c for c in page.evaluate(ENUMERATE) if c["visible"] and not c["disabled"]]
        if controls:
            break
        page.wait_for_timeout(1500)
    return controls


def run(only=None):
    env = os.environ.get("VISUAL_QA_VIEWS")
    views = json.loads(env) if env else DEFAULT_VIEWS
    report = {}
    user = os.environ.get("DASH_USER", "admin")
    pw = os.environ.get("DASH_PASS")
    creds = {"username": user, "password": pw} if pw else None
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for v in views:
            if only and v["name"] not in only:
                continue
            # basic-auth (dashboard :8000 is auth-gated); harmless for un-gated :8080/:5000
            ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                      http_credentials=creds)
            page = ctx.new_page()
            page._iqa_errors = []
            page._iqa_dialogs = []
            # SAFETY: never ACCEPT a confirm()/prompt() (some gate destructive mode switches);
            # always dismiss + record it (a dialog proves the control is wired).
            page.on("dialog", lambda d: (page._iqa_dialogs.append(d.type), d.dismiss()))
            page.on("console", lambda m: page._iqa_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: page._iqa_errors.append(str(e)))
            try:
                page.goto(v["url"], wait_until="load", timeout=30000)
            except Exception as e:
                report[v["name"]] = {"error": f"unreachable: {e}"[:120]}
                print(f"  !! {v['name']}: unreachable"); ctx.close(); continue
            def _load_and_enumerate():
                _await_app(page)                  # wait for controls to mount (heavy views)
                if v.get("click"):
                    try:
                        page.get_by_text(v["click"], exact=False).first.click(timeout=5000)
                        _await_app(page)          # view switched → let the new view mount
                    except Exception:
                        pass
                return _enumerate(page)           # retry-enumerate (robust to slow render)
            controls = _load_and_enumerate()
            if not controls:                      # transient blank render (heavy view under load) → reload once
                try:
                    page.reload(wait_until="load", timeout=30000)
                    controls = _load_and_enumerate()
                except Exception:
                    pass
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
