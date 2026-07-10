# Upstox — discovered features, functions & data census
_Generated 2026-07-10T09:16:04 from the App Driving School's live captures (read-only exploration of the logged-in app)._

## Learned market-data routes (the named goals)
| goal | page (route) | data endpoint |
|---|---|---|
| commodities | https://pro.upstox.com/trading-charts | `market-data.upstox.com/market-data-feeder/v2/feeds` |
| currency | https://pro.upstox.com/trading-charts | `market-data.upstox.com/market-data-feeder/v2/feeds` |
| futures | https://pro.upstox.com/trading-charts | `market-data.upstox.com/market-data-feeder/v2/feeds` |
| greeks | https://pro.upstox.com/option-chain | `market-data.upstox.com/market-data-feeder/v2/feeds` |
| movers | https://pro.upstox.com/trading-charts | `market-data.upstox.com/market-data-feeder/v2/feeds` |
| options | https://pro.upstox.com/option-chain | `market-data.upstox.com/market-data-feeder/v2/feeds` |
| orderbook | https://pro.upstox.com/trading-charts | `market-data.upstox.com/market-data-feeder/v2/feeds` |
| pcr | https://pro.upstox.com/option-chain | `market-data.upstox.com/market-data-feeder/v2/feeds` |
| spot_symbols | https://pro.upstox.com/trading-charts | `market-data.upstox.com/market-data-feeder/v2/feeds` |

## Every API function/data source captured (52 endpoints)
_kind = what the classifier grounds it as; `unknown` = an app function we recorded but don't map to a trading data-kind (yet) — each row lists the payload's top-level fields so future features can use it._

### balance (4)
| endpoint | seen | payload fields |
|---|---|---|
| `service.upstox.com/account-management/v1/profile/app/features` | 85× | data, requestId, success |
| `service.upstox.com/jfunds/limit/v1/fetch` | 55× | data, success |
| `service.upstox.com/funds/v2/history` | 9× | data, error, success |
| `service.upstox.com/payin/v3/payment-modes/SEC` | 9× | data, success |

### candles (1)
| endpoint | seen | payload fields |
|---|---|---|
| `service.upstox.com/chart/open/v3/candles` | 63× | data, success |

### positions (11)
| endpoint | seen | payload fields |
|---|---|---|
| `service.upstox.com/portfolio-streamer-v2/v4` | 243× | — |
| `service.upstox.com/portfolio/v2/orderbook/notification` | 83× | client_id, data, error, response_type, success, timestamp |
| `service.upstox.com/portfolio/v2/orderbook/orderrank` | 83× | client_id, data, error, response_type, success, timestamp |
| `service.upstox.com/portfolio/v4/orderbook` | 83× | data, error, success, timestamp |
| `service.upstox.com/strategy-builder/v2/positions` | 83× | data, error, success |
| `service.upstox.com/mutual-funds/v6/portfolio/summary` | 82× | data, success |
| `service.upstox.com/portfolio-insights/v1/trade-insights/top-insights` | 82× | data, error, success |
| `service.upstox.com/portfolio/v2/holdings` | 82× | data, success, timestamp |
| `service.upstox.com/portfolio/v2/mtf` | 82× | data, success, timestamp |
| `service.upstox.com/portfolio/v2/positions` | 82× | data, success, timestamp |
| `sdk-03.moengage.com/v2/device/add` | 1× | message, status |

### recent_trades (1)
| endpoint | seen | payload fields |
|---|---|---|
| `service.upstox.com/edis-cdsl/v3/mtf/authorization/trades` | 82× | data, error, success |

### symbol_info (1)
| endpoint | seen | payload fields |
|---|---|---|
| `service.upstox.com/instrument/v1/instruments` | 85× | data, metaData, success |

### ticker (1)
| endpoint | seen | payload fields |
|---|---|---|
| `market-data.upstox.com/market-data-feeder/v2/feeds` | 479× | — |

