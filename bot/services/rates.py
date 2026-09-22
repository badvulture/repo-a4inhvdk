import time

import aiohttp

from config import config

_cache: dict[str, float] = {"rate": 0.0, "ts": 0.0}


async def rub_per_usd() -> float:
    """Current RUB per 1 USD, cached for USD_RATE_TTL seconds."""
    if _cache["rate"] and time.time() - _cache["ts"] < config.usd_rate_ttl:
        return _cache["rate"]
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                config.usd_rate_url, timeout=aiohttp.ClientTimeout(10)
            ) as r:
                data = await r.json(content_type=None)
                rate = float(data["Valute"]["USD"]["Value"])
    except Exception:
        rate = _cache["rate"] or config.usd_rate_fallback
    _cache.update(rate=rate, ts=time.time())
    return rate


async def rub_to_usd(rub: float) -> float:
    rate = await rub_per_usd()
    return round(rub / rate, 2)


_CRYPTO_IDS = {
    "USDT": "tether",
    "TON": "the-open-network",
    "BTC": "bitcoin",
    "ETH": "ethereum",
}
_crypto_cache: dict[str, dict[str, float]] = {}
_CRYPTO_TTL = 300


async def rub_to_crypto(rub: float, symbol: str) -> float:
    """RUB -> crypto amount at the current CoinGecko rate, cached for 5 min."""
    coin_id = _CRYPTO_IDS.get(symbol.upper())
    if not coin_id:
        return 0.0
    now = time.time()
    cached = _crypto_cache.get(coin_id)
    if cached and now - cached["ts"] < _CRYPTO_TTL:
        rate = cached["rate"]
    else:
        try:
            async with aiohttp.ClientSession() as s:
                url = (
                    "https://api.coingecko.com/api/v3/simple/price"
                    f"?ids={coin_id}&vs_currencies=rub"
                )
                async with s.get(url, timeout=aiohttp.ClientTimeout(10)) as r:
                    data = await r.json(content_type=None)
                    rate = float(data.get(coin_id, {}).get("rub", 0))
                    if rate:
                        _crypto_cache[coin_id] = {"rate": rate, "ts": now}
        except Exception:
            rate = (cached or {}).get("rate", 0.0)
    if not rate:
        return 0.0
    return rub / rate


def format_crypto(amount: float, symbol: str) -> str:
    if symbol == "BTC":
        res = f"{amount:.8f}".rstrip("0").rstrip(".")
    elif symbol == "ETH":
        res = f"{amount:.6f}".rstrip("0").rstrip(".")
    else:  # USDT, TON
        res = f"{amount:.2f}".rstrip("0").rstrip(".")
    return res or "0"
