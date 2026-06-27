"""Arbitrage package discovery utilities.

The finder is intentionally exchange-agnostic: callers can provide quotes from
CSV files, APIs, notebooks, bots, or web services and receive structured
packages describing possible buy/sell spreads after fees and slippage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class MarketQuote:
    """Best executable quote for an asset on a venue.

    ``ask`` is the estimated buy price, ``bid`` is the estimated sell price,
    and fee/slippage values are decimal rates (``0.001`` means 0.10%).
    """

    venue: str
    symbol: str
    ask: float
    bid: float
    base_volume: float = 0
    quote_volume: float = 0
    taker_fee: float = 0
    withdrawal_fee: float = 0
    slippage: float = 0


@dataclass(frozen=True)
class ArbitragePackage:
    """A complete cross-venue arbitrage candidate."""

    symbol: str
    buy_venue: str
    sell_venue: str
    buy_price: float
    sell_price: float
    gross_spread_pct: float
    net_spread_pct: float
    estimated_profit: float
    trade_size: float
    capital_required: float
    notes: tuple[str, ...] = field(default_factory=tuple)


def _normalized_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def find_arbitrage_packages(
    quotes: Iterable[MarketQuote],
    *,
    trade_size: float = 1,
    min_net_spread_pct: float = 0.5,
    require_volume: bool = True,
    limit: int = 10,
) -> list[ArbitragePackage]:
    """Find cross-venue arbitrage packages from normalized market quotes.

    The calculation assumes buying ``trade_size`` base units at the source ask,
    selling at the destination bid, and subtracting venue taker fees,
    withdrawal fees, and slippage. Results are sorted by estimated profit.
    """

    if trade_size <= 0:
        raise ValueError("trade_size must be greater than zero")
    if limit <= 0:
        return []

    grouped: dict[str, list[MarketQuote]] = {}
    for quote in quotes:
        symbol = _normalized_symbol(quote.symbol)
        if quote.ask <= 0 or quote.bid <= 0 or not quote.venue.strip():
            continue
        grouped.setdefault(symbol, []).append(quote)

    packages: list[ArbitragePackage] = []
    for symbol, symbol_quotes in grouped.items():
        for buy_quote in symbol_quotes:
            for sell_quote in symbol_quotes:
                if buy_quote.venue == sell_quote.venue:
                    continue
                if require_volume and (
                    buy_quote.base_volume < trade_size
                    or sell_quote.base_volume < trade_size
                ):
                    continue

                effective_buy = buy_quote.ask * (
                    1 + buy_quote.taker_fee + buy_quote.slippage
                )
                effective_sell = sell_quote.bid * (
                    1 - sell_quote.taker_fee - sell_quote.slippage
                )
                capital_required = (effective_buy * trade_size) + buy_quote.withdrawal_fee
                proceeds = effective_sell * trade_size
                estimated_profit = proceeds - capital_required
                gross_spread_pct = ((sell_quote.bid - buy_quote.ask) / buy_quote.ask) * 100
                net_spread_pct = (estimated_profit / capital_required) * 100

                if net_spread_pct < min_net_spread_pct:
                    continue

                notes: list[str] = []
                if buy_quote.withdrawal_fee:
                    notes.append("includes withdrawal fee")
                if buy_quote.slippage or sell_quote.slippage:
                    notes.append("includes slippage estimate")
                if not require_volume:
                    notes.append("volume check disabled")

                packages.append(
                    ArbitragePackage(
                        symbol=symbol,
                        buy_venue=buy_quote.venue,
                        sell_venue=sell_quote.venue,
                        buy_price=buy_quote.ask,
                        sell_price=sell_quote.bid,
                        gross_spread_pct=round(gross_spread_pct, 4),
                        net_spread_pct=round(net_spread_pct, 4),
                        estimated_profit=round(estimated_profit, 8),
                        trade_size=trade_size,
                        capital_required=round(capital_required, 8),
                        notes=tuple(notes),
                    )
                )

    return sorted(packages, key=lambda package: package.estimated_profit, reverse=True)[
        :limit
    ]
