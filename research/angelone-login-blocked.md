# Angel One web login is server-blocked for automated browsers (2026-07-06)

## Evidence (live probes, screenshots in session scratchpad)
- `https://www.angelone.in/login/` responds **"Unable to authenticate you with this device, please try again"** to PROCEED for BOTH mobile-number and client-ID identities — whether the fill/click came from code or from the OWNER typing through the LiveBrowserPanel stream. The rejection is fingerprint-based (headless/automated browser), not identity-based.
- **QR login generation is blocked the same way**: clicking GENERATE QR consumes the button but no scannable QR is ever issued (placeholder stays blurred), on fresh pages too.
- The old registry URL `angelone.in/stocks/screener` 404s; the real login lives at `angelone.in/login/` (trade.angelone.in redirects there). Fixed in `trading/broker_sense/brokers.py`.
- Two of our own bugs found while probing (both fixed + regression-tested in
  `tests/test_broker_sense.py::TestOtpBoxDetection` and sessions.py):
  1. invisible reCAPTCHA v3 badge false-flagged as a human CAPTCHA (`_challenge_present` now requires a VISIBLE widget);
  2. the step-1 mobile input (`inputmode=numeric`) false-flagged as an OTP box → "OTP sent" with no SMS (`_otp_attrs_are_code_box` predicate).

## Decision: do NOT fight the fingerprinting (bot-detection evasion). Use the official door.
**SmartAPI** (https://smartapi.angelone.in) is Angel One's free, official API for retail
automation: login = client ID + PIN + TOTP; gives quotes, OHLCV candles, market movers,
order book, positions — everything the broker-sense NSE account lane needs, plus optional
order APIs later. Official SDK: `smartapi-python` (pip) + `pyotp` for the TOTP.

## Owner one-time signup (pending)
1. smartapi.angelone.in → Sign Up (login with the Angel One account)
2. Create App (type: Trading APIs; any name; redirect URL http://127.0.0.1) → copy **API Key**
3. smartapi.angelone.in/enable-totp → login (client ID + PIN) → copy the **TOTP text secret**
4. Hand api_key + totp_secret to the brain (vault fields `api_key`, `totp_secret` on site angelone.in)

## Build plan once keys arrive
- pip install smartapi-python pyotp (ask-to-install honored: user approved by handing keys)
- `trading/broker_sense/smartapi_source.py`: login/session cache + movers/quotes/candles
- Wire as the angelone ACCOUNT lane: `account_screen` fast path (before the browser fallback)
  + `fast_candles`/`_fast_book` NSE branch → funnel LOOK/VERIFY stages get real NSE data
- Keep browser lanes for brokers that allow it (Binance session works fine on disk)
