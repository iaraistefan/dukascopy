"""
main.py — ORCHESTRATOR v4 | Lead Time entry timestamp
"""
import asyncio
import time
from datetime import datetime, timezone, timedelta
from loguru import logger

from config import (
    SYMBOLS, SYMBOLS_3MIN,
    EXPIRY_OPTIONS_3MIN, EXPIRY_OPTIONS_10MIN,
    SCAN_INTERVAL, CANDLES_REQUIRED, MIN_CANDLES_REQUIRED,
    MIN_FINAL_SCORE, ATR_RATIO_MIN, ATR_RATIO_MAX,
    MAX_SIGNALS_PER_CYCLE, LEAD_TIME_SEC,
)
from data.feed_dukascopy        import get_ohlcv
from engine.hurst               import get_current_regime, is_regime_compatible
from engine.fractal_sr          import get_sr_levels, compute_atr
from engine.fpt_model           import run_fpt_signal
from engine.ou_model            import run_ou_grid_scoring
from engine.expiry_optimizer    import select_optimal_expiry
from engine.confluence          import compute_confluence_score
from engine.signal_gate         import (
    SignalGate, compute_rank_score,
    select_best_signals, is_session_allowed,
)
from engine.ultra_checklist     import is_ultra_premium_signal
from engine.performance_tracker import PerformanceTracker
from engine.outcome_checker     import OutcomeChecker
from engine.news_filter         import is_news_safe
from engine.mtf_filter          import is_mtf_aligned
from telegram_bot               import send_signal, send_text

gate    = SignalGate()
tracker = PerformanceTracker()
checker = OutcomeChecker(tracker)


def process_symbol(symbol: str):
    pf_ok, pf_reason = tracker.is_symbol_allowed(symbol)
    if not pf_ok or not gate.can_emit(symbol):
        return None

    df, latency, is_real = get_ohlcv(symbol, CANDLES_REQUIRED)
    if len(df) < MIN_CANDLES_REQUIRED:
        return None

    atr_s   = compute_atr(df)
    atr_c   = float(atr_s.iloc[-1])
    atr_avg = float(atr_s.rolling(50).mean().iloc[-1])
    atr_r   = atr_c / (atr_avg + 1e-10)
    if not (ATR_RATIO_MIN <= atr_r <= ATR_RATIO_MAX):
        return None

    last    = df.iloc[-1]
    spr     = float(last.get("spread", (last["high"] - last["low"]) * 0.15))
    spr_atr = spr / (atr_c + 1e-10)

    regime, h, drift = get_current_regime(df)
    if regime == "random":
        return None

    sr = get_sr_levels(df)
    res, sup = sr
    exp_opts = EXPIRY_OPTIONS_3MIN if symbol in SYMBOLS_3MIN else EXPIRY_OPTIONS_10MIN

    signal, src = None, ""
    if regime == "momentum":
        signal, src = run_fpt_signal(df, sr, expiry_options=exp_opts), "FPT"
    elif regime == "mean_reversion":
        signal, src = run_ou_grid_scoring(df, expiry_options=exp_opts), "OU"
    if signal is None:
        return None

    direction          = signal["direction"]
    reg_ok, reg_reason = is_regime_compatible(regime, direction, drift, src)
    if not reg_ok:
        return None

    probs             = {d: signal["prob"] for d in exp_opts}
    best_d, best_s, _ = select_optimal_expiry(probs, df, direction, res, sup)
    if best_s < MIN_FINAL_SCORE:
        return None

    conf, stab, rsi_c = compute_confluence_score(df, direction)

    c = {
        "symbol":           symbol,
        "direction":        direction,
        "prob":             signal["prob"],
        "delta":            best_d,
        "expiry_score":     best_s,
        "target_level":     signal.get("target_level"),
        "dist_atr":         signal.get("dist_atr", 0.0),
        "hurst":            h,
        "regime":           regime,
        "drift_dir":        drift,
        "atr_ratio":        atr_r,
        "n_candles":        len(df),
        "is_real_data":     is_real,
        "fetch_latency":    latency,
        "source":           src,
        "regime_ok":        reg_ok,
        "regime_reason":    reg_reason,
        "confluence_score": conf,
        "stability_score":  stab,
        "rsi_confirmation": rsi_c,
        "spread_atr_ratio": spr_atr,
        "pf_ok":            pf_ok,
        "pf_reason":        pf_reason,
        "entry_price":      float(df["close"].iloc[-1]),
        "mu":               signal.get("mu", 0),
        "sigma":            signal.get("sigma", 0),
    }
    c["rank_score"] = compute_rank_score(c)
    logger.success(
        f"[{symbol}] {direction} D={best_d}min "
        f"P={c['prob']:.3f} RS={c['rank_score']:.4f}"
    )
    return c


