"""Portfolio manager — tracks multiple trades with rebalancing."""

from calculator import (
    calc_position_size,
    calc_liquidation_price,
    calc_liquidation_cross,
    calc_pnl,
    calc_pnl_at_tp,
    calc_risk_reward,
)


class Trade:
    _next_id = 1

    def __init__(self, symbol, side, mode, entry_price, tp_price, margin, leverage):
        self.id = Trade._next_id
        Trade._next_id += 1
        self.symbol = symbol.upper()
        self.side = side          # "long" or "short"
        self.mode = mode          # "isolated" or "cross"
        self.entry_price = entry_price
        self.tp_price = tp_price
        self.margin = margin      # collateral allocated
        self.leverage = leverage
        self.position_size = margin * leverage
        self.qty = self.position_size / entry_price
        self.is_open = True
        self.realized_pnl = 0.0

    def unrealized_pnl(self, current_price):
        if not self.is_open:
            return 0
        return calc_pnl(self.entry_price, current_price, self.qty, self.side)

    def pnl_at_tp(self):
        return calc_pnl_at_tp(
            self.entry_price, self.tp_price, self.margin, self.leverage, self.side
        )

    def to_dict(self, current_price=None):
        pnl_tp, roi_tp = self.pnl_at_tp()
        d = {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "mode": self.mode,
            "entry": self.entry_price,
            "tp": self.tp_price,
            "margin": self.margin,
            "leverage": self.leverage,
            "size": self.position_size,
            "qty": self.qty,
            "pnl_at_tp": pnl_tp,
            "roi_at_tp": roi_tp,
            "open": self.is_open,
        }
        if current_price is not None:
            d["current_price"] = current_price
            d["unrealized_pnl"] = self.unrealized_pnl(current_price)
        return d


class Portfolio:
    def __init__(self, balance):
        self.initial_balance = balance
        self.balance = balance          # available + margin in trades
        self.realized_pnl = 0.0
        self.trades = []

    @property
    def total_balance(self):
        """Balance including realized P&L."""
        return self.initial_balance + self.realized_pnl

    @property
    def open_trades(self):
        return [t for t in self.trades if t.is_open]

    @property
    def isolated_margin_used(self):
        return sum(t.margin for t in self.open_trades if t.mode == "isolated")

    @property
    def cross_margin_used(self):
        return sum(t.margin for t in self.open_trades if t.mode == "cross")

    @property
    def total_margin_used(self):
        return self.isolated_margin_used + self.cross_margin_used

    @property
    def available_balance(self):
        return self.total_balance - self.total_margin_used

    def add_trade(self, symbol, side, mode, entry_price, tp_price, risk_pct, leverage):
        """Add a new trade. Returns the Trade object or raises ValueError."""
        margin, position_size = calc_position_size(self.total_balance, risk_pct, leverage)

        if margin > self.available_balance:
            raise ValueError(
                f"Insufficient balance. Need ${margin:.2f} margin but only "
                f"${self.available_balance:.2f} available."
            )

        trade = Trade(symbol, side, mode, entry_price, tp_price, margin, leverage)
        self.trades.append(trade)
        return trade

    def add_trade_fixed_margin(self, symbol, side, mode, entry_price, tp_price, margin, leverage):
        """Add trade with a fixed margin amount instead of risk %."""
        if margin > self.available_balance:
            raise ValueError(
                f"Insufficient balance. Need ${margin:.2f} margin but only "
                f"${self.available_balance:.2f} available."
            )

        trade = Trade(symbol, side, mode, entry_price, tp_price, margin, leverage)
        self.trades.append(trade)
        return trade

    def close_trade(self, trade_id, close_price):
        """Close a trade at the given price, realize P&L."""
        trade = self._get_trade(trade_id)
        if not trade.is_open:
            raise ValueError(f"Trade #{trade_id} is already closed.")

        pnl = trade.unrealized_pnl(close_price)
        trade.realized_pnl = pnl
        trade.is_open = False
        self.realized_pnl += pnl
        return pnl

    def get_liquidation_price(self, trade_id):
        """Get liquidation price for a specific trade."""
        trade = self._get_trade(trade_id)

        if trade.mode == "isolated":
            return calc_liquidation_price(
                trade.entry_price, trade.leverage, trade.side, "isolated"
            )
        else:
            # Cross margin: available balance (minus other isolated margins) backs this
            available = self.available_balance
            return calc_liquidation_cross(
                trade.entry_price, trade.leverage, trade.side,
                trade.margin, available
            )

    def get_trade_summary(self, trade_id, current_price=None):
        """Full summary for one trade."""
        trade = self._get_trade(trade_id)
        liq = self.get_liquidation_price(trade_id)
        rr = calc_risk_reward(trade.entry_price, trade.tp_price, liq, trade.side)

        d = trade.to_dict(current_price)
        d["liquidation_price"] = liq
        d["risk_reward"] = rr

        if trade.mode == "isolated":
            d["max_loss"] = trade.margin
        else:
            d["max_loss"] = self.total_balance  # cross can wipe balance
        return d

    def portfolio_summary(self, prices=None):
        """
        Overall portfolio summary.
        prices: dict of {symbol: current_price} for unrealized P&L calc.
        """
        total_unrealized = 0.0
        trade_summaries = []

        for trade in self.open_trades:
            cp = prices.get(trade.symbol) if prices else None
            summary = self.get_trade_summary(trade.id, cp)
            if cp is not None:
                total_unrealized += summary.get("unrealized_pnl", 0)
            trade_summaries.append(summary)

        return {
            "initial_balance": self.initial_balance,
            "total_balance": self.total_balance,
            "available_balance": self.available_balance,
            "total_margin_used": self.total_margin_used,
            "isolated_margin": self.isolated_margin_used,
            "cross_margin": self.cross_margin_used,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": total_unrealized,
            "equity": self.total_balance + total_unrealized,
            "open_trades": len(self.open_trades),
            "total_trades": len(self.trades),
            "trades": trade_summaries,
        }

    def rebalance_summary(self, prices=None):
        """
        Recalculate all cross-margin liquidation prices after portfolio changes.
        This is called automatically — cross positions share margin, so adding/removing
        a trade changes liquidation prices for all cross positions.
        """
        results = []
        for trade in self.open_trades:
            if trade.mode == "cross":
                new_liq = self.get_liquidation_price(trade.id)
                cp = prices.get(trade.symbol) if prices else None
                results.append({
                    "id": trade.id,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "entry": trade.entry_price,
                    "new_liquidation": new_liq,
                    "current_price": cp,
                })
        return results

    def _get_trade(self, trade_id):
        for t in self.trades:
            if t.id == trade_id:
                return t
        raise ValueError(f"Trade #{trade_id} not found.")
