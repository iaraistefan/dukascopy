"(avg_deviation / atr)
    
    return float(np.clip(stability, 0.0, 1.0))

def compute_rsi_confirmation(df: pd.DataFrame, direction: str) -> float:
    """Interpoleaza liniar scorul RSI bazat pe zonele de overbought/oversold."""
    rsi_series = compute_rsi(df["close"])
    rsi = float(rsi_series.iloc[-1])
    
    if direction == "CALL":
        if rsi <= RSI_OVERSOLD:
            return 1.0
        if rsi <= 50.0:
            return 0.5 + 0.5 * ((50.0 - rsi) / (50.0 - RSI_OVERSOLD))
        return max(0.0, 0.5 - 0.5 * ((rsi - 50.0) / (RSI_OVERBOUGHT - 50.0)))
    else:  # PUT
        if rsi >= RSI_OVERBOUGHT:
            return 1.0
        if rsi >= 50.0:
            return 0.5 + 0.5 * ((rsi - 50.0) / (RSI_OVERBOUGHT - 50.0))
        return max(0.0, 0.5 - 0.5 * ((50.0 - rsi) / (50.0 - RSI_OVERSOLD)))

def compute_confluence_score(df: pd.DataFrame, direction: str) -> tuple[float, float, float]:
    """Combina si pondereaza stabilitatea si RSI-ul intr-un scor final."""
    stab = compute_stability_score(df)
    rsi_score = compute_rsi_confirmation(df, direction)
    
    conf = (stab * CONFLUENCE_STABILITY_WEIGHT) + (rsi_score * CONFLUENCE_RSI_WEIGHT)
    
    logger.debug(f"Confluenta: Stab={stab:.3f} RSI={rsi_score:.3f} -> Total={conf:.3f}")
    
    return float(conf), float(stab), float(rsi_score)
