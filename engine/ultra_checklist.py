"""
engine/ultra_checklist.py — Checklist 15 condiții (Ultra Premium + Slippage Shield)
"""

from loguru import logger
from config import (
    MIN_FPT_PROB, MIN_FINAL_SCORE, MIN_SR_DISTANCE_ATR,
    ATR_RATIO_MIN, ATR_RATIO_MAX, MIN_CANDLES_REQUIRED,
    MIN_WIN_PROBABILITY, MAX_FETCH_LATENCY_SEC,
    MIN_STABILITY_SCORE, MAX_SPREAD_ATR_RATIO,
    MIN_ATR_PIPS, SLIPPAGE_BUFFER_PIPS
)

def is_ultra_premium_signal(
    n_candles: int,
    is_real_data: bool,
    fetch_latency: float,
    hurst: float,
    regime: str,
    regime_ok: bool,
    regime_reason: str,
    prob: float,
    dist_atr: float,
    expiry_score: float,
    atr_ratio: float,
    stability_score: float,
    spread_atr_ratio: float,
    session_allowed: bool,
    session_reason: str,
    pf_ok: bool,
    pf_reason: str,
    cooldown_ok: bool,
    is_rank_1: bool,
    symbol: str,
    entry_price: float,
    target_level: float = None,
    confluence_score: float = 0.0,
    **kwargs,
) -> tuple[bool, list[str]]:
    
    fails = []

    # C1: Date reale
    if not is_real_data: fails.append("C1: date_mock")

    # C1.1: Latența datelor 
    if fetch_latency > MAX_FETCH_LATENCY_SEC:
        fails.append(f"C1.1: latency={fetch_latency:.1f}s > {MAX_FETCH_LATENCY_SEC}s")

    # C2: Lumânări suficiente
    if n_candles < MIN_CANDLES_REQUIRED:
        fails.append(f"C2: candles={n_candles} < {MIN_CANDLES_REQUIRED}")

    # C3: Regim compatibil
    if not regime_ok:
        fails.append(f"C3: {regime_reason}")

    # C4: Evităm piețele aleatorii
    if regime == "random":
        fails.append(f"C4: regim_random_H={hurst:.3f}")

    # C5: Distanță relativă față de S/R
    if dist_atr < MIN_SR_DISTANCE_ATR:
        fails.append(f"C5: dist_atr={dist_atr:.2f} < {MIN_SR_DISTANCE_ATR}")

    # C6: Probabilitate Matematică (Model Dinamic)
    min_req_prob = MIN_WIN_PROBABILITY if regime == "mean_reversion" else MIN_FPT_PROB
    if prob < min_req_prob:
        fails.append(f"C6: prob={prob:.3f} < {min_req_prob}")

    # C7: Scor Expiry Optimizer
    if expiry_score < MIN_FINAL_SCORE:
        fails.append(f"C7: score_exp={expiry_score:.4f} < {MIN_FINAL_SCORE}")

    # C8: ATR ratio în bandă sănătoasă
    if atr_ratio < ATR_RATIO_MIN or atr_ratio > ATR_RATIO_MAX:
        fails.append(f"C8: atr_ratio={atr_ratio:.2f} out_of_band")

    # C9: Cooldown global
    if not cooldown_ok: fails.append("C9: cooldown_activ")

    # C10: Rank #1
    if not is_rank_1: fails.append("C10: nu_rank_1")

    # C11: Stability Score
    if stability_score < MIN_STABILITY_SCORE:
        fails.append(f"C11: stability={stability_score:.3f} < {MIN_STABILITY_SCORE}")

    # C12: Spread filter
    if spread_atr_ratio > MAX_SPREAD_ATR_RATIO:
        fails.append(f"C12: spread={spread_atr_ratio:.3f} > {MAX_SPREAD_ATR_RATIO}")

    # C13: Session filter
    if not session_allowed: fails.append(f"C13: {session_reason}")

    # C14: Performance tracker
    if not pf_ok: fails.append(f"C14: {pf_reason}")

    # ─── C15: SLIPPAGE SHIELD & VOLATILITY CHECK ──────────────────────────────
    if target_level is not None and dist_atr > 0:
        # Determinam dinamica perechii (0.01 pt JPY, 0.0001 pt restul)
        pip_size = 0.01 if entry_price > 20 else 0.0001
        
        # Distanța absolută până la bariera vizată
        dist_abs = abs(target_level - entry_price)
        dist_pips = dist_abs / pip_size
        
        # Extragem ATR-ul absolut (în pips) din formula distanței
        atr_c_pips = (dist_abs / dist_atr) / pip_size
        
        # 15.1: Protecție piață moartă (Volatilitate minusculă)
        if atr_c_pips < MIN_ATR_PIPS:
            fails.append(f"C15.1: dead_market (ATR={atr_c_pips:.1f}p < {MIN_ATR_PIPS}p)")
            
        # 15.2: Buffer-ul de Slippage (Mișcarea nu acoperă posibila execuție proastă a brokerului)
        if dist_pips < SLIPPAGE_BUFFER_PIPS:
            fails.append(f"C15.2: slippage_risk (Dist={dist_pips:.1f}p < {SLIPPAGE_BUFFER_PIPS}p)")

    passed = len(fails) == 0

    if not passed:
        logger.debug(
            f"[{symbol}] Checklist FAIL ({len(fails)}): "
            f"{' | '.join(fails[:3])}"
        )
    else:
        logger.success(
            f"[{symbol}] \u2694\ufe0f ULTRA PASS \u2694\ufe0f "
            f"P={prob:.3f} Dist={dist_pips:.1f}pips "
            f"(ATR={atr_c_pips:.1f}p) Stab={stability_score:.3f}"
        )

    return passed, fails
