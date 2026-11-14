#!/usr/bin/env python3
"""
scripts/verify_model_accuracy.py

Verification harness for the two-model architecture:
- Model 1: Bet Size Predictor
- Model 2: Flop-to-Turn Counterfactual Leaf Value Network

The engine bridge talks to the real CFR daemon, so the "ground truth" below is
an actual best-response solve. Both models are retrained on
`datasets/generated/nl500_100bb_real_cfr.parquet`, generated from 1,755
canonical flops solved by that daemon.

Verification Checks:
1. Exploitability (best response) audit across 50 canonical boards
2. Leaf model vs. real CFR on 25 representative spots (residual error after
   retraining on real CFR labels)
3. Reference table for 5 canonical spots (for manual comparison; does not call
   ZenoSolver, whose Terms prohibit automated benchmarking)
"""

import os
import sys
import json
import time
import asyncio
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple

import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.features import (
    encode_board,
    encode_range,
    CLASS_TO_SIZE,
    CANDIDATE_SIZES,
)
from ml.models.size_predictor import BetSizePredictor
from ml.models.leaf_value_net import LeafValueNet
from backend.solutions.services.range_service import PreflopRangeService
from backend.solutions.services.engine_bridge import EngineBridge

try:
    from scripts.canonical_boards import CANONICAL_50_BOARDS
except Exception:  # pragma: no cover
    CANONICAL_50_BOARDS = [
        ["Ah", "Kd", "2c"], ["As", "Qh", "5d"], ["Ad", "Jc", "4h"], ["Ah", "Th", "3c"],
        ["As", "8c", "2d"], ["Kh", "Qd", "4c"], ["Ks", "Jc", "3d"], ["Kd", "Tc", "2h"],
        ["Qh", "Jd", "3c"], ["Qs", "Tc", "2d"], ["Jh", "Tc", "4d"], ["Ah", "7c", "2s"],
        ["9s", "8h", "7s"], ["9d", "8c", "7h"], ["8s", "7c", "6d"], ["7s", "6h", "5d"],
        ["Ts", "9d", "8h"], ["Jh", "Ts", "9c"], ["Qs", "Jh", "Td"], ["6s", "5h", "4d"],
        ["5s", "4h", "3d"], ["9s", "7c", "6d"], ["8s", "6h", "5c"], ["Ts", "8h", "7d"],
        ["Js", "9c", "8d"],
        ["8s", "8h", "2c"], ["Ks", "Kh", "3d"], ["As", "Ah", "5c"], ["Qs", "Qc", "7d"],
        ["Js", "Jd", "4c"], ["Ts", "Tc", "8d"], ["7s", "7h", "2d"], ["6s", "6c", "3h"],
        ["5s", "5d", "2c"], ["4s", "4h", "9c"], ["3s", "3c", "Kd"], ["2s", "2h", "Ac"],
        ["8s", "8h", "8d"], ["Kh", "Kd", "Ks"], ["2s", "2c", "2d"],
        ["Kh", "Th", "4h"], ["As", "8s", "2s"], ["Qd", "Jd", "5d"], ["Jh", "9h", "4h"],
        ["Ts", "7s", "2s"], ["8c", "6c", "3c"], ["Kd", "9d", "3d"], ["Ac", "Tc", "7c"],
        ["Qh", "8h", "3h"], ["9s", "5s", "2s"],
    ]

REFERENCE_5_SPOTS = [
    {"board": ["Ah", "Kd", "2c"], "desc": "Dry Ace-High (A-K-2 rainbow)"},
    {"board": ["9s", "8h", "7s"], "desc": "Wet Connected (9-8-7 two-tone)"},
    {"board": ["8s", "8h", "2c"], "desc": "Paired Board (8-8-2 rainbow)"},
    {"board": ["Kh", "Th", "4h"], "desc": "Monotone Flush (K-T-4 monotone)"},
    {"board": ["Qs", "Jd", "4c"], "desc": "Broadway Unpaired (Q-J-4 rainbow)"},
]


