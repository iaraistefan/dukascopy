import time
import os
import requests
import pandas as pd
from loguru import logger

# Ia cheia din .env: TWELVEDATA_API_KEY=cheia_ta
API_KEY  = os.getenv("TWELVEDATA_API_KEY", "demo")
BASE_URL = "https://api.twelvedata.com/time_series"

# Format Twelve Data pentru Forex
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


def get_ohlcv(symbol: str, n_candles: int = 120):
    instrument = SYMBOL_MAP.get(symbol, symbol)
    params = {
        "symbol":    instrument,
        "interval":  "1min",
        "outputsize": min(n_candles, 120),
        "apikey":    API_KEY,
        "format":    "JSON",
    }

    t0 = time.time()
    try:
        resp = requests.get(BASE_URL, params=params, timeout=8)
        latency = time.time() - t0

        if resp.status_code != 200:
            logger.warning(f"{symbol} TwelveData HTTP {resp.status_code}. SKIP.")
            return pd.DataFrame(), latency, False

        data = resp.json()

        # Rate limit atins
        if data.get("status") == "error":
            msg = data.get("message", "unknown")
            logger.warning(f"{symbol} TwelveData eroare: {msg}. SKIP.")
            return pd.DataFrame(), latency, False

        values = data.get("values", [])
        if len(values) < 10:
            logger.warning(f"{symbol} TwelveData: {len(values)} bare. SKIP.")
            return pd.DataFrame(), latency, False

        df = pd.DataFrame(values)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df[["open", "high", "low", "close"]].dropna()
        df = df.sort_index()  # ordine cronologica

        if latency > 5.0:
            logger.warning(f"{symbol} Latency={latency:.1f}s >5.0s. SKIP.")
            return pd.DataFrame(), latency, False

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
