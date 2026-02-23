#!/usr/bin/env python3
"""Crypto Trading Risk Calculator — Interactive CLI."""

import sys
from calculator import quick_calculate, get_mmf, DEFAULT_MMF, FALLBACK_MMF
from portfolio import Portfolio
from prices import fetch_prices, fetch_price_single, get_supported_symbols


# ── Formatting helpers ───────────────────────────────────────────────

def fmt_usd(val):
    if abs(val) >= 1:
        return f"${val:,.2f}"
    return f"${val:.6f}"


def fmt_pct(val):
    return f"{val:+.2f}%"


def color(text, code):
    """ANSI color: 32=green, 31=red, 33=yellow, 36=cyan, 0=reset."""
    return f"\033[{code}m{text}\033[0m"


def green(text):
    return color(text, 32)


def red(text):
    return color(text, 31)


def yellow(text):
    return color(text, 33)


def cyan(text):
    return color(text, 36)


def pnl_color(val, text=None):
    text = text or fmt_usd(val)
    return green(text) if val >= 0 else red(text)


def divider(title=""):
    if title:
        print(f"\n{'─' * 3} {cyan(title)} {'─' * (50 - len(title))}")
    else:
        print(f"{'─' * 56}")


# ── Input helpers ────────────────────────────────────────────────────

def input_float(prompt, min_val=None, max_val=None, allow_empty=False):
    while True:
        raw = input(prompt).strip()
        if allow_empty and raw == "":
            return None
        try:
            val = float(raw)
            if min_val is not None and val < min_val:
                print(f"  Must be >= {min_val}")
                continue
            if max_val is not None and val > max_val:
                print(f"  Must be <= {max_val}")
                continue
            return val
        except ValueError:
            print("  Enter a valid number.")


def input_int(prompt, min_val=None, max_val=None):
    while True:
        raw = input(prompt).strip()
        try:
            val = int(raw)
            if min_val is not None and val < min_val:
                print(f"  Must be >= {min_val}")
                continue
            if max_val is not None and val > max_val:
                print(f"  Must be <= {max_val}")
                continue
            return val
        except ValueError:
            print("  Enter a valid integer.")


def input_choice(prompt, choices):
    choices_lower = [c.lower() for c in choices]
    while True:
        raw = input(prompt).strip().lower()
        if raw in choices_lower:
            return raw
        print(f"  Choose one of: {', '.join(choices)}")


# ── Display functions ────────────────────────────────────────────────

def display_prices(prices_dict, changes_dict):
    divider("Live Crypto Prices (USD)")
    print(f"  {'Symbol':<8} {'Price':>14} {'24h Change':>12}")
    print(f"  {'─' * 8} {'─' * 14} {'─' * 12}")
    for symbol in sorted(prices_dict.keys()):
        price = prices_dict[symbol]
        change = changes_dict.get(symbol, 0) or 0
        change_str = fmt_pct(change)
        change_colored = green(change_str) if change >= 0 else red(change_str)
        print(f"  {symbol:<8} {fmt_usd(price):>14} {change_colored:>23}")
    print()


def display_calc_result(result):
    divider("Calculation Result")
    side_str = green("LONG") if result["side"] == "long" else red("SHORT")
    mode_str = yellow("CROSS") if result["mode"] == "cross" else cyan("ISOLATED")
    mmf_pct = result.get("mmf", 0) * 100

    print(f"  Side: {side_str}  |  Mode: {mode_str}  |  Leverage: {result['leverage']}x")
    print(f"  Entry Price:       {fmt_usd(result['entry_price'])}")
    print(f"  Take Profit:       {fmt_usd(result['tp_price'])}")
    print(f"  Maint. Margin:     {mmf_pct:.1f}%  (dYdX MMF)")
    print()
    print(f"  Margin (Risk):     {fmt_usd(result['margin'])}")
    print(f"  Position Size:     {fmt_usd(result['position_size'])}")
    print(f"  Quantity:          {result['qty']:.6f}")
    print()
    print(f"  Liquidation Price: {red(fmt_usd(result['liquidation_price']))}")
    print(f"  P&L at TP:         {pnl_color(result['pnl_at_tp'])}")
    print(f"  ROI at TP:         {pnl_color(result['roi_pct'], fmt_pct(result['roi_pct']))}")
    print(f"  Risk/Reward:       {result['risk_reward']:.2f}")
    print(f"  Max Loss:          {red(fmt_usd(result['max_loss']))}")
    print()


