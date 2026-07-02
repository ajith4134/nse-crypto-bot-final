"""catalog/alternative_data.py — alternative-data alpha (Level-3 institutional, data-gated).

Alpha from non-price data: news & social sentiment, search trends, on-chain/blockchain flow,
satellite imagery, supply-chain tracking. All DATA_GATED on an external feed; the repo already
has sentiment infrastructure (vendor/vaderSentiment, trading/brain/sentiment.py & news.py,
advintel/onchain.py) so news/social/on-chain flip to executable first.
OSS: vendor/vaderSentiment, repo trading/brain/sentiment.py, advintel/onchain.py.
"""
from __future__ import annotations

from trading.strategy.library.base import DataReq, LibraryStrategy


def _g(name, family, logic, segments, data_req, oss, notes=""):
    return LibraryStrategy(name=name, category="machine_learning", family=family, logic=logic,
                           segments=segments, timeframe="hours–weeks", data_req=tuple(data_req),
                           signal=None, oss_source=oss, notes="alternative-data alpha — " + notes)


STRATEGIES = [
    _g("alt_news_sentiment", "news_sentiment",
       "Trade direction from scored news-headline sentiment.",
       ("nse_cash", "nse_futures", "crypto_spot", "crypto_futures"),
       (DataReq.NEWS_EVENTS,), "vendor/vaderSentiment; repo trading/brain/news.py",
       notes="repo has news+sentiment; needs live news feed"),
    _g("alt_social_sentiment", "social_sentiment",
       "Trade Twitter/Reddit/Telegram social-sentiment shifts.",
       ("crypto_spot", "crypto_futures"), (DataReq.NEWS_EVENTS,),
       "repo trading/brain/sentiment.py", notes="needs social feed"),
    _g("alt_search_trends", "search_trends",
       "Use search-interest (Google Trends) spikes as a demand proxy.",
       ("crypto_spot", "nse_cash"), (DataReq.NEWS_EVENTS,), "search-trends alpha"),
    _g("alt_blockchain_flow", "onchain_flow",
       "On-chain flow alpha: exchange in/outflows, whale moves, stablecoin supply.",
       ("crypto_spot", "crypto_futures"), (DataReq.NEWS_EVENTS, DataReq.MULTI_ASSET),
       "repo advintel/onchain.py", notes="repo computes some on-chain signals"),
    _g("alt_satellite_imagery", "satellite",
       "Satellite-imagery alpha (parking lots, oil tanks, crop/mine activity).",
       ("nse_cash", "mcx_commodities"), (DataReq.FUNDAMENTALS,), "satellite imagery (Two Sigma-style)"),
    _g("alt_supply_chain", "supply_chain",
       "Supply-chain / shipping / logistics tracking as a fundamentals lead.",
       ("nse_cash", "mcx_commodities"), (DataReq.FUNDAMENTALS,), "supply-chain tracking"),
]
