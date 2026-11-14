#!/usr/bin/env python3
"""
scripts/reference_spot_check.py

Compare our live solve against a CSV of independently obtained reference values.

Reference sources
-----------------
* `ref_*` columns  — values a human read from ZenoSolver's UI during normal use
  (or any other permitted source). **Do not** point this at an automated scrape
  of ZenoSolver: their Terms of Use prohibit scripts/bots and benchmarking.
* `oracle_*` columns — the same spot re-solved by a daemon started with
  `GTO_LEAF_NET=off`, i.e. exact showdown equity with no learned model. This is
  our own independent reference implementation (not Zeno).

`scripts/zeno_parity_harness.py solve` generates both sets of columns and the
capture sheet; this script only compares and reports.

Columns
-------
    label, board, pot, effective_stack, rake_percent, rake_cap,
    ante_bb, num_folded_players, use_bunching,
    ref_oop_ev, ref_ip_ev, ref_cbet_pct, ref_oop_check_pct, ref_bet_size_pct,
    source, oracle_*, our_*

Usage
-----
    python scripts/reference_spot_check.py docs/reference_spots.example.csv
    python scripts/reference_spot_check.py my.csv --port 9998 --source oracle
    python scripts/reference_spot_check.py my.csv --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import socket
import statistics
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

METRICS = ("oop_ev", "ip_ev", "cbet_pct", "oop_check_pct", "bet_size_pct")


def num(row: Dict[str, str], key: str) -> Optional[float]:
    raw = (row.get(key) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def as_bool(value: Optional[str], default: bool = True) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def post_http(base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/api/solutions/live-solve/"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def post_socket(port: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    sock = socket.create_connection(("127.0.0.1", port), timeout=120)
    try:
        sock.sendall((json.dumps(payload) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(1 << 20)
            if not chunk:
                break
            buf += chunk
    finally:
        sock.close()
    return json.loads(buf.decode().strip())


def build_payload(row: Dict[str, str]) -> Dict[str, Any]:
    board = row["board"].split()
    rake_percent = num(row, "rake_percent") if num(row, "rake_percent") is not None else 5.0
    rake_cap = num(row, "rake_cap") if num(row, "rake_cap") is not None else 0.6
    # Same preflop ranges the parity harness and the live API use.
    from backend.solutions.services.range_service import PreflopRangeService
    oop_range, ip_range = PreflopRangeService.get_spot_ranges(
        "BTN_vs_BB_SRP", rake_percent, rake_cap
    )
    payload: Dict[str, Any] = {
        "board": board,
        "oop_range": oop_range,
        "ip_range": ip_range,
        "pot": num(row, "pot") if num(row, "pot") is not None else 5.5,
        "effective_stack": num(row, "effective_stack") or 100.0,
        "rake_percent": rake_percent,
        "rake_cap": rake_cap,
        "ante_bb": num(row, "ante_bb") or 0.0,
        "num_folded_players": int(num(row, "num_folded_players") or 4),
        "use_bunching": as_bool(row.get("use_bunching"), True),
        "max_bets_per_node": 1,
        "target_dEV": 0.005,
        "max_iterations": 500,
        # Reproducible solve (no wall-clock cut-off) so a re-solve matches the
        # values recorded in the CSV.
        "deterministic": True,
    }
    return payload


def metrics_from(res: Dict[str, Any]) -> Dict[str, Optional[float]]:
    return {
        "oop_ev": res.get("oop_ev"),
        "ip_ev": res.get("ip_ev"),
        "cbet_pct": (res.get("btn_cbet_frequency") or 0) * 100.0,
        "oop_check_pct": (res.get("bb_check_frequency") or 0) * 100.0,
        "bet_size_pct": (res.get("optimal_sizing") or 0) * 100.0,
    }


def pearson(a: List[float], b: List[float]) -> Optional[float]:
    if len(a) < 3:
        return None
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    num_ = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da == 0 or db == 0:
        return None
    return num_ / (da * db)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--base-url", default="", help="HTTP API base URL (Django)")
    parser.add_argument("--port", type=int, default=0, help="Rust daemon port (direct)")
    parser.add_argument("--source", choices=("auto", "zeno", "oracle", "our"), default="auto")
    parser.add_argument("--report", default="", help="optional markdown report path")
    parser.add_argument("--max-ev-mae", type=float, default=None,
                        help="fail if the worst per-metric EV MAE exceeds this (bb)")
    parser.add_argument("--use-recorded", action="store_true",
                        help="compare the `our_*` columns recorded in the CSV instead of re-solving")
    args = parser.parse_args()

    rows: List[Dict[str, str]] = []
    with args.csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("board") or "").strip():
                rows.append(row)

    if not rows:
        print("No rows with a board found.")
        return 1

    source = args.source
    if source == "auto":
        has_zeno = any((r.get("ref_oop_ev") or "").strip() for r in rows)
        source = "zeno" if has_zeno else "oracle"
    prefix = {"zeno": "ref", "oracle": "oracle", "our": "our"}[source]
    source_label = {
        "zeno": "ZenoSolver (human capture)",
        "oracle": "exact-CFR oracle (GTO_LEAF_NET=off; not Zeno)",
        "our": "our own recorded values (re-solve reproducibility check)",
    }[source]

    print("=" * 100)
    print(" REFERENCE SPOT CHECK")
    print(f" Reference file : {args.csv_path}")
    print(f" Source         : {source_label}")
    if args.use_recorded:
        print(" Engine values  : recorded `our_*` columns (no re-solve)")
    elif args.port:
        print(f" Engine         : direct daemon on 127.0.0.1:{args.port}")
    else:
        print(f" Engine         : {args.base_url.rstrip('/')}/api/solutions/live-solve/")
    print("=" * 100)
    print(f"{'Spot':<24} {'Metric':<16} {'Reference':>10} {'Ours':>10} {'Delta':>10} {'Abs':>8}")
    print("-" * 100)

    pairs: Dict[str, List[Tuple[float, float]]] = {m: [] for m in METRICS}
    per_config: Dict[str, List[float]] = {}
    compared_rows = 0
    solved = 0

    for row in rows:
        board = row["board"].split()
        label = (row.get("label") or " ".join(board)).strip()
        cfg_label = (f"{row.get('rake_percent', '?')}%/{row.get('rake_cap', '?')} "
                     f"{row.get('effective_stack', '?')}bb ante {row.get('ante_bb', '0')}")

        if args.use_recorded:
            ours = {m: num(row, f"our_{m}") for m in METRICS}
        else:
            payload = build_payload(row)
            if args.port:
                res = post_socket(args.port, payload)
            else:
                res = post_http(args.base_url, payload)
            if "error" in res:
                print(f"  !! {label}: engine error {res['error']}")
                continue
            ours = metrics_from(res)
            solved += 1

        row_had_value = False
        for metric in METRICS:
            ref = num(row, f"{prefix}_{metric}")
            ours_val = ours.get(metric)
            if ref is None or ours_val is None:
                continue
            delta = float(ours_val) - ref
            pairs[metric].append((float(ours_val), ref))
            per_config.setdefault(cfg_label, []).append(abs(delta))
            row_had_value = True
            print(f"{label[:24]:<24} {metric:<16} {ref:>10.3f} {float(ours_val):>10.3f} "
                  f"{delta:>+10.3f} {abs(delta):>8.3f}")
        compared_rows += 1 if row_had_value else 0

    print("-" * 100)
    print(f"Spots compared            : {compared_rows}/{len(rows)}"
          + (f" ({solved} re-solved)" if not args.use_recorded else ""))
    if pairs["oop_ev"]:
        print(f"{'Metric':<14} {'n':>4} {'MAE':>9} {'medAE':>9} {'p90AE':>9} {'maxAE':>9} "
              f"{'bias':>9} {'r':>7}")
        print("-" * 100)
        worst_ev = 0.0
        summary = []
        for m in METRICS:
            vals = pairs[m]
            if not vals:
                continue
            ours_v = [a for a, _ in vals]
            refs_v = [b for _, b in vals]
            ae = [abs(a - b) for a, b in vals]
            mae = statistics.fmean(ae)
            bias = statistics.fmean(a - b for a, b in vals)
            med = statistics.median(ae)
            p90 = sorted(ae)[max(0, int(math.ceil(0.9 * len(ae))) - 1)]
            mx = max(ae)
            r = pearson(ours_v, refs_v)
            if m.endswith("_ev"):
                worst_ev = max(worst_ev, mae)
            print(f"{m:<14} {len(vals):>4} {mae:>9.4f} {med:>9.4f} {p90:>9.4f} {mx:>9.4f} "
                  f"{bias:>+9.4f} {('-' if r is None else f'{r:>7.3f}')}")
            summary.append((m, len(vals), mae, med, p90, mx, bias, r))
        print("-" * 100)
        print(f"Worst per-metric EV MAE   : {worst_ev:.4f} bb")
        if per_config:
            print("Per-config mean absolute delta (all compared metrics):")
            for cfg, errs in sorted(per_config.items()):
                print(f"  {cfg:<28} n={len(errs):<4} meanAE={statistics.fmean(errs):.4f} "
                      f"maxAE={max(errs):.4f}")
        if source == "oracle":
            print("\nNote: this comparison is against our own exact-CFR oracle, NOT against")
            print("      ZenoSolver. Capture Zeno values into the ref_* columns (see")
            print("      docs/zeno_capture_sheet.md) for the real side-by-side check.")
        elif source == "our":
            print("\nNote: this is a reproducibility check — the recorded `our_*` columns")
            print("      must match a fresh deterministic re-solve exactly (MAE 0.0000).")
    else:
        print("No reference values matched. Fill the ref_* (Zeno) or oracle_* columns.")
        worst_ev = None

    if args.report:
        Path(args.report).write_text(
            f"# Reference spot check\n\nSource: {source_label}\n\n"
            f"Spots compared: {compared_rows}/{len(rows)}\n",
            encoding="utf-8",
        )

    if args.max_ev_mae is not None and worst_ev is not None and worst_ev > args.max_ev_mae:
        print(f"FAIL: EV MAE {worst_ev:.4f} bb > tolerance {args.max_ev_mae:.4f} bb")
        return 1
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
