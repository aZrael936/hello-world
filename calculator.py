"""Core trading risk calculator logic."""


def calc_position_size(balance, risk_pct, leverage):
    """Calculate position size (margin allocated) from balance and risk %."""
    margin = balance * (risk_pct / 100)
    position_size = margin * leverage
    return margin, position_size


def calc_liquidation_price(entry_price, leverage, side, mode, balance=0, total_margin_used=0):
    """
    Calculate liquidation price.

    For ISOLATED mode:
        Long:  liq = entry * (1 - 1/leverage)
        Short: liq = entry * (1 + 1/leverage)

    For CROSS mode:
        Uses available balance as additional margin buffer.
        Long:  liq = entry - (available_balance / (position_size / entry))
        Short: liq = entry + (available_balance / (position_size / entry))
        Simplified with leverage math.
    """
    if mode == "isolated":
        if side == "long":
            return entry_price * (1 - 1 / leverage)
        else:
            return entry_price * (1 + 1 / leverage)
    else:
        # Cross margin: entire available balance acts as margin
        # available = balance - total_margin_used (from other isolated positions)
        # effective_leverage is reduced because more margin backs the position
        available = max(balance - total_margin_used, 0)
        margin_for_this = available  # all free balance backs cross positions
        if margin_for_this <= 0:
            # No available balance, same as isolated
            if side == "long":
                return entry_price * (1 - 1 / leverage)
            else:
                return entry_price * (1 + 1 / leverage)

        # position_value = margin_for_this * leverage (but we use the trade's own margin * leverage)
        # For cross, the liquidation distance is: margin_for_this / (position_qty)
        # position_qty = (trade_margin * leverage) / entry_price
        # But we don't have trade_margin here directly — caller passes what we need
        # Simpler: effective_margin_ratio = available / (trade_margin * leverage)
        # liq_long  = entry * (1 - effective_margin_ratio)
        # liq_short = entry * (1 + effective_margin_ratio)
        # We'll handle this in the Portfolio class where we have full context
        # Fallback for standalone calc:
        if side == "long":
            return entry_price * (1 - 1 / leverage)
        else:
            return entry_price * (1 + 1 / leverage)


def calc_liquidation_cross(entry_price, leverage, side, trade_margin, available_balance):
    """
    Cross-margin liquidation with full available balance as buffer.

    available_balance = total_balance - sum(isolated margins) - sum(cross margins)
    The full available_balance + trade_margin backs this position.
    """
    effective_margin = trade_margin + available_balance
    position_size = trade_margin * leverage
    qty = position_size / entry_price

    if qty == 0:
        return 0

    if side == "long":
        # Liquidation when loss = effective_margin
        # (entry - liq) * qty = effective_margin
        liq = entry_price - (effective_margin / qty)
    else:
        # (liq - entry) * qty = effective_margin
        liq = entry_price + (effective_margin / qty)

    return max(liq, 0)


def calc_pnl(entry_price, current_price, qty, side, leverage=1):
    """Calculate unrealized P&L for a position."""
    if side == "long":
        pnl = (current_price - entry_price) * qty
    else:
        pnl = (entry_price - current_price) * qty
    return pnl


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


def quick_calculate(balance, risk_pct, leverage, entry_price, tp_price, side, mode):
    """
    One-shot calculation returning all key metrics.
    Returns a dict with all computed values.
    """
    margin, position_size = calc_position_size(balance, risk_pct, leverage)
    qty = position_size / entry_price

    if mode == "isolated":
        liq_price = calc_liquidation_price(entry_price, leverage, side, "isolated")
    else:
        # For standalone quick calc, cross uses full balance as buffer
        liq_price = calc_liquidation_cross(
            entry_price, leverage, side, margin, balance - margin
        )

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
    }
