#!/usr/bin/env python3
"""
dashboard-visual-qa — screenshot + before/after diff + load-perf + "landed" check
for the dashboard / FreqUI / OpenAlgo views. Report-only; drives the decision on
the fastest-loading, top-design version. Generalizes dashboard/verify_render.py.

Reuse: Playwright (headless chromium, browsers already cached), Performance API for
load metrics (lighter than Lighthouse; pass --lighthouse for a full npx audit),
PIL+numpy for pixel diff. Secrets (basic-auth) come from env, never printed.

Usage:
    python visual_qa.py --label baseline            # capture all reachable views
    python visual_qa.py --label current --views main
    python visual_qa.py --compare                   # diff baseline vs current
    python visual_qa.py --promote                    # accept current as new baseline
Env: DASH_USER (default admin), DASH_PASS (basic-auth password, optional)
     VISUAL_QA_VIEWS = JSON list [{"name","url","auth":true}] to override views.
"""
from __future__ import annotations
import argparse, json, os, shutil, socket, subprocess, sys, time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "research" / "visual-qa"
CHROMIUM_ARGS = ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist",
                 "--enable-unsafe-swiftshader"]

DEFAULT_VIEWS = [
    {"name": "main", "url": "http://localhost:8000/", "auth": True},
    # FreqUI (base /frequi/) mounts only via the Caddy gateway :8100/frequi/ (auth-gated),
    # NOT direct :8080/ which serves a blank shell. See memory frequi-blank-gateway-path.
    {"name": "frequi", "url": "http://localhost:8100/frequi/", "auth": True},
]


def views():
    env = os.environ.get("VISUAL_QA_VIEWS")
    if env:
        try:
            return json.loads(env)
        except Exception:
            pass
    return DEFAULT_VIEWS


def reachable(url: str) -> bool:
    u = urlparse(url)
    try:
        with socket.create_connection((u.hostname, u.port or 80), timeout=2):
            return True
    except Exception:
        return False


PERF_JS = """() => {
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const paint = performance.getEntriesByType('paint') || [];
  const fcp = (paint.find(p=>p.name==='first-contentful-paint')||{}).startTime || null;
  const res = performance.getEntriesByType('resource') || [];
  let transfer = (nav.transferSize||0);
  res.forEach(r => transfer += (r.transferSize||0));
  const root = document.querySelector('#root') || document.body;
  return {
    domContentLoaded: Math.round(nav.domContentLoadedEventEnd||0),
    loadEvent: Math.round(nav.loadEventEnd||0),
    firstContentfulPaint: fcp ? Math.round(fcp) : null,
    resourceCount: res.length,
    transferBytes: Math.round(transfer),
    rootChildren: root ? root.children.length : 0,
  };
}"""


def capture(label: str, only=None):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[visual-qa] Playwright not installed for this python. "
              "Ask to run: pip install playwright  (chromium browsers are already cached).")
        return 2
    user = os.environ.get("DASH_USER", "admin")
    pw = os.environ.get("DASH_PASS")
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=CHROMIUM_ARGS)
        for v in views():
            if only and v["name"] not in only:
                continue
            if not reachable(v["url"]):
                print(f"[visual-qa] skip {v['name']}: {v['url']} not reachable")
                continue
            creds = {"username": user, "password": pw} if (v.get("auth") and pw) else None
            ctx = browser.new_context(viewport={"width": 1400, "height": 900},
                                      http_credentials=creds)
            page = ctx.new_page()
            errors, page_errors = [], []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: page_errors.append(str(e)))
            t0 = time.time()
            # "load" not "networkidle": a live-polling dashboard never goes network-quiet, so
            # networkidle would hang until timeout. wait_for_timeout below gives fetches time.
            resp = page.goto(v["url"], wait_until="load", timeout=30000)
            page.wait_for_timeout(4000)
            perf = {}
            try:
                perf = page.evaluate(PERF_JS)
            except Exception as e:
                perf = {"error": str(e)}
            body_len = len(page.content())
            vdir = OUT / v["name"]
            vdir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(vdir / f"{label}.png"), full_page=True)
            status = resp.status if resp else None
            landed = bool(status == 200 and (perf.get("rootChildren", 0) > 0 or body_len > 2000))
            meta = {"url": v["url"], "http_status": status, "landed": landed,
                    "console_errors": errors[:20], "page_errors": page_errors[:20],
                    "body_len": body_len, "wall_ms": round((time.time() - t0) * 1000),
                    "perf": perf, "label": label, "stamp": time.strftime("%Y%m%d-%H%M%S")}
            (vdir / f"{label}.json").write_text(json.dumps(meta, indent=2))
            results[v["name"]] = meta
            flag = "OK " if landed and not errors else "!! "
            print(f"[visual-qa] {flag}{v['name']}: status={status} landed={landed} "
                  f"errors={len(errors)} load={perf.get('loadEvent')}ms "
                  f"fcp={perf.get('firstContentfulPaint')}ms bytes={perf.get('transferBytes')}")
            ctx.close()
        browser.close()
    if not results:
        print("[visual-qa] no views captured (nothing reachable). Is the dashboard running?")
    return 0