def display_trade(summary):
    side_str = green("LONG") if summary["side"] == "long" else red("SHORT")
    mode_str = yellow("CROSS") if summary["mode"] == "cross" else cyan("ISOLATED")
    status = green("OPEN") if summary["open"] else red("CLOSED")

    mmf_pct = summary.get("mmf", 0) * 100
    print(f"  #{summary['id']} {summary['symbol']} {side_str} {mode_str} {summary['leverage']}x  [{status}]  MMF:{mmf_pct:.0f}%")
    print(f"     Entry: {fmt_usd(summary['entry'])}  |  TP: {fmt_usd(summary['tp'])}")
    print(f"     Margin: {fmt_usd(summary['margin'])}  |  Size: {fmt_usd(summary['size'])}  |  Qty: {summary['qty']:.6f}")

    if "liquidation_price" in summary:
        print(f"     Liquidation: {red(fmt_usd(summary['liquidation_price']))}")

    pnl_tp, roi_tp = summary["pnl_at_tp"], summary["roi_at_tp"]
    print(f"     P&L at TP: {pnl_color(pnl_tp)}  ({pnl_color(roi_tp, fmt_pct(roi_tp))})")

    if "unrealized_pnl" in summary and summary.get("current_price") is not None:
        upnl = summary["unrealized_pnl"]
        cp = summary["current_price"]
        print(f"     Current: {fmt_usd(cp)}  |  Unrealized P&L: {pnl_color(upnl)}")

    if "risk_reward" in summary:
        print(f"     Risk/Reward: {summary['risk_reward']:.2f}")
    print()


def display_portfolio(port_summary):
    divider("Portfolio Summary")
    s = port_summary
    print(f"  Initial Balance:   {fmt_usd(s['initial_balance'])}")
    print(f"  Total Balance:     {fmt_usd(s['total_balance'])}")
    print(f"  Available:         {fmt_usd(s['available_balance'])}")
    print(f"  Equity:            {fmt_usd(s['equity'])}")
    print()
    print(f"  Margin Used:       {fmt_usd(s['total_margin_used'])}  "
          f"(Isolated: {fmt_usd(s['isolated_margin'])} | Cross: {fmt_usd(s['cross_margin'])})")
    print(f"  Realized P&L:      {pnl_color(s['realized_pnl'])}")
    print(f"  Unrealized P&L:    {pnl_color(s['unrealized_pnl'])}")
    print(f"  Open Trades:       {s['open_trades']} / {s['total_trades']}")
    print()

    if s["trades"]:
        divider("Open Positions")
        for t in s["trades"]:
            display_trade(t)


# ── Menu actions ─────────────────────────────────────────────────────

def action_view_prices(portfolio, cached_prices):
    print("\n  Fetching prices...")
    result, changes = fetch_prices()
    if result is None:
        print(red(f"  Error fetching prices: {changes}"))
        return cached_prices
    display_prices(result, changes)
    return result


