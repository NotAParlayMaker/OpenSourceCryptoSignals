"""Core crypto-market scanning logic.

The scanner is deliberately lightweight: it can consume live CoinGecko market
snapshots or test fixtures and ranks coins by transparent momentum, liquidity,
and pullback signals. It is not financial advice; it is a research aid that
helps users build a shortlist for deeper analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Coin:
    """Normalized market data for a crypto asset."""

    symbol: str
    name: str
    price: float
    volume_24h: float
    market_cap: float
    change_1h: float
    change_24h: float
    change_7d: float


@dataclass(frozen=True)
class Opportunity:
    """A ranked trading-opportunity candidate."""

    coin: Coin
    score: float
    setup: str
    reasons: tuple[str, ...]
    risk_notes: tuple[str, ...]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def score_coin(coin: Coin, min_volume: float = 10_000_000) -> Opportunity | None:
    """Score a coin and classify its current market setup.

    The score favors liquid markets, positive 24h/7d momentum, and recent
    intraday confirmation. Excessively extended 24h moves receive a risk note
    and a small penalty because they can be prone to mean reversion.
    """

    if coin.volume_24h < min_volume or coin.price <= 0:
        return None

    liquidity_score = _clamp(coin.volume_24h / 250_000_000, 0, 1) * 25
    momentum_score = _clamp((coin.change_24h + 10) / 25, 0, 1) * 30
    trend_score = _clamp((coin.change_7d + 15) / 40, 0, 1) * 25
    confirmation_score = _clamp((coin.change_1h + 2) / 6, 0, 1) * 20
    score = liquidity_score + momentum_score + trend_score + confirmation_score

    reasons: list[str] = []
    risk_notes: list[str] = []

    if coin.volume_24h >= 100_000_000:
        reasons.append("strong 24h liquidity")
    if coin.change_24h > 3:
        reasons.append("positive 24h momentum")
    if coin.change_7d > 5:
        reasons.append("confirmed 7d uptrend")
    if coin.change_1h > 0.5:
        reasons.append("recent intraday strength")

    if coin.change_24h > 18:
        score -= 8
        risk_notes.append("24h move is extended; wait for confirmation or pullback")
    if coin.change_7d < -10:
        risk_notes.append("7d trend remains weak")
    if coin.market_cap and coin.volume_24h / coin.market_cap > 0.75:
        risk_notes.append("volume is unusually high relative to market cap")

    if coin.change_24h >= 3 and coin.change_7d >= 3:
        setup = "momentum breakout"
    elif coin.change_24h > 0 and coin.change_7d < -3:
        setup = "possible reversal"
    elif coin.change_24h < 0 and coin.change_7d > 6:
        setup = "trend pullback"
    else:
        setup = "watchlist candidate"

    if not reasons:
        reasons.append("meets liquidity filter but lacks a clear catalyst")

    return Opportunity(
        coin=coin,
        score=round(max(score, 0), 2),
        setup=setup,
        reasons=tuple(reasons),
        risk_notes=tuple(risk_notes),
    )


def scan_market(
    coins: Iterable[Coin],
    *,
    min_volume: float = 10_000_000,
    limit: int = 10,
) -> list[Opportunity]:
    """Return the highest-scoring market opportunities."""

    opportunities = [
        opportunity
        for coin in coins
        if (opportunity := score_coin(coin, min_volume=min_volume)) is not None
    ]
    return sorted(opportunities, key=lambda item: item.score, reverse=True)[:limit]