def _pixel_diff(base: Path, cur: Path):
    try:
        from PIL import Image, ImageChops
        import numpy as np
    except Exception:
        return {"available": False, "hint": "pip install pillow"}
    a = Image.open(base).convert("RGB")
    b = Image.open(cur).convert("RGB")
    size_changed = a.size != b.size
    if size_changed:
        b = b.resize(a.size)
    diff = ImageChops.difference(a, b)
    arr = np.asarray(diff)
    changed_ratio = float((arr.sum(axis=2) > 24).mean())
    return {"available": True, "size_changed": size_changed, "base_size": a.size,
            "cur_size": Image.open(cur).size, "changed_pct": round(changed_ratio * 100, 2),
            "bbox": diff.getbbox()}


def compare():
    stamp = time.strftime("%Y%m%d-%H%M%S")
    L = [f"# Dashboard visual-QA — baseline vs current ({stamp})\n"]
    any_view = False
    for v in views():
        vdir = OUT / v["name"]
        base, cur = vdir / "baseline.png", vdir / "current.png"
        if not cur.exists():
            continue
        any_view = True
        L.append(f"## View: `{v['name']}`  ({v['url']})")
        cmeta = json.loads((vdir / "current.json").read_text()) if (vdir / "current.json").exists() else {}
        bmeta = json.loads((vdir / "baseline.json").read_text()) if (vdir / "baseline.json").exists() else {}
        # landed / errors
        L.append(f"- **Landed:** {cmeta.get('landed')}  ·  http {cmeta.get('http_status')}  ·  "
                 f"console-errors {len(cmeta.get('console_errors', []))}  ·  "
                 f"page-errors {len(cmeta.get('page_errors', []))}")
        for e in cmeta.get("console_errors", [])[:5]:
            L.append(f"  - console error: `{e}`")
        # perf delta
        cp, bp = cmeta.get("perf", {}), bmeta.get("perf", {})
        def d(k):
            cv, bv = cp.get(k), bp.get(k)
            if isinstance(cv, (int, float)) and isinstance(bv, (int, float)):
                arrow = "🔺slower/heavier" if cv > bv else ("🟢faster/lighter" if cv < bv else "=")
                return f"{bv} → {cv} ({arrow})"
            return f"{bv} → {cv}"
        L.append(f"- **Load event:** {d('loadEvent')} ms")
        L.append(f"- **First contentful paint:** {d('firstContentfulPaint')} ms")
        L.append(f"- **Transfer:** {d('transferBytes')} bytes  ·  **Resources:** {d('resourceCount')}")
        # pixel diff
        if base.exists():
            pd = _pixel_diff(base, cur)
            if pd.get("available"):
                L.append(f"- **Pixel change:** {pd['changed_pct']}%  ·  changed-region bbox {pd['bbox']}"
                         + ("  ·  ⚠️ canvas size changed" if pd["size_changed"] else ""))
            else:
                L.append(f"- **Pixel diff:** unavailable ({pd['hint']})")
        else:
            L.append("- **Pixel diff:** no baseline yet (run `--label baseline` on a known-good build).")
        L.append(f"- Screenshots: `{base.relative_to(ROOT) if base.exists() else '—'}` (baseline) · "
                 f"`{cur.relative_to(ROOT)}` (current)\n")
    if not any_view:
        print("[visual-qa] nothing to compare — capture `current` first.")
        return 1
    L.append("---\n_Reviewer: open the before/after PNGs, confirm the view **landed** (renders, no "
             "console errors), pick the **fastest-loading, lightest, top-design** version. "
             "If current regressed load/errors, recommend reverting or optimizing. `--promote` accepts current as baseline._")
    OUT.mkdir(parents=True, exist_ok=True)
    rep = OUT / f"report-{stamp}.md"
    rep.write_text("\n".join(L))
    print(f"[visual-qa] report -> {rep.relative_to(ROOT)}")
    return 0


def promote():
    for v in views():
        vdir = OUT / v["name"]
        for ext in ("png", "json"):
            cur = vdir / f"current.{ext}"
            if cur.exists():
                shutil.copy2(cur, vdir / f"baseline.{ext}")
                print(f"[visual-qa] promoted {v['name']} current -> baseline ({ext})")


def lighthouse(url):
    if not shutil.which("npx"):
        print("[visual-qa] npx not found; cannot run Lighthouse."); return
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"lighthouse-{urlparse(url).port}.json"
    print(f"[visual-qa] running Lighthouse on {url} (npx downloads on first run)...")
    subprocess.run(["npx", "--yes", "lighthouse", url, "--quiet", "--chrome-flags=--headless",
                    "--only-categories=performance", "--output=json", f"--output-path={out}"],
                   cwd=str(ROOT))
    print(f"[visual-qa] lighthouse -> {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", help="capture all reachable views under this label (e.g. baseline/current)")
    ap.add_argument("--views", nargs="*", help="limit to these view names")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--promote", action="store_true")
    ap.add_argument("--lighthouse", metavar="URL")
    args = ap.parse_args()
    if args.lighthouse:
        return lighthouse(args.lighthouse)
    if args.promote:
        return promote()
    if args.compare:
        return compare()
    if args.label:
        return capture(args.label, only=set(args.views) if args.views else None)
    ap.print_help()


if __name__ == "__main__":
    sys.exit(main() or 0)
