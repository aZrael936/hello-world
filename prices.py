"""Fetch live crypto prices from CoinGecko free API."""

import requests

COINGECKO_URL = "https://api.coingecko.com/api/v3"

# Top 20 crypto coin IDs on CoinGecko
TOP_20_IDS = [
    "bitcoin", "ethereum", "tether", "binancecoin", "solana",
    "ripple", "usd-coin", "cardano", "dogecoin", "tron",
    "avalanche-2", "chainlink", "polkadot", "polygon-pos",  "litecoin",
    "shiba-inu", "uniswap", "stellar", "near", "aptos",
]

# Mapping from CoinGecko ID to common trading symbol
ID_TO_SYMBOL = {
    "bitcoin": "BTC", "ethereum": "ETH", "tether": "USDT",
    "binancecoin": "BNB", "solana": "SOL", "ripple": "XRP",
    "usd-coin": "USDC", "cardano": "ADA", "dogecoin": "DOGE",
    "tron": "TRX", "avalanche-2": "AVAX", "chainlink": "LINK",
    "polkadot": "DOT", "polygon-pos": "MATIC", "litecoin": "LTC",
    "shiba-inu": "SHIB", "uniswap": "UNI", "stellar": "XLM",
    "near": "NEAR", "aptos": "APT",
}

SYMBOL_TO_ID = {v: k for k, v in ID_TO_SYMBOL.items()}


def fetch_prices(vs_currency="usd"):
    """
    Fetch current prices for top 20 cryptos.
    Returns dict: {SYMBOL: price}
    """
    ids = ",".join(TOP_20_IDS)
    params = {
        "ids": ids,
        "vs_currencies": vs_currency,
        "include_24hr_change": "true",
    }

    try:
        resp = requests.get(
            f"{COINGECKO_URL}/simple/price",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return None, str(e)

    prices = {}
    changes = {}
    for coin_id, values in data.items():
        symbol = ID_TO_SYMBOL.get(coin_id, coin_id.upper())
        price = values.get(vs_currency, 0)
        change = values.get(f"{vs_currency}_24h_change", 0)
        prices[symbol] = price
        changes[symbol] = change

    return prices, changes


def fetch_price_single(symbol, vs_currency="usd"):
    """Fetch price for a single symbol. Returns (price, error_msg)."""
    symbol = symbol.upper()
    coin_id = SYMBOL_TO_ID.get(symbol)
    if not coin_id:
        return None, f"Unknown symbol: {symbol}. Use one of: {', '.join(sorted(SYMBOL_TO_ID.keys()))}"

    try:
        resp = requests.get(
            f"{COINGECKO_URL}/simple/price",
            params={"ids": coin_id, "vs_currencies": vs_currency},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return None, str(e)

    price = data.get(coin_id, {}).get(vs_currency)
    if price is None:
        return None, f"No price data for {symbol}"
    return price, None


def get_supported_symbols():
    """Return list of supported trading symbols."""
    return sorted(SYMBOL_TO_ID.keys())
