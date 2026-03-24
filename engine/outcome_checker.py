"""
engine/outcome_checker.py - Verificare automata WIN/LOSS
"""
import asyncio
from datetime import datetime, timezone
from loguru import logger
from engine.performance_tracker import PerformanceTracker


class OutcomeChecker:

    def __init__(self, tracker: PerformanceTracker):
        self.tracker = tracker
        self._pending = []
        self._results = []
        self._stats = {
            "wins": 0,
            "losses": 0,
            "unknown": 0,
            "total": 0,
        }

    async def schedule_check(self, signal, entry_price, extra_wait=0, **kwargs):
        symbol = signal["symbol"]
        direction = signal["direction"]
        delta_min = signal["delta"]
        wait_sec = delta_min * 60 + 10 + extra_wait

        logger.info(symbol + " Outcome check: " + str(wait_sec) + "s total")

        pending = {
            "symbol": symbol,
            "direction": direction,
            "delta_min": delta_min,
            "entry_price": entry_price,
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "check_after_sec": wait_sec,
        }

        self._pending.append(pending)
        asyncio.create_task(self._check_after_delay(pending))

    async def _check_after_delay(self, pending):
        symbol = pending["symbol"]
        direction = pending["direction"]
        wait_sec = pending["check_after_sec"]
        entry_px = pending["entry_price"]

        await asyncio.sleep(wait_sec)

        try:
            from data.feed_dukascopy import get_ohlcv
            df, _, is_real = get_ohlcv(symbol, n_candles=5)

            if len(df) == 0 or not is_real:
                logger.warning(symbol + " Outcome: fara pret. UNKNOWN.")
                self._record_result(pending, None, None, "no_data")
                return

            exit_price = float(df["close"].iloc[-1])

        except Exception as e:
            logger.error(symbol + " Outcome eroare: " + str(e))
            self._record_result(pending, None, None, "error")
            return

        if direction == "CALL":
            win = exit_price > entry_px
        else:
            win = exit_price < entry_px

        result_str = "WIN" if win else "LOSS"
        diff = round(abs(exit_price - entry_px), 5)

        self.tracker.record_result(symbol, win)
        self._record_result(pending, exit_price, win, result_str)

        emoji = "WIN" if win else "LOSS"
        logger.info(
            symbol + " " + emoji + " | " + direction +
            " | Entry=" + str(round(entry_px, 5)) +
            " Exit=" + str(round(exit_price, 5)) +
            " D=" + str(diff)
        )

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
        return {
            "wins": self._stats["wins"],
            "losses": self._stats["losses"],
            "unknown": self._stats["unknown"],
            "total": self._stats["total"],
            "win_rate": str(round(self.win_rate * 100, 1)) + "%",
            "pending": len(self._pending),
            "break_even": "54.05%",
            "above_break_even": self.win_rate >= 0.5405,
        }

    def format_result_message(self, result):
        if result["win"] is None:
            return "UNKNOWN: " + result["symbol"] + " | " + result["status"]

        if result["win"]:
            emoji = "WIN"
            status = "WIN"
        else:
            emoji = "LOSS"
            status = "LOSS"

        msg = (
            emoji + " REZULTAT: " + status + "
" +
            "Simbol: " + result["symbol"] + " | " + result["direction"] + "
" +
            "Entry: " + str(round(result["entry_price"], 5)) + "
" +
            "Exit: " + str(round(result["exit_price"], 5)) + "
" +
            "Expiry: " + str(result["delta_min"]) + " min
" +
            "Win Rate: " + str(round(self.win_rate * 100, 1)) + "%" +
            " (" + str(self._stats["wins"]) + "W / " +
            str(self._stats["losses"]) + "L)"
        )
        return msg

    def get_last_results(self, n=10):
        return self._results[-n:]
