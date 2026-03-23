"""
engine/fpt_model.py — First Passage Time v2 (fereastra 60 bare)
"""
import numpy as np
import pandas as pd
from scipy import stats
from loguru import logger
from config import MIN_FPT_PROB, MIN_SR_DISTANCE_ATR, EXPIRY_OPTIONS
from engine.fractal_sr import compute_atr

def estimate_drift_vol(log_returns: np.ndarray, dt: float = 1.0) -> tuple:
    mu    = float(np.mean(log_returns)/dt)
    sigma = float(np.std(log_returns,ddof=1)/np.sqrt(dt))
    return mu, max(sigma, 1e-12)

def inverse_gaussian_cdf(t, a, mu, sigma) -> float:
    if t<=0 or sigma<=0 or a<=0: return 0.0
    a_s, mu_s = a/sigma, mu/sigma
    sq = np.sqrt(t)
    t1 = stats.norm.cdf((mu_s*t-a_s)/sq)
    ev = 2*mu_s*a_s
    t2 = 0.0 if ev>500 else np.exp(ev)*stats.norm.cdf(-(mu_s*t+a_s)/sq)
    return float(np.clip(t1+t2, 0.0, 1.0))

def run_fpt_signal(df: pd.DataFrame, sr_levels: tuple, expiry_options: list = None) -> dict | None:
    if expiry_options is None: expiry_options = EXPIRY_OPTIONS
    close   = df["close"]
    log_ret = np.log(close/close.shift(1)).dropna().values[-60:]
    if len(log_ret)<10: return None
    mu, sigma  = estimate_drift_vol(log_ret)
    price_now  = float(close.iloc[-1])
    atr_now    = float(compute_atr(df).iloc[-1])
    if atr_now<=0 or np.isnan(atr_now): return None
    resistances, supports = sr_levels
    best = {"delta":None,"prob":0.0,"direction":None,"target_level":None,
            "mu":mu,"sigma":sigma,"dist_atr":0.0}
    for level in resistances:
        if level<=price_now: continue
        dist_atr = (level-price_now)/atr_now
        if dist_atr<MIN_SR_DISTANCE_ATR: continue
        dist_log = np.log(level/price_now)
        for delta in expiry_options:
            prob = inverse_gaussian_cdf(delta, dist_log, max(mu,1e-10), sigma)
            if prob>best["prob"]:
                best.update({"delta":delta,"prob":prob,"direction":"CALL",
                             "target_level":level,"dist_atr":dist_atr})
    for level in supports:
        if level>=price_now: continue
        dist_atr = (price_now-level)/atr_now
        if dist_atr<MIN_SR_DISTANCE_ATR: continue
        dist_log = np.log(price_now/level)
        for delta in expiry_options:
            prob = inverse_gaussian_cdf(delta, dist_log, max(abs(mu),1e-10), sigma)
            if prob>best["prob"]:
                best.update({"delta":delta,"prob":prob,"direction":"PUT",
                             "target_level":level,"dist_atr":dist_atr})
    if best["prob"]<MIN_FPT_PROB or best["direction"] is None:
        logger.debug(f"FPT: prob={best['prob']:.3f}<{MIN_FPT_PROB}. Skip.")
        return None
    logger.info(f"FPT: {best['direction']} D={best['delta']}min P={best['prob']:.3f}")
    return best