def load_trained_models(artifact_dir: Path) -> Tuple[BetSizePredictor, LeafValueNet]:
    """Loads Model 1 and Model 2 weights from artifact directory."""
    m1_path = artifact_dir / "size_predictor.pt"
    m2_path = artifact_dir / "leaf_value_net.pt"

    if not m1_path.exists():
        # Fallback to ml/checkpoints if ml/artifacts not yet populated
        m1_alt = REPO_ROOT / "ml" / "checkpoints" / "size_predictor.pt"
        if m1_alt.exists():
            m1_path = m1_alt
    if not m2_path.exists():
        m2_alt = REPO_ROOT / "ml" / "checkpoints" / "leaf_value_net.pt"
        if m2_alt.exists():
            m2_path = m2_alt

    if not m1_path.exists() or not m2_path.exists():
        raise FileNotFoundError(f"Missing model checkpoints: m1={m1_path.exists()}, m2={m2_path.exists()}")

    m1 = BetSizePredictor(input_dim=82, hidden_dim=128, num_classes=4)
    m1.load_state_dict(torch.load(m1_path, map_location=torch.device("cpu")))
    m1.eval()

    m2 = LeafValueNet()
    m2.load_state_dict(torch.load(m2_path, map_location=torch.device("cpu")))
    m2.eval()

    return m1, m2


def run_exploitability_audit(
    m1: BetSizePredictor,
    m2: LeafValueNet,
    bridge: EngineBridge,
    boards: List[List[str]],
    threshold_pct: float = 0.5,
) -> Dict[str, Any]:
    """
    Runs the real daemon on every canonical board and reports the exploitability
    it measured, as a percentage of the pot.

    The threshold is expressed in percent of pot because that is the unit the
    engine reports. ``exploitability_bb`` (NashConv/2 in bb) is shown alongside
    it so the two can be cross-checked. The engine solves a depth-limited game:
    future streets are replaced by showdown equity, so these values measure
    convergence to *that* game, not to a full multi-street equilibrium.
    """
    print("\n" + "=" * 100)
    print(" 1. EXPLOITABILITY (BEST RESPONSE) AUDIT ACROSS 50 CANONICAL BOARDS")
    print("=" * 100)
    print(
        f"{'#':<3} | {'Board':<11} | {'Texture':<18} | {'Pred Size':<10} | "
        f"{'expl% pot':<10} | {'expl bb':<9} | {'iters':<6} | {'conv':<5} | Status"
    )
    print("-" * 100)

    # Real BTN (IP) vs BB (OOP) ranges, not empty placeholder dicts.
    oop_range, ip_range = PreflopRangeService.get_spot_ranges("BTN_vs_BB_SRP", 5.0, 0.6)

    results = []
    exceeded = []
    loop = asyncio.new_event_loop()

    for idx, board in enumerate(boards, 1):
        board_str = " ".join(board)
        # Classify texture
        ranks = [c[0] for c in board]
        suits = [c[1] for c in board]
        is_paired = len(set(ranks)) < len(ranks)
        is_monotone = len(set(suits)) == 1
        is_twotone = len(set(suits)) == 2
        high_ace = "A" in ranks

        if is_monotone:
            tex = "Monotone Flush"
        elif is_paired:
            tex = "Paired Board"
        elif high_ace:
            tex = "Dry Ace-High"
        elif is_twotone:
            tex = "Wet Connected"
        else:
            tex = "Rainbow Dynamic"

        # Model 1 prediction
        pred_size, _ = m1.predict_size(board, pot=5.5, effective_stack=100.0)

        res = loop.run_until_complete(
            bridge.solve_flop(
                board=board,
                oop_range=oop_range,
                ip_range=ip_range,
                pot=5.5,
                effective_stack=100.0,
                rake_percent=5.0,
                rake_cap=0.6,
                max_bets_per_node=1,
            )
        )
        wall_ms = float(res.get("solve_time_ms", 0))

        expl_pct = res.get("exploitability_pct_pot")
        expl_bb = res.get("exploitability_bb")
        converged = bool(res.get("converged", False))
        iters = int(res.get("iterations", 0))

        if expl_pct is None:
            # No fabricated fallback: an engine that did not report a value is a
            # failure, not a passing board.
            passed = False
            expl_pct = float("nan")
            expl_bb = float("nan")
        else:
            passed = expl_pct <= threshold_pct and converged

        status_str = "PASS" if passed else "FAIL"
        if not passed:
            exceeded.append((board_str, expl_pct))

        results.append({
            "board": board_str,
            "texture": tex,
            "pred_size": f"{int(pred_size*100)}%",
            "exploit_pct_pot": expl_pct,
            "exploit_bb": expl_bb,
            "solve_time_ms": wall_ms,
            "iterations": iters,
            "converged": converged,
            "engine": res.get("engine", "unknown"),
            "leaf_mode": res.get("leaf_mode", "unknown"),
            "passed": passed,
        })

        if idx <= 15 or idx % 10 == 0 or idx == len(boards):
            print(
                f"{idx:<3} | {board_str:<11} | {tex:<18} | {int(pred_size*100):>3}% pot   | "
                f"{expl_pct:<10.3f} | {expl_bb:<9.4f} | {iters:<6} | "
                f"{str(converged):<5} | {status_str}"
            )

    loop.close()

    valid = [r["exploit_pct_pot"] for r in results if not np.isnan(r["exploit_pct_pot"])]
    engines = {r["engine"] for r in results}
    latencies = [r["solve_time_ms"] for r in results]
    avg_exploit = float(np.mean(valid)) if valid else float("nan")
    max_exploit = float(np.max(valid)) if valid else float("nan")

    print("-" * 100)
    print("Audit Summary:")
    print(f"  • Engine(s)               : {', '.join(sorted(engines))}")
    print(f"  • Total Boards Tested     : {len(results)}")
    print(f"  • Mean Exploitability     : {avg_exploit:.3f}% pot")
    print(f"  • Max Exploitability      : {max_exploit:.3f}% pot (threshold: {threshold_pct:.2f}% pot)")
    print(f"  • Converged               : {sum(r['converged'] for r in results)}/{len(results)}")
    print(
        f"  • Solve latency           : mean {np.mean(latencies):.0f} ms, "
        f"p50 {np.percentile(latencies, 50):.0f} ms, p95 {np.percentile(latencies, 95):.0f} ms"
    )
    print(f"  • Iterations              : mean {np.mean([r['iterations'] for r in results]):.0f}, "
          f"max {max(r['iterations'] for r in results)}")
    modes: Dict[str, int] = {}
    for r in results:
        modes[r["leaf_mode"]] = modes.get(r["leaf_mode"], 0) + 1
    print("  • Leaf evaluator          : " + ", ".join(f"{k} {v}/{len(results)}" for k, v in sorted(modes.items())))
    print(f"  • Pass Rate               : {(len(results) - len(exceeded)) / len(results) * 100.0:.1f}%")
    if exceeded:
        print(f"  • Flagged boards           : {exceeded}")
    else:
        print(f"  • All tested boards converged below {threshold_pct:.2f}% pot exploitability.")

    return {
        "results": results,
        "avg_exploit": avg_exploit,
        "max_exploit": max_exploit,
        "pass_rate": (len(results) - len(exceeded)) / len(results),
        "exceeded": exceeded,
    }


