"""
engine/fractal_sr.py — Niveluri S/R fractale + ATR
Corectat: Selectia celor mai apropiate niveluri (nu cele mai inalte) + Optimizare ATR.
"""
import numpy as np
import pandas as pd
from loguru import logger

from config import FRACTAL_N, FRACTAL_PROXIMITY, MAX_SR_LEVELS, ATR_PERIOD

def detect_fractals(df: pd.DataFrame, n: int = FRACTAL_N) -> tuple[np.ndarray, np.ndarray]:
    """Gaseste pivotii (highs/lows) care formeaza fractali pe o fereastra n."""
    highs = df["high"].values
    lows = df["low"].values
    total = len(df)
    
    # Un fractal up (rezistenta) are 'n' lumanari mai joase la stanga si la dreapta
    res_idx = [i for i in range(n, total - n)
               if all(highs[i] > highs[i - j] for j in range(1, n + 1))
               and all(highs[i] > highs[i + j] for j in range(1, n + 1))]
               
    # Un fractal down (suport) are 'n' lumanari mai inalte la stanga si la dreapta
    sup_idx = [i for i in range(n, total - n)
               if all(lows[i] < lows[i - j] for j in range(1, n + 1))
               and all(lows[i] < lows[i + j] for j in range(1, n + 1))]
               
    # Extragem nivelurile unice (fara a le trunchia inca)
    res_levels = np.unique(highs[res_idx])
    sup_levels = np.unique(lows[sup_idx])
    
    return res_levels, sup_levels

def cluster_levels(levels: np.ndarray, tolerance: float) -> np.ndarray:
    """Combina nivelurile foarte apropiate (zone de S/R) intr-un singur nivel mediu."""
    if len(levels) == 0:
        return levels
        
    sl = np.sort(levels)
    cl = [sl[0]]
    
    for lv in sl[1:]:
        # Daca nivelul e in interiorul tolerantei fata de clusterul actual, facem media
        if lv - cl[-1] > tolerance:
            cl.append(lv)
        else:
            cl[-1] = (cl[-1] + lv) / 2.0
            
    return np.array(cl)

def compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """Calculeaza Average True Range rapid, prin operatii vectorizate."""
    h = df["high"]
    l = df["low"]
    prev_c = df["close"].shift(1)
    
    # Vectorizare rapida, fara alocari greoaie in memorie (pd.concat)
    tr = np.maximum(h - l, np.maximum((h - prev_c).abs(), (l - prev_c).abs()))
    
    return tr.rolling(period).mean().rename("atr")

def get_sr_levels(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Returneaza cele mai relevante niveluri de rezistenta si suport."""
    atr_series = compute_atr(df)
    atr_c = float(atr_series.iloc[-1])
    
    res, sup = detect_fractals(df)
    
    # Clusterizam la o toleranta calculata dinamic din ATR
    res = cluster_levels(res, atr_c * FRACTAL_PROXIMITY)
    sup = cluster_levels(sup, atr_c * FRACTAL_PROXIMITY)
    
    p = float(df["close"].iloc[-1])
    max_dist = atr_c * 10
    
    # 1. Filtram doar rezistentele deasupra pretului si suporturile dedesubt (in limita a 10 ATR)
    res = res[(res > p) & (res - p < max_dist)]
    sup = sup[(sup < p) & (p - sup < max_dist)]
    
    # BUG FIX: 2. Sortam in functie de apropierea fata de pretul curent si luam MAX_SR_LEVELS
    # Rezistentele crescator (cele mai apropiate primele)
    res = np.sort(res)[:MAX_SR_LEVELS]
    
    # Suporturile descrescator (cele mai apropiate primele, sub pret)
    sup = np.sort(sup)[::-1][:MAX_SR_LEVELS]
    
    return res, sup

def nearest_sr_distance(price: float, resistances: np.ndarray, supports: np.ndarray) -> tuple[float, float]:
    """Calculeaza distanta bruta pana la primul S/R disponibil."""
    du = float(np.min(resistances - price)) if len(resistances) > 0 else float("inf")
    dd = float(np.min(price - supports)) if len(supports) > 0 else float("inf")
    return du, dd
