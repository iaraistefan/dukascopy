import time
import requests
import pandas as pd
from loguru import logger

DUKA_URL = "https://freeserv.dukascopy.com/2.0/index.php"

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/122.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.dukascopy.com/trading-tools/widgets/charts/online_chart",
    "Origin":          "https://www.dukascopy.com",
    "Connection":      "keep-alive",
}

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

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def get_ohlcv(symbol: str, n_candles: int = 120):
    instrument = SYMBOL_MAP.get(symbol, symbol)
    params = {
        "path":           "chart/json",
        "instrument":     instrument,
        "offer_side":     "B",
        "interval":       "1MIN",
        "splits":         "true",
        "time_direction": "P",
        "timestamp":      int(time.time() * 1000),
        "count":          n_candles,
    }

    t0 = time.time()
    try:
        resp = SESSION.get(DUKA_URL, params=params, timeout=8)
        latency = time.time() - t0

        if resp.status_code == 403:
            logger.warning(f"{symbol} HTTP 403 (IP blocat). SKIP.")
            return pd.DataFrame(), latency, False

        if resp.status_code != 200 or not resp.text.strip():
            logger.warning(f"{symbol} HTTP {resp.status_code}. SKIP.")
            return pd.DataFrame(), latency, False

        data = resp.json()
        if not data or len(data) < 10:
            logger.warning(f"{symbol} Date insuficiente ({len(data)} bare). SKIP.")
            return pd.DataFrame(), latency, False

        df = pd.DataFrame(
            data,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna()

        if latency > 5.0:
            logger.warning(f"{symbol} Latency={latency:.1f}s >5.0s. SKIP.")
            return pd.DataFrame(), latency, False

        logger.debug(f"{symbol} {len(df)} lumânări M1 | Latency={latency:.2f}s")
        return df, latency, True

    except requests.exceptions.Timeout:
        latency = time.time() - t0
        logger.warning(f"{symbol} Timeout dupa {latency:.1f}s. SKIP.")
        return pd.DataFrame(), latency, False
    except Exception as e:
        latency = time.time() - t0
        logger.error(f"{symbol} Eroare fetch: {e}")
        return pd.DataFrame(), latency, False
