#!/usr/bin/env python3
"""
scripts/verify_generalization.py

Task 4: verifies the generalized engine across rake / stack / ante / bunching
configurations. For each configuration it reports:

  * solve latency (mean / p95 / max, ms),
  * measured exploitability (% pot) and the pass rate at the threshold,
  * zero-sum EV conservation: EV_oop + EV_ip must equal the post-rake pot,
  * the engine label (which leaf evaluator actually ran).

The default matrix covers a 6-max NL500 cash spot and a 40bb MTT ante spot with
preflop card bunching active, plus the wider MTT stack ladder and NL50 rake for
breadth.

Usage:
  python scripts/verify_generalization.py --port 9998
  python scripts/verify_generalization.py --port 9998 --boards 12
  python scripts/verify_generalization.py --port 9998 --configs cash_nl500,mtt_40bb --boards 50
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.solutions.services.engine_bridge import EngineBridge
from backend.solutions.services.range_service import PreflopRangeService

try:
    from scripts.canonical_boards import CANONICAL_50_BOARDS
except Exception:  # pragma: no cover - fallback for direct script execution
    CANONICAL_50_BOARDS = [
        ["Ah", "Kd", "2c"], ["9s", "8h", "7s"], ["As", "Ah", "5c"],
        ["Kh", "Th", "4h"], ["Qd", "Jc", "2s"], ["7d", "7h", "3c"],
        ["Ts", "9s", "8d"], ["Ac", "Qd", "5h"], ["Jh", "8h", "2h"],
        ["6c", "5c", "4d"],
    ]

# name: (pot, stack_bb, ante_bb, rake_pct, rake_cap, folded, bunching)
CONFIGS: Dict[str, Dict[str, Any]] = {
    "cash_nl500": dict(pot=5.5, stack=100.0, ante=0.0, rake=5.0, cap=0.6, folded=4, bunching=True),
    "cash_nl50": dict(pot=5.5, stack=100.0, ante=0.0, rake=5.0, cap=4.0, folded=4, bunching=True),
    "mtt_20bb": dict(pot=6.5, stack=20.0, ante=0.125, rake=0.0, cap=0.0, folded=4, bunching=True),
    "mtt_40bb": dict(pot=6.5, stack=40.0, ante=0.125, rake=0.0, cap=0.0, folded=4, bunching=True),
    "mtt_60bb": dict(pot=6.5, stack=60.0, ante=0.125, rake=0.0, cap=0.0, folded=4, bunching=True),
    "mtt_100bb": dict(pot=6.5, stack=100.0, ante=0.125, rake=0.0, cap=0.0, folded=4, bunching=True),
}


def conservation_violation(cfg: Dict[str, Any], ev_sum: float) -> Tuple[float, float]:
    """Returns (violation_bb, rake_paid_bb).

    Zero-sum conservation for a raked game is ``EV_oop + EV_ip = pot - rake``.
    Rake is charged on the *final* pot, so for a raked config the target is not
    a fixed number; the engine values must instead split the starting pot and
    pay between ``rake(start_pot)`` and the cap. For a zero-rake (MTT) config
    the target is exactly the starting pot.
    """
    pot = cfg["pot"]
    rake_paid = pot - ev_sum
    if cfg["rake"] == 0.0 and cfg["cap"] == 0.0:
        return abs(rake_paid), 0.0
    lo = min(cfg["cap"], pot * cfg["rake"] / 100.0)
    hi = cfg["cap"]
    return max(0.0, lo - rake_paid, rake_paid - hi), rake_paid


async def solve_config(
    bridge: EngineBridge,
    cfg: Dict[str, Any],
    boards: List[List[str]],
    threshold_pct: float,
) -> Dict[str, Any]:
    oop, ip = PreflopRangeService.get_spot_ranges(
        "BTN_vs_BB_SRP", cfg["rake"], cfg["cap"]
    )
    rows: List[Dict[str, Any]] = []
    for board in boards:
        res = await bridge.solve_flop(
            board=board,
            oop_range=oop,
            ip_range=ip,
            pot=cfg["pot"],
            effective_stack=cfg["stack"],
            ante_bb=cfg["ante"],
            rake_percent=cfg["rake"],
            rake_cap=cfg["cap"],
            num_folded_players=cfg["folded"],
            use_bunching=cfg["bunching"],
            max_bets_per_node=1,
            target_dEV=0.005,
            max_iterations=500,
        )
        ev_o = float(res.get("oop_ev", 0.0))
        ev_i = float(res.get("ip_ev", 0.0))
        expl = res.get("exploitability_pct_pot")
        viol, rake_paid = conservation_violation(cfg, ev_o + ev_i)
        rows.append({
            "board": " ".join(board),
            "latency_ms": float(res.get("solve_time_ms", 0.0)),
            "expl_pct": float(expl) if expl is not None else float("nan"),
            "converged": bool(res.get("converged", False)),
            "ev_sum": ev_o + ev_i,
            "rake_paid": rake_paid,
            "conservation_err_bb": viol,
            "leaf_mode": res.get("leaf_mode") or res.get("engine", "?"),
        })

    expl = np.array([r["expl_pct"] for r in rows], dtype=float)
    lat = np.array([r["latency_ms"] for r in rows], dtype=float)
    cons = np.array([r["conservation_err_bb"] for r in rows], dtype=float)
    raked = np.array([r["rake_paid"] for r in rows], dtype=float)
    converged = np.array([r["converged"] for r in rows], dtype=bool)
    valid = ~np.isnan(expl)
    passed = valid & converged & (expl <= threshold_pct)

    return {
        "n": len(rows),
        "latency_mean_ms": float(lat.mean()),
        "latency_p95_ms": float(np.percentile(lat, 95)),
        "latency_max_ms": float(lat.max()),
        "expl_mean_pct": float(expl[valid].mean()) if valid.any() else float("nan"),
        "expl_max_pct": float(expl[valid].max()) if valid.any() else float("nan"),
        "pass_rate": float(passed.sum() / max(1, valid.sum())),
        "converged_rate": float(converged.mean()),
        "cons_err_max_bb": float(cons.max()),
        "cons_err_mean_bb": float(cons.mean()),
        "rake_paid_mean_bb": float(raked.mean()),
        "leaf_modes": sorted({r["leaf_mode"] for r in rows}),
        "rows": rows,
    }


async def run(args: argparse.Namespace) -> int:
    try:
        from scripts.canonical_boards import CANONICAL_50_BOARDS as canonical
    except Exception:
        canonical = CANONICAL_50_BOARDS
    boards = canonical[: args.boards]

    bridge = EngineBridge(
        host=os.environ.get("SOLVER_DAEMON_HOST", "127.0.0.1"),
        port=args.port or int(os.environ.get("SOLVER_DAEMON_PORT", "9998")),
        timeout_sec=args.timeout,
    )

    print("=" * 104)
    print(" GENERALIZATION VERIFICATION (rake / stack / ante / bunching)")
    print("=" * 104)
    print(f"Boards per config : {len(boards)}")
    print(f"Threshold         : {args.threshold_pct:.2f}% pot (NashConv/2, converged)")
    print("-" * 104)
    print(f"{'Config':<12} | {'Stack':<6} | {'Ante':<6} | {'Rake':<10} | "
          f"{'Bunch':<5} | {'ms avg':<7} | {'ms p95':<7} | {'expl%':<7} | "
          f"{'pass':<6} | {'cons err':<9} | {'leaf mode'}")
    print("-" * 104)

    summaries: Dict[str, Dict[str, Any]] = {}
    for name in args.configs:
        cfg = CONFIGS[name]
        s = await solve_config(bridge, cfg, boards, args.threshold_pct)
        summaries[name] = s
        print(f"{name:<12} | {cfg['stack']:<6.0f} | {cfg['ante']:<6.3f} | "
              f"{cfg['rake']:.0f}%/{cfg['cap']:.1f} | {'on' if cfg['bunching'] else 'off':<5} | "
              f"{s['latency_mean_ms']:<7.0f} | {s['latency_p95_ms']:<7.0f} | "
              f"{s['expl_mean_pct']:<7.3f} | {s['pass_rate'] * 100:>5.1f}% | "
              f"{s['cons_err_max_bb']:<9.2e} | {','.join(s['leaf_modes'])}")

    print("-" * 104)
    all_pass = all(s["pass_rate"] >= 1.0 for s in summaries.values())
    cons_ok = all(s["cons_err_max_bb"] <= 1e-6 for s in summaries.values())
    print(f"Exploitability <= {args.threshold_pct:.2f}% pot on every board : "
          f"{'PASS' if all_pass else 'FAIL'}")
    print(f"Zero-sum EV conservation (max err <= 1e-6 bb)        : "
          f"{'PASS' if cons_ok else 'FAIL'}")
    print("Note: zero-rake configs require EV_oop + EV_ip == starting pot exactly;")
    print("      raked configs must pay between rake(start pot) and the cap, so no")
    print("      chips are created. The pair evaluator conserves the pot structurally.")
    return 0 if (all_pass and cons_ok) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9998)
    ap.add_argument("--boards", type=int, default=50,
                    help="Number of canonical boards per configuration")
    ap.add_argument("--configs", default="cash_nl500,mtt_40bb",
                    help="Comma-separated configs from: " + ",".join(CONFIGS))
    ap.add_argument("--threshold-pct", type=float, default=0.5)
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()
    args.configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    for c in args.configs:
        if c not in CONFIGS:
            raise SystemExit(f"Unknown config {c!r}; choices: {', '.join(CONFIGS)}")
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
