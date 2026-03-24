"""
data/feed_dukascopy.py — Date reale Dukascopy HTTP direct
Fara librarie wrapper. LZMA decompress. Cache 55s.
"""

import time
import struct
import lzma
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from loguru import logger

# ══════════════════════════════════════════════════════
# CACHE IN-MEMORY
# ══════════════════════════════════════════════════════
_cache: dict = {}
_last_fetch: dict = {}
CACHE_TTL = 55  # secunde

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

# Perechi JPY: impartire la 1000 in loc de 100000
JPY_PAIRS = {
    "USDJPY", "EURJPY", "GBPJPY", "AUDJPY",
    "CADJPY", "NZDJPY", "CHFJPY",
}


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
        resp = requests.get(
            url,
            timeout=6,
            headers={"User-Agent": "Mozilla/5.0"},
        )

        if resp.status_code != 200 or len(resp.content) < 10:
            return []

        # Dukascopy foloseste LZMA (nu zlib!)
        raw = lzma.decompress(resp.content)

        ticks = []
        record_size = 20
        for i in range(0, len(raw) - record_size + 1, record_size):
            chunk = raw[i:i + record_size]
            ms_offset, ask_raw, bid_raw = struct.unpack(">III", chunk[:12])
            price = bid_raw / divisor
            ticks.append((hour_ts_ms + ms_offset, price))

        return ticks

    except lzma.LZMAError:
        return []
    except Exception as e:
        logger.warning(f"{symbol} _fetch_hour eroare: {e}")
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
    **kwargs accepta orice parametru extra (ex: timeframe)
    fara sa dea eroare.

    Return: (df, latency_sec, is_real_data)
    """
    now = time.time()

    # Returneaza din cache daca e valid
    cached = _cache.get(symbol)
    if cached and now - _last_fetch.get(symbol, 0) < CACHE_TTL:
        df, fetched_at = cached
        age = now - fetched_at
        logger.debug(f"{symbol} din cache | Age={age:.0f}s | {len(df)} bare")
        return df.copy(), age, True

    duka_sym = SYMBOL_MAP_DUKA.get(symbol, symbol)
    now_utc  = datetime.now(timezone.utc)
    t0       = time.time()

    # Fetch ultimele 5 ore pentru a acoperi orice scenariu
    # (inclusiv start de sesiune / ora noua cu putine ticks)
    all_ticks = []
    for hours_back in range(4, -1, -1):
        target_dt = now_utc - timedelta(hours=hours_back)
        ticks     = _fetch_hour(duka_sym, target_dt)
        all_ticks.extend(ticks)

    latency = time.time() - t0
    df      = _ticks_to_ohlc(all_ticks, n_candles)

    if len(df) < 10:
        logger.warning(f"{symbol} Dukascopy: {len(df)} bare insuficiente. SKIP.")
        return pd.DataFrame(), latency, False

    # Salveaza in cache
    _cache[symbol]       = (df, time.time())
    _last_fetch[symbol]  = now

    logger.debug(f"{symbol} {len(df)} lumânări M1 | Latency={latency:.2f}s")
    return df.copy(), latency, True
