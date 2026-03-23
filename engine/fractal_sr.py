"""
engine/fractal_sr.py — Niveluri S/R fractale + ATR
"""
import numpy as np
import pandas as pd
from loguru import logger
from config import FRACTAL_N, FRACTAL_PROXIMITY, MAX_SR_LEVELS, ATR_PERIOD

def detect_fractals(df: pd.DataFrame, n: int = FRACTAL_N) -> tuple:
    highs, lows, total = df["high"].values, df["low"].values, len(df)
    res_idx = [i for i in range(n, total-n)
               if all(highs[i]>highs[i-j] for j in range(1,n+1))
               and all(highs[i]>highs[i+j] for j in range(1,n+1))]
    sup_idx = [i for i in range(n, total-n)
               if all(lows[i]<lows[i-j] for j in range(1,n+1))
               and all(lows[i]<lows[i+j] for j in range(1,n+1))]
    return (np.unique(df["high"].iloc[res_idx].values)[-MAX_SR_LEVELS:],
            np.unique(df["low"].iloc[sup_idx].values)[-MAX_SR_LEVELS:])

def cluster_levels(levels: np.ndarray, tolerance: float) -> np.ndarray:
    if len(levels) == 0:
        return levels
    sl = np.sort(levels)
    cl = [sl[0]]
    for lv in sl[1:]:
        if lv - cl[-1] > tolerance: cl.append(lv)
        else: cl[-1] = (cl[-1]+lv)/2
    return np.array(cl)

def compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    h,l,c = df["high"],df["low"],df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([h-l,(h-prev_c).abs(),(l-prev_c).abs()],axis=1).max(axis=1)
    return tr.rolling(period).mean().rename("atr")

def get_sr_levels(df: pd.DataFrame) -> tuple:
    atr_c = float(compute_atr(df).iloc[-1])
    res, sup = detect_fractals(df)
    res = cluster_levels(res, atr_c*FRACTAL_PROXIMITY)
    sup = cluster_levels(sup, atr_c*FRACTAL_PROXIMITY)
    p, md = float(df["close"].iloc[-1]), atr_c*10
    res = res[(res>p)&(res-p<md)]
    sup = sup[(sup<p)&(p-sup<md)]
    return res, sup

def nearest_sr_distance(price, resistances, supports) -> tuple:
    du = float(np.min(resistances-price)) if len(resistances)>0 else float("inf")
    dd = float(np.min(price-supports))    if len(supports)>0    else float("inf")
    return du, dd
