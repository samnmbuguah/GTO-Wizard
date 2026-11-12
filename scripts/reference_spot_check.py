#!/usr/bin/env python3
"""
scripts/reference_spot_check.py

Compare our live solve endpoint against a CSV of independently obtained reference
values (e.g. values a human read from ZenoSolver's UI during normal use, a
published solution, or an open-source CFR oracle).

Columns (only `board` is required; blank reference cells are skipped):
    label, board, pot, effective_stack, rake_percent, rake_cap,
    ref_oop_ev, ref_ip_ev, ref_cbet_pct, ref_oop_check_pct, ref_bet_size_pct, source

`board` uses space-separated cards, e.g. "Ah Kd 2c".

Usage:
    python scripts/reference_spot_check.py docs/reference_spots.example.csv
    python scripts/reference_spot_check.py my.csv --base-url http://localhost:8000

IMPORTANT: do not point this at an automated scrape of ZenoSolver. Their Terms of
Use prohibit scripts/bots and benchmarking for a competing product. Use values
you are permitted to use.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


def num(row: Dict[str, str], key: str) -> Optional[float]:
    raw = (row.get(key) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def post(base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/api/solutions/live-solve/"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    rows: List[Dict[str, str]] = []
    with args.csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("board") or "").strip():
                rows.append(row)

    if not rows:
        print("No rows with a board found.")
        return 1

    print("=" * 100)
    print(" REFERENCE SPOT CHECK")
    print(f" Reference file : {args.csv_path}")
    print(f" Endpoint       : {args.base_url.rstrip('/')}/api/solutions/live-solve/")
    print("=" * 100)
    print(
        f"{'Spot':<22} {'Metric':<16} {'Reference':>10} {'Ours':>10} {'Delta':>10} {'Abs':>8}"
    )
    print("-" * 100)

    deltas: List[float] = []
    compared = 0

    for row in rows:
        board = row["board"].split()
        label = (row.get("label") or " ".join(board)).strip()
        pot = num(row, "pot") or 5.5
        stack = num(row, "effective_stack") or 100.0
        rake = num(row, "rake_percent") or 5.0
        cap = num(row, "rake_cap") or 0.6

        res = post(
            args.base_url,
            {
                "board": board,
                "pot": pot,
                "effective_stack": stack,
                "rake_percent": rake,
                "rake_cap": cap,
            },
        )

        ours = {
            "oop_ev": res.get("oop_ev"),
            "ip_ev": res.get("ip_ev"),
            "cbet_pct": (res.get("btn_cbet_frequency") or 0) * 100.0,
            "oop_check_pct": (res.get("bb_check_frequency") or 0) * 100.0,
            "bet_size_pct": (res.get("optimal_sizing") or 0) * 100.0,
        }

        for metric in ("oop_ev", "ip_ev", "cbet_pct", "oop_check_pct", "bet_size_pct"):
            ref = num(row, f"ref_{metric}")
            if ref is None or ours[metric] is None:
                continue
            delta = float(ours[metric]) - ref
            compared += 1
            if metric.endswith("_pct"):
                deltas.append(abs(delta))
            else:
                deltas.append(abs(delta))
            print(
                f"{label:<22} {metric:<16} {ref:>10.3f} {float(ours[metric]):>10.3f} "
                f"{delta:>+10.3f} {abs(delta):>8.3f}"
            )

    print("-" * 100)
    if deltas:
        print(f"Compared numeric fields : {compared}")
        print(f"Mean absolute delta     : {sum(deltas) / len(deltas):.4f}")
        print(f"Max absolute delta      : {max(deltas):.4f}")
        print(
            "\nNote: a single aggregate MAE mixes units (bb and percentage points).\n"
            "Read the per-metric columns; they are not directly comparable."
        )
    else:
        print("No reference values filled in. Add ref_* columns and re-run.")

    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
