"""Core crypto-market scanning logic.

The scanner is deliberately lightweight: it can consume live CoinGecko market
snapshots or test fixtures and ranks coins by transparent momentum, liquidity,
and pullback signals. It is not financial advice; it is a research aid that
helps users build a shortlist for deeper analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

Bias = Literal["bullish", "neutral", "bearish"]


@dataclass(frozen=True)
class TechnicalSignals:
    """Optional technical-analysis signals for a crypto asset."""

    rsi: float | None = None
    macd_histogram: float | None = None
    price_vs_sma50: float | None = None
    price_vs_sma200: float | None = None


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
    technicals: TechnicalSignals | None = None


@dataclass(frozen=True)
class Opportunity:
    """A ranked trading-opportunity candidate."""

    coin: Coin
    score: float
    setup: str
    reasons: tuple[str, ...]
    risk_notes: tuple[str, ...]
    bullish_signals: tuple[str, ...] = ()
    bearish_signals: tuple[str, ...] = ()
    bullish_score: float = 0
    is_bullish: bool = False
    bias: Bias = "neutral"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _score_technical_signals(
    technicals: TechnicalSignals | None,
) -> tuple[float, tuple[str, ...], tuple[str, ...]]:
    """Return a technical-score adjustment plus bullish/bearish signal labels."""

    if technicals is None:
        return 0, (), ()

    adjustment = 0.0
    bullish: list[str] = []
    bearish: list[str] = []

    if technicals.rsi is not None:
        if 50 <= technicals.rsi <= 70:
            adjustment += 8
            bullish.append("RSI is in bullish momentum range")
        elif technicals.rsi < 30:
            adjustment += 4
            bullish.append("RSI is oversold and may be reversing")
        elif technicals.rsi > 75:
            adjustment -= 6
            bearish.append("RSI is overbought")
        elif technicals.rsi < 45:
            adjustment -= 4
            bearish.append("RSI is below neutral")

    if technicals.macd_histogram is not None:
        if technicals.macd_histogram > 0:
            adjustment += 7
            bullish.append("MACD histogram is positive")
        elif technicals.macd_histogram < 0:
            adjustment -= 5
            bearish.append("MACD histogram is negative")

    if technicals.price_vs_sma50 is not None:
        if technicals.price_vs_sma50 > 0:
            adjustment += 6
            bullish.append("price is above the 50-day SMA")
        else:
            adjustment -= 4
            bearish.append("price is below the 50-day SMA")

    if technicals.price_vs_sma200 is not None:
        if technicals.price_vs_sma200 > 0:
            adjustment += 6
            bullish.append("price is above the 200-day SMA")
        else:
            adjustment -= 4
            bearish.append("price is below the 200-day SMA")

    return adjustment, tuple(bullish), tuple(bearish)


def classify_bias(score: float, coin: Coin, bullish_count: int = 0, bearish_count: int = 0) -> Bias:
    """Classify a scored coin as bullish, neutral, or bearish."""

    trend_points = sum(
        (
            coin.change_24h > 0,
            coin.change_7d > 0,
            coin.change_1h >= 0,
        )
    )
    bearish_trend_points = sum(
        (
            coin.change_24h < 0,
            coin.change_7d < 0,
            coin.change_1h < 0,
        )
    )
    technical_breadth = bullish_count - bearish_count

    if score >= 60 and trend_points >= 2 and technical_breadth >= 0:
        return "bullish"
    if score <= 35 or (bearish_trend_points >= 2 and technical_breadth <= 0):
        return "bearish"
    return "neutral"


def score_coin(coin: Coin, min_volume: float = 10_000_000) -> Opportunity | None:
    """Score a coin and classify its current market setup."""

    if coin.volume_24h < min_volume or coin.price <= 0:
        return None

    liquidity_score = _clamp(coin.volume_24h / 250_000_000, 0, 1) * 25
    momentum_score = _clamp((coin.change_24h + 10) / 25, 0, 1) * 30
    trend_score = _clamp((coin.change_7d + 15) / 40, 0, 1) * 25
    confirmation_score = _clamp((coin.change_1h + 2) / 6, 0, 1) * 20
    technical_score, bullish_signals, bearish_signals = _score_technical_signals(coin.technicals)
    score = liquidity_score + momentum_score + trend_score + confirmation_score + technical_score

    reasons: list[str] = []
    risk_notes: list[str] = []

    if coin.volume_24h >= 100_000_000:
        reasons.append("strong 24h liquidity")
    if coin.change_24h > 3:
        reasons.append("positive 24h momentum")
    elif coin.change_24h < -3:
        risk_notes.append("negative 24h momentum")
    if coin.change_7d > 5:
        reasons.append("confirmed 7d uptrend")
    elif coin.change_7d < -5:
        risk_notes.append("weak 7d trend")
    if coin.change_1h > 0.5:
        reasons.append("recent intraday strength")
    elif coin.change_1h < -1:
        risk_notes.append("short-term selling pressure")
    reasons.extend(bullish_signals)

    if coin.change_24h > 18:
        score -= 8
        risk_notes.append("24h move is extended; wait for confirmation or pullback")
    if coin.change_7d < -10:
        risk_notes.append("7d trend remains weak")
    if coin.market_cap > 0 and coin.volume_24h / coin.market_cap > 0.75:
        risk_notes.append("volume is unusually high relative to market cap")
    risk_notes.extend(bearish_signals)

    rounded_score = round(max(score, 0), 2)
    bias = classify_bias(rounded_score, coin, len(bullish_signals), len(bearish_signals))
    has_technical_confirmation = coin.technicals is not None and len(bullish_signals) >= 2
    is_bullish = bias == "bullish" and has_technical_confirmation

    if is_bullish and coin.change_24h >= 3 and coin.change_7d >= 3:
        setup = "bullish breakout"
    elif is_bullish:
        setup = "bullish confirmation"
    elif coin.change_24h >= 3 and coin.change_7d >= 3:
        setup = "momentum breakout"
    elif coin.change_24h > 0 and coin.change_7d < -3:
        setup = "possible reversal"
    elif coin.change_24h < 0 and coin.change_7d > 6:
        setup = "trend pullback"
    elif bias == "bearish":
        setup = "bearish pressure"
    else:
        setup = "watchlist candidate"

    if not reasons:
        reasons.append("meets liquidity filter but lacks a clear catalyst")

    return Opportunity(
        coin=coin,
        score=rounded_score,
        setup=setup,
        reasons=tuple(reasons),
        risk_notes=tuple(risk_notes),
        bullish_signals=bullish_signals,
        bearish_signals=bearish_signals,
        bullish_score=rounded_score,
        is_bullish=is_bullish,
        bias=bias,
    )


def scan_market(
    coins: Iterable[Coin],
    *,
    min_volume: float = 10_000_000,
    limit: int = 10,
    bullish_only: bool = False,
) -> list[Opportunity]:
    """Return the highest-scoring market opportunities."""

    if limit <= 0:
        return []

    opportunities = [
        opportunity
        for coin in coins
        if (opportunity := score_coin(coin, min_volume=min_volume)) is not None
    ]
    if bullish_only:
        opportunities = [opportunity for opportunity in opportunities if opportunity.is_bullish]
    return sorted(opportunities, key=lambda item: item.score, reverse=True)[:limit]
