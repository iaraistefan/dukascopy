"""
engine/mtf_filter.py — Filtru Multi-Timeframe M5 (EMA 9/21)
"""
from loguru import logger
from config import MTF_FILTER_ENABLED, MTF_EMA_FAST, MTF_EMA_SLOW

def get_m5_trend(symbol: str) -> str:
    try:
        from data.feed_dukascopy import get_ohlcv
        df, _, _ = get_ohlcv(symbol, n_candles=50, timeframe="M5")
        if len(df)<MTF_EMA_SLOW+5: return "FLAT"
        close = df["close"]
        ef = float(close.ewm(span=MTF_EMA_FAST, adjust=False).mean().iloc[-1])
        es = float(close.ewm(span=MTF_EMA_SLOW, adjust=False).mean().iloc[-1])
        if ef>es*1.0001: return "BULL"
        if ef<es*0.9999: return "BEAR"
        return "FLAT"
    except Exception as e:
        logger.debug(f"[{symbol}] MTF: {e}")
        return "FLAT"

def is_mtf_aligned(symbol: str, direction: str) -> tuple:
    if not MTF_FILTER_ENABLED: return True, "disabled"
    trend = get_m5_trend(symbol)
    if direction=="CALL" and trend=="BEAR": return False, "CALL contra BEAR M5"
    if direction=="PUT"  and trend=="BULL": return False, "PUT contra BULL M5"
    return True, f"MTF_OK={trend}"
