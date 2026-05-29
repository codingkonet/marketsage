from dataclasses import dataclass, field
from datetime import datetime
from math import erfc, sqrt, exp, log, pi

import numpy as np
import pandas as pd
import yfinance as yf


# ── Black-Scholes ────────────────────────────────────────────────────────────

def _ncdf(x: float) -> float:
    return 0.5 * erfc(-x / sqrt(2))


def _npdf(x: float) -> float:
    return exp(-0.5 * x ** 2) / sqrt(2 * pi)


def bs_greeks(S: float, K: float, T: float, sigma: float, option_type: str = "call", r: float = 0.045) -> dict:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {}
    sqrtT = sqrt(T)
    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrtT)
    d2 = d1 - sigma * sqrtT
    delta = _ncdf(d1) if option_type == "call" else _ncdf(d1) - 1
    gamma = _npdf(d1) / (S * sigma * sqrtT)
    vega = S * _npdf(d1) * sqrtT / 100
    if option_type == "call":
        theta = (-S * _npdf(d1) * sigma / (2 * sqrtT) - r * K * exp(-r * T) * _ncdf(d2)) / 365
    else:
        theta = (-S * _npdf(d1) * sigma / (2 * sqrtT) + r * K * exp(-r * T) * _ncdf(-d2)) / 365
    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
    }


# ── Result ───────────────────────────────────────────────────────────────────

@dataclass
class OptionsResult:
    symbol: str
    name: str
    current_price: float
    expiry: str
    expiries: list
    days_to_expiry: int
    # chain
    calls: list = field(default_factory=list)
    puts: list = field(default_factory=list)
    # IV skew
    iv_strikes: list = field(default_factory=list)
    iv_calls: list = field(default_factory=list)
    iv_puts: list = field(default_factory=list)
    # market intelligence
    put_call_ratio: float = 0.0
    max_pain: float = 0.0
    unusual: list = field(default_factory=list)
    # payoff diagram
    payoff_spots: list = field(default_factory=list)
    payoff_call: list = field(default_factory=list)
    payoff_put: list = field(default_factory=list)
    payoff_straddle: list = field(default_factory=list)
    atm_call_strike: float = 0.0
    atm_put_strike: float = 0.0
    atm_call_premium: float = 0.0
    atm_put_premium: float = 0.0


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mid(row) -> float:
    bid, ask = float(row.get("bid") or 0), float(row.get("ask") or 0)
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    return float(row.get("lastPrice") or 0)


def _atm_row(df: pd.DataFrame, spot: float) -> pd.Series:
    df = df.copy()
    df["_d"] = (df["strike"] - spot).abs()
    return df.nsmallest(1, "_d").iloc[0]


def _max_pain(calls_df: pd.DataFrame, puts_df: pd.DataFrame) -> float:
    strikes = sorted(set(calls_df["strike"].tolist()) | set(puts_df["strike"].tolist()))
    call_oi = dict(zip(calls_df["strike"], calls_df["openInterest"].fillna(0)))
    put_oi = dict(zip(puts_df["strike"], puts_df["openInterest"].fillna(0)))
    pain = {}
    for S in strikes:
        c_loss = sum(max(0, S - K) * oi for K, oi in call_oi.items())
        p_loss = sum(max(0, K - S) * oi for K, oi in put_oi.items())
        pain[S] = c_loss + p_loss
    return float(min(pain, key=pain.get)) if pain else 0.0


def _unusual(calls_df: pd.DataFrame, puts_df: pd.DataFrame) -> list:
    rows = []
    for df, opt_type in [(calls_df, "call"), (puts_df, "put")]:
        for _, row in df.iterrows():
            raw_vol = row.get("volume")
            raw_oi  = row.get("openInterest")
            vol = int(raw_vol) if raw_vol is not None and raw_vol == raw_vol else 0
            oi  = int(raw_oi)  if raw_oi  is not None and raw_oi  == raw_oi  else 0
            if vol < 500:
                continue
            ratio = vol / oi if oi > 0 else float("inf")
            if ratio >= 2 or vol >= 5000:
                rows.append({
                    "type": opt_type,
                    "strike": float(row["strike"]),
                    "volume": vol,
                    "oi": oi,
                    "iv": round(float(row.get("impliedVolatility") or 0) * 100, 1),
                    "ratio": round(ratio, 1) if oi > 0 else "∞",
                })
    return sorted(rows, key=lambda x: x["volume"], reverse=True)[:12]


