"""Command-line interface for scanning crypto markets."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .coingecko import fetch_markets
from .scanner import Coin, TechnicalSignals, scan_market


def _optional_float(row: dict[str, str], key: str) -> float | None:
    value = row.get(key)
    return float(value) if value not in (None, "") else None


def _load_csv(path: Path) -> list[Coin]:
    with path.open(newline="", encoding="utf-8") as handle:
        coins: list[Coin] = []
        for row in csv.DictReader(handle):
            technicals = TechnicalSignals(
                rsi=_optional_float(row, "rsi"),
                macd_histogram=_optional_float(row, "macd_histogram"),
                price_vs_sma50=_optional_float(row, "price_vs_sma50"),
                price_vs_sma200=_optional_float(row, "price_vs_sma200"),
            )
            if all(
                value is None
                for value in (
                    technicals.rsi,
                    technicals.macd_histogram,
                    technicals.price_vs_sma50,
                    technicals.price_vs_sma200,
                )
            ):
                technicals = None

            coins.append(
                Coin(
                    symbol=row["symbol"].upper(),
                    name=row["name"],
                    price=float(row["price"]),
                    volume_24h=float(row["volume_24h"]),
                    market_cap=float(row.get("market_cap") or 0),
                    change_1h=float(row["change_1h"]),
                    change_24h=float(row["change_24h"]),
                    change_7d=float(row["change_7d"]),
                    technicals=technicals,
                )
            )
        return coins


def _format_money(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.2f}"


def render_table(opportunities) -> str:
    """Render opportunities as a terminal-friendly table."""

    rows = [
        [
            "Rank",
            "Asset",
            "Bullish",
            "Setup",
            "Score",
            "Price",
            "Vol 24h",
            "1h",
            "24h",
            "7d",
            "Notes",
        ],
    ]
    for rank, opportunity in enumerate(opportunities, start=1):
        coin = opportunity.coin
        rows.append(
            [
                str(rank),
                f"{coin.symbol} ({coin.name})",
                "YES" if opportunity.is_bullish else "no",
                opportunity.setup,
                f"{opportunity.score:.2f}",
                _format_money(coin.price),
                _format_money(coin.volume_24h),
                f"{coin.change_1h:+.2f}%",
                f"{coin.change_24h:+.2f}%",
                f"{coin.change_7d:+.2f}%",
                "; ".join(opportunity.reasons),
            ]
        )

    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return "\n".join(
        " | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))
        for row in rows
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan crypto markets for liquid momentum, reversal, and pullback candidates."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Read market data from a CSV file instead of CoinGecko.",
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Maximum number of opportunities to show."
    )
    parser.add_argument(
        "--min-volume",
        type=float,
        default=10_000_000,
        help="Minimum 24h volume filter.",
    )
    parser.add_argument(
        "--vs-currency", default="usd", help="Quote currency for live CoinGecko data."
    )
    parser.add_argument(
        "--bullish-only",
        action="store_true",
        help="Only show assets with bullish momentum and technical confirmation.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    coins = (
        _load_csv(args.csv) if args.csv else fetch_markets(vs_currency=args.vs_currency)
    )
    opportunities = scan_market(
        coins,
        min_volume=args.min_volume,
        limit=args.limit,
        bullish_only=args.bullish_only,
    )

    if not opportunities:
        print("No opportunities matched the current filters.")
        return 1

    print(render_table(opportunities))
    print(
        "\nResearch aid only; not financial advice. Confirm setups, risk, and liquidity before trading."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
