"""
engine/fpt_model.py — First Passage Time v2 (fereastra 60 bare)
Corectat matematic: Drift directional precis pentru CALL si PUT.
"""
import numpy as np
import pandas as pd
from scipy import stats
from loguru import logger

from config import MIN_FPT_PROB, MIN_SR_DISTANCE_ATR, EXPIRY_OPTIONS
from engine.fractal_sr import compute_atr

def estimate_drift_vol(log_returns: np.ndarray, dt: float = 1.0) -> tuple:
    """Estimeaza drift-ul (mu) si volatilitatea (sigma) din log returns."""
    mu    = float(np.mean(log_returns) / dt)
    sigma = float(np.std(log_returns, ddof=1) / np.sqrt(dt))
    return mu, max(sigma, 1e-12)

def inverse_gaussian_cdf(t: float, a: float, mu: float, sigma: float) -> float:
    """
    Calculeaza probabilitatea First Passage Time (FPT) folosind Inverse Gaussian CDF.
    t: timpul disponibil (delta)
    a: distanta logaritmica pana la bariera (suport/rezistenta)
    mu: drift-ul directional (viteza inspre bariera)
    sigma: volatilitatea miscarii
    """
    if t <= 0 or sigma <= 0 or a <= 0:
        return 0.0
        
    a_s = a / sigma
    mu_s = mu / sigma
    sq_t = np.sqrt(t)
    
    # Calcul termen 1
    t1 = stats.norm.cdf((mu_s * t - a_s) / sq_t)
    
    # Calcul termen 2 (cu protectie la overflow exponential)
    ev = 2 * mu_s * a_s
    t2 = 0.0 if ev > 500 else np.exp(ev) * stats.norm.cdf(-(mu_s * t + a_s) / sq_t)
    
    return float(np.clip(t1 + t2, 0.0, 1.0))

def run_fpt_signal(df: pd.DataFrame, sr_levels: tuple, expiry_options: list = None) -> dict | None:
    """
    Evalueaza probabilitatea atingerii nivelurilor de S/R folosind modelul FPT.
    Returneaza cel mai bun semnal (dict) sau None daca nu intruneste conditiile.
    """
    if expiry_options is None:
        expiry_options = EXPIRY_OPTIONS
        
    close = df["close"]
    
    # Calculam return-urile logaritmice pentru ultimele 60 de bare
    log_ret = np.log(close / close.shift(1)).dropna().values[-60:]
    if len(log_ret) < 10:
        return None
        
    mu, sigma = estimate_drift_vol(log_ret)
    
    price_now = float(close.iloc[-1])
    atr_now   = float(compute_atr(df).iloc[-1])
    
    if atr_now <= 0 or np.isnan(atr_now):
        return None
        
    resistances, supports = sr_levels
    
    best = {
        "delta": None,
        "prob": 0.0,
        "direction": None,
        "target_level": None,
        "mu": mu,
        "sigma": sigma,
        "dist_atr": 0.0
    }
    
    # ─── EVALUARE PENTRU CALL (ATINGERE REZISTENTE) ───────────────
    for level in resistances:
        if level <= price_now:
            continue
            
        dist_atr = (level - price_now) / atr_now
        if dist_atr < MIN_SR_DISTANCE_ATR:
            continue
            
        dist_log = np.log(level / price_now)
        
        for delta in expiry_options:
            # Drift-ul trebuie să fie pozitiv (în sus). Limităm la o valoare minimă pozitivă.
            prob = inverse_gaussian_cdf(delta, dist_log, max(mu, 1e-10), sigma)
            
            if prob > best["prob"]:
                best.update({
                    "delta": delta,
                    "prob": prob,
                    "direction": "CALL",
                    "target_level": level,
                    "dist_atr": dist_atr
                })
                
    # ─── EVALUARE PENTRU PUT (ATINGERE SUPORTURI) ─────────────────
    for level in supports:
        if level >= price_now:
            continue
            
        dist_atr = (price_now - level) / atr_now
        if dist_atr < MIN_SR_DISTANCE_ATR:
            continue
            
        dist_log = np.log(price_now / level)
        
        for delta in expiry_options:
            # BUG FIX CRITIC: Pentru PUT, drift-ul in directia suportului este -mu.
            # Daca mu e negativ (downtrend real), -mu devine pozitiv si FPT creste.
            prob = inverse_gaussian_cdf(delta, dist_log, max(-mu, 1e-10), sigma)
            
            if prob > best["prob"]:
                best.update({
                    "delta": delta,
                    "prob": prob,
                    "direction": "PUT",
                    "target_level": level,
                    "dist_atr": dist_atr
                })

    # ─── VALIDARE FINALA ──────────────────────────────────────────
    if best["prob"] < MIN_FPT_PROB or best["direction"] is None:
        logger.debug(f"FPT respins: prob={best['prob']:.3f} < {MIN_FPT_PROB}")
        return None
        
    logger.info(f"FPT generat: {best['direction']} D={best['delta']}min P={best['prob']:.3f} (S/R Dist: {best['dist_atr']:.2f} ATR)")
    
    return best
