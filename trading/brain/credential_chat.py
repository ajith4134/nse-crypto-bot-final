"""trading/brain/credential_chat.py — capture a credential answer typed into Brain Chat.

When the brain has a PENDING login ask (e.g. "connect your Binance account") and the operator
answers in the free-text chat box, that message must go to the ENCRYPTED VAULT — never to the
cloud LLM. Before this, every message hit the LLM, which (correctly, as a generic assistant)
refused to store passwords — and worse, the password was sent to a cloud provider.

`try_capture(message)` runs FIRST in the chat pipeline:
  • no pending ask                     → None  (normal chat)
  • message parses as the asked fields → submits to the vault, returns a SAFE confirmation
                                          (field names only, never the values), no LLM call
  • pending ask + looks like a fumbled → returns GUIDANCE (the exact format), no LLM call, so a
    secret                                partially-typed secret still never reaches the LLM
  • pending ask + a normal question     → None  (falls through to normal chat)

Secrets-safe: values are never logged, echoed, or returned; only field NAMES appear in replies."""
from __future__ import annotations

import re

_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
# labels accept ':' '=' '-' OR the word 'is' OR bare whitespace as the separator, so
# "password: x", "password is x" and "password x" all capture — a real secret must not slip
# past the label into the LLM.
_LABELS = {
    "username": re.compile(
        r"(?:user(?:\s*name|\s*id)?|email|e-?mail|client\s*id|clientid|mobile|login)\b"
        r"\s*(?:is\s+|[:=\-]+\s*)([^\s,;]+)", re.I),
    "password": re.compile(r"(?:pass(?:word)?|pwd|pin)\b\s*(?:is\s+|[:=\-]+\s*)([^\s,;]+)", re.I),
    "otp": re.compile(r"(?:otp|code|2fa|token)\b\s*(?:is\s+|[:=\-]+\s*)(\d{4,8})", re.I),
}


def _secret_like(message: str) -> bool:
    """A token that plausibly IS a secret (so we guide-not-LLM even if we can't parse it)."""
    if _EMAIL.search(message):
        return True
    toks = message.split()
    # a lone token (no spaces) while a login ask is pending is almost certainly the answer
    # (username or password) — even an all-lowercase, no-digit password like "correcthorse";
    # treat it as secret so it is GUIDED to the vault, never forwarded to the cloud LLM
    if len(toks) == 1 and len(toks[0]) >= 6:
        return True
    for tok in toks:
        if len(tok) >= 8 and re.search(r"\d", tok):
            return True
        if len(tok) >= 10 and re.search(r"[a-z]", tok) and re.search(r"[A-Z]", tok):
            return True
    return False


def _cred_shaped(value: str, message: str) -> bool:
    """A LABELED value is only trusted as a real credential if it looks like one — so a chatty
    'my password is broken' doesn't save the word 'broken' as the password."""
    if not value:
        return False
    if len(message.split()) <= 3:                # "email pass" style → trust
        return True
    return bool(len(value) >= 8 or re.search(r"[A-Z0-9@._\-]", value))   # else needs a secret-ish char


def _pick(pending: list[dict], message: str) -> dict:
    low = message.lower()
    for req in pending:                          # explicit site mention wins ("binance …")
        if req["site"].split(".")[0] in low:
            return req
    if len(pending) == 1:
        return pending[0]
    return sorted(pending, key=lambda r: r.get("ts", 0))[0]      # else oldest ask


def _synthesize(message: str) -> dict | None:
    """No live ask pending, but the operator EXPLICITLY names a known broker and gives labeled
    credentials → let them connect anyway (a TTL-expired ask must not block connecting)."""
    low = message.lower()
    try:
        from trading.broker_sense.brokers import REGISTRY
    except Exception:
        return None
    for app in REGISTRY.values():
        if not app.login_fields:
            continue
        if app.name in low or app.site.split(".")[0] in low:
            # require at least one LABELED field so this is unambiguous intent, not chatter
            if _LABELS["username"].search(message) or _LABELS["password"].search(message) \
                    or _LABELS["otp"].search(message):
                return {"site": app.site, "fields": ["username", "password"], "ts": 0}
    return None


_LABELISH = {"client", "clint", "user", "username", "userid", "id", "login", "email", "mail",
             "my", "is", "the", "and", "here", "it", "this", "code", "angelone", "angel", "one",
             "binance", "password", "pass", "pwd", "pin", "otp"}


