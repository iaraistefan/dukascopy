# engine/ultrachecklist.py
# Checklist Ultra Premium - ACCURACY FIRST
# Fix: C13 NOU - FPT si RSI trebuie aliniate
# Fix: C12 prag dinamic (major=0.5, crosses=1.0)

from loguru import logger

MAJOR_PAIRS = {
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
    "AUDUSD", "USDCAD", "NZDUSD"
}

def is_ultra_premium_signal(candidate: dict) -> tuple[bool, str]:
    symbol       = candidate.get("symbol", "")
    direction    = candidate.get("direction", "")
    prob         = candidate.get("prob", 0.0)
    dist_atr     = candidate.get("dist_atr", 0.0)
    hurst        = candidate.get("hurst", 0.0)
    drift_dir    = candidate.get("drift_dir", "flat")
    atr_ratio    = candidate.get("atr_ratio", 1.0)
    mu           = candidate.get("mu", 0.0)
    sigma        = candidate.get("sigma", 1.0)
    stability    = candidate.get("stability_score", 0.0)
    rsi_conf     = candidate.get("rsi_confirmation", 0.0)
    spread_atr   = candidate.get("spread_atr_ratio", 0.0)
    expiry_score = candidate.get("expiry_score", 0.0)
    is_real      = candidate.get("is_real_data", True)

    # C1 — Date reale
    if not is_real:
        return False, "C1_not_real_data"

    # C2 — FPT prob minim
    if prob < 0.70:
        return False, f"C2_prob{prob:.3f}<0.70"

    # C3 — Distanta fata de S/R (nu intra IN S/R)
    if dist_atr < 0.50:
        return False, f"C3_dist{dist_atr:.2f}ATR<0.50"

    # C4 — Hurst confirma regimul
    if hurst < 0.65:
        return False, f"C4_hurst{hurst:.3f}<0.65"

    # C5 — Drift aliniat cu directia semnalului
    if direction == "CALL" and drift_dir == "down":
        return False, "C5_CALL_contra_drift_DOWN"
    if direction == "PUT" and drift_dir == "up":
        return False, "C5_PUT_contra_drift_UP"

    # C6 — ATR ratio: piata activa dar nu exploziva
    if atr_ratio < 0.6 or atr_ratio > 2.5:
        return False, f"C6_atr_ratio{atr_ratio:.2f}_out_of_range"

    # C7 — Sigma nu e zero
    if sigma < 1e-8:
        return False, "C7_sigma_zero"

    # C8 — Mu are semn consistent cu directia
    if direction == "CALL" and mu < 0:
        return False, f"C8_CALL_mu_negativ{mu:.6f}"
    if direction == "PUT" and mu > 0:
        return False, f"C8_PUT_mu_pozitiv{mu:.6f}"

    # C9 — Stability score
    if stability < 0.35:
        return False, f"C9_stability{stability:.3f}<0.35"

    # C10 — Expiry score minim
    if expiry_score < 0.28:
        return False, f"C10_expiry_score{expiry_score:.4f}<0.28"

    # C11 — Distanta maxima fata de S/R
    if dist_atr > 2.0:
        return False, f"C11_dist{dist_atr:.2f}ATR>2.0"

    # C12 — Spread/ATR dinamic: major=0.5, crosses=1.0
    spread_limit = 0.5 if symbol in MAJOR_PAIRS else 1.0
    if spread_atr > spread_limit:
        return False, f"C12_spread_atr{spread_atr:.3f}>{spread_limit}"

    # C13 NOU — FPT si RSI aliniate (nu in conflict)
    if rsi_conf < 0.50:
        return False, f"C13_rsi_conf{rsi_conf:.3f}<0.50_conflict_FPT"

    logger.success(
        f"{symbol} Checklist PASS 13/13 | "
        f"P={prob:.3f} Stab={stability:.3f} RSI={rsi_conf:.3f} "
        f"Dist={dist_atr:.2f}ATR Spread={spread_atr:.3f}"
    )
    return True, "OK"
