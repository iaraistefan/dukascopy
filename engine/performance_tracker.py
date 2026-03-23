"""
engine/performance_tracker.py — Profit Factor + auto-suspend
"""
import json, os
from datetime import datetime, timezone
from loguru import logger
from config import (PF_TRACKING_ENABLED, PF_MIN_SIGNALS_FOR_EVAL,
                    PF_SUSPEND_THRESHOLD, PF_RESUME_THRESHOLD, PF_LOOKBACK_SIGNALS)

PF_DATA_FILE = "performance_data.json"

class PerformanceTracker:
    def __init__(self, data_file=PF_DATA_FILE):
        self.data_file = data_file
        self._data: dict = {}
        self._suspended: set = set()
        self._load()

    def _load(self):
        if os.path.exists(self.data_file):
            try:
                raw = json.load(open(self.data_file))
                self._data      = raw.get("signals",{})
                self._suspended = set(raw.get("suspended",[]))
            except Exception as e:
                logger.warning(f"PF load: {e}")

    def _save(self):
        try:
            json.dump({"signals":self._data,"suspended":list(self._suspended)},
                      open(self.data_file,"w"), indent=2)
        except Exception as e:
            logger.warning(f"PF save: {e}")

    def record_result(self, symbol: str, win: bool):
        if not PF_TRACKING_ENABLED: return
        self._data.setdefault(symbol,[])
        self._data[symbol].append({"win":win,"ts":datetime.now(timezone.utc).isoformat()})
        self._data[symbol] = self._data[symbol][-PF_LOOKBACK_SIGNALS:]
        self._evaluate(symbol)
        self._save()

    def _evaluate(self, symbol):
        records = self._data.get(symbol,[])
        if len(records)<PF_MIN_SIGNALS_FOR_EVAL: return
        wins   = sum(1 for r in records if r["win"])
        losses = len(records)-wins
        pf     = (wins*0.85)/max(losses*1.0, 0.01)
        if symbol in self._suspended:
            if pf>=PF_RESUME_THRESHOLD:
                self._suspended.discard(symbol)
                logger.info(f"PF: {symbol} RE-ACTIVAT PF={pf:.2f}")
        elif pf<PF_SUSPEND_THRESHOLD:
            self._suspended.add(symbol)
            logger.warning(f"PF: {symbol} SUSPENDAT PF={pf:.2f}")

    def is_symbol_allowed(self, symbol: str) -> tuple:
        if not PF_TRACKING_ENABLED: return True, "disabled"
        if symbol in self._suspended:
            r  = self._data.get(symbol,[])
            w  = sum(1 for x in r if x["win"])
            pf = (w*0.85)/max((len(r)-w)*1.0, 0.01)
            return False, f"suspendat_PF={pf:.2f}"
        return True, "ok"

    @property
    def global_win_rate(self) -> float:
        all_h = [r["win"] for v in self._data.values() for r in v]
        return sum(all_h)/len(all_h) if all_h else 0.0
