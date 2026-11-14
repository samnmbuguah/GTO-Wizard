#!/usr/bin/env python3
"""
scripts/data_gen/generate_leaf_perturbations.py

Augments the per-class leaf dataset with reach perturbations.

The original leaf extraction solves each board once with the BTN/BB root ranges,
so every board contributes only 5-9 leaf rows and the model never sees the
skewed node-local reaches that CFR actually produces. This script re-solves the
same boards with randomly perturbed root ranges (multiplicative noise plus
random pruning), which produces many different reach distributions at the same
showdown nodes. Targets remain exact (`GTO_LEAF_NET=off`).

Output schema matches `datasets/generated/nl500_100bb_leaf_cfr.parquet`.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.solutions.services.range_service import PreflopRangeService


def ask_daemon(port: int, payload: Dict[str, Any], timeout: float = 120.0) -> Dict[str, Any]:
    sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
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
    if not buf.strip():
        raise RuntimeError("empty response")
    return json.loads(buf.decode().strip())


def perturb(weights: Dict[str, float], rng: np.random.Generator, sigma: float,
            prune: float) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for hand, w in weights.items():
        if w <= 0.0:
            continue
        if rng.random() < prune:
            continue
        out[hand] = float(w * np.exp(rng.normal(0.0, sigma)))
    if not out:
        out = dict(weights)
    # Keep the overall mass in the same ballpark; leaf values are linear in the
    # opponent's reach mass, so the absolute scale does not change the target
    # shares, only the reconstruction. Preserve the original total for
    # comparability with the unaugmented rows.
    target = sum(weights.values())
    cur = sum(out.values())
    if cur > 1e-12:
        scale = target / cur
        out = {k: v * scale for k, v in out.items()}
    return out


def build_leaf_rows(board: List[str], board_tag: str, res: Dict[str, Any],
                    pot: float, stack: float, rake_pct: float, rake_cap: float,
                    folded: int, ante_bb: float = 0.0) -> List[Dict[str, Any]]:
    rows = []
    for idx, ls in enumerate(res.get("leaf_samples", [])):
        inv_o = float(ls["invested"][0])
        inv_i = float(ls["invested"][1])
        tot_pot = pot + inv_o + inv_i
        rake = min(tot_pot * rake_pct / 100.0, rake_cap)
        rows.append({
            "spot_id": f"{board_tag}_leaf_{idx}",
            "board": board,
            "invested_oop": inv_o,
            "invested_ip": inv_i,
            "pot": tot_pot,
            "net_pot": tot_pot - rake,
            "effective_stack": stack,
            "ante_bb": ante_bb,
            "rake_percent": rake_pct,
            "rake_cap": rake_cap,
            "num_folded_players": folded,
            "reach_oop_json": json.dumps(ls["reach_oop"]),
            "reach_ip_json": json.dumps(ls["reach_ip"]),
            "v_oop_json": json.dumps(ls["v_oop"]),
            "v_ip_json": json.dumps(ls["v_ip"]),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", default="9971,9972,9973,9974,9975,9976")
    ap.add_argument("--perturbations", type=int, default=8)
    ap.add_argument("--sigma", type=float, default=0.7)
    ap.add_argument("--prune", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--pot", type=float, default=5.5)
    ap.add_argument("--stack", type=float, default=100.0)
    ap.add_argument("--rake-pct", type=float, default=5.0)
    ap.add_argument("--rake-cap", type=float, default=0.6)
    ap.add_argument("--max-iterations", type=int, default=2000)
    ap.add_argument("--time-limit-ms", type=int, default=5000)
    ap.add_argument("--out", default=str(REPO_ROOT / "datasets/generated/leaf_cfr_aug_multiconfig.parquet"))
    args = ap.parse_args()

    ports = [int(p) for p in args.ports.split(",") if p.strip()]

    base = pd.read_parquet(REPO_ROOT / "datasets/generated/nl500_100bb_leaf_cfr.parquet")
    boards = []
    seen = set()
    for b in base["board"]:
        key = " ".join(list(b))
        if key not in seen:
            seen.add(key)
            boards.append(list(b))

    # Each board was solved under one configuration in the stratified root
    # dataset. Re-use that exact configuration here so the augmentation covers
    # cash NL500/NL50 and MTT 20-100bb with the right stack/ante/rake/bunching.
    configs: Dict[str, Dict[str, Any]] = {}
    root_path = REPO_ROOT / "datasets/generated/nl500_100bb_real_cfr.parquet"
    if root_path.exists():
        root = pd.read_parquet(root_path)
        for r in root.itertuples(index=False):
            key = " ".join(list(r.board))
            configs[key] = {
                "pot": float(r.pot),
                "stack": float(r.effective_stack),
                "ante": float(getattr(r, "ante_bb", 0.0)),
                "rake": float(r.rake_percent),
                "cap": float(r.rake_cap),
                "folded": int(getattr(r, "num_folded_players", 4))
                if bool(getattr(r, "use_bunching", True)) else 0,
                "bunching": bool(getattr(r, "use_bunching", True)),
            }
        print(f"Loaded per-board configs for {len(configs)} boards from {root_path.name}")

    default_cfg = {
        "pot": args.pot, "stack": args.stack, "ante": 0.0,
        "rake": args.rake_pct, "cap": args.rake_cap,
        "folded": 4, "bunching": True,
    }

    # Precompute root ranges per (rake, cap); ranges are rake-sensitive.
    range_cache: Dict[Tuple[float, float], Tuple[Dict[str, float], Dict[str, float]]] = {}
    for cfg in configs.values():
        key = (round(cfg["rake"], 4), round(cfg["cap"], 4))
        if key not in range_cache:
            range_cache[key] = PreflopRangeService.get_spot_ranges(
                "BTN_vs_BB_SRP", cfg["rake"], cfg["cap"]
            )
    dkey = (round(default_cfg["rake"], 4), round(default_cfg["cap"], 4))
    if dkey not in range_cache:
        range_cache[dkey] = PreflopRangeService.get_spot_ranges(
            "BTN_vs_BB_SRP", default_cfg["rake"], default_cfg["cap"]
        )

    print(f"Boards: {len(boards)} | perturbations/board: {args.perturbations} | workers: {len(ports)}")

    shards: List[Tuple[int, List[List[str]]]] = []
    for i, port in enumerate(ports):
        shards.append((port, boards[i::len(ports)]))

    def run_shard(port: int, shard: List[List[str]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        rng = np.random.default_rng(args.seed + port)
        for n, board in enumerate(shard, 1):
            board_tag = " ".join(board)
            cfg = configs.get(board_tag, default_cfg)
            oop0, ip0 = range_cache[(round(cfg["rake"], 4), round(cfg["cap"], 4))]
            for k in range(args.perturbations):
                if k == 0:
                    oop, ip = oop0, ip0
                else:
                    oop = perturb(oop0, rng, args.sigma, args.prune)
                    ip = perturb(ip0, rng, args.sigma, args.prune)
                payload = {
                    "board": board,
                    "oop_range": oop,
                    "ip_range": ip,
                    "pot": cfg["pot"],
                    "effective_stack": cfg["stack"],
                    "ante_bb": cfg["ante"],
                    "rake_percent": cfg["rake"],
                    "rake_cap": cfg["cap"],
                    "num_folded_players": cfg["folded"],
                    "use_bunching": cfg["bunching"],
                    "max_bets_per_node": 1,
                    "target_dEV": 0.005,
                    "max_iterations": args.max_iterations,
                    "time_limit_ms": args.time_limit_ms,
                    "collect_leaves": True,
                }
                res = ask_daemon(port, payload)
                if "error" in res:
                    raise RuntimeError(res["error"])
                out.extend(build_leaf_rows(board, f"{board_tag}_p{k}", res, cfg["pot"],
                                           cfg["stack"], cfg["rake"], cfg["cap"],
                                           cfg["folded"], ante_bb=cfg["ante"]))
            if n % 10 == 0:
                print(f"  port {port}: {n}/{len(shard)} boards ({len(out)} leaf rows)")
        return out

    started = time.perf_counter()
    rows: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, len(ports))) as pool:
        futures = [pool.submit(run_shard, port, shard) for port, shard in shards]
        for fut in futures:
            rows.extend(fut.result())
    wall = time.perf_counter() - started

    df = pd.DataFrame(rows)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, engine="pyarrow", compression="snappy", index=False)
    print(f"\nWrote {len(df)} augmented leaf rows in {wall:.1f}s")
    print(f"  {out} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
