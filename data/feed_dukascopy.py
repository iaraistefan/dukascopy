import time
import os
import requests
import pandas as pd
from loguru import logger

API_KEY  = os.getenv("TWELVEDATA_API_KEY", "demo")
BASE_URL = "https://api.twelvedata.com/time_series"

# Rate limiter: max 8 req/min -> 1 req la 8 secunde
_last_call_time = 0.0
RATE_LIMIT_INTERVAL = 8.0  # secunde intre cereri

SYMBOL_MAP = {
    "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD", "USDJPY": "USD/JPY",
    "USDCHF": "USD/CHF", "AUDUSD": "AUD/USD", "USDCAD": "USD/CAD",
    "NZDUSD": "NZD/USD", "EURGBP": "EUR/GBP", "EURJPY": "EUR/JPY",
    "EURAUD": "EUR/AUD", "EURCAD": "EUR/CAD", "EURNZD": "EUR/NZD",
    "EURCHF": "EUR/CHF", "GBPJPY": "GBP/JPY", "GBPAUD": "GBP/AUD",
    "GBPCAD": "GBP/CAD", "GBPNZD": "GBP/NZD", "GBPCHF": "GBP/CHF",
    "AUDJPY": "AUD/JPY", "AUDNZD": "AUD/NZD", "AUDCAD": "AUD/CAD",
    "NZDJPY": "NZD/JPY", "CADJPY": "CAD/JPY",
}


def _rate_limit():
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < RATE_LIMIT_INTERVAL:
        time.sleep(RATE_LIMIT_INTERVAL - elapsed)
    _last_call_time = time.time()


def get_ohlcv(symbol: str, n_candles: int = 120):
    _rate_limit()

    instrument = SYMBOL_MAP.get(symbol, symbol)
    params = {
        "symbol":     instrument,
        "interval":   "1min",
        "outputsize": min(n_candles, 120),
        "apikey":     API_KEY,
        "format":     "JSON",
    }

    t0 = time.time()
    try:
        resp = requests.get(BASE_URL, params=params, timeout=8)
        latency = time.time() - t0

        if resp.status_code != 200:
            logger.warning(f"{symbol} HTTP {resp.status_code}. SKIP.")
            return pd.DataFrame(), latency, False

        data = resp.json()

        if data.get("status") == "error":
            logger.warning(f"{symbol} TwelveData: {data.get('message','?')}. SKIP.")
            return pd.DataFrame(), latency, False

        values = data.get("values", [])
        if len(values) < 10:
            logger.warning(f"{symbol} date insuficiente ({len(values)} bare). SKIP.")
            return pd.DataFrame(), latency, False

        df = pd.DataFrame(values)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime").sort_index()
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df[["open", "high", "low", "close"]].dropna()

        logger.debug(f"{symbol} {len(df)} lumânări M1 | Latency={latency:.2f}s")
        return df, latency, True

    except requests.exceptions.Timeout:
        latency = time.time() - t0
        logger.warning(f"{symbol} Timeout {latency:.1f}s. SKIP.")
        return pd.DataFrame(), latency, False
    except Exception as e:
        latency = time.time() - t0
        logger.error(f"{symbol} Eroare: {e}")
        return pd.DataFrame(), latency, False
