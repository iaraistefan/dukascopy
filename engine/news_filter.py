"""
engine/news_filter.py — Filtru stiri ForexFactory HIGH impact
"""
import time, requests
from datetime import datetime, timezone, timedelta
from loguru import logger
from config import NEWS_FILTER_ENABLED, NEWS_BUFFER_BEFORE_MIN, NEWS_BUFFER_AFTER_MIN

_CACHE, _CACHE_TS = [], 0.0
_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_PAIRS = {
    "EURUSD":["EUR","USD"],"GBPUSD":["GBP","USD"],"USDJPY":["USD","JPY"],
    "USDCHF":["USD","CHF"],"AUDUSD":["AUD","USD"],"USDCAD":["USD","CAD"],
    "EURJPY":["EUR","JPY"],"GBPJPY":["GBP","JPY"],"NZDUSD":["NZD","USD"],
    "EURGBP":["EUR","GBP"],"EURAUD":["EUR","AUD"],"GBPAUD":["GBP","AUD"],
    "EURCAD":["EUR","CAD"],"GBPCAD":["GBP","CAD"],"GBPCHF":["GBP","CHF"],
    "GBPNZD":["GBP","NZD"],"AUDJPY":["AUD","JPY"],"CADJPY":["CAD","JPY"],
}

def _fetch() -> list:
    global _CACHE, _CACHE_TS
    if time.time()-_CACHE_TS<3600 and _CACHE: return _CACHE
    try:
        r = requests.get(_URL, timeout=5)
        if r.status_code==200:
            _CACHE    = [n for n in r.json() if n.get("impact","").lower()=="high"]
            _CACHE_TS = time.time()
    except Exception as e:
        logger.warning(f"News fetch: {e}")
    return _CACHE

def is_news_safe(symbol: str) -> tuple:
    if not NEWS_FILTER_ENABLED: return True, "disabled"
    currencies = _PAIRS.get(symbol.upper(),[])
    if not currencies: return True, "unknown"
    now = datetime.now(timezone.utc)
    for news in _fetch():
        if news.get("currency","").upper() not in currencies: continue
        try:
            dt = datetime.fromisoformat(news["date"].replace("Z","+00:00"))
            if dt-timedelta(minutes=NEWS_BUFFER_BEFORE_MIN) <= now <= dt+timedelta(minutes=NEWS_BUFFER_AFTER_MIN):
                dm = int((dt-now).total_seconds()/60)
                return False, f"NEWS {news.get('currency')}: {news.get('title','?')[:25]} in {dm}min"
        except Exception:
            continue
    return True, "safe"
