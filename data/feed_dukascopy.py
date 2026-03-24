"""
data/feed_dukascopy.py — Date reale Dukascopy HTTP direct
Rescris profesional: Connection Pooling, Exponential Backoff, LZMA robust.
Cache 55s.
"""

import time
import struct
import lzma
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timezone, timedelta
from loguru import logger

# ══════════════════════════════════════════════════════
# CONFIGURĂRI & CACHE
# ══════════════════════════════════════════════════════
_cache: dict = {}
_last_fetch: dict = {}

CACHE_TTL = 55           # secunde
REQUEST_TIMEOUT = 15     # secunde maxime de asteptare per request
MAX_RETRIES = 3          # numar maxim de reincercari in caz de eroare

# ══════════════════════════════════════════════════════
# MAPARE SIMBOLURI
# ══════════════════════════════════════════════════════
SYMBOL_MAP_DUKA = {
    "EURUSD": "EURUSD", "GBPUSD": "GBPUSD", "USDJPY": "USDJPY",
    "USDCHF": "USDCHF", "AUDUSD": "AUDUSD", "USDCAD": "USDCAD",
    "NZDUSD": "NZDUSD", "EURGBP": "EURGBP", "EURJPY": "EURJPY",
    "EURAUD": "EURAUD", "EURCAD": "EURCAD", "EURNZD": "EURNZD",
    "EURCHF": "EURCHF", "GBPJPY": "GBPJPY", "GBPAUD": "GBPAUD",
    "GBPCAD": "GBPCAD", "GBPNZD": "GBPNZD", "GBPCHF": "GBPCHF",
    "AUDJPY": "AUDJPY", "AUDNZD": "AUDNZD", "AUDCAD": "AUDCAD",
    "NZDJPY": "NZDJPY", "CADJPY": "CADJPY",
}

JPY_PAIRS = {
    "USDJPY", "EURJPY", "GBPJPY", "AUDJPY",
    "CADJPY", "NZDJPY", "CHFJPY",
}

# ══════════════════════════════════════════════════════
# HTTP SESSION CU EXPONENTIAL BACKOFF
# ══════════════════════════════════════════════════════
def _create_robust_session() -> requests.Session:
    """Creeaza o sesiune HTTP care reincearca automat request-urile esuate."""
    session = requests.Session()
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=1,  # Va astepta 1s, 2s, 4s intre incercari
        status_forcelist=[408, 429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "Mozilla/5.0 (TradingBot/2.0)"})
    return session

# Initializam sesiunea global pentru a beneficia de Connection Pooling
_http_session = _create_robust_session()

# ══════════════════════════════════════════════════════
# FETCH DUKASCOPY HTTP
# ══════════════════════════════════════════════════════
def _build_url(symbol: str, dt: datetime) -> str:
    """Construieste URL-ul bi5 pentru o ora specifica."""
    return (
        f"https://datafeed.dukascopy.com/datafeed/{symbol}/"
        f"{dt.year}/{dt.month - 1:02d}/{dt.day:02d}/{dt.hour:02d}h_ticks.bi5"
    )

def _fetch_hour(symbol: str, dt: datetime) -> list:
    """
    Descarca si decodeaza tick-urile pentru o singura ora.
    Returneaza lista de tuple (timestamp_ms, price).
    """
    url = _build_url(symbol, dt)
    hour_ts_ms = int(dt.replace(minute=0, second=0, microsecond=0).timestamp() * 1000)
    divisor = 1000.0 if symbol in JPY_PAIRS else 100000.0

    try:
        resp = _http_session.get(url, timeout=REQUEST_TIMEOUT)

        if resp.status_code != 200 or len(resp.content) < 10:
            return []

        # Decompresie LZMA protejata
        try:
            raw = lzma.decompress(resp.content)
        except lzma.LZMAError as e:
            logger.error(f"{symbol} LZMA decompress failed pt {dt.strftime('%Y-%m-%d %H:00')}: {e}")
            return []

        ticks = []
        record_size = 20
        # Parsare structurata rapida
        for i in range(0, len(raw) - record_size + 1, record_size):
            chunk = raw[i:i + record_size]
            ms_offset, ask_raw, bid_raw = struct.unpack(">III", chunk[:12])
            price = bid_raw / divisor
            ticks.append((hour_ts_ms + ms_offset, price))

        return ticks

    except requests.exceptions.RequestException as e:
        logger.warning(f"{symbol} Conexiune esuata dupa {MAX_RETRIES} incercari: {e}")
        return []
    except Exception as e:
        logger.error(f"{symbol} Eroare neasteptata in _fetch_hour: {e}")
        return []

def _ticks_to_ohlc(ticks: list, n_candles: int) -> pd.DataFrame:
    """Converteste lista de tick-uri in lumânări M1 OHLC."""
    if not ticks:
        return pd.DataFrame()

    df = pd.DataFrame(ticks, columns=["ts_ms", "close"])
    df["ts"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True)
    df = df.set_index("ts").sort_index()

    ohlc = df["close"].resample("1min").ohlc().dropna()
    return ohlc.tail(n_candles)

# ══════════════════════════════════════════════════════
# FUNCTIA PRINCIPALA
# ══════════════════════════════════════════════════════
def get_ohlcv(symbol: str, n_candles: int = 120, **kwargs):
    """
    Returneaza DataFrame OHLC M1 pentru simbolul dat.
    **kwargs accepta orice parametru extra (ex: timeframe) fara sa dea eroare.

    Return: (df, latency_sec, is_real_data)
    """
    now = time.time()

    # Management Cache
    cached = _cache.get(symbol)
    if cached and now - _last_fetch.get(symbol, 0) < CACHE_TTL:
        df, fetched_at = cached
        age = now - fetched_at
        logger.debug(f"{symbol} din cache | Age={age:.0f}s | {len(df)} bare")
        return df.copy(), age, True

    duka_sym = SYMBOL_MAP_DUKA.get(symbol, symbol)
    now_utc  = datetime.now(timezone.utc)
    t0       = time.time()

    # Fetch ultimele 5 ore
    all_ticks = []
    for hours_back in range(4, -1, -1):
        target_dt = now_utc - timedelta(hours=hours_back)
        ticks     = _fetch_hour(duka_sym, target_dt)
        all_ticks.extend(ticks)

    latency = time.time() - t0
    df      = _ticks_to_ohlc(all_ticks, n_candles)

    # Validare rezultate finale
    if len(df) < 10:
        logger.warning(f"{symbol} Dukascopy: Date insuficiente ({len(df)} bare) obtinute. Reteaua ar putea fi inca blocata.")
        return pd.DataFrame(), latency, False

    # Salvare in cache
    _cache[symbol]       = (df, time.time())
    _last_fetch[symbol]  = now

    logger.debug(f"{symbol} actualizat direct | {len(df)} bare M1 | Latency={latency:.2f}s")
    return df.copy(), latency, True
