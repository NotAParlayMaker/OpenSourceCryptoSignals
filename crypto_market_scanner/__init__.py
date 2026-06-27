"""Crypto market scanner package."""

from .arbitrage import ArbitragePackage, MarketQuote, find_arbitrage_packages
from .scanner import Coin, Opportunity, TechnicalSignals, scan_market, score_coin

__version__ = "0.1.0"

__all__ = [
    "ArbitragePackage",
    "Coin",
    "MarketQuote",
    "Opportunity",
    "TechnicalSignals",
    "find_arbitrage_packages",
    "scan_market",
    "score_coin",
    "__version__",
]
