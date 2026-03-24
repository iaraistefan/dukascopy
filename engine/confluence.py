"""
engine/confluence.py — RSI + Stability Score
Optimizat: Vectorizare NumPy pentru viteza maxima de calcul.
"""
import numpy as np
import pandas as pd
from loguru import logger

from config import (
    RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    STABILITY_EMA_PERIOD, STABILITY_LOOKBACK,
    CONFLUENCE_RSI_WEIGHT, CONFLUENCE_STABILITY_WEIGHT
)

def compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Calculeaza Relative Strength Index (RSI) folosind Wilder's Smoothing."""
    delta = close.diff()
    
    # Vectorizare rapida in loc de .where()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    
    # Folosim exponential moving average specific Wilder
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    return rsi.rename("rsi")

def compute_stability_score(df: pd.DataFrame) -> float:
    """
    Masoara cat de uniform urmareste pretul un trend (EMA).
    Scor 1.0 = trend extrem de stabil. Scor 0.0 = volatilitate haotica.
    """
    close = df["close"]
    ema = close.ewm(span=STABILITY_EMA_PERIOD, adjust=False).mean()
    n = min(STABILITY_LOOKBACK, len(close))
    
    # Extragem array-urile in format NumPy pentru viteza maxima
    rc = close.iloc[-n:].values
    re = ema.iloc[-n:].values
    
    # Calcul optimizat True Range (fara pandas.concat)
    h = df["high"]
    l = df["low"]
    c_prev = df["close"].shift(1)
    
    tr = np.maximum(h - l, np.maximum((h - c_prev).abs(), (l - c_prev).abs()))
    atr = float(tr.rolling(14).mean().iloc[-1])
    
    if atr <= 0 or np.isnan(atr):
        return 0.5
        
    # Normalizam deviatia medie a pretului fata de EMA folosind ATR
    avg_deviation = np.sum(np.abs(rc - re)) / n
    stability = 1.0 - (avg_deviation / atr)
    
    return float(np.clip(stability, 0.0, 1.0))

def compute_rsi_confirmation(df: pd.DataFrame, direction: str) -> float:
    """Interpoleaza liniar scorul RSI bazat pe zonele de overbought/oversold."""
    rsi_series = compute_rsi(df["close"])
    rsi = float(rsi_series.iloc[-1])
    
    if direction == "CALL":
        if rsi <= RSI_OVERSOLD:
            return 1.0
        if rsi <= 50.0:
            return 0.5 + 0.5 * ((50.0 - rsi) / (50.0 - RSI_OVERSOLD))
        return max(0.0, 0.5 - 0.5 * ((rsi - 50.0) / (RSI_OVERBOUGHT - 50.0)))
    else:  # PUT
        if rsi >= RSI_OVERBOUGHT:
            return 1.0
        if rsi >= 50.0:
            return 0.5 + 0.5 * ((rsi - 50.0) / (RSI_OVERBOUGHT - 50.0))
        return max(0.0, 0.5 - 0.5 * ((50.0 - rsi) / (50.0 - RSI_OVERSOLD)))

def compute_confluence_score(df: pd.DataFrame, direction: str) -> tuple[float, float, float]:
    """Combina si pondereaza stabilitatea si RSI-ul intr-un scor final."""
    stab = compute_stability_score(df)
    rsi_score = compute_rsi_confirmation(df, direction)
    
    conf = (stab * CONFLUENCE_STABILITY_WEIGHT) + (rsi_score * CONFLUENCE_RSI_WEIGHT)
    
    logger.debug(f"Confluenta: Stab={stab:.3f} RSI={rsi_score:.3f} -> Total={conf:.3f}")
    
    return float(conf), float(stab), float(rsi_score)
