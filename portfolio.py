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
    entries.append(
        {
            "type": args.type,
            "ticker": args.ticker.upper(),
            "price": args.price,
            "units": args.units,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    save(entries)
    total = args.price * args.units
    print(
        f"{args.type.upper()} {args.units}× {args.ticker.upper()} "
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


def main() -> None:
    parser = argparse.ArgumentParser(description="ETF portfolio tracker")
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="record a transaction")
    p_add.add_argument("--type", required=True, choices=["buy", "sell"])
    p_add.add_argument("--ticker", required=True, help="ETF ticker (e.g. VOO)")
    p_add.add_argument("--price", required=True, type=float, help="price per unit")
    p_add.add_argument("--units", required=True, type=float, help="number of units")
    p_add.set_defaults(func=add)

    p_show = sub.add_parser("show", help="list all transactions")
    p_show.set_defaults(func=show)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()