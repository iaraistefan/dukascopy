"""
telegram_bot.py — Semnale + WIN/LOSS pe Telegram (v4 cu entry time fix)
"""
from loguru import logger
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

try:
    from telegram import Bot
    _TG = True
except ImportError:
    _TG = False
    logger.warning("python-telegram-bot indisponibil.")


async def send_signal(c: dict):
    if not _TG or not TELEGRAM_BOT_TOKEN:
        return
    e          = "\U0001f7e2" if c["direction"] == "CALL" else "\U0001f534"
    arrow      = "\u2b06\ufe0f CALL" if c["direction"] == "CALL" else "\u2b07\ufe0f PUT"
    entry_time = c.get("entry_time_str", "imediat")
    prob_str   = f"{c.get('prob', 0):.1%}"
    price_str  = f"{c.get('entry_price', 0):.5f}"
    dist_str   = f"{c.get('dist_atr', 0):.2f}"
    conf_str   = f"{c.get('confluence_score', 0):.0%}"
    trend_str  = c.get("mtf_trend", "?")
    rs_str     = f"{c.get('rank_score', 0):.4f}"
    src        = c.get("source", "FPT")
    delta      = c["delta"]
    symbol     = c["symbol"]

    msg = (
        f"{e} <b>SEMNAL {src}</b>\n"
        f"\U0001f4b1 <b>{symbol}</b> \u2014 {arrow}\n"
        f"\u23f1 Expirare: <b>{delta} minute</b>\n"
        f"\u23f0 <b>Intrare la: {entry_time}</b>\n"
        f"\U0001f4ca Probabilitate: <b>{prob_str}</b>\n"
        f"\U0001f4c8 Price acum: <code>{price_str}</code>\n"
        f"\U0001f3af Dist S/R: {dist_str} ATR | Conf: {conf_str}\n"
        f"\U0001f4c9 Trend M5: {trend_str} | RS: {rs_str}\n"
        f"\n<b>\u26a0\ufe0f Deschide pozitia EXACT la {entry_time}!</b>"
    )
    try:
        await Bot(token=TELEGRAM_BOT_TOKEN).send_message(
            chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="HTML"
        )
        logger.info(f"[{symbol}] TG semnal trimis OK -> intrare {entry_time}")
    except Exception as ex:
        logger.error(f"TG send_signal: {ex}")


async def send_result(symbol, direction, win, entry, exit_, delta,
                      win_rate, wins, losses):
    if not _TG or not TELEGRAM_BOT_TOKEN:
        return
    emoji  = "\u2705" if win else "\u274c"
    result = "WIN" if win else "LOSS"
    arrow  = "\u2b06\ufe0f CALL" if direction == "CALL" else "\u2b07\ufe0f PUT"
    msg = (
        f"{emoji} <b>REZULTAT: {result}</b>\n"
        f"\U0001f4b1 {symbol} | {arrow}\n"
        f"\U0001f4c8 Entry: <code>{entry:.5f}</code> \u2192 <code>{exit_:.5f}</code>\n"
        f"\u23f1 {delta} min | \U0001f4ca WR: <b>{win_rate:.1%}</b> ({wins}W/{losses}L)"
    )
    try:
        await Bot(token=TELEGRAM_BOT_TOKEN).send_message(
            chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="HTML"
        )
    except Exception as ex:
        logger.error(f"TG send_result: {ex}")


async def send_text(text: str):
    if not _TG or not TELEGRAM_BOT_TOKEN:
        logger.info(f"[TG] {text}")
        return
    try:
        await Bot(token=TELEGRAM_BOT_TOKEN).send_message(
            chat_id=TELEGRAM_CHAT_ID, text=text
        )
    except Exception as ex:
        logger.error(f"TG send_text: {ex}")
