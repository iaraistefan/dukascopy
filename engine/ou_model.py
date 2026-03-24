"""
engine/ou_model.py — Model Ornstein-Uhlenbeck (mean-reversion)
Corectat matematic: Z-Score echilibrat si conversie sigma continuu.
"""

import numpy as np
import pandas as pd
from scipy import stats
from loguru import logger
from config import OU_WINDOW_MIN, EXPIRY_OPTIONS, Z_SCORE_THRESHOLD, MIN_WIN_PROBABILITY

def calibrate_ou(series: pd.Series, dt: float = 1.0) -> dict:
    """Calibreaza parametrii OU folosind regresie liniara (Euler-Maruyama)."""
    x_t = series.values[:-1]
    x_tp1 = series.values[1:]
    
    if len(x_t) < 10:
        return {"kappa": 0.1, "theta": 0.0, "sigma": 0.001, "half_life": 7.0}
        
    slope, intercept, _, _, _ = stats.linregress(x_t, x_tp1)
    
    # Asiguram mean-reversion valid (0 < beta < 1)
    beta = float(np.clip(slope, 0.01, 0.9999))
    kappa = -np.log(beta) / dt
    theta = intercept / (1 - beta)
    
    # Reziduurile regresiei reprezinta zgomotul discret
    residuals = x_tp1 - (intercept + slope * x_t)
    sigma_discrete = float(np.std(residuals, ddof=2))
    
    # BUG FIX CRITIC: Conversia volatilitatii discrete in volatilitate continua
    sigma_continuous = sigma_discrete * np.sqrt((2 * kappa) / (1 - beta**2))
    
    half_life = np.log(2) / kappa if kappa > 0 else 999.0
    
    logger.debug(
        f"OU Calibrare: kappa={kappa:.4f} theta={theta:.6f} "
        f"sigma_c={sigma_continuous:.6f} half_life={half_life:.2f}min"
    )
    
    return {
        "kappa": float(kappa),
        "theta": float(theta),
        "sigma": float(sigma_continuous),
        "half_life": float(half_life),
    }

def ou_forecast(x_now: float, params: dict, delta_min: int) -> tuple[float, float]:
    """Prognozeaza media si deviatia standard viitoare dupa delta_min minute."""
    kappa = params["kappa"]
    theta = params["theta"]
    sigma = params["sigma"]
    
    decay = np.exp(-kappa * delta_min)
    mean_fwd = theta + (x_now - theta) * decay
    var_fwd = (sigma ** 2) / (2 * kappa) * (1 - np.exp(-2 * kappa * delta_min))
    
    return float(mean_fwd), float(np.sqrt(max(var_fwd, 1e-10)))

def compute_direction_probability(x_now: float, params: dict, delta_min: int, direction: str) -> float:
    """Calculeaza probabilitatea ca pretul sa se fi miscat favorabil la expirare."""
    mean_fwd, std_fwd = ou_forecast(x_now, params, delta_min)
    
    # Vrem sa aflam P(X_fwd > X_now) pentru CALL si P(X_fwd < X_now) pentru PUT
    if direction == "CALL":
        prob = 1 - stats.norm.cdf(0, loc=mean_fwd - x_now, scale=std_fwd)
    else:  # PUT
        prob = stats.norm.cdf(0, loc=mean_fwd - x_now, scale=std_fwd)
        
    return float(np.clip(prob, 0.0, 1.0))

def run_ou_grid_scoring(df: pd.DataFrame, expiry_options: list = None) -> dict | None:
    """Evalueaza oportunitatile de intrare bazate pe deviatii extreme (Z-Score)."""
    if expiry_options is None:
        expiry_options = EXPIRY_OPTIONS
        
    close = df["close"]
    window = min(OU_WINDOW_MIN, len(close) - 2)
    
    # Extragem componenta statica (reziduul fata de medie)
    ema = close.ewm(span=20, adjust=False).mean()
    resid = close - ema
    
    params = calibrate_ou(resid.iloc[-window:])
    x_now = float(resid.iloc[-1])
    
    # BUG FIX CRITIC: Calculul Z-Score folosind deviatia standard teoretica de echilibru
    eq_std = params["sigma"] / np.sqrt(2 * params["kappa"])
    z_now = x_now / (eq_std + 1e-10)

    if abs(z_now) < Z_SCORE_THRESHOLD:
        logger.debug(f"OU: Z={z_now:.3f} < threshold {Z_SCORE_THRESHOLD}. Skip.")
        return None

    direction = "CALL" if z_now < -Z_SCORE_THRESHOLD else "PUT"
    
    best = {
        "delta": None,
        "prob": 0.0,
        "direction": direction,
        "params": params,
        "zscore": float(z_now),
        "dist_atr": 0.0,
    }

    # Cautam cel mai profitabil timp de expirare
    for delta in expiry_options:
        prob = compute_direction_probability(x_now, params, delta, direction)
        if prob > best["prob"]:
            best["delta"] = delta
            best["prob"] = prob

    if best["prob"] < MIN_WIN_PROBABILITY:
        return None

    logger.info(
        f"OU Generat: {direction} delta={best['delta']}min "
        f"P={best['prob']:.3f} Z={z_now:.3f}"
    )
    
    return best
