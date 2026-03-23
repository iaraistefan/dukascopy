"""
engine/confluence.py — RSI + Stability Score
"""
import numpy as np
import pandas as pd
from loguru import logger
from config import (RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
                    STABILITY_EMA_PERIOD, STABILITY_LOOKBACK,
                    CONFLUENCE_RSI_WEIGHT, CONFLUENCE_STABILITY_WEIGHT)

def compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    d  = close.diff()
    g  = d.where(d>0, 0.0)
    l  = (-d).where(d<0, 0.0)
    ag = g.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    al = l.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return (100-100/(1+ag/(al+1e-10))).rename("rsi")

def compute_stability_score(df: pd.DataFrame) -> float:
    close = df["close"]
    ema   = close.ewm(span=STABILITY_EMA_PERIOD, adjust=False).mean()
    n     = min(STABILITY_LOOKBACK, len(close))
    rc,re = close.iloc[-n:].values, ema.iloc[-n:].values
    h,l,c = df["high"],df["low"],df["close"]
    tr  = pd.concat([h-l,(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])
    if atr<=0 or np.isnan(atr): return 0.5
    return float(np.clip(1.0-np.sum(np.abs(rc-re))/(n*atr), 0.0, 1.0))

def compute_rsi_confirmation(df: pd.DataFrame, direction: str) -> float:
    rsi = float(compute_rsi(df["close"]).iloc[-1])
    if direction=="CALL":
        if rsi<=RSI_OVERSOLD:  return 1.0
        if rsi<=50: return 0.5+0.5*(50-rsi)/(50-RSI_OVERSOLD)
        return max(0.0, 0.5-0.5*(rsi-50)/(RSI_OVERBOUGHT-50))
    else:
        if rsi>=RSI_OVERBOUGHT: return 1.0
        if rsi>=50: return 0.5+0.5*(rsi-50)/(RSI_OVERBOUGHT-50)
        return max(0.0, 0.5-0.5*(50-rsi)/(50-RSI_OVERSOLD))

def compute_confluence_score(df: pd.DataFrame, direction: str) -> tuple:
    stab = compute_stability_score(df)
    rsi  = compute_rsi_confirmation(df, direction)
    conf = stab*CONFLUENCE_STABILITY_WEIGHT + rsi*CONFLUENCE_RSI_WEIGHT
    logger.debug(f"Confluence: stab={stab:.3f} rsi={rsi:.3f} -> {conf:.3f}")
    return conf, stab, rsi
