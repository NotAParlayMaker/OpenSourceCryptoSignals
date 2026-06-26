# Open Source Crypto Signals

A lightweight Python CLI that helps traders scan the crypto market for research candidates. It ranks assets by liquidity, short-term momentum, seven-day trend, and intraday confirmation so users can quickly build a shortlist of possible trading opportunities.

> This project is a research aid only and is not financial advice.

## Features

- Fetches live market snapshots from CoinGecko without mandatory third-party Python dependencies.
- Supports offline CSV scans for repeatable research and testing.
- Scores assets with transparent momentum, trend, liquidity, technical indicators, and risk heuristics.
- Classifies candidates as bullish breakouts, bullish confirmations, momentum breakouts, possible reversals, trend pullbacks, or watchlist candidates.
- Prints a compact terminal table that includes setup notes and performance columns.

## Quick start

```bash
python -m crypto_market_scanner.cli --limit 10 --min-volume 50000000
```

Or install the console script in editable mode:

```bash
python -m pip install -e .
crypto-scan --limit 10
crypto-scan --bullish-only --limit 10
```


## Package installation

Install the package from a local checkout:

```bash
python -m pip install .
crypto-scan --help
```

Build distributable artifacts for PyPI or another package index:

```bash
python -m pip install .[dev]
python -m build
python -m twine check dist/*
```

Tagged GitHub releases can publish the package through the `Publish Python package` workflow using PyPI trusted publishing.

## Offline CSV input

Use `--csv` with required market columns plus optional technical columns (`rsi`, `macd_histogram`, `price_vs_sma50`, and `price_vs_sma200`).

```csv
symbol,name,price,volume_24h,market_cap,change_1h,change_24h,change_7d,rsi,macd_histogram,price_vs_sma50,price_vs_sma200
BTC,Bitcoin,65000,32000000000,1200000000000,0.4,2.1,7.8,58,120,4.0,18.0
SOL,Solana,150,4500000000,68000000000,1.2,8.5,18.4,64,1.8,7.5,22.0
```

Run:

```bash
python -m crypto_market_scanner.cli --csv examples/sample_markets.csv --limit 5
```

## How scoring works

The scanner gives each asset a score out of roughly 100 based on:

1. **Liquidity**: higher 24h volume ranks better and avoids thin markets.
2. **24h momentum**: positive daily moves are rewarded.
3. **7d trend**: sustained weekly strength improves conviction.
4. **1h confirmation**: recent intraday strength helps identify active markets.
5. **Technical confirmation**: bullish RSI, positive MACD histogram, and price above the 50-day/200-day simple moving averages can lift conviction.
6. **Risk flags**: extended moves, overbought RSI, bearish MACD, weak moving-average posture, or unusual volume-to-market-cap ratios are called out.

Use `--bullish-only` when you only want assets with aligned momentum and technical confirmation.

Always confirm signals with your own strategy, risk controls, exchange liquidity, and market context before trading.
