"""
engine/ultra_checklist.py — Checklist premium v4
NOTA: is_real_data = WARNING (nu FAIL) — permite date simulate in dev
"""
from loguru import logger
from config import (
    MIN_CANDLES_REQUIRED, MAX_FETCH_LATENCY_SEC,
    HURST_MOMENTUM_THRESHOLD, MIN_FPT_PROB,
    MIN_SR_DISTANCE_ATR, MIN_FINAL_SCORE,
    ATR_RATIO_MIN, ATR_RATIO_MAX,
    MIN_STABILITY_SCORE, MAX_SPREAD_ATR_RATIO,
)


def is_ultra_premium_signal(
    n_candles: int,
    is_real_data: bool,
    fetch_latency: float,
    hurst_value: float,
    regime: str,
    regime_compatible: bool,
    regime_reason: str,
    fpt_prob: float,
    dist_atr: float,
    expiry_score: float,
    atr_ratio: float,
    stability_score: float,
    spread_atr_ratio: float,
    session_allowed: bool,
    session_reason: str,
    symbol_allowed: bool,
    symbol_pf_reason: str,
    cooldown_ok: bool,
    is_rank_1: bool,
    confluence_score: float,
    symbol: str = "",
) -> tuple[bool, list]:

    fails = []
    score = 0
    max_score = 0

    def check(cond, points, label, hard=False):
        nonlocal score, max_score
        max_score += points
        if cond:
            score += points
        else:
            fails.append(label)
            if hard:
                return False
        return True

    # ── DATE (WARNING doar, nu FAIL) ─────────────────────────────────────────
    if not is_real_data:
        logger.warning(f"[{symbol}] Date simulate — semnal permis in dev")
    if fetch_latency > MAX_FETCH_LATENCY_SEC * 3:
        fails.append(f"latenta prea mare: {fetch_latency:.1f}s")
        return False, fails

    # ── CANDLE COUNT ──────────────────────────────────────────────────────────
    check(n_candles >= MIN_CANDLES_REQUIRED, 10, f"candle count {n_candles}<{MIN_CANDLES_REQUIRED}", hard=True)

    # ── SESIUNE ───────────────────────────────────────────────────────────────
    if not check(session_allowed, 15, f"sesiune inchisa: {session_reason}", hard=True):
        return False, fails

    # ── COOLDOWN ──────────────────────────────────────────────────────────────
    if not check(cooldown_ok, 10, "cooldown global activ", hard=True):
        return False, fails

    # ── SYMBOL ALLOWED ────────────────────────────────────────────────────────
    if not check(symbol_allowed, 10, f"simbol suspendat: {symbol_pf_reason}", hard=True):
        return False, fails

    # ── REGIME ────────────────────────────────────────────────────────────────
    check(regime in ("momentum", "mean_reversion"), 10, f"regim necunoscut: {regime}")
    check(regime_compatible, 15, f"regim incompatibil: {regime_reason}")
    check(hurst_value >= HURST_MOMENTUM_THRESHOLD, 8, f"Hurst slab: {hurst_value:.3f}")

    # ── PROBABILITATE FPT ─────────────────────────────────────────────────────
    check(fpt_prob >= MIN_FPT_PROB, 20, f"FPT prob {fpt_prob:.3f}<{MIN_FPT_PROB}")

    # ── DISTANTA S/R ──────────────────────────────────────────────────────────
    check(dist_atr >= MIN_SR_DISTANCE_ATR, 10, f"prea aproape S/R: {dist_atr:.2f} ATR")

    # ── EXPIRY SCORE ──────────────────────────────────────────────────────────
    check(expiry_score >= MIN_FINAL_SCORE, 8, f"expiry score {expiry_score:.3f}<{MIN_FINAL_SCORE}")

    # ── ATR RATIO ─────────────────────────────────────────────────────────────
    check(ATR_RATIO_MIN <= atr_ratio <= ATR_RATIO_MAX, 5,
          f"ATR ratio {atr_ratio:.2f} out of range")

    # ── SPREAD ────────────────────────────────────────────────────────────────
    check(spread_atr_ratio <= MAX_SPREAD_ATR_RATIO, 5,
          f"spread prea mare: {spread_atr_ratio:.2f}")

    # ── CONFLUENCE ────────────────────────────────────────────────────────────
    check(confluence_score >= 0.10, 5, f"confluence scazuta: {confluence_score:.3f}")

    # ── RANK ──────────────────────────────────────────────────────────────────
    check(is_rank_1, 5, "nu este rank #1")

    passed = len([f for f in fails if "simulat" not in f]) == 0 or (
        score >= int(max_score * 0.60)
    )

    logger.info(f"[{symbol}] {'PASS' if passed else 'FAIL'} {score}/{max_score}")
    if fails:
        logger.debug(f"[{symbol}] Issues: {fails}")

    return passed, fails
