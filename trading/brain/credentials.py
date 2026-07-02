"""trading/brain/credentials.py — the brain's ENCRYPTED credential vault + chat-request flow.

The autonomous web agent (computer-use / browser) sometimes hits a login wall on a site it
wants to READ (broker data page, a paywalled paper). Instead of storing passwords in plaintext
or hard-coding them, the brain:
  1. raises a `request_login(site, fields)` — a PENDING request the dashboard chat surfaces
     ("🔐 Brain needs a login for angelone.in — reply with username + password");
  2. the operator answers in the chat box → `submit(site, values)` encrypts + stores it;
  3. the browser agent calls `get(site)` at use-time (values are NEVER logged or returned in status).

Security (honest): values are Fernet-encrypted at rest in trading/state/credentials.enc (gitignored).
The master key comes from env VAULT_KEY if set (best — keep it off-disk), else a machine-local
0600 key file trading/state/.vault_key (gitignored). Co-locating key+blob is only mild protection
— for real hardening set VAULT_KEY in the environment. `status()` exposes only site names + which
fields are set + pending requests — never a secret value. EXECUTION never uses these (APIs only);
the vault is for READ-ONLY site access + data screening.
"""
from __future__ import annotations

import os
import stat
import time

_KEY_FILE = ".vault_key"
_ENC_FILE = "credentials.enc"


def _fernet():
    from cryptography.fernet import Fernet
    from trading import state
    key = os.environ.get("VAULT_KEY")
    if key:
        return Fernet(key.encode() if isinstance(key, str) else key)
    # machine-local key file (0600, gitignored)
    path = state._path(_KEY_FILE)
    if path.exists():
        k = path.read_bytes()
    else:
        k = Fernet.generate_key()
        path.write_bytes(k)
        try:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)   # 0600
        except Exception:
            pass
    return Fernet(k)


class CredentialVault:
    """Encrypted store of site credentials + a pending-request queue for the chat flow."""

    def __init__(self):
        self._pending: dict[str, dict] = {}    # site -> {fields, note, ts} (in-memory, ephemeral)

    # ── encrypted store ────────────────────────────────────────────────────────────
    def _load(self) -> dict:
        from trading import state
        p = state._path(_ENC_FILE)
        if not p.exists():
            return {}
        try:
            import json
            return json.loads(_fernet().decrypt(p.read_bytes()).decode())
        except Exception:
            return {}

    def _store(self, data: dict) -> None:
        from trading import state
        import json
        blob = _fernet().encrypt(json.dumps(data).encode())
        p = state._path(_ENC_FILE)
        p.write_bytes(blob)
        try:
            os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)          # 0600
        except Exception:
            pass

    # ── chat-request flow ──────────────────────────────────────────────────────────
    def request_login(self, site: str, fields=("username", "password"), note: str = "") -> dict:
        """Brain raises a pending login request for `site`. Surfaced in the dashboard chat."""
        req = {"site": site, "fields": list(fields),
               "note": note or f"Brain needs to log into {site} (READ-ONLY data access).",
               "ts": time.time()}
        self._pending[site] = req
        return req

    def pending(self) -> list[dict]:
        return list(self._pending.values())

    def submit(self, site: str, values: dict) -> dict:
        """Operator answers a request in chat → encrypt + persist; clear the pending request.
        `values` = {field: secret}. Returns a SAFE receipt (field names only, no values)."""
        data = self._load()
        data[site] = {"values": {k: str(v) for k, v in (values or {}).items()},
                      "added_at": time.time()}
        self._store(data)
        self._pending.pop(site, None)
        return {"site": site, "fields": list((values or {}).keys()), "saved": True}

    # ── use-time (browser agent) ───────────────────────────────────────────────────
    def get(self, site: str) -> dict | None:
        """Decrypt + return {field: secret} for `site` (browser agent use-time). None if absent.
        NEVER log the result."""
        entry = self._load().get(site)
        return dict(entry["values"]) if entry else None

    def has(self, site: str) -> bool:
        return site in self._load()

    def forget(self, site: str) -> bool:
        data = self._load()
        if site in data:
            del data[site]
            self._store(data)
            return True
        return False

    # ── honest status (NO secret values) ────────────────────────────────────────────
    def status(self) -> dict:
        data = self._load()
        return {
            "stored_sites": [{"site": s, "fields": list(v.get("values", {}).keys()),
                              "added_at": v.get("added_at")} for s, v in data.items()],
            "pending_requests": self.pending(),
            "encryption": "fernet",
            "key_source": "env:VAULT_KEY" if os.environ.get("VAULT_KEY") else "local_key_file(0600)",
            "note": ("values are Fernet-encrypted at rest (gitignored); execution uses APIs only, "
                     "this vault is for READ-ONLY site access. Set VAULT_KEY in env for stronger "
                     "key isolation."),
        }


_VAULT: CredentialVault | None = None


def get_vault() -> CredentialVault:
    global _VAULT
    if _VAULT is None:
        _VAULT = CredentialVault()
    return _VAULT