async def emit_signal(w: dict):
    sym, dir_ = w["symbol"], w["direction"]

    mtf_ok, mtf_r = is_mtf_aligned(sym, dir_)
    w["mtf_trend"] = mtf_r
    if not mtf_ok:
        logger.info(f"[{sym}] MTF FAIL: {mtf_r}")
        return

    news_ok, news_r = is_news_safe(sym)
    if not news_ok:
        logger.info(f"[{sym}] NEWS BLOCK: {news_r}")
        return

    entry_dt            = datetime.now(timezone.utc) + timedelta(seconds=LEAD_TIME_SEC)
    w["entry_time_str"] = entry_dt.strftime("%H:%M:%S UTC")
    w["entry_time_dt"]  = entry_dt

    await send_signal(w)
    gate.record_emit(sym)

    logger.success(
        f"EMIS: {sym} {dir_} D={w['delta']}min "
        f"Entry={w['entry_price']:.5f} | Intrare la {w['entry_time_str']}"
    )

    await checker.schedule_check(w, w["entry_price"], extra_wait=LEAD_TIME_SEC)


async def main_loop():
    n = len(SYMBOLS)
    logger.info(f"Forex Radar v4 | {n} simboluri | Lead time {LEAD_TIME_SEC}s")

    start_msg = (
        "Forex Radar Bot v4 pornit! "
        + str(n) + " perechi Dukascopy. "
        + "Lead time: " + str(LEAD_TIME_SEC) + " secunde inainte de intrare."
    )
    await send_text(start_msg)

    while True:
        t0 = time.time()

        sess_ok, sess_r = is_session_allowed()
        if not sess_ok:
            logger.debug(f"Sesiune inchisa: {sess_r}")
            await asyncio.sleep(SCAN_INTERVAL)
            continue

        candidates = []
        for symbol in SYMBOLS:
            try:
                r = process_symbol(symbol)
                if r:
                    candidates.append(r)
            except Exception as e:
                logger.error(f"[{symbol}] {e}")
            await asyncio.sleep(0.1)

        elapsed = time.time() - t0
        logger.info(
            f"Ciclu: {len(candidates)}/{len(SYMBOLS)} candidati "
            f"({elapsed:.1f}s) | Stats: {checker.stats}"
        )

        if not candidates:
            await asyncio.sleep(max(0, SCAN_INTERVAL - elapsed))
            continue

        selected = select_best_signals(candidates, MAX_SIGNALS_PER_CYCLE)
        if not selected:
            await asyncio.sleep(max(0, SCAN_INTERVAL - elapsed))
            continue

        w = selected[0]
        s_ok2, s_r2 = is_session_allowed()

        passed, fails = is_ultra_premium_signal(
            n_candles         = w["n_candles"],
            is_real_data      = w["is_real_data"],
            fetch_latency     = w["fetch_latency"],
            hurst_value       = w["hurst"],
            regime            = w["regime"],
            regime_compatible = w["regime_ok"],
            regime_reason     = w["regime_reason"],
            fpt_prob          = w["prob"],
            dist_atr          = w["dist_atr"],
            expiry_score      = w["expiry_score"],
            atr_ratio         = w["atr_ratio"],
            stability_score   = w["stability_score"],
            spread_atr_ratio  = w["spread_atr_ratio"],
            session_allowed   = s_ok2,
            session_reason    = s_r2,
            symbol_allowed    = w["pf_ok"],
            symbol_pf_reason  = w["pf_reason"],
            cooldown_ok       = gate.can_emit_global(),
            is_rank_1         = True,
            confluence_score  = w["confluence_score"],
            symbol            = w["symbol"],
        )

        if passed:
            await emit_signal(w)
        else:
            logger.info(f"[{w['symbol']}] Checklist FAIL ({len(fails)} issues)")

        await asyncio.sleep(max(0, SCAN_INTERVAL - (time.time() - t0)))


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("Bot oprit.")
    except Exception as e:
        logger.critical(f"Eroare fatala: {e}", exc_info=True)
