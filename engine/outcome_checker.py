"""
engine/outcome_checker.py — Verificare automată WIN/LOSS
"""
import asyncio
from datetime import datetime, timezone
from loguru import logger
from engine.performance_tracker import PerformanceTracker


class OutcomeChecker:

    def __init__(self, tracker: PerformanceTracker):
        self.tracker = tracker
        self._pending: list[dict] = []
        self._results: list[dict] = []
        self._stats = {"wins": 0, "losses": 0, "unknown": 0, "total": 0}

    async def schedule_check(
        self,
        signal: dict,
        entry_price: float,
        extra_wait: int = 0,
        **kwargs,
    ):
        symbol    = signal["symbol"]
        direction = signal["direction"]
        delta_min = signal["delta"]
        wait_sec  = delta_min * 60 + 10 + extra_wait

        logger.info(
            f"[{symbol}] Outcome check: {delta_min}min + 10s + {extra_wait}s = {wait_sec}s"
        )

        pending = {
            "symbol":          symbol,
            "direction":       direction,
            "delta_min":       delta_min,
            "entry_price":     entry_price,
            "entry_time":      datetime.now(timezone.utc).isoformat(),
            "check_after_sec": wait_sec,
        }

        self._pending.append(pending)
        asyncio.create_task(self._check_after_delay(pending))

    async def _check_after_delay(self, pending: dict):
        symbol    = pending["symbol"]
        direction = pending["direction"]
        wait_sec  = pending["check_after_sec"]
        entry_px  = pending["entry_price"]

        await asyncio.sleep(wait_sec)

        try:
            from data.feed_dukascopy import get_ohlcv
            df, _, is_real = get_ohlcv(symbol, n_candles=5)

            if len(df) == 0 or not is_real:
                logger.warning(f"[{symbol}] Outcome: fără preț. UNKNOWN.")
                self._record_result(pending, None, None, "no_data")
                return

            exit_price = float(df["close"].iloc[-1])

        except Exception as e:
            logger.error(f"[{symbol}] Outcome eroare: {e}")
            self._record_result(pending, None, None, "error")
            return

        win = exit_price > entry_px if direction == "CALL" else exit_price < entry_px
        result_str = "WIN" if win else "LOSS"

        self.tracker.record_result(symbol, win)
        self._record_result(pending, exit_price, win, result_str)

        emoji = "✅" if win else "❌"
        logger.info(
            f"[{symbol}] {emoji} {result_str} | {direction} | "
            f"Entry={entry_px:.5f} → Exit={exit_price:.5f} | "
            f"Δ={abs(exit_price - entry_px):.5f}"
        )

    def _record_result(self, pending, exit_price, win, status):
        result = {
            **pending,
            "exit_price": exit_price,
            "win":        win,
            "status":     status,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        self._results.append(result)

        if win is True:
            self._stats["wins"]    += 1
        elif win is False:
            self._stats["losses"]  += 1
        else:
            self._stats["unknown"] += 1
        self._stats["total"] += 1

        if len(self._results) > 500:
            self._results = self._results[-500:]

        if pending in self._pending:
            self._pending.remove(pending)

    @property
    def win_rate(self) -> float:
        total = self._stats["wins"] + self._stats["losses"]
        return self._stats["wins"] / total if total > 0 else 0.0

    @property
    def stats(self) -> dict:
        return {
            **self._stats,
            "win_rate":         f"{self.win_rate:.1%}",
            "pending":          len(self._pending),
            "break_even":       "54.05%",
            "above_break_even": self.win_rate >= 0.5405,
        }

    def format_result_message(self, result: dict) -> str:
        if result["win"] is None:
            return f"⚠️ {result['symbol']} | {result['status']}"
        emoji  = "✅" if result["win"] else "❌"
        status = "WIN" if result["win"] else "LOSS"
        return (
            f"{emoji} REZULTAT: {status}
"
            f"💱 {result['symbol']} | {result['direction']}
"
            f"📈 Entry: {result['entry_price']:.5f}
"
            f"📉 Exit:  {result['exit_price']:.5f}
"
            f"⏱ Expiry: {result['delta_min']} min
"
            f"📊 Win Rate: {self.win_rate:.1%} "
            f"({self._stats['wins']}W / {self._stats['losses']}L)"
        )

    def get_last_results(self, n: int = 10) -> list[dict]:
        return self._results[-n:]
