# Understanding: AngelOne Login + Navigation
**Video:** VIDEO20260705175955.mp4 | Duration: ~1m44s | Frames: 11 (ingest) + 35 (manual)  
**Date analyzed:** 2026-07-05

---

## Summary
The user manually demonstrates the full flow of logging into AngelOne (India's NSE/BSE broker) using mobile-number + OTP authentication, then navigating through the account overview, equity markets overview (top movers), option chain for NIFTY, and individual stock charts. The video is a demonstration of what the user wants the brain to automate.

---

## Every Distinct Element (with frame timestamps)

### [00:00] Login Page
- URL: `angelone.in/login/redirectlid=account`
- Form: "Login with Mobile Number" radio selected
- Mobile number entered: **7702664278**
- Alternative: "Login with Client ID"
- "PROCEED" button (blue)
- "GENERATE QR" option (for QR-code login)
- Left panel shows: "Access Advanced Trading Analytics — Analyse price action trading activity, discover hidden patterns, and make smarter trading decisions"

### [00:12] OTP Screen
- URL: same login URL
- Message: "OTP Sent — We have sent an OTP to your mobile number and registered email address"
- Input field: "Enter your OTP" with **00:24 countdown timer**
- "PROCEED" button below

### [00:27] Account Page (post-login)
- URL: `angelone.in/trade/account`
- Header: NIFTY 34,270.85 ▲+95.15 (+0.38%), SENSEX ₹74,63.31 ▲+263.79 (+0.34%)
- Account: **Dudekula Ajith** | VIEW PROFILE
- Trading Balance: **₹ 0.00**
- VIEW TRADING BALANCE SUMMARY link
- Buttons: WITHDRAW FUNDS | ADD FUNDS
- Reports section: Trades & Charges, Statements, Profit & Loss, Trading Insights
- Pledging & Pay Later: Pledge Holdings For Extra Margin | MTF | Transfer Stocks
- "Ask Angel" AI chat button (bottom right)

### [00:42] Account Page (same, user navigating nav tabs)
- Nav tabs visible: Markets | TradeOne | Portfolio | Orders | Positions | Tools
- "Markets" tab highlighted/being navigated to

### [00:50] Option Chain Popup
- Account page still open in background
- **Option Chain modal** overlay open
- NIFTY selected | 01 AUG 24 (expiry date shown)
- CALL side | PUT side columns
- Strike prices visible: around 19150, 19350, 19450, 19500, 19750, 19850, 20000 range
- Current spot: ~24270 (from header)
- Data columns: likely OI, Premium, Delta columns (small text)

### [01:00] Markets → Equity Overview
- URL: `angelone.in/trade/markets/equity/overview`
- Sub-tabs: Stock Discovery | Index F&O | Stocks F&O | Commodities | All Indexes | News
- "Stock Discovery" selected
- Featured stocks: IDEA (₹14.25), YESBANK (₹24.38), JPOWER (₹17.88), APPOWER (₹323.79)
- **Top Movers and Sectorwise Movements** table
- Gainers tab | Losers tab (Gainers selected)
- Filter: Index | Market Cap | Sector | IT | Software | Finance/NBFC
- Stock rows: SUMICHEM (+43.65%), ZENSARTECH (+45.40%), AERONOVIRKA (-3.80%), TCL.ERA (+*), HELTECH (+5.01%), PINELARE, WIPRO, PANTIV, IGNATIOPIN, LATEVIEWW
- "Top Performers" section visible at bottom

### [01:12] SUMICHEM Stock Chart
- SUMICHEM NSE stock popup/panel
- Price: ₹502.30 ▲+49.13 (+10.84%)
- Company: Summons Chem India Ltd
- BUY ₹492.30 | SELL ₹492.30 buttons (Instant Orders)
- Watchlist button
- Chart: TradingView embedded
- Timeframe: 5m | 10s interval
- Price range visible: ~₹480–₹530
- Volume bars below chart
- Bottom row: 1D 5D 1M 3M 6M 1Y 1Y 3Y

### [01:27] Same SUMICHEM chart (user reviewing)
- Same view, user appears to be studying chart before possibly placing order

---

## Open Questions

1. **OTP handling:** The OTP is sent to mobile 7702664278. The brain cannot auto-receive SMS OTPs. Will the user enter the OTP manually (brain pauses and waits), or should the brain use TOTP/authenticator if set up?

2. **What should brain DO after login?** Just read and report data? Or also place trades? (User said "read the data and process the data and works with data and uses that data")

3. **Credentials storage:** Password is not shown (OTP-based login). The mobile number is 7702664278. Where should credentials be stored? (credential vault in trading/brain/credentials.py)

4. **Which data to extract?** Account balance, NIFTY/SENSEX index, top movers list, option chain data, or specific stock charts?

5. **Option chain:** The user opened NIFTY option chain popup — does the brain need to read option chain data (OI, premiums, greeks)?
