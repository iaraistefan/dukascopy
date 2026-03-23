"""
engine/ultra_checklist.py — Checklist scoring ponderat v2 (prag 65%)
"""
from loguru import logger
from config import (MIN_FPT_PROB, MIN_FINAL_SCORE, MIN_SR_DISTANCE_ATR,
                    ATR_RATIO_MIN, ATR_RATIO_MAX, MIN_CANDLES_REQUIRED,
                    MIN_STABILITY_SCORE, MAX_SPREAD_ATR_RATIO)

_W = {
    "C1_real_data":15,"C2_candles":10,"C3_regime_compat":10,
    "C4_not_random":10,"C5_dist_sr":8,"C6_fpt_prob":12,
    "C7_expiry_score":8,"C8_atr_ratio":5,"C9_cooldown":5,
    "C10_rank1":3,"C11_stability":5,"C12_spread":5,
    "C13_session":5,"C14_pf_allowed":5,
}
_MAX  = sum(_W.values())
_PASS = int(_MAX*0.65)

def is_ultra_premium_signal(
    n_candles, is_real_data, fetch_latency,
    hurst_value, regime, regime_compatible, regime_reason,
    fpt_prob, dist_atr, expiry_score, atr_ratio,
    stability_score, spread_atr_ratio,
    session_allowed, session_reason,
    symbol_allowed, symbol_pf_reason,
    cooldown_ok, is_rank_1,
    confluence_score=0.5, symbol="",
) -> tuple:
    fails = []
    score = 0

    def chk(key, passed, reason=""):
        nonlocal score
        if passed: score += _W[key]
        else: fails.append(f"{key}:{reason}" if reason else key)

    chk("C1_real_data",    is_real_data,                                "mock")
    chk("C2_candles",      n_candles>=MIN_CANDLES_REQUIRED,             f"{n_candles}<{MIN_CANDLES_REQUIRED}")
    chk("C3_regime_compat",regime_compatible,                           regime_reason)
    chk("C4_not_random",   regime!="random",                            f"H={hurst_value:.3f}")
    chk("C5_dist_sr",      dist_atr>=MIN_SR_DISTANCE_ATR,              f"{dist_atr:.2f}")
    chk("C6_fpt_prob",     fpt_prob>=MIN_FPT_PROB,                     f"{fpt_prob:.3f}")
    chk("C7_expiry_score", expiry_score>=MIN_FINAL_SCORE,               f"{expiry_score:.4f}")
    chk("C8_atr_ratio",    ATR_RATIO_MIN<=atr_ratio<=ATR_RATIO_MAX,    f"{atr_ratio:.2f}")
    chk("C9_cooldown",     cooldown_ok,                                 "activ")
    chk("C10_rank1",       is_rank_1,                                   "nu_rank1")
    chk("C11_stability",   stability_score>=MIN_STABILITY_SCORE,        f"{stability_score:.3f}")
    chk("C12_spread",      spread_atr_ratio<=MAX_SPREAD_ATR_RATIO,      f"{spread_atr_ratio:.3f}")
    chk("C13_session",     session_allowed,                             session_reason)
    chk("C14_pf_allowed",  symbol_allowed,                              symbol_pf_reason)

    passed = score>=_PASS
    if passed: logger.info(f"[{symbol}] PASS {score}/{_MAX}")
    else:      logger.debug(f"[{symbol}] FAIL {score}/{_MAX} min={_PASS}: {' | '.join(fails[:4])}")
    return passed, fails
