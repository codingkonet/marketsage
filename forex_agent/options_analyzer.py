from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf


def _ncdf(x):
    """Standard normal CDF via math.erfc — no scipy needed."""
    from math import erfc, sqrt
    return 0.5 * erfc(-x / sqrt(2))


def _npdf(x):
    return np.exp(-0.5 * x ** 2) / np.sqrt(2 * np.pi)


def bs_greeks(S: float, K: float, T: float, sigma: float, option_type: str = "call", r: float = 0.045) -> dict:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {}
    sqrtT = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrtT)
    d2 = d1 - sigma * sqrtT

    if option_type == "call":
        delta = float(_ncdf(d1))
    else:
        delta = float(_ncdf(d1) - 1)

    gamma = float(_npdf(d1) / (S * sigma * sqrtT))
    vega = float(S * _npdf(d1) * sqrtT / 100)

    if option_type == "call":
        theta = float((-S * _npdf(d1) * sigma / (2 * sqrtT) - r * K * np.exp(-r * T) * _ncdf(d2)) / 365)
    else:
        theta = float((-S * _npdf(d1) * sigma / (2 * sqrtT) + r * K * np.exp(-r * T) * _ncdf(-d2)) / 365)

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
    }


@dataclass
class OptionsResult:
    symbol: str
    name: str
    current_price: float
    expiry: str
    expiries: list
    days_to_expiry: int
    calls: list = field(default_factory=list)
    puts: list = field(default_factory=list)
    iv_strikes: list = field(default_factory=list)
    iv_calls: list = field(default_factory=list)
    iv_puts: list = field(default_factory=list)


def analyze_options(symbol: str, expiry: str = None) -> OptionsResult:
    ticker = yf.Ticker(symbol.upper())

    info = ticker.fast_info
    current_price = float(info.last_price)

    try:
        name = ticker.info.get("shortName") or ticker.info.get("longName") or symbol.upper()
    except Exception:
        name = symbol.upper()

    expiries = list(ticker.options)
    if not expiries:
        raise ValueError(f"No options data available for {symbol.upper()}. Try a stock ticker like SPY, AAPL, or TSLA.")

    if not expiry or expiry not in expiries:
        expiry = expiries[0]

    chain = ticker.option_chain(expiry)
    calls_df = chain.calls.copy()
    puts_df = chain.puts.copy()

    expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
    days_to_expiry = max((expiry_dt - datetime.now()).days, 1)
    T = days_to_expiry / 365

    # Keep ATM ± 20 strikes for the table
    def atm_filter(df, n=20):
        df = df.copy()
        df["_dist"] = (df["strike"] - current_price).abs()
        return df.nsmallest(n, "_dist").sort_values("strike")

    calls_near = atm_filter(calls_df)
    puts_near = atm_filter(puts_df)

    def to_records(df, opt_type):
        rows = []
        for _, row in df.iterrows():
            strike = float(row["strike"])
            iv = float(row.get("impliedVolatility") or 0)
            greeks = bs_greeks(current_price, strike, T, iv, opt_type) if iv > 0 else {}
            itm = (opt_type == "call" and strike < current_price) or (opt_type == "put" and strike > current_price)
            rows.append({
                "strike": strike,
                "last": round(float(row.get("lastPrice") or 0), 4),
                "bid": round(float(row.get("bid") or 0), 4),
                "ask": round(float(row.get("ask") or 0), 4),
                "volume": int(row.get("volume") or 0),
                "oi": int(row.get("openInterest") or 0),
                "iv": round(iv * 100, 1),
                "itm": itm,
                **greeks,
            })
        return rows

    calls = to_records(calls_near, "call")
    puts = to_records(puts_near, "put")

    # IV skew — full strike range
    call_iv = dict(zip(calls_df["strike"].tolist(), (calls_df["impliedVolatility"] * 100).tolist()))
    put_iv = dict(zip(puts_df["strike"].tolist(), (puts_df["impliedVolatility"] * 100).tolist()))
    all_strikes = sorted(set(call_iv) | set(put_iv))

    iv_strikes = [float(s) for s in all_strikes]
    iv_calls = [round(float(call_iv.get(s, 0)), 2) for s in all_strikes]
    iv_puts = [round(float(put_iv.get(s, 0)), 2) for s in all_strikes]

    return OptionsResult(
        symbol=symbol.upper(),
        name=name,
        current_price=current_price,
        expiry=expiry,
        expiries=expiries,
        days_to_expiry=days_to_expiry,
        calls=calls,
        puts=puts,
        iv_strikes=iv_strikes,
        iv_calls=iv_calls,
        iv_puts=iv_puts,
    )
