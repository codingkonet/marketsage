import pandas as pd
import yfinance as yf


def load_forex_data(pair: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Download forex data for a currency pair.

    Args:
        pair: The yfinance forex ticker, e.g. EURUSD=X.
        period: Data period, e.g. 1y, 6mo, 3mo.
        interval: Interval string, e.g. 1d, 1h.
    """
    data = yf.download(pair, period=period, interval=interval, progress=False)
    if data.empty:
        raise ValueError(f"No data returned for {pair} with period={period} and interval={interval}.")
    # yfinance >=0.2 returns a MultiIndex like ("Close", "EURUSD=X"); flatten for single-ticker use
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [col[0] for col in data.columns]
    return data
