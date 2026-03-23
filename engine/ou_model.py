"""
engine/ou_model.py — Model Ornstein-Uhlenbeck (mean-reversion) v2
"""
import numpy as np
import pandas as pd
from scipy import stats
from loguru import logger
from config import OU_WINDOW_MIN, Z_SCORE_THRESHOLD, MIN_WIN_PROBABILITY, EXPIRY_OPTIONS

def calibrate_ou(series: pd.Series, dt: float = 1.0) -> dict:
    x_t, x_tp1 = series.values[:-1], series.values[1:]
    if len(x_t)<10:
        return {"kappa":0.1,"theta":0.0,"sigma":0.001,"half_life":7.0}
    slope, intercept, *_ = stats.linregress(x_t, x_tp1)
    beta  = float(np.clip(slope, 0.01, 0.9999))
    kappa = -np.log(beta)/dt
    theta = intercept/(1-beta)
    sigma = float(np.std(x_tp1-(intercept+slope*x_t), ddof=2))
    hl    = np.log(2)/kappa if kappa>0 else 999.0
    return {"kappa":float(kappa),"theta":float(theta),"sigma":float(sigma),"half_life":float(hl)}

def ou_forecast(x_now, params, delta_min) -> tuple:
    k,th,s = params["kappa"],params["theta"],params["sigma"]
    d  = np.exp(-k*delta_min)
    mf = th+(x_now-th)*d
    vf = (s**2)/(2*k)*(1-np.exp(-2*k*delta_min))
    return float(mf), float(np.sqrt(max(vf,1e-10)))

def compute_direction_probability(x_now, params, delta_min, direction) -> float:
    mf, sf = ou_forecast(x_now, params, delta_min)
    if direction=="CALL": prob = 1-stats.norm.cdf(0, loc=mf-x_now, scale=sf)
    else:                 prob = stats.norm.cdf(0, loc=mf-x_now, scale=sf)
    return float(np.clip(prob, 0.0, 1.0))

def run_ou_grid_scoring(df: pd.DataFrame, expiry_options: list = None) -> dict | None:
    if expiry_options is None: expiry_options = EXPIRY_OPTIONS
    close  = df["close"]
    window = min(OU_WINDOW_MIN, len(close)-2)
    resid  = close - close.ewm(span=20, adjust=False).mean()
    params = calibrate_ou(resid.iloc[-window:])
    x_now  = float(resid.iloc[-1])
    z_now  = x_now/(params["sigma"]+1e-10)
    if abs(z_now)<Z_SCORE_THRESHOLD:
        logger.debug(f"OU: Z={z_now:.3f}<{Z_SCORE_THRESHOLD}. Skip.")
        return None
    direction = "CALL" if z_now<-Z_SCORE_THRESHOLD else "PUT"
    best = {"delta":None,"prob":0.0,"direction":direction,"params":params,"zscore":z_now,"dist_atr":0.0}
    for delta in expiry_options:
        prob = compute_direction_probability(x_now, params, delta, direction)
        if prob>best["prob"]:
            best["delta"], best["prob"] = delta, prob
    if best["prob"]<MIN_WIN_PROBABILITY: return None
    logger.info(f"OU: {direction} D={best['delta']}min P={best['prob']:.3f} Z={z_now:.3f}")
    return best
