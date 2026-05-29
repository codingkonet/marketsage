import pandas as pd


def compute_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=window, min_periods=window).mean()
    avg_loss = loss.rolling(window=window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


def build_features(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    close = df["Close"]

    df["return"] = close.pct_change()
    df["sma_14"] = close.rolling(window=14).mean()
    df["ema_14"] = close.ewm(span=14, adjust=False).mean()
    df["volatility_14"] = df["return"].rolling(window=14).std()
    df["momentum_7"] = close - close.shift(7)
    df["rsi_14"] = compute_rsi(close, window=14)

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Bollinger Bands (20-period)
    sma20 = close.rolling(window=20).mean()
    std20 = close.rolling(window=20).std()
    df["bb_upper"] = sma20 + 2 * std20
    df["bb_lower"] = sma20 - 2 * std20
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma20
    df["bb_pct"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    df = df.dropna()
    return df