def action_add_trade(portfolio, cached_prices):
    divider("Add New Trade")

    symbol = input("  Symbol (e.g. BTC, ETH): ").strip().upper()
    supported = get_supported_symbols()
    if symbol not in supported:
        print(f"  Supported: {', '.join(supported)}")
        return

    side = input_choice("  Side (long/short): ", ["long", "short"])
    mode = input_choice("  Margin mode (isolated/cross): ", ["isolated", "cross"])
    leverage = input_float("  Leverage (e.g. 10): ", min_val=1, max_val=200)

    # Offer to use live price
    use_live = input_choice("  Use live price for entry? (y/n): ", ["y", "n"])
    if use_live == "y":
        print("  Fetching price...")
        price, err = fetch_price_single(symbol)
        if err:
            print(red(f"  Error: {err}"))
            return
        print(f"  Current {symbol} price: {fmt_usd(price)}")
        entry_price = price
    else:
        entry_price = input_float("  Entry price: ", min_val=0.0000001)

    tp_price = input_float("  Take-profit price: ", min_val=0.0000001)

    # Validate TP direction
    if side == "long" and tp_price <= entry_price:
        print(red("  Warning: TP is below entry for a LONG. Continuing anyway."))
    elif side == "short" and tp_price >= entry_price:
        print(red("  Warning: TP is above entry for a SHORT. Continuing anyway."))

    print(f"\n  Available balance: {fmt_usd(portfolio.available_balance)}")
    margin_mode = input_choice("  Set risk by (pct/amount): ", ["pct", "amount"])

    if margin_mode == "pct":
        risk_pct = input_float("  Risk % of balance: ", min_val=0.01, max_val=100)
        try:
            trade = portfolio.add_trade(
                symbol, side, mode, entry_price, tp_price, risk_pct, leverage
            )
        except ValueError as e:
            print(red(f"  {e}"))
            return
    else:
        margin = input_float("  Margin amount ($): ", min_val=0.01)
        try:
            trade = portfolio.add_trade_fixed_margin(
                symbol, side, mode, entry_price, tp_price, margin, leverage
            )
        except ValueError as e:
            print(red(f"  {e}"))
            return

    print(green(f"\n  Trade #{trade.id} opened!"))
    summary = portfolio.get_trade_summary(trade.id)
    display_trade(summary)

    # Show rebalancing info for cross trades
    rebalanced = portfolio.rebalance_summary(cached_prices)
    if rebalanced:
        divider("Cross Margin Rebalanced")
        for r in rebalanced:
            print(f"  #{r['id']} {r['symbol']} {r['side'].upper()} — "
                  f"New Liquidation: {red(fmt_usd(r['new_liquidation']))}")
        print()


def action_view_trades(portfolio, cached_prices):
    if not portfolio.open_trades:
        print(yellow("\n  No open trades."))
        return

    # Try to use cached or fetch fresh prices
    prices = cached_prices or {}
    divider("Open Trades")
    for trade in portfolio.open_trades:
        cp = prices.get(trade.symbol)
        summary = portfolio.get_trade_summary(trade.id, cp)
        display_trade(summary)


def action_close_trade(portfolio, cached_prices):
    if not portfolio.open_trades:
        print(yellow("\n  No open trades to close."))
        return

    print("\n  Open trades:")
    for t in portfolio.open_trades:
        print(f"    #{t.id} {t.symbol} {t.side.upper()} @ {fmt_usd(t.entry_price)}")

    trade_id = input_int("  Trade ID to close: ", min_val=1)

    use_live = input_choice("  Use live price to close? (y/n): ", ["y", "n"])
    if use_live == "y":
        trade = portfolio._get_trade(trade_id)
        print("  Fetching price...")
        price, err = fetch_price_single(trade.symbol)
        if err:
            print(red(f"  Error: {err}"))
            return
        close_price = price
        print(f"  Current price: {fmt_usd(close_price)}")
    else:
        close_price = input_float("  Close price: ", min_val=0.0000001)

    try:
        pnl = portfolio.close_trade(trade_id, close_price)
    except ValueError as e:
        print(red(f"  {e}"))
        return

    print(f"\n  Trade #{trade_id} closed!")
    print(f"  Realized P&L: {pnl_color(pnl)}")
    print(f"  New Balance:   {fmt_usd(portfolio.total_balance)}")

    # Show rebalancing
    rebalanced = portfolio.rebalance_summary(cached_prices)
    if rebalanced:
        divider("Cross Margin Rebalanced")
        for r in rebalanced:
            print(f"  #{r['id']} {r['symbol']} {r['side'].upper()} — "
                  f"New Liquidation: {red(fmt_usd(r['new_liquidation']))}")
        print()


