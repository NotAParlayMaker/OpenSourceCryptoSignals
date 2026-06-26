from crypto_market_scanner import __version__
from crypto_market_scanner.scanner import (
    Coin,
    TechnicalSignals,
    scan_market,
    score_coin,
)


def test_scan_market_filters_low_volume_and_sorts_by_score():
    coins = [
        Coin("SLOW", "Slow Coin", 1, 500_000, 20_000_000, 0.1, 3, 4),
        Coin("SOL", "Solana", 150, 4_500_000_000, 68_000_000_000, 1.2, 8.5, 18.4),
        Coin(
            "BTC", "Bitcoin", 65_000, 32_000_000_000, 1_200_000_000_000, 0.4, 2.1, 7.8
        ),
    ]

    opportunities = scan_market(coins, min_volume=10_000_000, limit=2)

    assert [item.coin.symbol for item in opportunities] == ["SOL", "BTC"]
    assert all(item.coin.symbol != "SLOW" for item in opportunities)


def test_score_coin_identifies_momentum_breakout():
    coin = Coin("TIA", "Celestia", 8.5, 180_000_000, 1_500_000_000, 0.8, 5.4, 9.2)

    opportunity = score_coin(coin)

    assert opportunity is not None
    assert opportunity.setup == "momentum breakout"
    assert "positive 24h momentum" in opportunity.reasons
    assert opportunity.score > 50


def test_score_coin_flags_extended_moves():
    coin = Coin("FAST", "Fast Token", 4, 300_000_000, 900_000_000, 3.2, 25.0, 40.0)

    opportunity = score_coin(coin)

    assert opportunity is not None
    assert any("extended" in note for note in opportunity.risk_notes)


def test_package_exposes_version():
    assert __version__ == "0.1.0"


def test_score_coin_marks_bullish_when_technicals_confirm():
    coin = Coin(
        "BULL",
        "Bull Token",
        10,
        250_000_000,
        2_000_000_000,
        0.9,
        4.2,
        8.5,
        technicals=TechnicalSignals(
            rsi=62,
            macd_histogram=0.12,
            price_vs_sma50=3.4,
            price_vs_sma200=9.1,
        ),
    )

    opportunity = score_coin(coin)

    assert opportunity is not None
    assert opportunity.is_bullish is True
    assert opportunity.setup == "bullish breakout"
    assert "MACD histogram is positive" in opportunity.bullish_signals
    assert "price is above the 200-day SMA" in opportunity.reasons


def test_scan_market_can_filter_to_bullish_only():
    coins = [
        Coin("BEAR", "Bear Token", 3, 150_000_000, 1_000_000_000, -0.2, -1.0, -4.0),
        Coin(
            "BULL",
            "Bull Token",
            10,
            250_000_000,
            2_000_000_000,
            0.9,
            4.2,
            8.5,
            technicals=TechnicalSignals(62, 0.12, 3.4, 9.1),
        ),
    ]

    opportunities = scan_market(coins, bullish_only=True)

    assert [item.coin.symbol for item in opportunities] == ["BULL"]
