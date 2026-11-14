#!/usr/bin/env python3
"""
scripts/benchmark_multistreet_parity.py

Benchmarks the ZenoSolver-parity multi-street (Flop -> Turn -> River) and
multi-formation (SRP / 3-Bet / 4-Bet across Cash NL500, Cash NL50, MTT) workflow.

For each of 5 canonical spots it verifies:
  * Solve latency (< 600ms overall, < 500ms on Turn / River transitions)
  * Exploitability <= 0.50% pot (converged == True)
  * Zero-sum / post-rake EV conservation within <= 1e-6 bb
  * Exact dead-card exclusion across all 169 canonical hands in alive_combos

Usage:
  backend/venv/bin/python3 scripts/benchmark_multistreet_parity.py --port 9998
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.solutions.services.engine_bridge import EngineBridge
from backend.solutions.services.range_service import PreflopRangeService

RANKS = "AKQJT98765432"
SUITS = "shdc"


@dataclass
class StreetStep:
    board: List[str]
    actions: List[str]


@dataclass
class SpotSpec:
    name: str
    spot_id: str
    pot: float
    stack: float
    ante: float
    rake: float
    cap: float
    folded_positions: List[str]
    steps: List[StreetStep]


CANONICAL_SPOTS: List[SpotSpec] = [
    SpotSpec(
        name="1_BTN_vs_BB_SRP_Cash_NL500",
        spot_id="BTN_vs_BB_SRP",
        pot=5.5,
        stack=97.5,
        ante=0.0,
        rake=5.0,
        cap=0.6,
        folded_positions=["UTG", "MP", "CO", "SB"],
        steps=[
            StreetStep(board=["Ah", "Kd", "2c"], actions=["Check", "Bet 33%", "Call"]),
            StreetStep(board=["Ah", "Kd", "2c", "7s"], actions=["Check", "Check"]),
            StreetStep(board=["Ah", "Kd", "2c", "7s", "2d"], actions=[]),
        ],
    ),
    SpotSpec(
        name="2_CO_vs_BB_SRP_Cash_NL50",
        spot_id="CO_vs_BB_SRP",
        pot=5.5,
        stack=97.5,
        ante=0.0,
        rake=5.0,
        cap=4.0,
        folded_positions=["UTG", "MP", "BTN", "SB"],
        steps=[
            StreetStep(board=["9s", "8h", "7d"], actions=["Check", "Bet 33%", "Call"]),
            StreetStep(board=["9s", "8h", "7d", "2c"], actions=[]),
        ],
    ),
    SpotSpec(
        name="3_BTN_vs_BB_3BET_Cash_NL500",
        spot_id="BTN_vs_BB_3BET",
        pot=18.5,
        stack=91.0,
        ante=0.0,
        rake=5.0,
        cap=0.6,
        folded_positions=["UTG", "MP", "CO", "SB"],
        steps=[
            StreetStep(board=["Qs", "Jd", "4c"], actions=["Check", "Bet 33%", "Call"]),
            StreetStep(board=["Qs", "Jd", "4c", "Ah"], actions=[]),
        ],
    ),
    SpotSpec(
        name="4_SB_vs_BB_SRP_MTT_40bb",
        spot_id="SB_vs_BB_SRP",
        pot=7.0,
        stack=37.0,
        ante=0.125,
        rake=0.0,
        cap=0.0,
        folded_positions=["UTG", "MP", "CO", "BTN"],
        steps=[
            StreetStep(board=["8s", "8h", "2c"], actions=["Check", "Check"]),
            StreetStep(board=["8s", "8h", "2c", "Kd"], actions=["Check", "Bet 33%", "Call"]),
            StreetStep(board=["8s", "8h", "2c", "Kd", "5s"], actions=[]),
        ],
    ),
    SpotSpec(
        name="5_BTN_vs_BB_4BET_MTT_60bb",
        spot_id="BTN_vs_BB_4BET",
        pot=46.5,
        stack=37.0,
        ante=0.125,
        rake=0.0,
        cap=0.0,
        folded_positions=["UTG", "MP", "CO", "SB"],
        steps=[
            StreetStep(board=["Kh", "Th", "4h"], actions=["Check", "Bet 33%", "Call"]),
            StreetStep(board=["Kh", "Th", "4h", "2d"], actions=[]),
        ],
    ),
]


def expected_alive_combos(hand: str, board: List[str]) -> int:
    """Computes exact surviving 52-card combinations for a canonical 169-hand."""
    dead = set(board)
    r1, r2 = hand[0], hand[1]
    if len(hand) == 2:
        cards = [f"{r1}{s}" for s in SUITS if f"{r1}{s}" not in dead]
        n = len(cards)
        return n * (n - 1) // 2
    suited = hand[2] == "s"
    count = 0
    for s1 in SUITS:
        c1 = f"{r1}{s1}"
        if c1 in dead:
            continue
        for s2 in SUITS:
            if suited and s1 != s2:
                continue
            if (not suited) and s1 == s2:
                continue
            c2 = f"{r2}{s2}"
            if c2 not in dead:
                count += 1
    return count


def conservation_violation(pot: float, rake_pct: float, rake_cap: float, ev_sum: float) -> Tuple[float, float]:
    """Returns (violation_bb, rake_paid_bb)."""
    rake_paid = pot - ev_sum
    if rake_pct == 0.0 and rake_cap == 0.0:
        return abs(rake_paid), 0.0
    lo = min(rake_cap, pot * rake_pct / 100.0)
    hi = rake_cap
    # Allow tiny floating rounding (1e-6) while checking exact conservation bounds
    violation = max(0.0, lo - rake_paid, rake_paid - hi)
    return violation, rake_paid


def verify_dead_cards(board: List[str], alive_combos: Dict[str, int]) -> int:
    """Asserts every hand in alive_combos matches exact 52-card removal."""
    mismatches = 0
    for hand, reported in alive_combos.items():
        if reported != expected_alive_combos(hand, board):
            mismatches += 1
    return mismatches


async def run_spot(
    bridge: EngineBridge,
    spec: SpotSpec,
    expl_threshold_pct: float,
) -> Tuple[List[Dict[str, Any]], bool]:
    oop_range, ip_range = PreflopRangeService.get_spot_ranges(
        spec.spot_id, spec.rake, spec.cap
    )
    pot = spec.pot
    stack = spec.stack
    rows: List[Dict[str, Any]] = []
    spot_ok = True

    for step in spec.steps:
        street_name = {3: "Flop", 4: "Turn", 5: "River"}.get(len(step.board), f"{len(step.board)}c")
        res = await bridge.solve_flop(
            board=step.board,
            oop_range=oop_range,
            ip_range=ip_range,
            pot=pot,
            effective_stack=stack,
            ante_bb=spec.ante,
            rake_percent=spec.rake,
            rake_cap=spec.cap,
            num_folded_players=len(spec.folded_positions),
            use_bunching=True,
            folded_positions=spec.folded_positions,
            max_bets_per_node=1,
            target_dEV=0.005,
            max_iterations=500,
            deterministic=True,
            action_sequence=[],
        )

        lat_ms = float(res.get("solve_time_ms", 0.0))
        expl = float(res.get("exploitability_pct_pot", 999.0))
        converged = bool(res.get("converged", False))
        oop_ev = float(res.get("oop_ev", 0.0))
        ip_ev = float(res.get("ip_ev", 0.0))
        cons_err, rake_paid = conservation_violation(pot, spec.rake, spec.cap, oop_ev + ip_ev)
        alive = res.get("alive_combos") or {}
        combo_mismatches = verify_dead_cards(step.board, alive)

        max_lat = 500.0 if len(step.board) >= 4 else 600.0
        ok = (
            lat_ms <= max_lat
            and converged
            and expl <= expl_threshold_pct
            and cons_err <= 1e-6
            and len(alive) == 169
            and combo_mismatches == 0
        )
        if not ok:
            spot_ok = False

        rows.append(
            {
                "spot": spec.name,
                "street": street_name,
                "board": " ".join(step.board),
                "line": " -> ".join(step.actions) if step.actions else "Root",
                "pot": pot,
                "stack": stack,
                "latency_ms": lat_ms,
                "expl_pct": expl,
                "converged": converged,
                "cons_err_bb": cons_err,
                "rake_paid": rake_paid,
                "combo_mismatches": combo_mismatches,
                "ok": ok,
            }
        )

        # Advance Bayesian posterior ranges & pot/stack along step.actions if continuing
        if step.actions:
            trans = await bridge.solve_flop(
                board=step.board,
                oop_range=oop_range,
                ip_range=ip_range,
                pot=pot,
                effective_stack=stack,
                ante_bb=spec.ante,
                rake_percent=spec.rake,
                rake_cap=spec.cap,
                num_folded_players=len(spec.folded_positions),
                use_bunching=True,
                folded_positions=spec.folded_positions,
                max_bets_per_node=1,
                target_dEV=0.005,
                max_iterations=500,
                deterministic=True,
                action_sequence=step.actions,
            )
            post_oop = trans.get("posterior_oop_range") or {}
            post_ip = trans.get("posterior_ip_range") or {}
            if not post_oop or not post_ip or not trans.get("street_closed"):
                spot_ok = False
                rows[-1]["ok"] = False
                break
            oop_range = post_oop
            ip_range = post_ip
            pot = float(trans.get("next_street_pot") or pot)
            stack = float(trans.get("next_street_stack") or stack)

    return rows, spot_ok


def check_http_smoke(base_url: str) -> bool:
    """Optionally verifies /api/solutions/formation-ranges/ and /api/solutions/live-solve/ over HTTP."""
    meta_url = f"{base_url.rstrip('/')}/api/solutions/formation-ranges/?spot=BTN_vs_BB_3BET"
    with urllib.request.urlopen(meta_url, timeout=10) as resp:
        assert resp.status == 200
        meta = json.loads(resp.read().decode())
        assert len(meta["oop_range"]) > 0 and len(meta["ip_range"]) > 0

    payload = json.dumps(
        {
            "board": ["Ah", "Kd", "2c", "7s"],
            "spot": "BTN_vs_BB_SRP",
            "flop_actions": ["Check", "Bet 33%", "Call"],
            "action_sequence": [],
            "pot": 5.5,
            "effective_stack": 97.5,
            "rake_percent": 5.0,
            "rake_cap": 0.6,
            "use_bunching": True,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/solutions/live-solve/",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert str(data.get("street", "")).lower() == "turn"
        assert float(data.get("pot", 0) or 0) > 5.5
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-street & multi-formation ZenoSolver parity benchmark.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("SOLVER_DAEMON_PORT", "9998")))
    parser.add_argument("--host", type=str, default=os.environ.get("SOLVER_DAEMON_HOST", "127.0.0.1"))
    parser.add_argument("--threshold-pct", type=float, default=0.50)
    parser.add_argument("--http-url", type=str, default="", help="Optional HTTP base URL (e.g. http://127.0.0.1)")
    args = parser.parse_args()

    bridge = EngineBridge(host=args.host, port=args.port, timeout_sec=15.0)
    print("=" * 116)
    print(" ZENOSOLVER MULTI-STREET & MULTI-FORMATION PARITY BENCHMARK")
    print("=" * 116)
    print(
        f"{'Spot':<30} | {'Street':<5} | {'Board':<15} | {'Line':<22} | "
        f"{'Pot':<6} | {'ms':<6} | {'dEV%':<6} | {'ConsErr':<8} | {'Status'}"
    )
    print("-" * 116)

    all_rows: List[Dict[str, Any]] = []
    all_ok = True
    for spec in CANONICAL_SPOTS:
        rows, ok = await run_spot(bridge, spec, args.threshold_pct)
        all_rows.extend(rows)
        if not ok:
            all_ok = False
        for r in rows:
            status = "PASS" if r["ok"] else "FAIL"
            print(
                f"{r['spot']:<30} | {r['street']:<5} | {r['board']:<15} | {r['line']:<22} | "
                f"{r['pot']:<6.2f} | {r['latency_ms']:<6.1f} | {r['expl_pct']:<6.3f} | "
                f"{r['cons_err_bb']:<8.2e} | {status}"
            )

    print("-" * 116)
    turn_river_lat = [r["latency_ms"] for r in all_rows if r["street"] in ("Turn", "River")]
    max_all_lat = max(r["latency_ms"] for r in all_rows)
    max_tr_lat = max(turn_river_lat) if turn_river_lat else 0.0
    max_expl = max(r["expl_pct"] for r in all_rows)
    max_cons = max(r["cons_err_bb"] for r in all_rows)
    total_mismatches = sum(r["combo_mismatches"] for r in all_rows)

    print(
        f"Summary: {len(all_rows)} nodes across {len(CANONICAL_SPOTS)} spots | "
        f"max latency={max_all_lat:.1f}ms (Turn/River max={max_tr_lat:.1f}ms) | "
        f"max dEV={max_expl:.3f}% pot | max cons err={max_cons:.2e} bb | "
        f"dead-card mismatches={total_mismatches}"
    )

    if args.http_url:
        check_http_smoke(args.http_url)
        print(f"HTTP E2E check ({args.http_url}): PASS")

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
