"""trading/broker_sense/stealth.py — make the brain's browser look like a human's.

Binance (and other broker apps) fingerprint the browser and throw a "Security Verification"
CAPTCHA when it smells automated. A fingerprint probe of our Chromium (2026-07-12) found the
tells that trip it on this GCP VM:

  • WebGL vendor/renderer = 'SwiftShader'  → software rendering, no GPU = VM/headless signature
  • navigator.plugins.length = 0           → real browsers ship a PDF plugin
  • window.chrome missing                   → present in every real desktop Chrome
  • navigator.webdriver truthy             → the canonical automation flag
  • one language, UTC timezone             → weak, but adds up

apply(context) injects ONE init script (runs before any page script on every page/frame of
the context) that patches these to realistic values — the same technique playwright-stealth
uses, hand-rolled so there's no extra dependency and we control exactly what's spoofed. It is
COSMETIC fingerprint hardening only: it changes nothing the brain reads from the market and
places no orders. The datacenter-IP signal it CANNOT fix — that needs a residential egress.

Levers: BROKER_STEALTH=0 disables; BROKER_STEALTH_WEBGL_VENDOR / _RENDERER override the spoofed
GPU strings.
"""
from __future__ import annotations

import os

# A plausible mainstream integrated GPU — matches what a typical laptop reports, so the WebGL
# fingerprint stops screaming "SwiftShader / VM". Overridable via env.
_WEBGL_VENDOR = os.getenv("BROKER_STEALTH_WEBGL_VENDOR", "Intel Inc.")
_WEBGL_RENDERER = os.getenv("BROKER_STEALTH_WEBGL_RENDERER",
                            "Intel Iris OpenGL Engine")


def enabled() -> bool:
    return os.getenv("BROKER_STEALTH", "1").strip().lower() not in ("0", "false", "off")


def _script() -> str:
    # Kept defensive: every patch is wrapped so a browser that already looks right (or a
    # future Chromium that locks a property) can't throw and abort page setup.
    return (
        "(() => { try {"
        # 1) navigator.webdriver → undefined (the #1 automation tell)
        "  try { Object.defineProperty(navigator,'webdriver',{get:()=>undefined}); } catch(e){}"
        # 2) window.chrome — a minimal but present runtime object like real Chrome
        "  try { if(!window.chrome){ window.chrome = { runtime:{}, app:{}, csi:function(){},"
        "        loadTimes:function(){} }; } } catch(e){}"
        # 3) navigator.plugins / mimeTypes — a non-empty, PDF-capable set
        "  try { const mk=(n,f)=>({name:n,filename:f,description:n,length:1});"
        "        const plugins=[mk('Chrome PDF Plugin','internal-pdf-viewer'),"
        "          mk('Chrome PDF Viewer','mhjfbmdgcfjbbpaeojofohoefgiehjai'),"
        "          mk('Native Client','internal-nacl-plugin')];"
        "        Object.defineProperty(navigator,'plugins',{get:()=>plugins});"
        "        Object.defineProperty(navigator,'mimeTypes',{get:()=>[{type:'application/pdf'}]});"
        "  } catch(e){}"
        # 4) languages → a realistic two-entry list
        "  try { Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']}); } catch(e){}"
        # 5) WebGL vendor/renderer → a real GPU instead of SwiftShader (the strongest VM tell)
        "  try { const V=%r, R=%r;"
        "    const patch=(proto)=>{ if(!proto) return; const g=proto.getParameter;"
        "      proto.getParameter=function(p){ if(p===37445) return V; if(p===37446) return R;"
        "        return g.apply(this,[p]); }; };"
        "    if(window.WebGLRenderingContext) patch(WebGLRenderingContext.prototype);"
        "    if(window.WebGL2RenderingContext) patch(WebGL2RenderingContext.prototype);"
        "  } catch(e){}"
        # 6) permissions.query — headless returns 'denied' for notifications where a real one
        #    returns 'prompt'; align them so the mismatch check passes
        "  try { const orig=navigator.permissions && navigator.permissions.query;"
        "    if(orig){ navigator.permissions.query=(p)=> p && p.name==='notifications' ?"
        "      Promise.resolve({state: Notification.permission}) : orig(p); } } catch(e){}"
        "} catch(e){} })();"
    ) % (_WEBGL_VENDOR, _WEBGL_RENDERER)


def apply(context) -> bool:
    """Inject the stealth init script into a Playwright context (runs on every page/frame,
    before site scripts). Best-effort; never raises. Returns True if injected."""
    if not enabled() or context is None:
        return False
    try:
        context.add_init_script(_script())
        return True
    except Exception:
        return False
