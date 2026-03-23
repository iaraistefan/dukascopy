import time, struct, zlib, requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from loguru import logger

_cache: dict = {}
_last_fetch: dict = {}
CACHE_TTL = 55

def _fetch_dukascopy_direct(symbol: str, n_candles: int = 120) -> pd.DataFrame:
    """Fetch direct din Dukascopy HTTP fara librarie wrapper."""
    now_utc = datetime.now(timezone.utc)
    hour_ts = int(now_utc.replace(minute=0, second=0, microsecond=0).timestamp()) * 1000

    url = (
        f"https://datafeed.dukascopy.com/datafeed/"
        f"{symbol.upper()}/{now_utc.year}/"
        f"{now_utc.month - 1:02d}/{now_utc.day:02d}/"
        f"{now_utc.hour:02d}h_ticks.bi5"
    )

    try:
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200 or len(resp.content) < 10:
            return pd.DataFrame()

        raw = zlib.decompress(resp.content, -zlib.MAX_WBITS)
        ticks = []
        for i in range(0, len(raw) - 19, 20):
            chunk = raw[i:i+20]
            if len(chunk) < 20:
                break
            ms, ask, bid, avol, bvol = struct.unpack(">IIIff", chunk)
            ts = hour_ts + ms
            price = bid / 100000.0
            ticks.append((ts, price))

        if not ticks:
            return pd.DataFrame()

        df_ticks = pd.DataFrame(ticks, columns=["ts", "close"])
        df_ticks["ts"] = pd.to_datetime(df_ticks["ts"], unit="ms", utc=True)
        df_ticks = df_ticks.set_index("ts")

        # Resample ticks -> OHLC M1
        ohlc = df_ticks["close"].resample("1min").ohlc().dropna()
        return ohlc.tail(n_candles)

    except Exception as e:
        logger.warning(f"{symbol} Dukascopy direct: {e}")
        return pd.DataFrame()


def get_ohlcv(symbol: str, n_candles: int = 120):
    now = time.time()
    if now - _last_fetch.get(symbol, 0) < CACHE_TTL and symbol in _cache:
        df, fetched_at = _cache[symbol]
        age = now - fetched_at
        logger.debug(f"{symbol} din cache | Age={age:.0f}s | {len(df)} bare")
        return df.copy(), age, True

    t0 = time.time()
    df = _fetch_dukascopy_direct(symbol, n_candles)
    latency = time.time() - t0

    if len(df) < 10:
        # Fallback: ora precedenta
        logger.warning(f"{symbol} ora curenta goala, incerc ora precedenta...")
        df = _fetch_dukascopy_prev_hour(symbol, n_candles)

    if len(df) < 10:
        logger.warning(f"{symbol} Dukascopy: date insuficiente. SKIP.")
        return pd.DataFrame(), latency, False

    _cache[symbol] = (df, time.time())
    _last_fetch[symbol] = now
    logger.debug(f"{symbol} {len(df)} lumânări M1 | Latency={latency:.2f}s")
    return df.copy(), latency, True


def _fetch_dukascopy_prev_hour(symbol: str, n_candles: int) -> pd.DataFrame:
    """Fallback: ora anterioara."""
    from datetime import timedelta
    now_utc = datetime.now(timezone.utc) - timedelta(hours=1)
    hour_ts = int(now_utc.replace(minute=0, second=0, microsecond=0).timestamp()) * 1000
    url = (
        f"https://datafeed.dukascopy.com/datafeed/"
        f"{symbol.upper()}/{now_utc.year}/"
        f"{now_utc.month - 1:02d}/{now_utc.day:02d}/"
        f"{now_utc.hour:02d}h_ticks.bi5"
    )
    try:
        resp = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200 or len(resp.content) < 10:
            return pd.DataFrame()
        raw = zlib.decompress(resp.content, -zlib.MAX_WBITS)
        ticks = []
        for i in range(0, len(raw) - 19, 20):
            chunk = raw[i:i+20]
            if len(chunk) < 20:
                break
            ms, ask, bid, avol, bvol = struct.unpack(">IIIff", chunk)
            price = bid / 100000.0
            ticks.append((hour_ts + ms, price))
        if not ticks:
            return pd.DataFrame()
        df_ticks = pd.DataFrame(ticks, columns=["ts", "close"])
        df_ticks["ts"] = pd.to_datetime(df_ticks["ts"], unit="ms", utc=True)
        ohlc = df_ticks.set_index("ts")["close"].resample("1min").ohlc().dropna()
        return ohlc.tail(n_candles)
    except Exception:
        return pd.DataFrame()
