# Understanding: Coinbase Advanced Trade Login + Navigation
**Video:** VIDEO20260705175741.mp4 | Duration: ~1m44s | Frames: 11 (ingest) + 35 (manual)  
**Date analyzed:** 2026-07-05

---

## Summary
The user manually demonstrates logging into Coinbase Advanced Trade using email+password authentication, then navigating to the Derivatives/Futures section to view BTC perpetual order book, list of crypto futures contracts, and BTC futures price chart. Key constraint: CDX derivatives are **view-only from India** — the brain can read all data but cannot place orders on Coinbase derivatives from this location.

---

## Every Distinct Element (with frame timestamps)

### [00:00] Coinbase Homepage
- URL: `coinbase.com/en-in` (India locale)
- Headline: "The future of finance is here. Buy, sell and trade crypto on a platform you can trust."
- CTA: "Sign up" button
- Balance preview shown on mock device: **₹1,30,535.00**
- Prices shown: Bitcoin, Ethereum, Solana with current prices
- Top navigation: Cryptocurrencies | Individuals | Businesses | Institutions | Developers | Company
- Sign In | Sign up buttons top right

### [00:12] Coinbase Password Entry
- URL: `login.coinbase.com/signin?client_id=...&nonce=...&redirect_uri=...&challenge=...`
- "Enter your password"
- "Sign in as **ajithd747@gmail.com**"
- Password field (empty/hidden)
- "Continue" button (blue)
- "Forgot password?" link
- Note: Email = ajithd747@gmail.com (same as user's Gmail)

### [00:42] Loading Screen
- Coinbase logo centered on white screen
- Loading spinner (authentication processing, 2FA may have been done off-camera)

### [01:00] Coinbase Advanced Trade — BTC PERP
- URL: `coinbase.com/advanced-trade/perpetual/BTC-PERP-INTX`
- Header: BTC PERP | Price: **62,452.30** (+0.26%) | Contract Name: nano Bitcoin Futures | Last Price: $62,452.30 | Open Interest: $76.7M | Expiry: 7/11/2026 | Contract: 0.01
- Navigation tabs: Open Orders | Order History | Positions | Assets | Trade History
- Price Chart tab | Depth Chart tab
- Advanced | Add widget | Deposit | Manage Funds
- **Order Book** visible on right:
  - BTC column (bid/ask amounts)
  - Red prices (asks): ~62,454, 62,455, 62,456... 
  - Green prices (bids): ~62,451, 62,450, 62,449...
  - Order size column
- Order Form on far right (Buy/Sell toggle)

### [01:12] Coinbase Advanced Trade — Futures List
- URL: `coinbase.com/advanced-trade/trade/futures` (Futures tab selected)
- Categories: All Instruments | Spot | Futures | DownloadStocks | Indices | TrackedCommodities | FX
- **"Futures" selected**
- Table columns: Expiry | Last price | 24h% | Volume | Open Interest | Open Interest $
- Contracts listed:
  - BTC-31JUL26 | Jul 31 | $92,165.69 | +1.50% | 2.0359 | $25,684 | $234,999
  - ADA-31JUL26 | Jul 31 | $4,746.88 | +1.27% | 2.0359 | (data)
  - GLD-31JUL26 | Jul 31 | $66,000 | +5.07% | 2.0359 | (data)
  - SOL-31JUL26 | Jul 31 | $1,700.00 | -3.02% | 2.0359 | $499,000 | $7,368,000
  - ETH-31JUL26 | Jul 31 | $1,099.00 | -4.25% | 2.0359 | (data)
  - DOGE-31JUL26 | Jul 31 | $0.09000 | -1.23% | 2.0359 | (data)
  - DYDX-31JUL26 | Jul 31 | $8.24 | -4.23% | 2.0359 | (data)
  - BCH-31JUL26 | Jul 31 | $319.00 | -4.29% | 2.0359 | (data)
  - XRP-31JUL26 | Jul 31 | $44.83 | -3.07% | 2.0359 | $301,500 | $204,000
  - (additional rows cut off: LTCCOIN, LTC-31JUL26, XRP-31JUL26...)
- **"Reduce entry orders" tooltip** visible — "Reduce mode will reduce or close your positions based on priority into close conditions"
- Side panel: Order Book showing BTC-PERP bid/ask at 62,498.3 / 62,498.8

### [01:27] Coinbase BTC 31JUL26 Futures — View-Only Warning
- URL: `coinbase.com/advanced-trade/trade/futures/BTC-31JUL26-CDE`
- Header: BTC 31JUL26 | Contract Name: nano Bitcoin Futures | Last Price (24h): $63,120.00 (+2.34%) | Open Interest: $76.7M | Expiry: 7/31/2026 | Contract: 0.01
- **CRITICAL WARNING BANNER:** "Viewing Instrument. CDX derivatives are currently a view-only experience. Trading is unavailable for your location."
- "Learn more" link
- Price Chart tab | Depth Chart tab
- Order Book on right: Bids/asks around $63,000
- Positions tab empty: "No open orders" shown

### [01:45] BTC 30m Chart
- URL: `coinbase.com/advanced/markets/trade/futures/BTC-31JUL26-CDE`
- Chart: 30m candlestick/line chart
- Price range: ~$38,000 to ~$44,000 (historical data)
- Time axis: hours of the day
- Volume indicators at bottom
- Indicators button visible

---

## Open Questions

1. **2FA/Authentication:** After password entry, did the user complete 2FA off-camera? Coinbase typically requires 2FA (Google Authenticator or SMS). The brain cannot auto-complete 2FA without TOTP secrets stored.

2. **View-only constraint:** CDX derivatives (futures) are view-only from India. The brain can READ all data (prices, order book, open interest, futures list) but CANNOT place orders. Is read-only data extraction the goal?

3. **What data to extract?** Order book (bid/ask spread), futures prices + open interest, BTC chart OHLC data, or all of the above?

4. **Credentials:** Email is ajithd747@gmail.com. Password is unknown (not shown). Should the user store password in the credential vault?

5. **TOTP:** Does the user have Google Authenticator / TOTP set up for Coinbase? This is needed for browser automation to complete login.
