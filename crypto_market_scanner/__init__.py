"""Crypto market scanner package."""

from .scanner import Coin, Opportunity, scan_market, score_coin

__version__ = "0.1.0"

__all__ = ["Coin", "Opportunity", "scan_market", "score_coin", "__version__"]
