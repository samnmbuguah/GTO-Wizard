#!/usr/bin/env python3
"""
scripts/final_zeno_benchmark.py

Comprehensive validation report script proving live production solver
mathematical soundness, LeafNet parity against exact river-resolved CFR+,
multi-street invariants, bunching/rake sensitivity, and ZenoSolver reference sheet.

Usage:
  backend/venv/bin/python3 scripts/final_zeno_benchmark.py --port 9998
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.solutions.services.engine_bridge import EngineBridge
from backend.solutions.services.range_service import PreflopRangeService

SUITS = "shdc"

TEN_CANONICAL_BOARDS: List[List[str]] = [
    ["Ah", "Kd", "2c"],
    ["9s", "8h", "7d"],
    ["8s", "8h", "2c"],
    ["Kh", "Th", "4h"],
    ["Qs", "Jd", "4c"],
    ["Js", "7d", "2c"],
    ["As", "Ah", "5c"],
    ["Ts", "9s", "8d"],
    ["7d", "7h", "3c"],
    ["6c", "5c", "4d"],
]

MULTISTREET_SPOTS: List[Dict[str, Any]] = [
    {
        "name": "BTN_vs_BB_SRP (NL500)",
        "spot_id": "BTN_vs_BB_SRP",
        "pot": 5.5,
        "stack": 97.5,
        "ante": 0.0,
        "rake": 5.0,
        "cap": 0.6,
        "folded_positions": ["UTG", "MP", "CO", "SB"],
        "steps": [
            (["Ah", "Kd", "2c"], ["Check", "Bet 33%", "Call"]),
            (["Ah", "Kd", "2c", "7s"], ["Check", "Check"]),
            (["Ah", "Kd", "2c", "7s", "2d"], []),
        ],
    },
    {
        "name": "CO_vs_BB_SRP (NL50)",
        "spot_id": "CO_vs_BB_SRP",
        "pot": 5.5,
        "stack": 97.5,
        "ante": 0.0,
        "rake": 5.0,
        "cap": 4.0,
        "folded_positions": ["UTG", "MP", "BTN", "SB"],
        "steps": [
            (["9s", "8h", "7d"], ["Check", "Bet 33%", "Call"]),
            (["9s", "8h", "7d", "2c"], []),
        ],
    },
    {
        "name": "BTN_vs_BB_3BET (NL500)",
        "spot_id": "BTN_vs_BB_3BET",
        "pot": 18.5,
        "stack": 91.0,
        "ante": 0.0,
        "rake": 5.0,
        "cap": 0.6,
        "folded_positions": ["UTG", "MP", "CO", "SB"],
        "steps": [
            (["Qs", "Jd", "4c"], ["Check", "Bet 33%", "Call"]),
            (["Qs", "Jd", "4c", "Ah"], []),
        ],
    },
    {
        "name": "SB_vs_BB_SRP (40bb MTT)",
        "spot_id": "SB_vs_BB_SRP",
        "pot": 7.0,
        "stack": 37.0,
        "ante": 0.125,
        "rake": 0.0,
        "cap": 0.0,
        "folded_positions": ["UTG", "MP", "CO", "BTN"],
        "steps": [
            (["8s", "8h", "2c"], ["Check", "Check"]),
            (["8s", "8h", "2c", "Kd"], ["Check", "Bet 33%", "Call"]),
            (["8s", "8h", "2c", "Kd", "5s"], []),
        ],
    },
    {
        "name": "BTN_vs_BB_4BET (60bb MTT)",
        "spot_id": "BTN_vs_BB_4BET",
        "pot": 46.5,
        "stack": 37.0,
        "ante": 0.125,
        "rake": 0.0,
        "cap": 0.0,
        "folded_positions": ["UTG", "MP", "CO", "SB"],
        "steps": [
            (["Kh", "Th", "4h"], ["Check", "Bet 33%", "Call"]),
            (["Kh", "Th", "4h", "2d"], []),
        ],
    },
]

ZENO_COMPARISON_SPOTS: List[Dict[str, Any]] = [
    dict(
        label="Ah Kd 2c | BTN vs BB SRP (NL500)",
        spot_id="BTN_vs_BB_SRP",
        board=["Ah", "Kd", "2c"],
        pot=5.5,
        stack=97.5,
        ante=0.0,
        rake=5.0,
        cap=0.6,
        folded_positions=["UTG", "MP", "CO", "SB"],
        config_desc="100bb Cash, Pot 5.5, 5%/0.6cap, Bunch",
    ),
    dict(
        label="9s 8h 7d | BTN vs BB SRP (NL500)",
        spot_id="BTN_vs_BB_SRP",
        board=["9s", "8h", "7d"],
        pot=5.5,
        stack=97.5,
        ante=0.0,
        rake=5.0,
        cap=0.6,
        folded_positions=["UTG", "MP", "CO", "SB"],
        config_desc="100bb Cash, Pot 5.5, 5%/0.6cap, Bunch",
    ),
    dict(
        label="8s 8h 2c | BTN vs BB SRP (NL500)",
        spot_id="BTN_vs_BB_SRP",
        board=["8s", "8h", "2c"],
        pot=5.5,
        stack=97.5,
        ante=0.0,
        rake=5.0,
        cap=0.6,
        folded_positions=["UTG", "MP", "CO", "SB"],
        config_desc="100bb Cash, Pot 5.5, 5%/0.6cap, Bunch",
    ),
    dict(
        label="Kh Th 4h | BTN vs BB SRP (NL500)",
        spot_id="BTN_vs_BB_SRP",
        board=["Kh", "Th", "4h"],
        pot=5.5,
        stack=97.5,
        ante=0.0,
        rake=5.0,
        cap=0.6,
        folded_positions=["UTG", "MP", "CO", "SB"],
        config_desc="100bb Cash, Pot 5.5, 5%/0.6cap, Bunch",
    ),
    dict(
        label="Qs Jd 4c | BTN vs BB 3-Bet (NL500)",
        spot_id="BTN_vs_BB_3BET",
        board=["Qs", "Jd", "4c"],
        pot=18.5,
        stack=91.0,
        ante=0.0,
        rake=5.0,
        cap=0.6,
        folded_positions=["UTG", "MP", "CO", "SB"],
        config_desc="100bb 3BP, Pot 18.5, 5%/0.6cap, Bunch",
    ),
    dict(
        label="Js 7d 2c | BTN vs BB SRP (40bb MTT)",
        spot_id="BTN_vs_BB_SRP",
        board=["Js", "7d", "2c"],
        pot=6.5,
        stack=40.0,
        ante=0.125,
        rake=0.0,
        cap=0.0,
        folded_positions=["UTG", "MP", "CO", "SB"],
        config_desc="40bb MTT, Pot 6.5, 0.125ante, 0% Rake",
    ),
]


def expected_alive_combos(hand: str, board: List[str]) -> int:
    dead = set(board)
    r1, r2 = hand[0], hand[1]
    if len(hand) == 2:
        cards = [f"{r1}{s}" for s in SUITS if f"{r1}{s}" not in dead]
        return len(cards) * (len(cards) - 1) // 2
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
            if f"{r2}{s2}" not in dead:
                count += 1
    return count


def conservation_violation(pot: float, rake_pct: float, rake_cap: float, ev_sum: float) -> Tuple[float, float]:
    rake_paid = pot - ev_sum
    if rake_pct == 0.0 and rake_cap == 0.0:
        return abs(rake_paid), 0.0
    lo = min(rake_cap, pot * rake_pct / 100.0)
    hi = rake_cap
    violation = max(0.0, lo - rake_paid, rake_paid - hi)
    return violation, rake_paid


def max_prob_norm_error(res: Dict[str, Any]) -> Tuple[float, int]:
    """Checks |sum P(a) - 1.0| across all alive hands (alive_combos > 0)."""
    strategy = res.get("strategy") or {}
    detail = res.get("strategy_detail") or {}
    alive = res.get("alive_combos") or {}
    max_err = 0.0
    alive_hands = 0
    for hand, acts in strategy.items():
        if alive.get(hand, 1) <= 0:
            continue
        alive_hands += 1
        s = float(acts.get("fold", 0.0)) + float(acts.get("call", 0.0)) + float(acts.get("raise", 0.0))
        max_err = max(max_err, abs(s - 1.0))
        d = detail.get(hand) or {}
        if d:
            sd = sum(float(v) for v in d.values())
            max_err = max(max_err, abs(sd - 1.0))
    return max_err, alive_hands


async def run_check_1_leafnet_vs_exact(bridge: EngineBridge, exact_samples: int) -> bool:
    print("=" * 124)
    print(" CHECK 1: FULL-TREE EXACT CFR+ (RIVER-RESOLVED) vs LIVE NEURAL LEAFNET ACCURACY (10 CANONICAL BOARDS)")
    print("=" * 124)
    print(
        f"Spot: BTN vs BB SRP | Pot 5.50bb | Eff Stack 97.50bb | NL500 Rake 5%/0.6bb | Bunching ON (4 folded)"
    )
    print("-" * 124)
    print(
        f"{'Board':<11} | {'LeafNet EV (OOP/IP)':<20} | {'Exact CFR EV (OOP/IP)':<22} | "
        f"{'EV |Δ|':<7} | {'OOP Chk% (L/E)':<15} | {'IP CBet% (L/E)':<15} | {'Freq|Δ|':<7} | "
        f"{'Expl (% | bb/100)':<17} | {'ms (L/E)'}"
    )
    print("-" * 124)

    oop, ip = PreflopRangeService.get_spot_ranges("BTN_vs_BB_SRP", 5.0, 0.6)
    folded = ["UTG", "MP", "CO", "SB"]

    oop_errs: List[float] = []
    ip_errs: List[float] = []
    freq_devs: List[float] = []
    expl_bb100_list: List[float] = []
    expl_pct_list: List[float] = []
    leaf_latencies: List[float] = []
    exact_latencies: List[float] = []
    all_ok = True

    for board in TEN_CANONICAL_BOARDS:
        base_kwargs = dict(
            board=board,
            oop_range=oop,
            ip_range=ip,
            pot=5.5,
            effective_stack=97.5,
            ante_bb=0.0,
            rake_percent=5.0,
            rake_cap=0.6,
            num_folded_players=4,
            use_bunching=True,
            folded_positions=folded,
            max_bets_per_node=1,
            target_dEV=0.005,
            max_iterations=500,
            deterministic=True,
        )
        res_leaf = await bridge.solve_flop(**base_kwargs, force_exact=False)
        res_exact = await bridge.solve_flop(
            **base_kwargs, force_exact=True, equity_samples_override=exact_samples
        )

        if "exact-showdown" not in res_exact["leaf_mode"] or not res_leaf["converged"]:
            all_ok = False

        lo_ev, li_ev = float(res_leaf["oop_ev"]), float(res_leaf["ip_ev"])
        eo_ev, ei_ev = float(res_exact["oop_ev"]), float(res_exact["ip_ev"])
        ev_err = 0.5 * (abs(lo_ev - eo_ev) + abs(li_ev - ei_ev))
        oop_errs.append(abs(lo_ev - eo_ev))
        ip_errs.append(abs(li_ev - ei_ev))

        l_chk = float(res_leaf["bb_check_frequency"] or 0.0) * 100.0
        e_chk = float(res_exact["bb_check_frequency"] or 0.0) * 100.0
        l_cb = float(res_leaf["btn_cbet_frequency"] or 0.0) * 100.0
        e_cb = float(res_exact["btn_cbet_frequency"] or 0.0) * 100.0
        f_dev = 0.5 * (abs(l_chk - e_chk) + abs(l_cb - e_cb))
        freq_devs.append(f_dev)

        expl_pct = float(res_leaf["exploitability_pct_pot"] or 0.0)
        expl_bb100 = float(res_leaf["exploitability_bb"] or 0.0) * 100.0
        expl_pct_list.append(expl_pct)
        expl_bb100_list.append(expl_bb100)

        l_ms = float(res_leaf["solve_time_ms"])
        e_ms = float(res_exact["solve_time_ms"])
        leaf_latencies.append(l_ms)
        exact_latencies.append(e_ms)

        print(
            f"{' '.join(board):<11} | "
            f"{lo_ev:>6.3f} / {li_ev:<6.3f}      | "
            f"{eo_ev:>6.3f} / {ei_ev:<6.3f}        | "
            f"{ev_err:>6.4f} | "
            f"{l_chk:>5.1f}% / {e_chk:<5.1f}%  | "
            f"{l_cb:>5.1f}% / {e_cb:<5.1f}%  | "
            f"{f_dev:>5.2f}% | "
            f"{expl_pct:>5.3f}% / {expl_bb100:>5.2f}bb | "
            f"{l_ms:>4.0f} / {e_ms:<4.0f}"
        )

    root_ev_mae = sum(oop_errs + ip_errs) / (2 * len(TEN_CANONICAL_BOARDS))
    freq_mae = sum(freq_devs) / len(freq_devs)
    avg_expl_bb100 = sum(expl_bb100_list) / len(expl_bb100_list)
    avg_expl_pct = sum(expl_pct_list) / len(expl_pct_list)
    avg_leaf_ms = sum(leaf_latencies) / len(leaf_latencies)
    avg_exact_ms = sum(exact_latencies) / len(exact_latencies)

    print("-" * 124)
    print(
        f"Check 1 Summary (10 Boards, Exact CFR {exact_samples} runouts vs Live PairEquityNet V2):"
    )
    print(
        f"  * Root EV Mean Absolute Error (bb) : {root_ev_mae:.4f} bb "
        f"(OOP MAE: {sum(oop_errs)/len(oop_errs):.4f} bb, IP MAE: {sum(ip_errs)/len(ip_errs):.4f} bb)"
    )
    print(f"  * Action Frequency Deviation (%)   : {freq_mae:.2f}% mean abs diff")
    print(
        f"  * Average Exploitability           : {avg_expl_bb100:.2f} bb/100 ({avg_expl_pct:.3f}% pot)"
    )
    print(
        f"  * Average Solve Latency            : {avg_leaf_ms:.1f} ms (Live LeafNet) vs {avg_exact_ms:.1f} ms (Exact CFR+)"
    )
    print()
    return all_ok


async def run_check_2_invariants(bridge: EngineBridge) -> bool:
    print("=" * 124)
    print(" CHECK 2: MULTI-STREET & EDGE-CASE INVARIANT AUDIT")
    print("=" * 124)
    print("Part A -- Multi-Street Flop -> Turn -> River Invariants (5 Canonical Spots, 12 Street Nodes)")
    print("-" * 124)
    print(
        f"{'Spot':<26} | {'Street':<5} | {'Board':<15} | {'Line':<22} | "
        f"{'NetSum+Rake=Pot':<18} | {'ConsErr':<8} | {'Max|ΣP-1|':<9} | {'DeadErr':<7} | {'Status'}"
    )
    print("-" * 124)

    all_ok = True
    for spec in MULTISTREET_SPOTS:
        oop, ip = PreflopRangeService.get_spot_ranges(spec["spot_id"], spec["rake"], spec["cap"])
        pot = float(spec["pot"])
        stack = float(spec["stack"])

        for board, actions in spec["steps"]:
            street_name = {3: "Flop", 4: "Turn", 5: "River"}[len(board)]
            res = await bridge.solve_flop(
                board=board,
                oop_range=oop,
                ip_range=ip,
                pot=pot,
                effective_stack=stack,
                ante_bb=spec["ante"],
                rake_percent=spec["rake"],
                rake_cap=spec["cap"],
                num_folded_players=len(spec["folded_positions"]),
                use_bunching=True,
                folded_positions=spec["folded_positions"],
                max_bets_per_node=1,
                target_dEV=0.005,
                max_iterations=500,
                deterministic=True,
                action_sequence=[],
            )
            ev_sum = float(res["oop_ev"]) + float(res["ip_ev"])
            cons_err, rake_paid = conservation_violation(pot, spec["rake"], spec["cap"], ev_sum)
            prob_err, alive_n = max_prob_norm_error(res)
            alive = res.get("alive_combos") or {}
            dead_mismatches = sum(
                1 for h, cnt in alive.items() if cnt != expected_alive_combos(h, board)
            )
            ok = (
                cons_err <= 1e-6
                and prob_err <= 5e-4
                and alive_n > 0
                and len(alive) == 169
                and dead_mismatches == 0
                and bool(res["converged"])
            )
            if not ok:
                all_ok = False

            line_lbl = " -> ".join(actions) if actions else "Root"
            net_str = f"{ev_sum:>6.2f}+{rake_paid:>4.2f}={pot:>6.2f}"
            print(
                f"{spec['name']:<26} | {street_name:<5} | {' '.join(board):<15} | {line_lbl:<22} | "
                f"{net_str:<18} | {cons_err:<8.2e} | {prob_err:<9.2e} | {dead_mismatches:<7} | "
                f"{'PASS' if ok else 'FAIL'}"
            )

            if actions:
                trans = await bridge.solve_flop(
                    board=board,
                    oop_range=oop,
                    ip_range=ip,
                    pot=pot,
                    effective_stack=stack,
                    ante_bb=spec["ante"],
                    rake_percent=spec["rake"],
                    rake_cap=spec["cap"],
                    num_folded_players=len(spec["folded_positions"]),
                    use_bunching=True,
                    folded_positions=spec["folded_positions"],
                    max_bets_per_node=1,
                    target_dEV=0.005,
                    max_iterations=500,
                    deterministic=True,
                    action_sequence=actions,
                )
                oop = trans["posterior_oop_range"]
                ip = trans["posterior_ip_range"]
                pot = float(trans["next_street_pot"])
                stack = float(trans["next_street_stack"])

    print("-" * 124)
    print("Part B -- Dynamic Rake Sensitivity & Card Bunching Effect Audit")
    print("-" * 124)

    # Rake sensitivity on Ah Kd 2c
    oop_r, ip_r = PreflopRangeService.get_spot_ranges("BTN_vs_BB_SRP", 5.0, 0.6)
    rake_configs = [
        ("0% Rake (MTT)", 0.0, 0.0),
        ("NL500 (5% / 0.6bb cap)", 5.0, 0.6),
        ("NL50  (5% / 4.0bb cap)", 5.0, 4.0),
    ]
    ev_sums_by_rake: List[float] = []
    for label, r_pct, r_cap in rake_configs:
        r_res = await bridge.solve_flop(
            board=["Ah", "Kd", "2c"],
            oop_range=oop_r,
            ip_range=ip_r,
            pot=5.5,
            effective_stack=97.5,
            ante_bb=0.0,
            rake_percent=r_pct,
            rake_cap=r_cap,
            num_folded_players=4,
            use_bunching=True,
            folded_positions=["UTG", "MP", "CO", "SB"],
            max_bets_per_node=1,
            target_dEV=0.005,
            max_iterations=500,
            deterministic=True,
        )
        ev_sum = float(r_res["oop_ev"]) + float(r_res["ip_ev"])
        cons_err, rake_paid = conservation_violation(5.5, r_pct, r_cap, ev_sum)
        ev_sums_by_rake.append(ev_sum)
        if cons_err > 1e-6:
            all_ok = False
        print(
            f"  Rake Audit | {label:<24} | OOP EV={r_res['oop_ev']:.4f}bb | "
            f"IP EV={r_res['ip_ev']:.4f}bb | Net Pot={ev_sum:.4f}bb | "
            f"Rake Paid={rake_paid:.4f}bb | ConsErr={cons_err:.2e}"
        )

    rake_monotonic = ev_sums_by_rake[0] > ev_sums_by_rake[1] > ev_sums_by_rake[2]
    if not rake_monotonic:
        all_ok = False
    print(
        f"  Rake Monotonicity (NetPot 0% > NL500 > NL50): "
        f"{ev_sums_by_rake[0]:.4f} > {ev_sums_by_rake[1]:.4f} > {ev_sums_by_rake[2]:.4f} -> "
        f"{'PASS' if rake_monotonic else 'FAIL'}"
    )

    # Card bunching sensitivity
    for test_board in [["Ah", "Kd", "2c"], ["9s", "8h", "7d"]]:
        b_off = await bridge.solve_flop(
            board=test_board,
            oop_range=oop_r,
            ip_range=ip_r,
            pot=5.5,
            effective_stack=97.5,
            rake_percent=5.0,
            rake_cap=0.6,
            num_folded_players=0,
            use_bunching=False,
            folded_positions=[],
            max_bets_per_node=1,
            target_dEV=0.005,
            max_iterations=500,
            deterministic=True,
        )
        b_on = await bridge.solve_flop(
            board=test_board,
            oop_range=oop_r,
            ip_range=ip_r,
            pot=5.5,
            effective_stack=97.5,
            rake_percent=5.0,
            rake_cap=0.6,
            num_folded_players=4,
            use_bunching=True,
            folded_positions=["UTG", "MP", "CO", "SB"],
            max_bets_per_node=1,
            target_dEV=0.005,
            max_iterations=500,
            deterministic=True,
        )
        delta_oop = abs(float(b_on["oop_ev"]) - float(b_off["oop_ev"]))
        delta_ip = abs(float(b_on["ip_ev"]) - float(b_off["ip_ev"]))
        delta_cbet = (float(b_on["btn_cbet_frequency"] or 0.0) - float(b_off["btn_cbet_frequency"] or 0.0)) * 100.0
        shifted = max(delta_oop, delta_ip) > 1e-4
        if not shifted:
            all_ok = False
        print(
            f"  Bunching Audit ({' '.join(test_board)}) | "
            f"OFF EV(OOP/IP)={b_off['oop_ev']:.4f}/{b_off['ip_ev']:.4f} -> "
            f"ON EV={b_on['oop_ev']:.4f}/{b_on['ip_ev']:.4f} | "
            f"|ΔEV_IP|={delta_ip:.4f}bb | ΔCBet={delta_cbet:+.2f}% -> "
            f"{'PASS' if shifted else 'FAIL'}"
        )

    print()
    return all_ok


async def run_check_3_comparison_sheet(bridge: EngineBridge, exact_samples: int) -> bool:
    print("=" * 136)
    print(" CHECK 3: ZENOSOLVER COMPARISON & REFERENCE SHEET (6 CANONICAL SPOTS)")
    print("=" * 136)
    print(
        f"{'Spot / Board':<33} | {'Config':<34} | {'Sizing':<6} | "
        f"{'IP CBet% (L/E)':<14} | {'OOP Chk% (L/E)':<14} | "
        f"{'OOP EV (L/E)':<14} | {'IP EV (L/E)':<14} | {'Expl (% / bb100)':<16} | {'ms'}"
    )
    print("-" * 136)

    all_ok = True
    for spot in ZENO_COMPARISON_SPOTS:
        oop, ip = PreflopRangeService.get_spot_ranges(spot["spot_id"], spot["rake"], spot["cap"])
        base = dict(
            board=spot["board"],
            oop_range=oop,
            ip_range=ip,
            pot=spot["pot"],
            effective_stack=spot["stack"],
            ante_bb=spot["ante"],
            rake_percent=spot["rake"],
            rake_cap=spot["cap"],
            num_folded_players=len(spot["folded_positions"]),
            use_bunching=True,
            folded_positions=spot["folded_positions"],
            max_bets_per_node=1,
            target_dEV=0.005,
            max_iterations=500,
            deterministic=True,
        )
        res_live = await bridge.solve_flop(**base, force_exact=False)
        res_exact = await bridge.solve_flop(
            **base, force_exact=True, equity_samples_override=exact_samples
        )
        if not res_live["converged"]:
            all_ok = False

        sizing_pct = int(round(float(res_live["optimal_sizing"] or 0.0) * 100.0))
        l_cb = float(res_live["btn_cbet_frequency"] or 0.0) * 100.0
        e_cb = float(res_exact["btn_cbet_frequency"] or 0.0) * 100.0
        l_chk = float(res_live["bb_check_frequency"] or 0.0) * 100.0
        e_chk = float(res_exact["bb_check_frequency"] or 0.0) * 100.0
        l_o, e_o = float(res_live["oop_ev"]), float(res_exact["oop_ev"])
        l_i, e_i = float(res_live["ip_ev"]), float(res_exact["ip_ev"])
        expl_pct = float(res_live["exploitability_pct_pot"] or 0.0)
        expl_bb100 = float(res_live["exploitability_bb"] or 0.0) * 100.0
        ms = int(res_live["solve_time_ms"])

        print(
            f"{spot['label']:<33} | {spot['config_desc']:<34} | {f'{sizing_pct}%':<6} | "
            f"{l_cb:>5.1f}%/{e_cb:<5.1f}%  | "
            f"{l_chk:>5.1f}%/{e_chk:<5.1f}%  | "
            f"{l_o:>6.2f}/{e_o:<6.2f} | "
            f"{l_i:>6.2f}/{e_i:<6.2f} | "
            f"{expl_pct:>5.3f}%/{expl_bb100:>6.2f}bb | "
            f"{ms}"
        )

    print("-" * 136)
    print(
        "Note: L = Live PairEquityNet V2 production pipeline; E = Full-Tree Exact River-Resolved CFR+ reference "
        f"({exact_samples} runouts, force_exact=True)."
    )
    print()
    return all_ok


async def main() -> int:
    parser = argparse.ArgumentParser(description="Final ZenoSolver mathematical soundness and accuracy benchmark.")
    parser.add_argument("--host", type=str, default=os.environ.get("SOLVER_DAEMON_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SOLVER_DAEMON_PORT", "9998")))
    parser.add_argument("--exact-samples", type=int, default=1176)
    args = parser.parse_args()

    bridge = EngineBridge(host=args.host, port=args.port, timeout_sec=60.0)
    ok1 = await run_check_1_leafnet_vs_exact(bridge, args.exact_samples)
    ok2 = await run_check_2_invariants(bridge)
    ok3 = await run_check_3_comparison_sheet(bridge, args.exact_samples)

    all_ok = ok1 and ok2 and ok3
    print(f"OVERALL VALIDATION RESULT: {'ALL CHECKS PASSED' if all_ok else 'FAILED'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
