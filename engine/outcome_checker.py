import asyncio
from datetime import datetime, timezone
from loguru import logger
from engine.performance_tracker import PerformanceTracker
from data.feed_dukascopy import get_ohlcv

# Importăm funcția de Telegram pentru rezultate
from telegram_bot import send_result

class OutcomeChecker:

    def __init__(self, tracker: PerformanceTracker):
        self.tracker = tracker
        self._pending = []
        self._results = []
        self._stats = {"wins": 0, "losses": 0, "unknown": 0, "total": 0}

    async def schedule_check(self, signal, entry_price, extra_wait=0, **kwargs):
        symbol = signal["symbol"]
        direction = signal["direction"]
        delta_min = signal["delta"]
        
        # Așteptăm expirarea (delta_min) + timpul de intrare (extra_wait) + 5s marjă pt formarea lumanării
        wait_sec = (delta_min * 60) + extra_wait + 5
        
        pending = {
            "symbol": symbol,
            "direction": direction,
            "delta_min": delta_min,
            "entry_price": entry_price,
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "check_after_sec": wait_sec,
        }
        self._pending.append(pending)
        
        # Lansăm verificarea în background
        asyncio.create_task(self._check_after_delay(pending))

    async def _check_after_delay(self, pending):
        symbol = pending["symbol"]
        direction = pending["direction"]
        wait_sec = pending["check_after_sec"]
        entry_px = pending["entry_price"]
        
        # Task-ul intră în repaus până când expiră opțiunea
        await asyncio.sleep(wait_sec)
        
        try:
            df, _, is_real = await asyncio.to_thread(get_ohlcv, symbol, n_candles=5)
            
            if df is None or len(df) == 0 or not is_real:
                self._record_result(pending, None, None, "no_data")
                return
                
            exit_price = float(df["close"].iloc[-1])
            
        except Exception as e:
            logger.error(f"Eroare la verificarea rezultatului pt {symbol}: {e}")
            self._record_result(pending, None, None, "error")
            return
            
        # Logica validării pentru Opțiuni Binare
        if direction == "CALL":
            win = exit_price > entry_px
        else:  # PUT
            win = exit_price < entry_px
            
        result_str = "WIN" if win else "LOSS"
        
        # Salvăm rezultatul intern
        self.tracker.record_result(symbol, win)
        self._record_result(pending, exit_price, win, result_str)
        
        logger.info(f"[{symbol}] REZULTAT: {result_str} | Intrare: {entry_px:.5f} -> Ieșire: {exit_price:.5f}")

        # TRIMITERE PE TELEGRAM
        try:
            await send_result(
                symbol=symbol,
                direction=direction,
                win=win,
                entry=entry_px,
                exit_=exit_price,
                delta=pending["delta_min"],
                win_rate=self.win_rate,
                wins=self._stats["wins"],
                losses=self._stats["losses"]
            )
        except Exception as e:
            logger.error(f"Nu am putut trimite rezultatul pe Telegram pt {symbol}: {e}")

    def _record_result(self, pending, exit_price, win, status):
        result = dict(pending)
        result["exit_price"] = exit_price
        result["win"] = win
        result["status"] = status
        result["checked_at"] = datetime.now(timezone.utc).isoformat()
        
        self._results.append(result)
        
        if win is True:
            self._stats["wins"] += 1
        elif win is False:
            self._stats["losses"] += 1
        else:
            self._stats["unknown"] += 1
            
        self._stats["total"] += 1
        
        if pending in self._pending:
            self._pending.remove(pending)
            
        if len(self._results) > 500:
            self._results = self._results[-500:]

    @property
    def win_rate(self):
        total = self._stats["wins"] + self._stats["losses"]
        if total == 0:
            return 0.0
        return self._stats["wins"] / total

    @property
    def stats(self):
        wr = f"{self.win_rate * 100:.1f}%"
        return {
            "wins": self._stats["wins"],
            "losses": self._stats["losses"],
            "unknown": self._stats["unknown"],
            "total": self._stats["total"],
            "win_rate": wr,
            "pending": len(self._pending),
            "break_even": "54.05%",
            "above_break_even": self.win_rate >= 0.5405,
        }

    def format_result_message(self, result):
        if result["win"] is None:
            return f"UNKNOWN: {result['symbol']}"
        status = "WIN" if result["win"] else "LOSS"
        return f"{status} | {result['symbol']} | {result['direction']}"

    def get_last_results(self, n=10):
        return self._results[-n:]