def action_portfolio_summary(portfolio, cached_prices):
    prices = cached_prices or {}
    refresh = "n"
    if portfolio.open_trades:
        refresh = input_choice("  Refresh live prices? (y/n): ", ["y", "n"])
    if refresh == "y":
        print("  Fetching prices...")
        result, _ = fetch_prices()
        if result:
            prices = result
    summary = portfolio.portfolio_summary(prices)
    display_portfolio(summary)


def action_quick_calc(portfolio):
    divider("Quick Risk Calculator")
    symbol = input("  Symbol (e.g. BTC, ETH — or press Enter to skip): ").strip().upper()
    default_mmf = get_mmf(symbol) if symbol else FALLBACK_MMF
    print(f"  Default MMF for {symbol or 'unknown'}: {default_mmf * 100:.1f}%")
    custom_mmf = input_float(
        f"  Maintenance margin % (Enter for {default_mmf * 100:.1f}%): ",
        min_val=0.1, max_val=100, allow_empty=True
    )
    mmf = (custom_mmf / 100) if custom_mmf is not None else default_mmf

    balance = input_float("  Balance ($): ", min_val=0.01)
    risk_pct = input_float("  Risk (% of balance): ", min_val=0.01, max_val=100)
    leverage = input_float("  Leverage: ", min_val=1, max_val=200)
    entry_price = input_float("  Entry price: ", min_val=0.0000001)
    tp_price = input_float("  Take-profit price: ", min_val=0.0000001)
    side = input_choice("  Side (long/short): ", ["long", "short"])
    mode = input_choice("  Margin mode (isolated/cross): ", ["isolated", "cross"])

    result = quick_calculate(balance, risk_pct, leverage, entry_price, tp_price, side, mode, mmf)
    display_calc_result(result)


# ── Main loop ────────────────────────────────────────────────────────

def main():
    print(cyan(r"""
   ╔══════════════════════════════════════════════╗
   ║     Crypto Trading Risk Calculator           ║
   ║     ─────────────────────────────             ║
   ║     Cross & Isolated Margin Modes             ║
   ║     Multi-Trade Portfolio Tracking            ║
   ╚══════════════════════════════════════════════╝
    """))

    balance = input_float("  Enter starting balance ($): ", min_val=0.01)
    portfolio = Portfolio(balance)
    cached_prices = {}

    print(green(f"\n  Portfolio initialized with {fmt_usd(balance)}"))

    while True:
        print(f"\n  {cyan('═' * 40)}")
        print(f"  Available: {fmt_usd(portfolio.available_balance)} / {fmt_usd(portfolio.total_balance)}")
        print(f"  Open trades: {len(portfolio.open_trades)}")
        print(f"  {cyan('═' * 40)}")
        print()
        print("  1. View Prices        (top 20 cryptos)")
        print("  2. Add Trade")
        print("  3. View Open Trades")
        print("  4. Close Trade")
        print("  5. Portfolio Summary")
        print("  6. Quick Calculate     (standalone)")
        print("  7. Set New Balance")
        print("  0. Exit")
        print()

        choice = input("  > ").strip()

        if choice == "1":
            cached_prices = action_view_prices(portfolio, cached_prices) or cached_prices
        elif choice == "2":
            action_add_trade(portfolio, cached_prices)
        elif choice == "3":
            action_view_trades(portfolio, cached_prices)
        elif choice == "4":
            action_close_trade(portfolio, cached_prices)
        elif choice == "5":
            action_portfolio_summary(portfolio, cached_prices)
        elif choice == "6":
            action_quick_calc(portfolio)
        elif choice == "7":
            new_bal = input_float("  New balance ($): ", min_val=0.01)
            portfolio.initial_balance = new_bal
            portfolio.realized_pnl = 0.0
            print(green(f"  Balance reset to {fmt_usd(new_bal)}"))
        elif choice == "0":
            print(cyan("\n  Goodbye!\n"))
            sys.exit(0)
        else:
            print(yellow("  Invalid choice."))


if __name__ == "__main__":
    main()