def run_ground_truth_comparison(
    m1: BetSizePredictor,
    m2: LeafValueNet,
    bridge: EngineBridge,
    boards: List[List[str]],
) -> Dict[str, Any]:
    """
    Compares Model 2's per-class leaf values against exact showdown values at the
    same leaf states.

    Ground truth is ``datasets/generated/nl500_100bb_leaf_cfr.parquet``, produced
    by the Rust solver with ``GTO_LEAF_NET=off``. Each row is one public showdown
    node with its exact node-local reaches and exact per-class counterfactual
    values, so this measures the model on the quantity the engine consumes. The
    earlier version compared a leaf model at the root, which is not a leaf state
    and overstated the error.
    """
    import pandas as pd

    print("\n" + "=" * 100)
    print(" 2. LEAF MODEL vs EXACT SHOWDOWN VALUES AT LEAF NODES - DIAGNOSTIC")
    print("=" * 100)

    paths = [
        REPO_ROOT / "datasets/generated/nl500_100bb_leaf_cfr.parquet",
        REPO_ROOT / "datasets/generated/nl500_100bb_leaf_cfr_aug.parquet",
    ]
    frames = []
    for p in paths:
        if p.exists():
            d = pd.read_parquet(p)
            d["source_col"] = "perturbed" if "aug" in p.name else "unaugmented"
            frames.append(d)
    if not frames:
        print("  leaf datasets missing")
        return {"mae_ev": float("nan"), "mae_p95": float("nan"),
                "val_mae": float("nan"), "val_p95": float("nan")}

    df = pd.concat(frames, ignore_index=True)
    df["_key"] = [
        f"{' '.join(list(b))}_{int(f)}"
        for b, f in zip(df["board"], df["num_folded_players"])
    ]
    # Reproduce the training split (shuffle sorted board keys with seed 0, hold
    # out the first 15%) so every row below is from an unseen board.
    uniq = np.unique(df["_key"].to_numpy())
    rng = np.random.default_rng(0)
    rng.shuffle(uniq)
    val_boards = set(uniq[: int(0.15 * len(uniq))])
    sub = df[df["_key"].isin(val_boards)].copy()
    if sub.empty:
        print("  no held-out leaf rows found")
        return {"mae_ev": float("nan"), "mae_p95": float("nan"),
                "val_mae": float("nan"), "val_p95": float("nan")}

    print(
        f"  held-out: {len(sub)} leaf rows across {len(val_boards)} unseen boards "
        f"(same board split as ml/train_leaf_model.py)"
    )
    print(
        f"{'#':<3} | {'Board':<11} | {'Rows':>5} | {'Range EV MAE':<13} | "
        f"{'p95':<8} | {'Max':<8} | {'Source'}"
    )
    print("-" * 100)

    errs: List[float] = []
    source_errs: Dict[str, List[float]] = {}
    per_board: Dict[str, List[float]] = {}
    per_board_src: Dict[str, str] = {}
    for r in sub.itertuples(index=False):
        board = list(r.board)
        ro = np.array(json.loads(r.reach_oop_json), dtype=np.float64)
        ri = np.array(json.loads(r.reach_ip_json), dtype=np.float64)
        vo_true = np.array(json.loads(r.v_oop_json), dtype=np.float64)
        vi_true = np.array(json.loads(r.v_ip_json), dtype=np.float64)
        start_pot = float(r.pot) - float(r.invested_oop) - float(r.invested_ip)
        v_o, v_i = m2.evaluate_leaf(
            board=board,
            reach_oop=ro,
            reach_ip=ri,
            invested_oop=float(r.invested_oop),
            invested_ip=float(r.invested_ip),
            pot=start_pot,
            rake_pct=float(r.rake_percent),
            rake_cap=float(r.rake_cap),
            effective_stack=float(r.effective_stack),
            ante_bb=float(r.ante_bb),
            num_folded_players=int(r.num_folded_players),
        )
        e = 0.5 * (
            abs(float(ro @ v_o) - float(ro @ vo_true))
            + abs(float(ri @ v_i) - float(ri @ vi_true))
        )
        errs.append(e)
        key = " ".join(board)
        per_board.setdefault(key, []).append(e)
        per_board_src[key] = r.source_col
        source_errs.setdefault(r.source_col, []).append(e)

    for idx, (board_str, board_errs) in enumerate(per_board.items(), 1):
        if idx <= 12 or idx == len(per_board):
            arr = np.array(board_errs)
            print(
                f"{idx:<3} | {board_str:<11} | {len(arr):>5} | {arr.mean():<13.4f} | "
                f"{np.percentile(arr, 95):<8.4f} | {arr.max():<8.4f} | "
                f"{per_board_src[board_str]}"
            )

    arr = np.array(errs)
    if arr.size == 0:
        print("  no leaf rows to evaluate")
        return {"mae_ev": float("nan"), "mae_p95": float("nan"),
                "val_mae": float("nan"), "val_p95": float("nan")}

    print("-" * 100)
    print("Leaf-value accuracy on unseen boards (per-leaf range EV vs exact showdown):")
    print(f"  • All held-out   : MAE {arr.mean():.4f} bb | p95 {np.percentile(arr, 95):.4f} bb | "
          f"max {arr.max():.4f} bb | n={len(arr)}")
    for src in ("unaugmented", "perturbed"):
        vals = np.array(source_errs.get(src, []))
        if vals.size:
            print(f"  • {src:<13}: MAE {vals.mean():.4f} bb | "
                  f"p95 {np.percentile(vals, 95):.4f} bb | n={vals.size}")
    print(
        "  • Ground truth is exact (GTO_LEAF_NET=off); values are compared at each\n"
        "    leaf's own reaches, before any strategy-dependent caching. Errors are\n"
        "    reach-mass-weighted pot contributions (m_o*m_i*EV), so they are smaller\n"
        "    than the normalised per-unit metric logged during training."
    )
    print("=" * 100)

    return {
        "mae_ev": float(arr.mean()),
        "mae_p95": float(np.percentile(arr, 95)),
        "val_mae": float(arr.mean()),
        "val_p95": float(np.percentile(arr, 95)),
    }


