"""Command-line interface for scanning crypto markets."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .coingecko import CoinGeckoError, fetch_markets
from .scanner import Coin, TechnicalSignals, scan_market


def _optional_float(row: dict[str, str], key: str) -> float | None:
    value = row.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value for {key}: {value!r}") from exc


def _required_float(row: dict[str, str], key: str) -> float:
    value = row.get(key)
    if value in (None, ""):
        raise ValueError(f"Missing required CSV column value: {key}")
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value for {key}: {value!r}") from exc


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
                    symbol=(row.get("symbol") or "UNKNOWN").upper(),
                    name=row.get("name") or row.get("symbol") or "Unknown",
                    price=_required_float(row, "price"),
                    volume_24h=_required_float(row, "volume_24h"),
                    market_cap=_optional_float(row, "market_cap") or 0,
                    change_1h=_optional_float(row, "change_1h") or 0,
                    change_24h=_optional_float(row, "change_24h") or 0,
                    change_7d=_optional_float(row, "change_7d") or 0,
                    technicals=technicals,
                )
            )
        return coins


def _load_quote_csv(path: Path) -> list[MarketQuote]:
    with path.open(newline="", encoding="utf-8") as handle:
        quotes: list[MarketQuote] = []
        for row in csv.DictReader(handle):
            quotes.append(
                MarketQuote(
                    venue=row["venue"],
                    symbol=row["symbol"],
                    ask=float(row["ask"]),
                    bid=float(row["bid"]),
                    base_volume=float(row.get("base_volume") or 0),
                    quote_volume=float(row.get("quote_volume") or 0),
                    taker_fee=float(row.get("taker_fee") or 0),
                    withdrawal_fee=float(row.get("withdrawal_fee") or 0),
                    slippage=float(row.get("slippage") or 0),
                )
            )
        return quotes


def _format_money(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.2f}"


def _short_notes(opportunity) -> str:
    notes = list(opportunity.reasons[:2])
    if opportunity.risk_notes:
        notes.append(f"Risk: {opportunity.risk_notes[0]}")
    return "; ".join(notes)


def render_table(opportunities) -> str:
    """Render opportunities as a terminal-friendly table."""

    rows = [
        [
            "Rank",
            "Asset",
            "Bias",
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
                opportunity.bias,
                opportunity.setup,
                f"{opportunity.score:.2f}",
                _format_money(coin.price),
                _format_money(coin.volume_24h),
                f"{coin.change_1h:+.2f}%",
                f"{coin.change_24h:+.2f}%",
                f"{coin.change_7d:+.2f}%",
                _short_notes(opportunity),
            ]
        )

    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return "\n".join(
        " | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))
        for row in rows
    )


def render_arbitrage_table(packages) -> str:
    """Render arbitrage packages as a terminal-friendly table."""

    rows = [
        ["Rank", "Symbol", "Route", "Net %", "Gross %", "Profit", "Capital", "Notes"]
    ]
    for rank, package in enumerate(packages, start=1):
        rows.append(
            [
                str(rank),
                package.symbol,
                f"buy {package.buy_venue} -> sell {package.sell_venue}",
                f"{package.net_spread_pct:+.2f}%",
                f"{package.gross_spread_pct:+.2f}%",
                _format_money(package.estimated_profit),
                _format_money(package.capital_required),
                "; ".join(package.notes),
            ]
        )
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return "\n".join(
        " | ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))
        for row in rows
    )


def _print_payload(payload, output_format: str, table_renderer) -> None:
    if output_format == "json":
        print(json.dumps([asdict(item) for item in payload], indent=2))
    else:
        print(table_renderer(payload))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan crypto markets and discover cross-venue arbitrage packages."
    )
    parser.add_argument(
        "--version", action="version", version="open-source-crypto-signals"
    )
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser(
        "scan", help="Scan markets for liquid momentum, reversal, and pullback candidates."
    )
    scan_parser.add_argument(
        "--csv", type=Path, help="Read market data from a CSV file instead of CoinGecko."
    )
    scan_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum number of opportunities to show."
    )
    scan_parser.add_argument(
        "--min-volume", type=float, default=10_000_000, help="Minimum 24h volume filter."
    )
    scan_parser.add_argument(
        "--vs-currency", default="usd", help="Quote currency for live CoinGecko data."
    )
    scan_parser.add_argument(
        "--bullish-only",
        action="store_true",
        help="Only show assets with bullish momentum and technical confirmation.",
    )
    scan_parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format for terminal, bots, dashboards, and APIs.",
    )

    arbitrage_parser = subparsers.add_parser(
        "arbitrage", help="Find cross-venue arbitrage packages from quote CSV data."
    )
    arbitrage_parser.add_argument(
        "--quotes-csv",
        type=Path,
        required=True,
        help="CSV with venue,symbol,ask,bid and optional fee/volume columns.",
    )
    arbitrage_parser.add_argument(
        "--trade-size", type=float, default=1, help="Base asset units to model for each package."
    )
    arbitrage_parser.add_argument(
        "--min-net-spread",
        type=float,
        default=0.5,
        help="Minimum net spread percentage after costs.",
    )
    arbitrage_parser.add_argument(
        "--limit", type=int, default=10, help="Maximum number of packages to show."
    )
    arbitrage_parser.add_argument(
        "--ignore-volume",
        action="store_true",
        help="Do not require venues to report enough base volume for the modeled trade size.",
    )
    arbitrage_parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format for terminal, bots, dashboards, and APIs.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        coins = (
            _load_csv(args.csv)
            if args.csv
            else fetch_markets(vs_currency=args.vs_currency)
        )
    except (CoinGeckoError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    opportunities = scan_market(
        coins,
        min_volume=args.min_volume,
        limit=args.limit,
        bullish_only=args.bullish_only,
    )

        if not opportunities:
            print("No opportunities matched the current filters.")
            return 1

        _print_payload(opportunities, args.format, render_table)
        if args.format == "table":
            print(
                "\nResearch aid only; not financial advice. "
                "Confirm setups, risk, and liquidity before trading."
            )
        return 0

    if args.command == "arbitrage":
        packages = find_arbitrage_packages(
            _load_quote_csv(args.quotes_csv),
            trade_size=args.trade_size,
            min_net_spread_pct=args.min_net_spread,
            require_volume=not args.ignore_volume,
            limit=args.limit,
        )
        if not packages:
            print("No arbitrage packages matched the current filters.")
            return 1
        _print_payload(packages, args.format, render_arbitrage_table)
        if args.format == "table":
            print(
                "\nResearch aid only; not financial advice. "
                "Confirm transfer times, order-book depth, fees, taxes, and venue "
                "risk before trading."
            )
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