def _payoff_diagram(spot: float, atm_call_row: pd.Series, atm_put_row: pd.Series) -> dict:
    call_strike = float(atm_call_row["strike"])
    put_strike = float(atm_put_row["strike"])
    call_prem = _mid(atm_call_row)
    put_prem = _mid(atm_put_row)

    lo, hi = spot * 0.80, spot * 1.20
    spots = [round(lo + (hi - lo) * i / 100, 4) for i in range(101)]

    call_payoff = [round(max(s - call_strike, 0) - call_prem, 4) for s in spots]
    put_payoff = [round(max(put_strike - s, 0) - put_prem, 4) for s in spots]
    straddle = [round(c + p, 4) for c, p in zip(call_payoff, put_payoff)]

    return {
        "spots": spots,
        "call": call_payoff,
        "put": put_payoff,
        "straddle": straddle,
        "call_strike": call_strike,
        "put_strike": put_strike,
        "call_prem": round(call_prem, 4),
        "put_prem": round(put_prem, 4),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def analyze_options(symbol: str, expiry: str = None) -> OptionsResult:
    ticker = yf.Ticker(symbol.upper())
    current_price = float(ticker.fast_info.last_price)

    try:
        name = ticker.info.get("shortName") or ticker.info.get("longName") or symbol.upper()
    except Exception:
        name = symbol.upper()

    expiries = list(ticker.options)
    if not expiries:
        raise ValueError(f"No options data for {symbol.upper()}. Try SPY, AAPL, TSLA, QQQ.")

    if not expiry or expiry not in expiries:
        expiry = expiries[0]

    chain = ticker.option_chain(expiry)
    calls_df = chain.calls.copy()
    puts_df = chain.puts.copy()

    expiry_dt = datetime.strptime(expiry, "%Y-%m-%d")
    days_to_expiry = max((expiry_dt - datetime.now()).days, 1)
    T = days_to_expiry / 365

    # ATM-filtered chain (nearest 20 strikes each side)
    def atm_filter(df, n=20):
        df = df.copy()
        df["_d"] = (df["strike"] - current_price).abs()
        return df.nsmallest(n, "_d").sort_values("strike")

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

    # IV skew (full range)
    call_iv_map = dict(zip(calls_df["strike"], (calls_df["impliedVolatility"] * 100).round(2)))
    put_iv_map = dict(zip(puts_df["strike"], (puts_df["impliedVolatility"] * 100).round(2)))
    all_strikes = sorted(set(call_iv_map) | set(put_iv_map))
    iv_strikes = [float(s) for s in all_strikes]
    iv_calls = [round(float(call_iv_map.get(s, 0)), 2) for s in all_strikes]
    iv_puts = [round(float(put_iv_map.get(s, 0)), 2) for s in all_strikes]

    # Put/call ratio (by volume)
    call_vol = calls_df["volume"].fillna(0).sum()
    put_vol = puts_df["volume"].fillna(0).sum()
    put_call_ratio = round(float(put_vol / call_vol), 3) if call_vol > 0 else 0.0

    # Max pain
    max_pain = _max_pain(calls_df, puts_df)

    # Unusual activity
    unusual = _unusual(calls_df, puts_df)

    # Payoff diagram
    atm_call_row = _atm_row(calls_df, current_price)
    atm_put_row = _atm_row(puts_df, current_price)
    pd_data = _payoff_diagram(current_price, atm_call_row, atm_put_row)

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
        put_call_ratio=put_call_ratio,
        max_pain=max_pain,
        unusual=unusual,
        payoff_spots=pd_data["spots"],
        payoff_call=pd_data["call"],
        payoff_put=pd_data["put"],
        payoff_straddle=pd_data["straddle"],
        atm_call_strike=pd_data["call_strike"],
        atm_put_strike=pd_data["put_strike"],
        atm_call_premium=pd_data["call_prem"],
        atm_put_premium=pd_data["put_prem"],
    )
