"""
engine/outcome_checker.py — Verificare WIN/LOSS dupa expiry (v4 cu extra_wait)
"""
import asyncio
from datetime import datetime, timezone
from loguru import logger
from engine.performance_tracker import PerformanceTracker


class OutcomeChecker:
    def __init__(self, tracker: PerformanceTracker):
        self.tracker = tracker
        self._results: list = []
        self._stats = {"wins": 0, "losses": 0, "total": 0}

    async def schedule_check(self, signal: dict, entry_price: float,
                             extra_wait: int = 0):
        """
        extra_wait: secunde de asteptat in plus fata de expiry
                    (egal cu LEAD_TIME_SEC — cat timp pana la intrarea efectiva)
        """
        asyncio.create_task(self._check(
            signal["symbol"],
            signal["direction"],
            signal["delta"],
            entry_price,
            signal["delta"] * 60 + extra_wait + 10,
        ))

    async def _check(self, symbol, direction, delta_min, entry_px, wait_sec):
        await asyncio.sleep(wait_sec)
        try:
            from data.feed_dukascopy import get_ohlcv
            df, _, is_real = get_ohlcv(symbol, n_candles=5)
            if len(df) == 0 or not is_real:
                logger.warning(f"[{symbol}] Outcome: no real data.")
                return
            exit_price = float(df["close"].iloc[-1])
        except Exception as e:
            logger.error(f"[{symbol}] outcome error: {e}")
            return

        win   = exit_price > entry_px if direction == "CALL" else exit_price < entry_px
        emoji = "\u2705" if win else "\u274c"

        self.tracker.record_result(symbol, win)
        self._stats["wins" if win else "losses"] += 1
        self._stats["total"] += 1
        self._results.append({
            "symbol":      symbol,
            "direction":   direction,
            "delta_min":   delta_min,
            "entry_price": entry_px,
            "exit_price":  exit_price,
            "win":         win,
            "ts":          datetime.now(timezone.utc).isoformat(),
        })
        if len(self._results) > 500:
            self._results = self._results[-500:]

        logger.info(
            f"[{symbol}] {emoji} {'WIN' if win else 'LOSS'} | "
            f"entry={entry_px:.5f} exit={exit_price:.5f} | WR={self.win_rate:.1%}"
        )

        try:
            from telegram_bot import send_result
            await send_result(
                symbol, direction, win, entry_px, exit_price,
                delta_min, self.win_rate,
                self._stats["wins"], self._stats["losses"],
            )
        except Exception:
            pass

    @property
    def win_rate(self) -> float:
        t = self._stats["wins"] + self._stats["losses"]
        return self._stats["wins"] / t if t > 0 else 0.0

    @property
    def stats(self) -> dict:
        return {**self._stats, "win_rate": f"{self.win_rate:.1%}"}
