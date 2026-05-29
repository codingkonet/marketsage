import pandas as pd
import yfinance as yf
from .cache import cache_get, cache_set


def load_forex_data(pair: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    key = f"{pair}:{period}:{interval}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    data = yf.download(pair, period=period, interval=interval, progress=False)
    if data.empty:
        raise ValueError(f"No data returned for {pair} with period={period} and interval={interval}.")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [col[0] for col in data.columns]

    cache_set(key, data, ttl=900)
    return data


def load_close_prices(pairs: list[str], period: str = "1y") -> pd.DataFrame:
    """Return a DataFrame of Close prices for multiple pairs (for correlation)."""
    closes = {}
    for pair in pairs:
        try:
            df = load_forex_data(pair, period=period, interval="1d")
            closes[pair] = df["Close"]
        except Exception:
            pass
    return pd.DataFrame(closes)
