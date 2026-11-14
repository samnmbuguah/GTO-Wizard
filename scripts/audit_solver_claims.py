#!/usr/bin/env python3
"""
scripts/audit_solver_claims.py

Truthfulness audit for the live solve endpoint.

The goal is not to prove we match ZenoSolver (their Terms prohibit automated
benchmarking), but to verify that the numbers the API returns are produced by a
real solve rather than a formula. The audit checks:

  1. Exploitability varies per board and is a real convergence measure.
  2. Root EV responds to the input ranges (AA vs KK must not equal KK vs AA).
  3. Root EVs do not collapse to a handful of constants across boards.
  4. OOP_EV + IP_EV is close to the raked starting pot.
  5. The legacy training data still contains the old constant labels. Those
     datasets must be regenerated with the real engine before retraining.

Usage:
    python scripts/audit_solver_claims.py
    python scripts/audit_solver_claims.py --base-url http://localhost:8000
    python scripts/audit_solver_claims.py --base-url https://gtowizard.2d5104a9.sslip.io
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from scripts.canonical_boards import CANONICAL_50_BOARDS as BOARDS
except Exception:  # pragma: no cover - keep the audit usable standalone
    BOARDS: List[List[str]] = [
        ["Ah", "Kd", "2c"],
        ["As", "Qh", "5d"],
        ["Kh", "Qd", "4c"],
        ["9s", "8h", "7s"],
        ["9d", "8c", "7h"],
        ["8s", "7c", "6d"],
        ["8s", "8h", "2c"],
        ["Js", "Jd", "4c"],
        ["2s", "2c", "2d"],
        ["Kh", "Th", "4h"],
        ["Qs", "Jd", "4c"],
        ["7d", "6d", "5d"],
    ]


def post(base_url: str, payload: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/api/solutions/live-solve/"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def fmt_board(board: List[str]) -> str:
    return " ".join(board)


def pct(res: Dict[str, Any]) -> Optional[float]:
    value = res.get("exploitability_pct_pot")
    if value is not None:
        return float(value)
    value = res.get("exploitability")
    if value is None:
        return None
    # Older responses returned a fraction of the pot.
    return float(value) * 100.0


def ev_pair(res: Dict[str, Any]):
    oop = res.get("oop_ev")
    ip = res.get("ip_ev")
    if oop is None or ip is None:
        return None
    return float(oop), float(ip)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)",
    )
    parser.add_argument("--pot", type=float, default=5.5)
    parser.add_argument("--stack", type=float, default=100.0)
    parser.add_argument("--rake", type=float, default=5.0)
    parser.add_argument("--cap", type=float, default=0.6)
    parser.add_argument(
        "--target",
        type=float,
        default=0.5,
        help="Convergence target in percent of pot (default: 0.5)",
    )
    args = parser.parse_args()

    common = {
        "spot": "BTN_vs_BB_SRP",
        "pot": args.pot,
        "effective_stack": args.stack,
        "rake_percent": args.rake,
        "rake_cap": args.cap,
    }

    print("=" * 96)
    print(" SOLVER CLAIM AUDIT")
    print(f" Endpoint: {args.base_url.rstrip('/')}/api/solutions/live-solve/")
    print(f" Target  : {args.target:g}% pot exploitability")
    print("=" * 96)

    # ------------------------------------------------------------------ 1
    print("\n[1] Exploitability and engine across boards")
    print(f"{'Board':<14} {'engine':<40} {'iters':>7} {'expl% pot':>10} {'conv':>6}")
    print("-" * 96)
    rows = []
    for board in BOARDS:
        res = post(args.base_url, {**common, "board": board})
        rows.append(res)
        expl = pct(res)
        expl_s = "n/a" if expl is None else f"{expl:.3f}"
        print(
            f"{fmt_board(board):<14} {str(res.get('engine'))[:40]:<40} "
            f"{int(res.get('iterations', 0)):>7} {expl_s:>10} "
            f"{str(bool(res.get('converged'))):>6}"
        )

    expl_values = [pct(r) for r in rows if pct(r) is not None]
    modes: Dict[str, int] = {}
    for r in rows:
        key = str(r.get("leaf_mode", "unknown"))
        modes[key] = modes.get(key, 0) + 1
    print("-" * 96)
    print("leaf evaluators: " + ", ".join(f"{k} {v}/{len(rows)}" for k, v in sorted(modes.items())))
    if not expl_values:
        print("VERDICT: FAIL - no exploitability returned.")
    elif len({round(v, 6) for v in expl_values}) == 1:
        print(
            "VERDICT: FAIL - exploitability is constant across every board. "
            "That is a formula, not a best-response measurement."
        )
    else:
        worst = max(expl_values)
        print(
            f"distinct exploitability values: {len({round(v, 6) for v in expl_values})} "
            f"(min {min(expl_values):.3f}% / max {worst:.3f}% pot)"
        )
        if worst <= args.target * 1.5:
            print("VERDICT: PASS - real per-solve convergence, close to target.")
        else:
            print(
                "VERDICT: WARN - exploitability varies but some boards did not reach "
                "the target within the time budget."
            )

    # ------------------------------------------------------------------ 2
    print("\n[2] Range sensitivity (same board, opposite holdings)")
    print("-" * 96)
    aa_kk = post(
        args.base_url,
        {**common, "board": ["Ah", "Kd", "2c"], "oop_range": {"AA": 1.0}, "ip_range": {"KK": 1.0}},
    )
    kk_aa = post(
        args.base_url,
        {**common, "board": ["Ah", "Kd", "2c"], "oop_range": {"KK": 1.0}, "ip_range": {"AA": 1.0}},
    )
    for label, res in (("AA vs KK", aa_kk), ("KK vs AA", kk_aa)):
        pair = ev_pair(res)
        print(
            f"{label:<12} oop_ev={pair[0] if pair else 'n/a':<10} "
            f"ip_ev={pair[1] if pair else 'n/a':<10} "
            f"expl%={pct(res):.3f}"
        )
    a, b = ev_pair(aa_kk), ev_pair(kk_aa)
    if not a or not b:
        print("VERDICT: FAIL - missing EV fields.")
    elif abs(a[0] - b[0]) < 0.5:
        print(
            "VERDICT: FAIL - swapping AA and KK barely changes EV. Root EV is "
            "not computed from the input ranges."
        )
    elif a[0] < b[0]:
        print(
            "VERDICT: FAIL - the AA holder has the lower EV. Equity orientation "
            "or EV accounting is inverted."
        )
    else:
        print(
            f"VERDICT: PASS - the AA holder wins about {a[0]:.2f} bb vs "
            f"{b[0]:.2f} bb for the KK holder."
        )

    # ------------------------------------------------------------------ 3
    print("\n[3] Distinct root EV outcomes across boards")
    print("-" * 96)
    pairs = sorted({tuple(round(x, 3) for x in ev_pair(r)) for r in rows if ev_pair(r)})
    for pair in pairs:
        print(f"  oop_ev={pair[0]:<8} ip_ev={pair[1]}")
    print(f"distinct (oop_ev, ip_ev) pairs: {len(pairs)}")
    if len(pairs) <= 4:
        print(
            "VERDICT: FAIL - EVs collapse to a few constants. Real flop solutions "
            "produce a distinct EV for essentially every board."
        )
    else:
        print("VERDICT: PASS - EVs vary per board.")

    # ------------------------------------------------------------------ 4
    print("\n[4] Value conservation")
    print("-" * 96)
    net_pot = args.pot - min(args.pot * args.rake / 100.0, args.cap)
    worst_gap = 0.0
    for res in rows:
        pair = ev_pair(res)
        if pair:
            gap = abs(sum(pair) - net_pot)
            worst_gap = max(worst_gap, gap)
    print(f"net pot after rake: {net_pot:.3f} bb; worst |oop+ip - net_pot|: {worst_gap:.3f} bb")
    if worst_gap <= 0.35:
        print("VERDICT: PASS - EVs conserve the pot within tolerance.")
    else:
        print("VERDICT: WARN - value does not conserve the pot; check rake/fold accounting.")

    # ------------------------------------------------------------------ 5
    print("\n[5] Legacy training-data audit")
    print("-" * 96)
    for line in audit_datasets():
        print(line)

    print("\n" + "=" * 96)
    print(" AUDIT COMPLETE")
    print("=" * 96)
    print(
        "Note: flop/turn solves are depth-limited (future streets are represented by\n"
        "their showdown equity). River solves are exact. Exploitability is measured\n"
        "against the modelled game, not a full multi-street tree."
    )
    return 0


def audit_datasets() -> List[str]:
    lines: List[str] = []
    try:
        import pandas as pd
    except ImportError:
        return ["pandas not available; skipping dataset audit (use backend venv python)."]

    paths = [
        "datasets/generated/zeno_baseline_100bb_nl500.parquet",
        "datasets/generated/nl500_100bb_full.parquet",
        "datasets/generated/leaf_spots_50_boards_100bb_5pct.parquet",
    ]
    for rel in paths:
        path = REPO_ROOT / rel
        if not path.exists():
            lines.append(f"  {rel}: missing")
            continue
        df = pd.read_parquet(path)
        exploit_unique = df["exploitability"].unique() if "exploitability" in df else []
        ev_unique = (
            df[["oop_ev", "ip_ev"]].drop_duplicates().shape[0] if "oop_ev" in df else "?"
        )
        lines.append(
            f"  {rel}: rows={len(df)}, exploitability values={list(exploit_unique)[:5]}, "
            f"distinct EV pairs={ev_unique}"
        )
    lines.append(
        "  -> These files predate the CFR engine. They still carry the old constant\n"
        "     labels, so Model 1 and Model 2 must be retrained after regeneration."
    )
    return lines


if __name__ == "__main__":
    sys.exit(main())