def run_reference_spot_table(
    m1: BetSizePredictor,
    m2: LeafValueNet,
    bridge: EngineBridge,
) -> None:
    """
    Prints a reference table for 5 canonical spots, produced entirely by our own
    engine.

    This used to be called the "ZenoSolver spot check", but it never called
    ZenoSolver. ZenoSolver's Terms prohibit automated benchmarking, so a real
    side-by-side comparison has to be done by hand (see
    scripts/reference_spot_check.py and docs/reference_spots.example.csv). Treat
    the numbers below as our own reference output, not as ZenoSolver values.
    """
    print("\n" + "=" * 100)
    print(" 3. OUR ENGINE REFERENCE TABLE (5 CANONICAL SPOTS)")
    print("=" * 100)
    print("Baseline: 6-Max NL500 | 100bb Stacks | 2.5bb Open | Pot 5.5bb | 5.0% Rake (0.6bb Cap)")
    print("These are our own CFR numbers, NOT ZenoSolver output.")
    print("-" * 100)
    print(
        f"{'Flop Board':<12} | {'Texture Description':<24} | {'Model1 Size':<11} | "
        f"{'IP C-Bet%':<10} | {'OOP Check%':<11} | {'OOP EV':<8} | {'IP EV'}"
    )
    print("-" * 100)

    oop_range_raw, ip_range_raw = PreflopRangeService.get_spot_ranges("BTN_vs_BB_SRP", 5.0, 0.6)
    loop = asyncio.new_event_loop()

    for spot in REFERENCE_5_SPOTS:
        board = spot["board"]
        desc = spot["desc"]
        board_str = " ".join(board)

        # Model 1 sizing prediction
        pred_size, _ = m1.predict_size(board, pot=5.5, effective_stack=100.0)

        res = loop.run_until_complete(
            bridge.solve_flop(
                board=board,
                oop_range=oop_range_raw,
                ip_range=ip_range_raw,
                pot=5.5,
                effective_stack=100.0,
                rake_percent=5.0,
                rake_cap=0.6,
                max_bets_per_node=1,
            )
        )

        cbet_pct = (res.get("btn_cbet_frequency") or 0.0) * 100.0
        check_pct = (res.get("bb_check_frequency") or 0.0) * 100.0
        oop_ev = res.get("oop_ev") or 0.0
        ip_ev = res.get("ip_ev") or 0.0

        print(
            f"{board_str:<12} | {desc:<24} | {int(pred_size * 100):>3}% pot    | "
            f"{cbet_pct:>6.1f}%   | {check_pct:>7.1f}%    | {oop_ev:>6.2f}bb | {ip_ev:>6.2f}bb"
        )

    loop.close()
    print("=" * 100)
    print("To compare with ZenoSolver, enter their published values manually in")
    print("docs/reference_spots.example.csv and run scripts/reference_spot_check.py.")


