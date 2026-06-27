import sys
from playwright.sync_api import sync_playwright

URL = "http://localhost:8000/"
USER = "admin"
PASS = sys.argv[1]
SHOT = "/home/karan18190164/dashboard/dashboard_screenshot.png"

console_msgs = []
errors = []
page_errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--use-gl=swiftshader",
            "--enable-webgl",
            "--ignore-gpu-blocklist",
            "--enable-unsafe-swiftshader",
        ],
    )
    ctx = browser.new_context(
        viewport={"width": 1400, "height": 900},
        http_credentials={"username": USER, "password": PASS},
    )
    page = ctx.new_page()

    def on_console(msg):
        console_msgs.append((msg.type, msg.text))
        if msg.type == "error":
            errors.append(msg.text)

    page.on("console", on_console)
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    resp = page.goto(URL, wait_until="networkidle", timeout=30000)
    print("HTTP status:", resp.status if resp else "none")
    page.wait_for_timeout(6000)

    # Assertion: app content present
    selectors = [".kpi", ".graphwrap"]
    found_sel = None
    for s in selectors:
        if page.query_selector(s):
            found_sel = s
            break
    has_headline = page.get_by_text("Headline accuracy").count() > 0 if True else False
    try:
        has_headline = "Headline accuracy" in page.content()
    except Exception:
        has_headline = False

    assertion_passed = bool(found_sel) or has_headline
    canvas_count = len(page.query_selector_all("canvas"))

    # WebGL context check
    webgl_ok = page.evaluate(
        """() => {
            const c = document.createElement('canvas');
            const gl = c.getContext('webgl') || c.getContext('experimental-webgl') || c.getContext('webgl2');
            if (!gl) return {ok:false};
            return {ok:true, renderer: gl.getParameter(gl.getParameter ? 0x1F01 : 0)};
        }"""
    )

    body_len = len(page.content())
    title = page.title()

    page.screenshot(path=SHOT, full_page=True)
    browser.close()

print("=== RESULTS ===")
print("title:", title)
print("assertion_passed:", assertion_passed)
print("found_selector:", found_sel)
print("has_headline_text:", has_headline)
print("canvas_count:", canvas_count)
print("webgl_context_creatable:", webgl_ok)
print("body_html_length:", body_len)
print("console_error_count:", len(errors))
for i, e in enumerate(errors):
    print(f"  CONSOLE_ERROR[{i}]: {e!r}")
print("pageerror_count:", len(page_errors))
for i, e in enumerate(page_errors):
    print(f"  PAGEERROR[{i}]: {e!r}")
print("--- all console (non-error) ---")
for t, txt in console_msgs:
    if t != "error":
        print(f"  [{t}] {txt!r}")
