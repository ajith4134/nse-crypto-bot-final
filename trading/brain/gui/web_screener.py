"""trading/brain/gui/web_screener.py — the brain's autonomous READ-ONLY web screener.

Opens external sites (broker data pages, TradingView, Google, news) in its OWN headless
Chromium browser and SCREENS them for data it lacks — candle-chart visuals (screenshot + OCR),
order-book / depth, in-app news, filters — plus Google-browses to fill knowledge gaps. Every
visit emits an EPHEMERAL transparency event (what it opened + what it learned) that the
dashboard shows and auto-clears on view.

HARD read-only guard (operator directive): the screener only NAVIGATES, fills a LOGIN form
(with vault creds), screenshots, and READS. It NEVER clicks order/submit-trade/buy/sell
controls — execution stays 100% on the APIs (ccxt/OpenAlgo), so there's no ToS/ban exposure.
When a site needs a login it doesn't have, it raises a credential request (chat) and stops.

Reuse-first: Playwright (installed) for the browser, OcrReader (PaddleOCR) for chart pixels,
ddgs for Google-style search, the credential vault for logins, the activity feed for transparency.
"""
from __future__ import annotations

import os
import re
import time
from urllib.parse import urlparse

# controls we must NEVER click — the read-only guard
_FORBIDDEN = re.compile(r"\b(buy|sell|order|submit|place|trade|confirm|withdraw|transfer|"
                        r"long|short|leverage|deposit)\b", re.I)
_DEFAULT_ALLOWLIST = (
    "tradingview.com", "coingecko.com", "coinmarketcap.com", "binance.com", "bybit.com",
    "angelone.in", "upstox.com", "nseindia.com", "google.com", "arxiv.org",
    "cointelegraph.com", "coindesk.com", "investing.com", "moneycontrol.com",
)