def main():
    parser = argparse.ArgumentParser(description="Two-model accuracy harness (real CFR ground truth)")
    parser.add_argument("--artifacts", type=str, default="ml/artifacts", help="Path to trained model weights")
    parser.add_argument(
        "--threshold-pct",
        type=float,
        default=0.5,
        help="Max converged exploitability in percent of pot (default: 0.5)",
    )
    args = parser.parse_args()

    artifact_dir = REPO_ROOT / args.artifacts
    print("=" * 90)
    print(" AUTOMATED MODEL ACCURACY & VERIFICATION HARNESS")
    print("=" * 90)
    print(f"Artifacts Directory : {artifact_dir}")
    print(f"Exploitability Limit: < {args.threshold_pct:.2f}% pot (real NashConv/2)")

    m1, m2 = load_trained_models(artifact_dir)
    print("Loaded Model 1 (BetSizePredictor) and Model 2 (LeafValueNet).")

    bridge = EngineBridge(host=os.environ.get("SOLVER_DAEMON_HOST", "127.0.0.1"),
                          port=int(os.environ.get("SOLVER_DAEMON_PORT", "9998")),
                          timeout_sec=30.0)

    # 1. Exploitability Audit
    audit_res = run_exploitability_audit(
        m1, m2, bridge, CANONICAL_50_BOARDS, threshold_pct=args.threshold_pct
    )

    # 2. Leaf model vs real CFR (diagnostic)
    gt_res = run_ground_truth_comparison(m1, m2, bridge, CANONICAL_50_BOARDS)

    # 3. Our own reference table
    run_reference_spot_table(m1, m2, bridge)

    print("\n" + "=" * 90)
    print(" FULL ACCURACY VERIFICATION REPORT SUMMARY")
    print("=" * 90)
    print(f"  • Exploitability Audit Pass Rate : {audit_res['pass_rate'] * 100.0:.1f}%")
    print(f"  • Mean Exploitability            : {audit_res['avg_exploit']:.3f}% pot")
    print(f"  • Max Exploitability             : {audit_res['max_exploit']:.3f}% pot")
    print(f"  • Leaf-value MAE (held-out)      : {gt_res['mae_ev']:.4f} bb (p95 {gt_res['mae_p95']:.4f})")
    print("    (range-EV error at exact leaf nodes, unseen boards)")
    print("=" * 90)
    print("Note: flop/turn solves are depth-limited; river solves are exact.")


if __name__ == "__main__":
    main()
