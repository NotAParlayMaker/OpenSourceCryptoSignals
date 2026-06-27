"""CoinGecko data adapter for the crypto market scanner."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .scanner import Coin

API_URL = "https://api.coingecko.com/api/v3/coins/markets"
DEFAULT_TIMEOUT = 20.0


class CoinGeckoError(RuntimeError):
    """Raised when CoinGecko market data cannot be fetched or parsed."""


def _to_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coin_from_payload(item: dict[str, Any]) -> Coin:
    symbol = str(item.get("symbol") or "UNKNOWN").upper()
    name = str(item.get("name") or symbol)
    return Coin(
        symbol=symbol,
        name=name,
        price=_to_float(item.get("current_price")),
        volume_24h=_to_float(item.get("total_volume")),
        market_cap=_to_float(item.get("market_cap")),
        change_1h=_to_float(item.get("price_change_percentage_1h_in_currency")),
        change_24h=_to_float(item.get("price_change_percentage_24h_in_currency")),
        change_7d=_to_float(item.get("price_change_percentage_7d_in_currency")),
    )


def fetch_markets(
    vs_currency: str = "usd", per_page: int = 100, timeout: float = DEFAULT_TIMEOUT
) -> list[Coin]:
    """Fetch and normalize current market data from CoinGecko."""

    if per_page <= 0:
        return []

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

    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise CoinGeckoError(f"CoinGecko returned HTTP {exc.code}.") from exc
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise CoinGeckoError(f"Could not reach CoinGecko: {reason}.") from exc
    except TimeoutError as exc:
        raise CoinGeckoError("CoinGecko request timed out.") from exc
    except json.JSONDecodeError as exc:
        raise CoinGeckoError("CoinGecko returned malformed JSON.") from exc

    if not isinstance(payload, list):
        raise CoinGeckoError("CoinGecko returned an unexpected response format.")
    if not payload:
        return []

    coins: list[Coin] = []
    for item in payload:
        if isinstance(item, dict):
            coins.append(_coin_from_payload(item))
    return coins