def _domain(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except Exception:
        return ""


class WebScreener:
    """Autonomous read-only browser: screen a URL / Google a gap → structured findings + feed."""

    def __init__(self, *, headless: bool = True, allowlist=None):
        self.headless = headless
        self.allowlist = tuple(allowlist) if allowlist else _DEFAULT_ALLOWLIST

    def allowed(self, url: str) -> bool:
        d = _domain(url)
        return any(d == a or d.endswith("." + a) for a in self.allowlist)

    # ── one read-only visit ─────────────────────────────────────────────────────
    def screen(self, url: str, *, site: str | None = None, want_ocr: bool = True,
               timeout_ms: int = 25000, allow_offlist: bool = False) -> dict:
        """Open `url` read-only → {title, text, controls, ocr, needs_login, learned}. Emits an
        ephemeral feed event. If a login wall is hit and no creds are stored, raises a vault
        request and returns needs_login=True.

        `allow_offlist=True` (used by Google gap-browsing) permits reading ANY public page
        read-only — but a LOGIN is only ever attempted on an allowlisted site, so off-allowlist
        pages are read-only-no-login by construction."""
        from trading.brain import activity_feed as feed
        site = site or _domain(url)
        on_allowlist = self.allowed(url)
        if not on_allowlist and not allow_offlist:
            feed.emit("note", f"Skipped {site} (not on allowlist)", site=site)
            return {"available": False, "reason": "not on allowlist", "site": site}
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            return {"available": False, "reason": f"playwright missing: {e}", "site": site}

        out = {"available": True, "site": site, "url": url, "title": "", "text": "",
               "controls": [], "ocr": [], "needs_login": False, "learned": ""}
        shot = f"/tmp/webscreen_{abs(hash(url)) % 10**8}.png"
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=self.headless)
                page = browser.new_page(viewport={"width": 1600, "height": 1200})
                page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)                       # let charts/JS render
                out["title"] = (page.title() or "")[:200]

                # login wall? (a visible password field) — only pursue a login on ALLOWLISTED
                # sites; off-allowlist gap-browsing stays read-only-no-login (just reads public).
                has_login = on_allowlist and page.query_selector("input[type=password]") is not None
                if has_login:
                    logged = self._try_login(page, site)
                    out["needs_login"] = not logged
                    if not logged:
                        browser.close()
                        from trading.brain.credentials import get_vault
                        get_vault().request_login(site, ["username", "password"],
                                                  f"Brain wants to READ {url} but needs a login.")
                        feed.emit("login_needed", f"Needs login for {site}", site=site,
                                  learned=f"Paused — asked you for {site} credentials in chat.")
                        return out
                    page.wait_for_timeout(2000)

                # READ: visible text (news/filters), interactive controls (read-only labels)
                body = (page.inner_text("body") or "")[:6000]
                out["text"] = body
                for el in page.query_selector_all("button, a[role=button], [class*=filter]")[:40]:
                    try:
                        t = (el.inner_text() or "").strip()[:40]
                        if t:
                            out["controls"].append(t)
                    except Exception:
                        pass
                if want_ocr:
                    try:
                        page.screenshot(path=shot, full_page=False)
                    except Exception:
                        shot = None
                browser.close()
        except Exception as e:
            feed.emit("note", f"Could not open {site}", site=site, learned=str(e)[:120])
            return {"available": False, "reason": str(e)[:160], "site": site}

        # OCR the chart pixels (numbers/labels the DOM can't expose)
        if want_ocr and shot and os.path.exists(shot):
            try:
                from trading.brain.gui.perception import OcrReader
                res = OcrReader().read_image(shot, max_items=60)
                out["ocr"] = res.get("items", res) if isinstance(res, dict) else res
            except Exception:
                out["ocr"] = []
            finally:
                try: os.remove(shot)
                except Exception: pass

        out["learned"] = self._summarize(out)
        feed.emit("read", f"Screened {site}", site=site, detail=out["title"],
                  learned=out["learned"], data={"controls": out["controls"][:8]})
        return out

    def _try_login(self, page, site: str) -> bool:
        """Best-effort generic login with vault creds (read-only intent). Returns True if it
        submitted a login (not a 2FA guarantee). Never raises."""
        try:
            from trading.brain.credentials import get_vault
            creds = get_vault().get(site)
            if not creds:
                return False
            user = creds.get("username") or creds.get("email") or creds.get("client_id")
            pw_ = creds.get("password")
            if not (user and pw_):
                return False
            u = page.query_selector("input[type=email], input[type=text], input[name*=user i], input[name*=email i]")
            p = page.query_selector("input[type=password]")
            if u and p:
                u.fill(str(user)); p.fill(str(pw_))
                btn = page.query_selector("button[type=submit], input[type=submit]")
                if btn and not _FORBIDDEN.search((btn.inner_text() or "")):
                    btn.click()
                else:
                    p.press("Enter")
                page.wait_for_timeout(3000)
                return page.query_selector("input[type=password]") is None   # login form gone
        except Exception:
            return False
        return False

    @staticmethod
    def _summarize(out: dict) -> str:
        """One-line 'what I learned' from the screened page (title + salient OCR numbers)."""
        nums = []
        for it in (out.get("ocr") or [])[:30]:
            txt = it.get("text") if isinstance(it, dict) else str(it)
            if txt and re.search(r"\d", txt):
                nums.append(txt.strip())
        head = out.get("title") or out.get("site")
        tail = (" · figures: " + ", ".join(nums[:6])) if nums else ""
        return (head + tail)[:240]

    # ── Google-browse a knowledge gap ────────────────────────────────────────────
    def google_gap(self, query: str, *, max_sites: int = 1) -> dict:
        """Search the web for a knowledge gap, open the top result(s) read-only, screen them.
        Fills gaps in the brain's knowledge (not just trading)."""
        from trading.brain import activity_feed as feed
        try:
            from ddgs import DDGS
            rows = DDGS().text(query, max_results=6) or []
        except Exception as e:
            return {"available": False, "reason": f"search failed: {e}", "query": query}
        feed.emit("opened", f"Google gap: {query[:60]}", learned=f"{len(rows)} results")
        screened = []
        for r in rows:
            url = r.get("href") or r.get("url") or ""
            if url.startswith("http"):
                screened.append(self.screen(url, allow_offlist=True, want_ocr=False))  # read-only, any public page
                if len(screened) >= max_sites:
                    break
        return {"available": True, "query": query, "n_results": len(rows),
                "screened": [{"site": s.get("site"), "learned": s.get("learned")} for s in screened]}


_SCREENER: WebScreener | None = None


def get_screener() -> WebScreener:
    global _SCREENER
    if _SCREENER is None:
        _SCREENER = WebScreener()
    return _SCREENER
