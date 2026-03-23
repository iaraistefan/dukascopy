"""
engine/expiry_optimizer.py — Scor compus per expiry v2
"""
import numpy as np
import pandas as pd
from loguru import logger
from config import W1, W2, W3, ATR_HIGH_VOL_MULT, ATR_LOW_VOL_MULT
from engine.fractal_sr import compute_atr

def compute_penalty_vol(atr_c, atr_mean, delta_min) -> float:
    ratio = atr_c/(atr_mean+1e-10)
    if ratio>ATR_HIGH_VOL_MULT: return min(0.4,(ratio-1.0)*0.3)
    if ratio<ATR_LOW_VOL_MULT:  return 0.05*(1/delta_min)
    return 0.0

def compute_penalty_level(price, direction, res, sup, atr_c, delta_min) -> float:
    reach = atr_c*delta_min
    if direction=="CALL" and len(res)>0:
        return min(0.35, len(res[(res>price)&(res<price+reach)])*0.12)
    if direction=="PUT" and len(sup)>0:
        return min(0.35, len(sup[(sup<price)&(sup>price-reach)])*0.12)
    return 0.0

def select_optimal_expiry(probabilities: dict, df: pd.DataFrame,
                          direction: str, resistances, supports,
                          w1=W1, w2=W2, w3=W3) -> tuple:
    atr_s   = compute_atr(df)
    atr_c   = float(atr_s.iloc[-1])
    atr_avg = float(atr_s.rolling(50).mean().iloc[-1])
    price   = float(df["close"].iloc[-1])
    scores  = {}
    for delta, prob in probabilities.items():
        pv = compute_penalty_vol(atr_c, atr_avg, delta)
        pl = compute_penalty_level(price, direction, resistances, supports, atr_c, delta)
        sc = prob*w1 - pv*w2 - pl*w3
        scores[delta] = {"prob":prob,"pen_vol":pv,"pen_level":pl,"score":sc}
        logger.debug(f"Score({delta}min): prob={prob:.3f} pV={pv:.3f} pL={pl:.3f} -> {sc:.4f}")
    best_d = max(scores, key=lambda d: scores[d]["score"])
    logger.info(f"Expirare optima: {best_d}min (Score={scores[best_d]['score']:.4f})")
    return best_d, scores[best_d]["score"], scores
