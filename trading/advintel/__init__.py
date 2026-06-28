"""trading/advintel/ — Advanced Intelligence (original Phase-T8 deferred items).

Data/analytics/risk layers that were deferred when T8 was repurposed for the
strategy-evolution + ultra-brain engine. All CPU, reuse-first, and offline-testable:
network/keyed sources go through INJECTED fetchers (stub in tests; live only when called
with credentials present), so nothing here requires the internet to import or test.

  portfolio_risk    — Riskfolio/PyPortfolioOpt VaR/CVaR/Kelly/HRP + portfolio heat
  stress            — stress testing + scenario analysis (COVID/2008/taper/"Nifty -5%")
  fii_dii           — NSE FII/DII daily-flows scraper (gated)
  nse_announcements — NSE earnings/bulk-deals/corp-actions scraper (gated)
  onchain           — crypto on-chain SOPR/MVRV + Fear&Greed (free APIs, gated)
  liquidations      — liquidation heatmap (Coinglass, key-gated)
  arbitrage         — cross-exchange arb scanner + funding-rate farming detector (ccxt)
"""
from __future__ import annotations

from trading.advintel.arbitrage import ArbitrageScanner
from trading.advintel.fii_dii import FiiDiiFlows
from trading.advintel.liquidations import LiquidationHeatmap
from trading.advintel.nse_announcements import NseAnnouncements
from trading.advintel.onchain import OnChainMetrics
from trading.advintel.portfolio_risk import PortfolioRisk
from trading.advintel.stress import StressTester

__all__ = [
    "PortfolioRisk", "StressTester", "FiiDiiFlows", "NseAnnouncements",
    "OnChainMetrics", "LiquidationHeatmap", "ArbitrageScanner",
]
