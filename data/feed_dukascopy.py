import time
import os
import requests
import pandas as pd
from loguru import logger

API_KEY  = os.getenv("FINNHUB_API_KEY", "")
BASE_URL = "https://finnhub.io/api/v1/forex/candle"

SYMBOL_MAP = {
    "EURUSD": "OANDA:EUR_USD", "GBPUSD": "OANDA:GBP_USD",
    "USDJPY": "OANDA:USD_JPY", "USDCHF": "OANDA:USD_CHF",
    "AUDUSD": "OANDA:AUD_USD", "USDCAD": "OANDA:USD_CAD",
    "NZDUSD": "OANDA:NZD_USD", "EURGBP": "OANDA:EUR_GBP",
    "EURJPY": "OANDA:EUR_JPY", "EURAUD": "OANDA:EUR_AUD",
    "EURCAD": "OANDA:EUR_CAD", "EURNZD": "OANDA:EUR_NZD",
    "EURCHF": "OANDA:EUR_CHF", "GBPJPY": "OANDA:GBP_JPY",
    "GBPAUD": "OANDA:GBP_AUD", "GBPCAD": "OANDA:GBP_CAD",
    "GBPNZD": "OANDA:GBP_NZD", "GBPCHF": "OANDA:GBP_CHF",
    "AUDJPY": "OANDA:AUD_JPY", "AUDNZD": "OANDA:AUD_NZD",
    "AUDCAD": "OANDA:AUD_CAD", "NZDJPY": "OANDA:NZD_JPY",
    "CADJPY": "OANDA:CAD_JPY",
}


def get_ohlcv(symbol: str, n_candles: int = 120):
    finnhub_symbol = SYMBOL_MAP.get(symbol, f"OANDA:{symbol[:3]}_{symbol[3:]}")

    # Interval: ultimele n_candles minute
    t_to   = int(time.time())
    t_from = t_to - (n_candles * 60)

    params = {
        "symbol":     finnhub_symbol,
        "resolution": "1",         # 1 minut
        "from":       t_from,
        "to":         t_to,
        "token":      API_KEY,
    }

    t0 = time.time()
    try:
        resp = requests.get(BASE_URL, params=params, timeout=8)
        latency = time.time() - t0

        if resp.status_code != 200:
            logger.warning(f"{symbol} Finnhub HTTP {resp.status_code}. SKIP.")
            return pd.DataFrame(), latency, False

        data = resp.json()

        if data.get("s") == "no_data" or not data.get("c"):
            logger.warning(f"{symbol} Finnhub: no_data. SKIP.")
            return pd.DataFrame(), latency, False

        if data.get("s") == "error":
            logger.warning(f"{symbol} Finnhub eroare: {data}. SKIP.")
            return pd.DataFrame(), latency, False

        df = pd.DataFrame({
            "open":   data["o"],
            "high":   data["h"],
            "low":    data["l"],
            "close":  data["c"],
            "volume": data.get("v", [0] * len(data["c"])),
        }, index=pd.to_datetime(data["t"], unit="s"))

        df = df.sort_index().dropna()

        if len(df) < 10:
            logger.warning(f"{symbol} Finnhub: {len(df)} bare insuficiente. SKIP.")
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
