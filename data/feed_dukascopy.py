"""
data/feed_dukascopy.py — Feed date Dukascopy M1/M5
"""
import time
import pandas as pd
import numpy as np
from loguru import logger
from config import MAX_FETCH_LATENCY_SEC

try:
    from dukascopy import Dukascopy
    _DC = Dukascopy()
    _HAS_DC = True
except Exception:
    _DC = None
    _HAS_DC = False
    logger.warning("dukascopy-python indisponibil. Date simulate.")

_TIMEFRAME_MAP = {"M1":"m1","M5":"m5","M15":"m15","H1":"h1"}

def _make_mock(symbol: str, n: int) -> pd.DataFrame:
    rng   = np.random.default_rng(hash(symbol) % (2**32))
    price = 1.1000 if "EUR" in symbol else (150.0 if "JPY" in symbol else 1.2500)
    ret   = rng.normal(0, 0.0003, n)
    close = price * np.exp(np.cumsum(ret))
    atr   = np.abs(rng.normal(0, 0.0005, n)) + 0.0002
    return pd.DataFrame({
        "open":close*(1-atr/2),"high":close+atr,
        "low":close-atr,"close":close,
        "volume":rng.integers(100,2000,n).astype(float),
        "spread":atr*0.1,
    })

def get_ohlcv(symbol: str, n_candles: int = 120, timeframe: str = "M1") -> tuple:
    t0 = time.time()
    if not _HAS_DC:
        return _make_mock(symbol, n_candles), 0.0, False
    try:
        tf  = _TIMEFRAME_MAP.get(timeframe.upper(), "m1")
        raw = _DC.get_candles(instrument=symbol, offer_side="BID", interval=tf, n_last=n_candles)
        latency = time.time() - t0
        if latency > MAX_FETCH_LATENCY_SEC:
            logger.warning(f"[{symbol}] Latenta {latency:.2f}s.")
            return pd.DataFrame(), latency, False
        df = pd.DataFrame(raw)
        df.columns = [c.lower() for c in df.columns]
        col_map = {"askclose":"close","askhigh":"high","asklow":"low","askopen":"open",
                   "bidclose":"close","bidhigh":"high","bidlow":"low","bidopen":"open"}
        df = df.rename(columns=col_map)
        for col in ["open","high","low","close","volume"]:
            if col not in df.columns:
                df[col] = df.get("close", 1.0)
        if "spread" not in df.columns:
            df["spread"] = (df["high"] - df["low"]) * 0.15
        return df.dropna(subset=["close"]).reset_index(drop=True), latency, True
    except Exception as e:
        logger.error(f"[{symbol}] Feed error: {e}")
        return pd.DataFrame(), time.time()-t0, False
