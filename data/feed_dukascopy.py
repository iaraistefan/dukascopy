import time, os, requests, pandas as pd
from loguru import logger

API_KEY  = os.getenv("TWELVEDATA_API_KEY", "demo")
BASE_URL = "https://api.twelvedata.com/time_series"

SYMBOL_MAP = {
    "EURUSD":"EUR/USD","GBPUSD":"GBP/USD","USDJPY":"USD/JPY","USDCHF":"USD/CHF",
    "AUDUSD":"AUD/USD","USDCAD":"USD/CAD","NZDUSD":"NZD/USD","EURGBP":"EUR/GBP",
    "EURJPY":"EUR/JPY","EURAUD":"EUR/AUD","EURCAD":"EUR/CAD","EURNZD":"EUR/NZD",
    "EURCHF":"EUR/CHF","GBPJPY":"GBP/JPY","GBPAUD":"GBP/AUD","GBPCAD":"GBP/CAD",
    "GBPNZD":"GBP/NZD","GBPCHF":"GBP/CHF",
}

BATCHES = [
    ["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","USDCAD"],
    ["NZDUSD","EURGBP","EURJPY","EURAUD","EURCAD","EURNZD"],
    ["EURCHF","GBPJPY","GBPAUD","GBPCAD","GBPNZD","GBPCHF"],
]

_cache: dict = {}
_last_batch_time: float = 0.0
CACHE_TTL = 50  # secunde

def _fetch_all_batches(n_candles: int = 120):
    global _last_batch_time
    if time.time() - _last_batch_time < CACHE_TTL:
        return

    for i, batch in enumerate(BATCHES):
        if i > 0:
            time.sleep(2)  # pauza intre batch-uri

        symbols_td = ",".join(SYMBOL_MAP[s] for s in batch)
        params = {
            "symbol": symbols_td,
            "interval": "1min",
            "outputsize": min(n_candles, 120),
            "apikey": API_KEY,
            "format": "JSON",
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=12)
            if resp.status_code != 200:
                logger.warning(f"Batch {i+1} HTTP {resp.status_code}. SKIP.")
                continue

            data = resp.json()
            if data.get("status") == "error":
                logger.warning(f"Batch {i+1} eroare API: {data.get('message','?')}")
                continue

            for symbol in batch:
                td_key = SYMBOL_MAP[symbol]
                sym_data = data.get(td_key, {})
                if not sym_data or sym_data.get("status") == "error":
                    continue
                values = sym_data.get("values", [])
                if len(values) < 10:
                    continue
                df = pd.DataFrame(values)
                df["datetime"] = pd.to_datetime(df["datetime"])
                df = df.set_index("datetime").sort_index()
                for col in ["open","high","low","close"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                df = df[["open","high","low","close"]].dropna()
                _cache[symbol] = (df, time.time())
                logger.debug(f"{symbol} {len(df)} lumânări M1 din batch {i+1}")

        except Exception as e:
            logger.error(f"Batch {i+1} eroare: {e}")

    _last_batch_time = time.time()

def get_ohlcv(symbol: str, n_candles: int = 120):
    _fetch_all_batches(n_candles)
    cached = _cache.get(symbol)
    if cached is None:
        logger.warning(f"{symbol} nu e in cache. SKIP.")
        return pd.DataFrame(), 0.0, False
    df, fetched_at = cached
    latency = time.time() - fetched_at
    if len(df) < 10:
        return pd.DataFrame(), latency, False
    logger.debug(f"{symbol} din cache | Varsta={latency:.0f}s | {len(df)} bare")
    return df.iloc[-n_candles:].copy(), latency, True
