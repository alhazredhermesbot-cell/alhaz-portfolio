#!/usr/bin/env python3
"""Append ETF transactions to ~/.config/alhaz-portfolio/portfolio.json."""

import argparse
import json
import os
from datetime import datetime, timezone

STORE = os.path.expanduser("~/.config/alhaz-portfolio/portfolio.json")


def load() -> list:
    if not os.path.exists(STORE):
        return []
    with open(STORE) as f:
        return json.load(f)


def save(entries: list) -> None:
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    with open(STORE, "w") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")


def add(args: argparse.Namespace) -> None:
    entries = load()
    txn_type = "sell" if args.sell else "buy"
    entries.append(
        {
            "type": txn_type,
            "ticker": args.ticker.upper(),
            "price": args.price,
            "units": args.units,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    save(entries)
    total = args.price * args.units
    print(
        f"{txn_type.upper()} {args.units}× {args.ticker.upper()} "
        f"@ ${args.price:.2f} = ${total:,.2f}"
    )


def show(_args: argparse.Namespace) -> None:
    entries = load()
    if not entries:
        print("No transactions yet.")
        return
    for e in entries:
        total = e["price"] * e["units"]
        print(
            f"{e['timestamp'][:10]}  {e['type']:4s}  {e['units']:6.2f}× "
            f"{e['ticker']:6s}  @ ${e['price']:8.2f}  = ${total:,.2f}"
        )


def position(_args: argparse.Namespace) -> None:
    entries = load()
    if not entries:
        print("No transactions yet.")
        return

    # Aggregate per ticker
    tickers: dict[str, dict] = {}
    for e in entries:
        t = e["ticker"].upper()
        if t not in tickers:
            tickers[t] = {"buys": [], "sells": []}
        tickers[t][e["type"] + "s"].append(e)

    # Fetch current prices — try .AX (ASX) first, fall back to bare (US)
    import yfinance as yf

    ax_tickers = [f"{t}.AX" for t in tickers]
    data = yf.download(ax_tickers, period="5d", progress=False, auto_adjust=True)

    # For any tickers that returned no data, retry without .AX suffix
    us_tickers = []
    for t in tickers:
        yf_t = f"{t}.AX"
        try:
            if yf_t not in data["Close"] or data["Close"][yf_t].dropna().empty:
                us_tickers.append(t)
        except KeyError:
            us_tickers.append(t)

    us_data = None
    if us_tickers:
        us_data = yf.download(us_tickers, period="5d", progress=False, auto_adjust=True)

    positions = []
    for t, txns in tickers.items():
        total_buy_units = sum(e["units"] for e in txns["buys"])
        total_buy_cost = sum(e["price"] * e["units"] for e in txns["buys"])
        total_sell_units = sum(e["units"] for e in txns["sells"])

        net_units = total_buy_units - total_sell_units
        if net_units <= 0:
            continue

        avg_cost = total_buy_cost / total_buy_units
        cost_basis = avg_cost * net_units

        # Get current price — try .AX first, then bare ticker
        yf_t = f"{t}.AX"
        current_price = None
        for source in [(data, yf_t), (us_data, t)]:
            df, col = source
            if df is None:
                continue
            try:
                if col in df["Close"] and not df["Close"][col].dropna().empty:
                    current_price = float(df["Close"][col].dropna().iloc[-1])
                    break
            except (KeyError, IndexError):
                continue

        current_value = net_units * current_price if current_price else None
        pnl = current_value - cost_basis if current_value else None
        pnl_pct = (pnl / cost_basis * 100) if pnl else None

        positions.append(
            {
                "ticker": t,
                "units": net_units,
                "avg_cost": avg_cost,
                "cost_basis": cost_basis,
                "current_price": current_price,
                "current_value": current_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
            }
        )

    if not positions:
        print("No open positions.")
        return

    # Display per ticker
    print(f"{'Ticker':>6s}  {'Units':>7s}  {'Avg Cost':>9s}  {'Price':>9s}  {'Value':>12s}  {'P/L':>10s}  {'%':>7s}")
    print("-" * 80)

    total_cost = 0.0
    total_value = 0.0

    for p in positions:
        price_str = f"${p['current_price']:>8.2f}" if p["current_price"] else "     N/A"
        value_str = f"${p['current_value']:>11,.2f}" if p["current_value"] else "        N/A"
        pnl_str = f"${p['pnl']:>9,.2f}" if p["pnl"] is not None else "      N/A"
        pct_str = f"{p['pnl_pct']:>+6.1f}%" if p["pnl_pct"] is not None else "   N/A"

        print(
            f"{p['ticker']:>6s}  {p['units']:>7.2f}  "
            f"${p['avg_cost']:>8.2f}  {price_str}  {value_str}  {pnl_str}  {pct_str}"
        )
        total_cost += p["cost_basis"]
        if p["current_value"]:
            total_value += p["current_value"]

    # Overall
    if total_cost > 0:
        total_pnl = total_value - total_cost
        total_pct = (total_pnl / total_cost * 100) if total_cost else 0
        print("-" * 80)
        print(
            f"{'TOTAL':>6s}  {'':>7s}  {'':>9s}  {'':>9s}  "
            f"${total_value:>11,.2f}  ${total_pnl:>9,.2f}  {total_pct:>+6.1f}%"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="ETF portfolio tracker")
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="record a buy (use --sell to record a sale)")
    p_add.add_argument("ticker", help="ETF ticker (e.g. VOO)")
    p_add.add_argument("price", type=float, help="price per unit")
    p_add.add_argument("units", type=float, help="number of units")
    p_add.add_argument("--sell", action="store_true", help="record as a sell instead of buy")
    p_add.set_defaults(func=add)

    p_show = sub.add_parser("show", help="list all transactions")
    p_show.set_defaults(func=show)

    p_pos = sub.add_parser("position", help="current positions with P/L")
    p_pos.set_defaults(func=position)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()