def _lone_value(message: str) -> str | None:
    """SINGLE-FIELD ask fallback: when exactly one field is pending, the one credential-shaped
    token in a short non-question message IS the answer — a missing or typo'd label ("clint id")
    must not bounce the owner back to guidance, or worse let the value fall through to the LLM.
    Requires a digit or '@' in the token so chatter ("thanks") is never saved as a credential."""
    if "?" in message:
        return None
    toks = [t.strip(":=,;") for t in message.split() if t.strip(":=,;")]
    if not toks or len(toks) > 5:
        return None
    cand = [t for t in toks
            if t.lower() not in _LABELISH and 4 <= len(t) <= 80
            and re.fullmatch(r"[A-Za-z0-9@._\-]+", t) and re.search(r"[\d@]", t)]
    return cand[0] if len(cand) == 1 else None


def _parse(message: str, fields: list[str]) -> dict:
    """Extract the requested fields conservatively. Unlabeled captures only fire on a
    CREDENTIAL-SHAPED message (≤3 tokens) so a chatty sentence is never mistaken for a secret."""
    values: dict[str, str] = {}
    for f in fields:                             # labeled form → trust it only if the value looks
        pat = _LABELS.get(f)                      # like a credential (not a chatty sentence word)
        if pat:
            m = pat.search(message)
            if m and (f == "otp" or _cred_shaped(m.group(1).strip(), message)):
                values[f] = m.group(1).strip()
    shaped = len(message.split()) <= 3           # e.g. "email password" / "otp" / one token
    if "otp" in fields and "otp" not in values:  # OTP-only ask: a bare 4-8 digit code
        digits = re.sub(r"\D", "", message)
        if 4 <= len(digits) <= 8 and len(re.sub(r"[\s\-]", "", message)) <= 10:
            values["otp"] = digits
    if shaped and "username" in fields and "username" not in values:   # email = username
        em = _EMAIL.search(message)
        if em:
            values["username"] = em.group(0)
    if shaped and "password" in fields and "password" not in values and "username" in values:
        rest = message.replace(values["username"], " ")          # the other token = password
        toks = [t for t in re.split(r"[\s,;|]+", rest)
                if t and t.lower() not in ("username", "password", "email", "pass", "pwd",
                                           "pin", "and", "is", "my")]
        if len(toks) == 1 and 3 <= len(toks[0]) <= 80:
            values["password"] = toks[0]
    if len(fields) == 1 and fields[0] != "otp" and not values:
        val = _lone_value(message)               # single-field ask: label optional (typo-proof)
        if val:
            values[fields[0]] = val
    return values


def try_capture(message: str, pending: list[dict] | None = None):
    """Route a credential answer to the vault. See module docstring for the four outcomes."""
    message = (message or "").strip()
    if not message:
        return None
    from trading.brain.credentials import get_vault
    v = get_vault()
    if pending is None:
        pending = v.pending()
    if pending:
        req = _pick(pending, message)
    else:                                        # no live ask → only an EXPLICIT labeled connect
        req = _synthesize(message)
        if req is None:
            return None                          # nothing asked, not an explicit connect → chat
    site, fields = req["site"], list(req.get("fields", []))
    got = {f: val for f, val in _parse(message, fields).items() if f in fields}

    if got:
        v.submit(site, got)                      # encrypt + persist; clears the pending ask
        remaining = [f for f in fields if f not in got]
        saved = " + ".join(got.keys())
        reply = (f"✅ Saved your {site} {saved} — encrypted and stored locally, never sent to "
                 f"any LLM or logged.")
        if "password" in got:
            reply += " Next time I'll only need the OTP."
        if remaining:
            reply += f" I still need: {', '.join(remaining)} — send it the same way."
        return {"reply": reply, "sources": [], "thoughts": ["credential → encrypted vault"],
                "captured": True}

    # pending ask + the message carries a secret-like token we couldn't cleanly parse → GUIDE
    # instead of leaking it to the LLM. A plain question (no secret-like token) passes through.
    if _secret_like(message):
        need = " + ".join(fields)
        return {"reply": (f"🔐 To connect {site} I need {need}. Send it like "
                          f"`username: your-login  password: your-pass` (or use the Connect "
                          f"form) — I store it encrypted locally and NEVER send it to any LLM."),
                "sources": [], "thoughts": ["guided credential entry (no secret to LLM)"],
                "captured": False}
    return None                                  # a normal question → fall through to chat
