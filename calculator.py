"""
Core trading risk calculator logic.

Liquidation formulas follow dYdX Chain documentation:

  Isolated:  p' = (e - s * p) / (|s| * MMF - s)
  Cross:     p' = (e - s * p - MMR_o) / (|s| * MMF - s)

Where:
  e   = account equity (isolated: margin for this trade, cross: total equity)
  s   = signed position size (+qty for long, -qty for short)
  p   = entry price
  MMF = maintenance margin fraction (e.g. 0.03 for BTC)
  MMR_o = maintenance margin requirement from OTHER positions (cross only)
"""

# Default maintenance margin fractions (dYdX-style tiers)
DEFAULT_MMF = {
    "BTC": 0.03, "ETH": 0.03,
    "SOL": 0.05, "XRP": 0.05, "BNB": 0.05, "ADA": 0.05,
    "DOGE": 0.05, "AVAX": 0.05, "LINK": 0.05, "DOT": 0.05,
    "LTC": 0.05, "TRX": 0.05, "MATIC": 0.05,
    "NEAR": 0.10, "APT": 0.10, "UNI": 0.10, "SHIB": 0.10,
    "XLM": 0.10, "USDT": 0.10, "USDC": 0.10,
}

FALLBACK_MMF = 0.05


def get_mmf(symbol):
    """Get maintenance margin fraction for a symbol."""
    return DEFAULT_MMF.get(symbol.upper(), FALLBACK_MMF)


def calc_position_size(balance, risk_pct, leverage):
    """Calculate position size (margin allocated) from balance and risk %."""
    margin = balance * (risk_pct / 100)
    position_size = margin * leverage
    return margin, position_size


def calc_liquidation_isolated(entry_price, qty, side, margin, mmf):
    """
    dYdX isolated liquidation price.

    Formula: p' = (e - s * p) / (|s| * MMF - s)

    Where e = margin (collateral for this position),
          s = +qty (long) or -qty (short),
          p = entry_price.
    """
    s = qty if side == "long" else -qty
    e = margin
    p = entry_price

    denominator = abs(s) * mmf - s
    if denominator == 0:
        return 0

    liq = (e - s * p) / denominator
    return max(liq, 0)


def calc_liquidation_cross(entry_price, qty, side, total_equity, mmf, mmr_other=0):
    """
    dYdX cross-margin liquidation price.

    Formula: p' = (e - s * p - MMR_o) / (|s| * MMF - s)

    Where e = total account equity,
          s = +qty (long) or -qty (short),
          p = entry_price,
          MMR_o = sum of maintenance margin requirements from OTHER positions.
    """
    s = qty if side == "long" else -qty
    e = total_equity
    p = entry_price

    denominator = abs(s) * mmf - s
    if denominator == 0:
        return 0

    liq = (e - s * p - mmr_other) / denominator
    return max(liq, 0)


def calc_mmr(qty, price, mmf):
    """
    Maintenance margin requirement for a position at a given price.
    MMR = |s| * price * MMF
    """
    return abs(qty) * price * mmf


def calc_pnl(entry_price, current_price, qty, side):
    """Calculate unrealized P&L for a position."""
    if side == "long":
        return (current_price - entry_price) * qty
    else:
        return (entry_price - current_price) * qty


def calc_pnl_at_tp(entry_price, tp_price, margin, leverage, side):
    """Calculate P&L if take-profit is hit."""
    position_size = margin * leverage
    qty = position_size / entry_price

    if side == "long":
        pnl = (tp_price - entry_price) * qty
    else:
        pnl = (entry_price - tp_price) * qty

    roi = (pnl / margin) * 100 if margin > 0 else 0
    return pnl, roi


def calc_risk_reward(entry_price, tp_price, liq_price, side):
    """Calculate risk/reward ratio."""
    if side == "long":
        reward = tp_price - entry_price
        risk = entry_price - liq_price
    else:
        reward = entry_price - tp_price
        risk = liq_price - entry_price

    if risk <= 0:
        return float("inf")
    return reward / risk


def quick_calculate(balance, risk_pct, leverage, entry_price, tp_price, side, mode, mmf=None):
    """
    One-shot calculation returning all key metrics.
    Returns a dict with all computed values.
    """
    if mmf is None:
        mmf = FALLBACK_MMF

    margin, position_size = calc_position_size(balance, risk_pct, leverage)
    qty = position_size / entry_price

    if mode == "isolated":
        liq_price = calc_liquidation_isolated(entry_price, qty, side, margin, mmf)
    else:
        # Cross: total equity = balance, no other positions in standalone calc
        liq_price = calc_liquidation_cross(entry_price, qty, side, balance, mmf, mmr_other=0)

    pnl_at_tp, roi = calc_pnl_at_tp(entry_price, tp_price, margin, leverage, side)
    rr = calc_risk_reward(entry_price, tp_price, liq_price, side)

    # Max loss
    if mode == "isolated":
        max_loss = margin
    else:
        max_loss = balance  # cross can lose entire balance

    return {
        "margin": margin,
        "position_size": position_size,
        "qty": qty,
        "liquidation_price": liq_price,
        "pnl_at_tp": pnl_at_tp,
        "roi_pct": roi,
        "risk_reward": rr,
        "max_loss": max_loss,
        "side": side,
        "mode": mode,
        "leverage": leverage,
        "entry_price": entry_price,
        "tp_price": tp_price,
        "mmf": mmf,
    }
