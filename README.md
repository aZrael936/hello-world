# Crypto Trading Risk Calculator

A terminal-based trading risk calculator and simulator for cryptocurrency futures trading.

## Features

- **Risk Calculator**: Input balance, risk %, leverage, entry price, and TP to see profit/loss and liquidation price
- **Multiple Trades**: Add multiple open trades and see portfolio-level rebalancing
- **Cross & Isolated Margin**: Supports both margin modes with correct liquidation math
- **Live Prices**: Fetches top 20 crypto prices from CoinGecko's free API
- **Trade Simulation**: Simulate trades against live prices

## Setup

```bash
pip install -r requirements.txt
python main.py
```

## Usage

Run `python main.py` and follow the interactive menu:

1. **View Prices** — Fetch and display top 20 crypto prices
2. **Add Trade** — Open a new position (long/short, cross/isolated)
3. **View Trades** — See all open trades with live P&L
4. **Close Trade** — Close a position and realize P&L
5. **Portfolio Summary** — See total balance, margin usage, unrealized P&L
6. **Quick Calculate** — One-off risk calculation without opening a trade
