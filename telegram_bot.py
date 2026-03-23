"""
telegram_bot.py — Semnale + WIN/LOSS pe Telegram
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
    if not _TG or not TELEGRAM_BOT_TOKEN: return
    e = "🟢" if c["direction"]=="CALL" else "🔴"
    a = "⬆️ CALL" if c["direction"]=="CALL" else "⬇️ PUT"
    msg = (
        f"{e} <b>SEMNAL {c.get('source','FPT')}</b>\n"
        f"💱 <b>{c['symbol']}</b> — {a}\n"
        f"⏱ Expirare: <b>{c['delta']} minute</b>\n"
        f"📊 Probabilitate: <b>{c.get('prob',0):.1%}</b>\n"
        f"📈 Entry: <code>{c.get('entry_price',0):.5f}</code>\n"
        f"🎯 Dist S/R: {c.get('dist_atr',0):.2f} ATR | Conf: {c.get('confluence_score',0):.0%}\n"
        f"📉 Trend M5: {c.get('mtf_trend','?')} | RS: {c.get('rank_score',0):.4f}\n"
        f"\n<i>Deschide pozitia in urmatoarele 90 sec!</i>"
    )
    try:
        await Bot(token=TELEGRAM_BOT_TOKEN).send_message(
            chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="HTML")
    except Exception as ex:
        logger.error(f"TG send_signal: {ex}")

async def send_result(symbol, direction, win, entry, exit_, delta, win_rate, wins, losses):
    if not _TG or not TELEGRAM_BOT_TOKEN: return
    msg = (
        f"{'✅' if win else '❌'} <b>{'WIN' if win else 'LOSS'}</b>\n"
        f"💱 {symbol} | {'⬆️ CALL' if direction=='CALL' else '⬇️ PUT'}\n"
        f"📈 Entry: <code>{entry:.5f}</code> → <code>{exit_:.5f}</code>\n"
        f"⏱ {delta} min | 📊 WR: <b>{win_rate:.1%}</b> ({wins}W/{losses}L)"
    )
    try:
        await Bot(token=TELEGRAM_BOT_TOKEN).send_message(
            chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="HTML")
    except Exception as ex:
        logger.error(f"TG send_result: {ex}")

async def send_text(text: str):
    if not _TG or not TELEGRAM_BOT_TOKEN:
        logger.info(f"[TG] {text}")
        return
    try:
        await Bot(token=TELEGRAM_BOT_TOKEN).send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as ex:
        logger.error(f"TG send_text: {ex}")
