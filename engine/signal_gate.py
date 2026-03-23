"""
engine/signal_gate.py — Cooldown per simbol + Rank + Session v2
"""
import time
import numpy as np
from datetime import datetime, timezone
from loguru import logger
from config import (GLOBAL_COOLDOWN_SEC, SYMBOL_COOLDOWN_SEC, MAX_SIGNALS_PER_CYCLE,
                    RANK_W_PROB, RANK_W_DIST, RANK_W_HURST, RANK_W_SCORE, RANK_W_CONFLUENCE,
                    SESSION_FILTER_ENABLED, SESSION_ALLOWED_START_UTC, SESSION_ALLOWED_END_UTC)

class SignalGate:
    def __init__(self):
        self._global_ts: float = 0.0
        self._symbol_ts: dict  = {}
        self._total: int       = 0

    def can_emit_global(self) -> bool:
        return (time.time()-self._global_ts) >= GLOBAL_COOLDOWN_SEC

    def can_emit(self, symbol: str) -> bool:
        if not self.can_emit_global(): return False
        return (time.time()-self._symbol_ts.get(symbol, 0.0)) >= SYMBOL_COOLDOWN_SEC

    def record_emit(self, symbol: str):
        now = time.time()
        self._global_ts         = now
        self._symbol_ts[symbol] = now
        self._total            += 1

    @property
    def total_emitted(self) -> int:
        return self._total

def is_session_allowed() -> tuple:
    if not SESSION_FILTER_ENABLED: return True, "disabled"
    hour = datetime.now(timezone.utc).hour
    if SESSION_ALLOWED_START_UTC <= hour < SESSION_ALLOWED_END_UTC:
        return True, f"activa_{hour}:00UTC"
    return False, f"inchisa_{hour}:00UTC"

def compute_rank_score(candidate: dict) -> float:
    p = candidate.get("prob",             0.5)
    d = candidate.get("dist_atr",         0.0)
    h = candidate.get("hurst",            0.5)
    s = candidate.get("expiry_score",     0.0)
    c = candidate.get("confluence_score", 0.5)
    return float(
        max(0.0,(p-0.5)/0.5)        * RANK_W_PROB +
        min(d/3.0, 1.0)             * RANK_W_DIST +
        max(0.0,(h-0.5)/0.5)        * RANK_W_HURST +
        max(0.0, s)/0.3             * RANK_W_SCORE +
        float(np.clip(c,0.0,1.0))   * RANK_W_CONFLUENCE
    )

def select_best_signals(candidates: list, max_signals: int = MAX_SIGNALS_PER_CYCLE) -> list:
    if not candidates: return []
    ranked = sorted(candidates, key=lambda c: c.get("rank_score",0), reverse=True)
    for i,c in enumerate(ranked[:max_signals], 1):
        logger.success(f"RANK #{i}: {c['symbol']} {c['direction']} "
                       f"RS={c['rank_score']:.4f} P={c['prob']:.3f}")
    return ranked[:max_signals]
