from loguru import logger
from config import (
    MIN_FPT_PROB, MIN_FINAL_SCORE, MIN_SR_DISTANCE_ATR,
    ATR_RATIO_MIN, ATR_RATIO_MAX, MIN_CANDLES_REQUIRED,
    HURST_MOMENTUM_THRESHOLD, HURST_MR_THRESHOLD,
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
    symbol: str = "",
) -> tuple[bool, list[str]]:

    fails = []

    if not is_real_data:
        fails.append("C1: date_mock")

    if n_candles < MIN_CANDLES_REQUIRED:
        fails.append(f"C2: candles={n_candles}<{MIN_CANDLES_REQUIRED}")

    if not regime_compatible:
        fails.append(f"C3: {regime_reason}")

    if regime == "random":
        fails.append(f"C4: regim_random_H={hurst_value:.3f}")

    if dist_atr < MIN_SR_DISTANCE_ATR:
        fails.append(f"C5: dist={dist_atr:.2f}<{MIN_SR_DISTANCE_ATR}")

    if fpt_prob < MIN_FPT_PROB:
        fails.append(f"C6: prob={fpt_prob:.3f}<{MIN_FPT_PROB}")

    if expiry_score < MIN_FINAL_SCORE:
        fails.append(f"C7: score={expiry_score:.4f}<{MIN_FINAL_SCORE}")

    if atr_ratio < ATR_RATIO_MIN or atr_ratio > ATR_RATIO_MAX:
        fails.append(f"C8: atr_ratio={atr_ratio:.2f}")

    if not cooldown_ok:
        fails.append("C9: cooldown_activ")

    if not is_rank_1:
        fails.append("C10: nu_rank_1")

    if stability_score < MIN_STABILITY_SCORE:
        fails.append(f"C11: stability={stability_score:.3f}<{MIN_STABILITY_SCORE}")

    if spread_atr_ratio > MAX_SPREAD_ATR_RATIO:
        fails.append(f"C12: spread_atr={spread_atr_ratio:.3f}>{MAX_SPREAD_ATR_RATIO}")

    if not session_allowed:
        fails.append(f"C13: {session_reason}")

    if not symbol_allowed:
        fails.append(f"C14: {symbol_pf_reason}")

    passed = len(fails) == 0

    if not passed:
        logger.debug(f"[{symbol}] Checklist FAIL ({len(fails)}): {' | '.join(fails[:3])}")
    else:
        logger.info(
            f"[{symbol}] Checklist PASS (14/14) P={fpt_prob:.3f} "
            f"D={dist_atr:.2f} S={expiry_score:.4f} Stab={stability_score:.3f}"
        )

    return passed, fails
