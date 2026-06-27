import json
from urllib.error import HTTPError, URLError

import pytest

from crypto_market_scanner.coingecko import CoinGeckoError, fetch_markets


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


def test_fetch_markets_handles_missing_and_malformed_fields(monkeypatch):
    payload = json.dumps([
        {
            "symbol": "abc",
            "name": None,
            "current_price": "not-a-number",
            "total_volume": 15000000,
        }
    ]).encode()
    monkeypatch.setattr("crypto_market_scanner.coingecko.urlopen", lambda request, timeout: FakeResponse(payload))

    coins = fetch_markets()

    assert len(coins) == 1
    assert coins[0].symbol == "ABC"
    assert coins[0].name == "ABC"
    assert coins[0].price == 0
    assert coins[0].change_24h == 0


def test_fetch_markets_raises_clean_error_for_network_failure(monkeypatch):
    def raise_url_error(request, timeout):
        raise URLError("offline")

    monkeypatch.setattr("crypto_market_scanner.coingecko.urlopen", raise_url_error)

    with pytest.raises(CoinGeckoError, match="Could not reach CoinGecko"):
        fetch_markets()


def test_fetch_markets_raises_clean_error_for_http_failure(monkeypatch):
    def raise_http_error(request, timeout):
        raise HTTPError("url", 429, "Too Many Requests", hdrs=None, fp=None)

    monkeypatch.setattr("crypto_market_scanner.coingecko.urlopen", raise_http_error)

    with pytest.raises(CoinGeckoError, match="HTTP 429"):
        fetch_markets()


def test_fetch_markets_rejects_unexpected_payload(monkeypatch):
    monkeypatch.setattr(
        "crypto_market_scanner.coingecko.urlopen",
        lambda request, timeout: FakeResponse(b'{"error":"bad"}'),
    )

    with pytest.raises(CoinGeckoError, match="unexpected response format"):
        fetch_markets()
