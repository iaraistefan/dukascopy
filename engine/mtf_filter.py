import pandas as pd
from loguru import logger


def get_m5_trend(symbol, df_m1=None):
    try:
        if df_m1 is None or len(df_m1) < 10:
            return {"trend": "flat", "aligned": True}
        df_m5 = df_m1["close"].resample("5min").ohlc().dropna()
        if len(df_m5) < 5:
            return {"trend": "flat", "aligned": True}
        ema5 = df_m5["close"].ewm(span=5, adjust=False).mean()
        ema13 = df_m5["close"].ewm(span=13, adjust=False).mean()
        last5 = float(ema5.iloc[-1])
        last13 = float(ema13.iloc[-1])
        if last5 > last13 * 1.0001:
            trend = "up"
        elif last5 < last13 * 0.9999:
            trend = "down"
        else:
            trend = "flat"
        logger.debug(symbol + " MTF M5: " + trend)
        return {"trend": trend, "aligned": True}
    except Exception as e:
        logger.debug(symbol + " MTF eroare: " + str(e))
        return {"trend": "flat", "aligned": True}


def is_mtf_aligned(symbol, direction, df_m1=None):
    mtf = get_m5_trend(symbol, df_m1)
    trend = mtf["trend"]
    if direction == "CALL":
        aligned = trend in ("up", "flat")
    else:
        aligned = trend in ("down", "flat")
    if aligned:
        reason = "MTF OK: " + trend + " aligns " + direction
    else:
        reason = "MTF FAIL: " + trend + " vs " + direction
    logger.debug(symbol + " " + reason)
    return aligned, reason
