"""
engine/mtf_filter.py — Multi-Timeframe Filter M5
Resampleaza M1 -> M5 intern, fara parametru 'timeframe'.
"""
import pandas as pd
from loguru import logger


def get_m5_trend(symbol: str, df_m1: pd.DataFrame) -> dict:
    """
    Calculează trendul M5 din lumânările M1 existente.
    Returnează: {"trend": "up"/"down"/"flat", "aligned": bool}
    """
    try:
        if df_m1 is None or len(df_m1) < 10:
            logger.debug(f"[{symbol}] MTF: date M1 insuficiente pentru M5.")
            return {"trend": "flat", "aligned": True}

        # Resample M1 -> M5
        df_m5 = df_m1["close"].resample("5min").ohlc().dropna()

        if len(df_m5) < 5:
            logger.debug(f"[{symbol}] MTF: {len(df_m5)} bare M5 insuficiente.")
            return {"trend": "flat", "aligned": True}

        # EMA 5 și EMA 13 pe M5
        ema5  = df_m5["close"].ewm(span=5,  adjust=False).mean()
        ema13 = df_m5["close"].ewm(span=13, adjust=False).mean()

        last_ema5  = float(ema5.iloc[-1])
        last_ema13 = float(ema13.iloc[-1])

        if last_ema5 > last_ema13 * 1.0001:
            trend = "up"
        elif last_ema5 < last_ema13 * 0.9999:
            trend = "down"
        else:
            trend = "flat"

        logger.debug(f"[{symbol}] MTF M5: trend={trend} EMA5={last_ema5:.5f} EMA13={last_ema13:.5f}")
        return {"trend": trend, "aligned": True}

    except Exception as e:
        logger.debug(f"[{symbol}] MTF eroare: {e}")
        return {"trend": "flat", "aligned": True}


def is_mtf_aligned(symbol: str, direction: str, df_m1: pd.DataFrame) -> bool:
    """
    Verifică dacă trendul M5 este aliniat cu direcția semnalului.
    CALL → trend M5 up sau flat
    PUT  → trend M5 down sau flat
    """
    mtf = get_m5_trend(symbol, df_m1)
    trend = mtf["trend"]

    if direction == "CALL":
        aligned = trend in ("up", "flat")
    else:
        aligned = trend in ("down", "flat")

    if not aligned:
        logger.debug(f"[{symbol}] MTF nealiniat: {direction} vs M5={trend}")

    return aligned