### unknown (33)
| endpoint | seen | payload fields |
|---|---|---|
| `api-js.mixpanel.com/track` | 108× | error, status |
| `service.upstox.com/notification-center/v1/expiring` | 90× | data, error, metadata, success |
| `service.upstox.com/notification-center/v1/notifications` | 90× | data, error, metadata, success |
| `service.upstox.com/watchlists/v3/user/{v}` | 90× | data, success |
| `assets.upstox.com/web/pro-web/config.json` | 85× | bar_notification_transition_timeout, bod_version, bod_version_dual_socket, bod_version_revamp_socket, cdsl_form_version, chart_content_size_limit_in_kb, chart_limit_size, charts_api_timeout |
| `firebase.googleapis.com/v1alpha/projects/-/apps/1:320624426303:web:d0cb49c6c0f6383084a78a/webConfig` | 85× | appId, authDomain, locationId, measurementId, messagingSenderId, projectId, storageBucket |
| `service.upstox.com/gateway-worker/v1/verify-access-token` | 85× | success |
| `service.upstox.com/market-data-api/v2/open/segment-timing` | 85× | data, success |
| `service.upstox.com/profile/v1/settings` | 85× | data, success |
| `service.upstox.com/profile/v5/client-info` | 85× | data, success |
| `service.upstox.com/user-settings/v2/preference/tv` | 85× | data, error, success |
| `service.upstox.com/watchlists/v3/user` | 84× | data, success |
| `assets.upstox.com/upstoxpro/platform/mobileandweb/pledge_terms.json` | 83× | sources |
| `service.upstox.com/basket-order/v1/baskets` | 83× | data, success |
| `service.upstox.com/market-alerts/v3/user` | 81× | data, success |
| `api.plotline.so/sdk/init` | 80× | data, message, status, statusCode |
| `api-js.mixpanel.com/engage` | 78× | error, status |
| `service.upstox.com/mtm-alerting/v3/alert` | 67× | data, success |
| `service.upstox.com/market-data-api/v2/open/holidays` | 34× | data, success |
| `service.upstox.com/market-data-api/v2/open/special-trading-dates` | 34× | data, success |
| `service.upstox.com/user-settings/v2/charts/saving-chart-layout/tv` | 32× | data, error, success |
| `service.upstox.com/user-settings/v2/charts/saving-chart-layout/tv/list` | 32× | data, error, success |
| `service.upstox.com/user-settings/v2/charts/saving-study-templates/tv/list` | 32× | data, error, success |
| `service.upstox.com/user-settings/v2/charts/saving-drawings/tv` | 31× | data, error, success |
| `pro.upstox.com/assets/lottie/web/pulsatingDot.json` | 22× | assets, ddd, fr, h, ip, layers, meta, nm |
| `api.plotline.so/sdk/event/track` | 19× | data, message, status, statusCode |
| `pro.upstox.com/assets/lottie/web/liveAlertsExplainerVideo.json` | 5× | — |
| `sdk-03.moengage.com/v3/campaigns/inapp/live` | 3× | campaigns, fc_settings, min_delay_btw_inapps, sync_interval |
| `firebaseremoteconfig.googleapis.com/v1/projects/upstox-app/namespaces/firebase:fetch` | 2× | entries, state, templateVersion |
| `api.plotline.so/sdk/campaign/trigger` | 1× | data, message, status, statusCode |
| `api.plotline.so/sdk/flow/save-action` | 1× | data, message, status, statusCode |
| `sdk-03.moengage.com/v2/websdksettings` | 1× | webData |
| `sdk-03.moengage.com/v3/sdkconfig/web/G0QP5P8Z199G9GSAUP88PFEF` | 1× | a_c_d_s_i, a_c_i_s, a_s, ac_s, b_d, b_e, c_s, c_w_p_e |

## Pages mapped (7)

- https://login.upstox.com/?redirect_uri=https://upstox.com/onboarding&client_id=UOB-z8072cf6l4ykp1qae5hu3ism&landing_page=homepage_form — Login to Upstox
- https://pro.upstox.com/funds/securities/wallet — Upstox Pro
- https://pro.upstox.com/holdings — Upstox Pro
- https://pro.upstox.com/option-chain — Upstox Pro
- https://pro.upstox.com/orders/regular — Upstox Pro
- https://pro.upstox.com/positions/regular — Upstox Pro
- https://pro.upstox.com/trading-charts — HCLTECH EQ

## Links saved (7)

- https://pro.upstox.com/funds/securities/wallet — 
- https://pro.upstox.com/holdings — Holdings
- https://pro.upstox.com/orders — Orders
- https://pro.upstox.com/positions — Positions
- https://pro.upstox.com/trading-charts — 
- https://upstox.com/contact-us/ — 
- https://upstox.com/terms-of-use-and-privacy-policy/ — T&C

## Built-in pickers (filters) already wired as candidate sources
_From trading/broker_sense/broker_features.py — Upstox's own screening filters (momentum 1m/3m/5m, top gainers/losers, trending, trending<₹500 …) feed the funnel as ranked candidate lists._