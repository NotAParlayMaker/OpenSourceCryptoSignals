from pathlib import Path

from crypto_market_scanner import cli
from crypto_market_scanner.coingecko import CoinGeckoError
from crypto_market_scanner.scanner import Coin


def test_cli_runs_with_csv(tmp_path, capsys):
    csv_path = tmp_path / "markets.csv"
    csv_path.write_text(
        "symbol,name,price,volume_24h,market_cap,change_1h,change_24h,change_7d\n"
        "btc,Bitcoin,65000,32000000000,1200000000000,0.4,2.1,7.8\n",
        encoding="utf-8",
    )

    exit_code = cli.main(["--csv", str(csv_path), "--limit", "1"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "BTC (Bitcoin)" in output
    assert "Bias" in output
    assert "not financial advice" in output


def test_cli_reports_network_errors_without_traceback(monkeypatch, capsys):
    def fail_fetch(vs_currency):
        raise CoinGeckoError("CoinGecko request timed out.")

    monkeypatch.setattr(cli, "fetch_markets", fail_fetch)

    exit_code = cli.main(["--limit", "1"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Error: CoinGecko request timed out." in captured.err
    assert "Traceback" not in captured.err


def test_render_table_includes_bias_and_short_notes():
    opportunities = cli.scan_market([
        Coin("ETH", "Ethereum", 3000, 5_000_000_000, 400_000_000_000, 1.0, 4.0, 6.0)
    ])

    table = cli.render_table(opportunities)

    assert "Bias" in table
    assert "ETH (Ethereum)" in table
    assert "positive 24h momentum" in table
