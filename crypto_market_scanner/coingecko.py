"""CoinGecko data adapter for the crypto market scanner."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .scanner import Coin

API_URL = "https://api.coingecko.com/api/v3/coins/markets"


def fetch_markets(vs_currency: str = "usd", per_page: int = 100) -> list[Coin]:
    """Fetch and normalize current market data from CoinGecko."""

    query = urlencode(
        {
            "vs_currency": vs_currency,
            "order": "volume_desc",
            "per_page": per_page,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d",
        }
    )
    request = Request(
        f"{API_URL}?{query}", headers={"User-Agent": "OpenSourceCryptoSignals/1.0"}
    )
    with urlopen(
        request, timeout=20
    ) as response:  # nosec B310: user-invoked public market-data API
        payload = json.loads(response.read().decode("utf-8"))

    return [
        Coin(
            symbol=str(item.get("symbol", "")).upper(),
            name=str(item.get("name", "Unknown")),
            price=float(item.get("current_price") or 0),
            volume_24h=float(item.get("total_volume") or 0),
            market_cap=float(item.get("market_cap") or 0),
            change_1h=float(item.get("price_change_percentage_1h_in_currency") or 0),
            change_24h=float(item.get("price_change_percentage_24h_in_currency") or 0),
            change_7d=float(item.get("price_change_percentage_7d_in_currency") or 0),
        )
        for item in payload
    ]
