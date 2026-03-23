import asyncio
import csv
import os
from datetime import datetime, timezone
from loguru import logger


CSV_PATH = "outcomes_real.csv"
CSV_FIELDS = [
    "timestamp_entry", "timestamp_check", "symbol", "direction",
    "expiry_min", "entry_price", "exit_price", "pips_diff",
    "result", "fpt_prob", "stability", "rsi_conf",
    "dist_atr", "hurst", "spread_atr", "expiry_score"
]


def _ensure_csv_header():
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()


def _write_outcome_row(row: dict):
    _ensure_csv_header()
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})


class OutcomeChecker:

    def __init__(self, tracker=None):
        self.tracker = tracker
        self.pending = []
        self.results = []
        self._stats = {"wins": 0, "losses": 0, "unknown": 0, "total": 0}

    async def schedule_check(self, signal: dict, entry_price: float):
        symbol    = signal["symbol"]
        direction = signal["direction"]
        delta_min = signal["delta"]
        wait_sec  = delta_min * 60 + 10

        entry_time = datetime.now(timezone.utc).isoformat()

        pending = {
            "symbol":       symbol,
            "direction":    direction,
            "delta_min":    delta_min,
            "entry_price":  entry_price,
            "entry_time":   entry_time,
            "wait_sec":     wait_sec,
            "fpt_prob":     signal.get("prob", 0),
            "stability":    signal.get("stability_score", 0),
            "rsi_conf":     signal.get("rsi_confirmation", 0),
            "dist_atr":     signal.get("dist_atr", 0),
            "hurst":        signal.get("hurst", 0),
            "spread_atr":   signal.get("spread_atr_ratio", 0),
            "expiry_score": signal.get("expiry_score", 0),
        }
        self.pending.append(pending)

        logger.info(
            f"{symbol} Outcome programat in {delta_min}min+10s | "
            f"Entry={entry_price:.5f}"
        )
        asyncio.create_task(self._check_after_delay(pending))

    async def _check_after_delay(self, pending: dict):
        await asyncio.sleep(pending["wait_sec"])

        symbol   = pending["symbol"]
        direction = pending["direction"]
        entry_px  = pending["entry_price"]

        try:
            from data.feed_dukascopy import get_ohlcv
            df, _, is_real = get_ohlcv(symbol, n_candles=3)
            if len(df) == 0 or not is_real:
                logger.warning(f"{symbol} Outcome: pret indisponibil. UNKNOWN.")
                self._record(pending, None, None, "UNKNOWN")
                return
            exit_price = float(df["close"].iloc[-1])
        except Exception as e:
            logger.error(f"{symbol} Outcome eroare: {e}")
            self._record(pending, None, None, "ERROR")
            return

        win    = exit_price > entry_px if direction == "CALL" else exit_price < entry_px
        pips   = abs(exit_price - entry_px)
        status = "WIN" if win else "LOSS"
        emoji  = "✅" if win else "❌"

        if self.tracker:
            try:
                self.tracker.record_result(symbol, win)
            except Exception:
                pass

        self._record(pending, exit_price, win, status)

        logger.info(
            f"{symbol} {emoji} {status} | {direction} | "
            f"Entry={entry_px:.5f} Exit={exit_price:.5f} Diff={pips:.5f} | "
            f"WR={self.win_rate:.1%} "
            f"({self._stats['wins']}W/{self._stats['losses']}L)"
        )

    def _record(self, pending: dict, exit_price, win, status: str):
        now  = datetime.now(timezone.utc).isoformat()
        pips = abs((exit_price or 0) - pending["entry_price"])

        row = {
            "timestamp_entry": pending["entry_time"],
            "timestamp_check": now,
            "symbol":          pending["symbol"],
            "direction":       pending["direction"],
            "expiry_min":      pending["delta_min"],
            "entry_price":     f"{pending['entry_price']:.5f}",
            "exit_price":      f"{exit_price:.5f}" if exit_price else "",
            "pips_diff":       f"{pips:.5f}",
            "result":          status,
            "fpt_prob":        f"{pending['fpt_prob']:.4f}",
            "stability":       f"{pending['stability']:.4f}",
            "rsi_conf":        f"{pending['rsi_conf']:.4f}",
            "dist_atr":        f"{pending['dist_atr']:.4f}",
            "hurst":           f"{pending['hurst']:.4f}",
            "spread_atr":      f"{pending['spread_atr']:.4f}",
            "expiry_score":    f"{pending['expiry_score']:.4f}",
        }

        self.results.append(row)
        _write_outcome_row(row)

        if win is True:
            self._stats["wins"] += 1
        elif win is False:
            self._stats["losses"] += 1
        else:
            self._stats["unknown"] += 1
        self._stats["total"] += 1

        if len(self.results) > 500:
            self.results = self.results[-500:]
        if pending in self.pending:
            self.pending.remove(pending)

    @property
    def win_rate(self) -> float:
        total = self._stats["wins"] + self._stats["losses"]
        return self._stats["wins"] / total if total > 0 else 0.0

    @property
    def stats(self) -> dict:
        return {
            **self._stats,
            "win_rate":         f"{self.win_rate:.1%}",
            "pending":          len(self.pending),
            "break_even":       "54.05%",
            "above_break_even": self.win_rate >= 0.5405,
        }

    def get_last_results(self, n: int = 20) -> list:
        return self.results[-n:]

    def format_result_message(self, result: dict) -> str:
        if result.get("result") in (None, "UNKNOWN", "ERROR"):
            return f"⚠️ {result['symbol']} rezultat nedisponibil"
        emoji = "✅" if result["result"] == "WIN" else "❌"
        return (
            f"{emoji} *REZULTAT {result['result']}*\n"
            f"Pereche: {result['symbol']} {result['direction']}\n"
            f"Entry: {result['entry_price']} | Exit: {result['exit_price']}\n"
            f"Expiry: {result['expiry_min']}min\n"
            f"Win Rate: {self.win_rate:.1%} "
            f"({self._stats['wins']}W / {self._stats['losses']}L)"
        )
