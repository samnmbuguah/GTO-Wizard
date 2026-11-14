#!/usr/bin/env python3
"""
scripts/data_gen/generate_equity_labels.py

Generates exact 169x169 pair-equity matrices for every board in the dataset.

Why this exists
---------------
The pair operator `E[i][j]` was originally trained from *range-averaged* share
targets (`t_oop = E @ r̂_ip`). That under-determines E: only the row averages
against the opponent ranges that happened to be sampled are constrained, so the
learned matrix can be wildly wrong for pairs that never showed up in a label
(measured: mean |ΔE| ~0.11-0.16 against the exact matrix).

This script asks the exact solver for the matrix itself, so the model can be
trained with direct pair-level supervision.

Each board is solved with `GTO_LEAF_NET=off` (exact showdown equity) and with
the board's own configuration (stack / ante / rake / cap / folded / bunching),
so the labels match the runtime context.

Usage:
    python scripts/data_gen/generate_equity_labels.py --ports 9971,9972,9973
    python scripts/data_gen/generate_equity_labels.py --ports 9971 --boards 20
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

N_CLASSES = 169


def ask(port: int, payload: Dict[str, Any], timeout: float = 300.0) -> Dict[str, Any]:
    sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    try:
        sock.sendall((json.dumps(payload) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(1 << 22)
            if not chunk:
                break
            buf += chunk
    finally:
        sock.close()
    return json.loads(buf.decode().strip())


def load_boards() -> List[Tuple[List[str], Dict[str, Any]]]:
    """Unique boards with their configuration from the stratified root dataset."""
    base = pd.read_parquet(REPO_ROOT / "datasets/generated/nl500_100bb_leaf_cfr.parquet")
    boards: List[str] = []
    seen = set()
    for b in base["board"]:
        key = " ".join(list(b))
        if key not in seen:
            seen.add(key)
            boards.append(key)

    root = pd.read_parquet(REPO_ROOT / "datasets/generated/nl500_100bb_real_cfr.parquet")
    configs: Dict[str, Dict[str, Any]] = {}
    for r in root.itertuples(index=False):
        key = " ".join(list(r.board))
        configs[key] = {
            "pot": float(r.pot),
            "stack": float(r.effective_stack),
            "ante": float(getattr(r, "ante_bb", 0.0)),
            "rake": float(r.rake_percent),
            "cap": float(r.rake_cap),
            "folded": int(getattr(r, "num_folded_players", 4)),
            "bunching": bool(getattr(r, "use_bunching", True)),
        }
    return [(k.split(), configs.get(k, {
        "pot": 5.5, "stack": 100.0, "ante": 0.0, "rake": 5.0, "cap": 0.6,
        "folded": 4, "bunching": True,
    })) for k in boards]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", default="9971,9972,9973,9974,9975,9976")
    ap.add_argument("--boards", type=int, default=0, help="0 = all boards")
    ap.add_argument("--samples", type=int, default=2000,
                    help="runouts per board (400 is the runtime default; 2000 cuts the "
                         "label noise from ~0.025 to ~0.01 mean absolute error)")
    ap.add_argument("--out", default=str(REPO_ROOT / "datasets/generated/equity_labels.parquet"))
    ap.add_argument("--progress-every", type=int, default=25)
    args = ap.parse_args()

    ports = [int(p) for p in args.ports.split(",") if p.strip()]
    items = load_boards()
    if args.boards:
        items = items[: args.boards]
    print(f"boards: {len(items)} | daemons: {ports}", flush=True)

    from backend.solutions.services.range_service import PreflopRangeService
    range_cache: Dict[Tuple[float, float], Tuple[Dict[str, float], Dict[str, float]]] = {}

    def ranges_for(cfg: Dict[str, Any]):
        key = (round(cfg["rake"], 4), round(cfg["cap"], 4))
        if key not in range_cache:
            range_cache[key] = PreflopRangeService.get_spot_ranges(
                "BTN_vs_BB_SRP", cfg["rake"], cfg["cap"])
        return range_cache[key]

    def run_shard(port: int, shard: List[Tuple[str, List[str], Dict[str, Any]]]):
        out: List[Dict[str, Any]] = []
        errors: List[str] = []
        for n, (key, board, cfg) in enumerate(shard, 1):
            oop, ip = ranges_for(cfg)
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
                "max_iterations": 60,
                "time_limit_ms": 1500,
                "collect_equity": True,
                "force_exact": True,
                "equity_samples_override": args.samples,
            }
            try:
                res = ask(port, payload)
            except Exception as exc:  # pragma: no cover
                errors.append(f"{key}: {exc}")
                continue
            eq = res.get("equity_matrix") or []
            if len(eq) != N_CLASSES * N_CLASSES:
                errors.append(f"{key}: bad equity matrix length {len(eq)}")
                continue
            arr = np.asarray(eq, dtype=np.float32).reshape(N_CLASSES, N_CLASSES)
            out.append({
                "board": board,
                "pot": cfg["pot"],
                "effective_stack": cfg["stack"],
                "ante_bb": cfg["ante"],
                "rake_percent": cfg["rake"],
                "rake_cap": cfg["cap"],
                "num_folded_players": cfg["folded"],
                "use_bunching": cfg["bunching"],
                "equity": arr.astype(np.float16).ravel().tolist(),
            })
            if n % args.progress_every == 0:
                print(f"  port {port}: {n}/{len(shard)} boards", flush=True)
        return out, errors

    shards = []
    for i, port in enumerate(ports):
        shards.append((port, [
            (" ".join(b), b, c) for j, (b, c) in enumerate(items) if j % len(ports) == i
        ]))

    rows: List[Dict[str, Any]] = []
    errors: List[str] = []
    with ThreadPoolExecutor(max_workers=len(ports)) as pool:
        futures = [pool.submit(run_shard, port, shard) for port, shard in shards]
        for fut in futures:
            r, e = fut.result()
            rows.extend(r)
            errors.extend(e)

    if errors:
        print(f"{len(errors)} errors, first 5:", flush=True)
        for e in errors[:5]:
            print(f"  {e}", flush=True)

    df = pd.DataFrame(rows)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df)} equity labels to {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
