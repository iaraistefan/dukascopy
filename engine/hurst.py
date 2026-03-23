"""
engine/hurst.py — Regim de piata: momentum / mean-reversion / random
"""
import numpy as np
import pandas as pd
from loguru import logger
from config import (HURST_WINDOW, HURST_MOMENTUM_THRESHOLD,
                    HURST_MR_THRESHOLD, REQUIRE_REGIME_ALIGNMENT)

def compute_hurst_rs(series: np.ndarray) -> float:
    n = len(series)
    if n < 20: return 0.5
    rs_values = []
    for lag in range(2, min(n//2, 20)):
        chunks = [series[i:i+lag] for i in range(0,n-lag+1,lag)]
        rs_chunk = []
        for chunk in chunks:
            if len(chunk)<2: continue
            dev = np.cumsum(chunk - np.mean(chunk))
            s   = np.std(chunk, ddof=1)
            if s>0: rs_chunk.append((np.max(dev)-np.min(dev))/s)
        if rs_chunk:
            rs_values.append((np.log(lag), np.log(np.mean(rs_chunk))))
    if len(rs_values)<2: return 0.5
    x = np.array([r[0] for r in rs_values])
    y = np.array([r[1] for r in rs_values])
    return float(np.clip(np.polyfit(x,y,1)[0], 0.01, 0.99))

def compute_moving_hurst(df: pd.DataFrame, window: int = HURST_WINDOW) -> pd.Series:
    close   = df["close"].values
    log_ret = np.diff(np.log(close))
    result  = np.full(len(close), 0.5)
    for i in range(window, len(close)):
        seg = log_ret[max(0,i-window):i-1]
        if len(seg)>=20: result[i] = compute_hurst_rs(seg)
    return pd.Series(result, index=df.index, name="hurst")

def classify_regime(h: float) -> str:
    if h <= HURST_MR_THRESHOLD:       return "mean_reversion"
    if h >= HURST_MOMENTUM_THRESHOLD: return "momentum"
    return "random"

def detect_drift_direction(df: pd.DataFrame, lookback: int = 20) -> str:
    close = df["close"].values
    if len(close)<lookback+1: return "flat"
    recent = close[-lookback:]
    drift  = recent[-1]-recent[0]
    atr_a  = np.mean(np.abs(np.diff(recent)))
    if atr_a==0: return "flat"
    ratio = drift/(atr_a*lookback)
    return "up" if ratio>0.05 else ("down" if ratio<-0.05 else "flat")

def get_current_regime(df: pd.DataFrame) -> tuple:
    h      = float(compute_moving_hurst(df).iloc[-1])
    regime = classify_regime(h)
    drift  = detect_drift_direction(df)
    logger.debug(f"Hurst={h:.3f} -> {regime} | Drift: {drift}")
    return regime, h, drift

def is_regime_compatible(regime, signal_direction, drift_direction, signal_source="FPT") -> tuple:
    if not REQUIRE_REGIME_ALIGNMENT: return True, "disabled"
    if regime=="random": return False, "regim_random"
    if regime=="momentum":
        if signal_source=="OU": return False, "OU_in_momentum"
        if drift_direction=="up"   and signal_direction=="PUT":  return False, "PUT_contra_UP"
        if drift_direction=="down" and signal_direction=="CALL": return False, "CALL_contra_DOWN"
        return True, "FPT_ok"
    if regime=="mean_reversion":
        if signal_source=="FPT": return False, "FPT_in_MR"
        return True, "OU_ok"
    return True, "ok"
