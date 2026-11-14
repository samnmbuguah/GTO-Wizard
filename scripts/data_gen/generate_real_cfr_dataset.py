#!/usr/bin/env python3
"""
scripts/data_gen/generate_real_cfr_dataset.py

Generates a training dataset by solving all 1,755 strategically distinct flops
with the live Rust CFR+ daemon.

This replaces the old `generate_leaf_data.py`, which shells out to a
`batch_leaf_gen` binary that no longer exists and which produced labels from the
retired heuristic. This generator:

  * enumerates the 1,755 canonical (suit-isomorphic) flops,
  * sends each one to a real CFR daemon over TCP,
  * records the real root EVs, frequencies, per-hand EVs, strategy and measured
    exploitability,
  * rejects any response whose engine label is a heuristic fallback,
  * writes JSONL + Parquet and validates the schema/math invariants.

Usage:
    # one daemon on the default port
    python scripts/data_gen/generate_real_cfr_dataset.py

    # six daemons for parallel generation
    python scripts/data_gen/generate_real_cfr_dataset.py --ports 9971,9972,9973,9974,9975,9976
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations, permutations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

RANKS = "23456789TJQKA"
SUITS = "shdc"
DEFAULT_OUT = REPO_ROOT / "datasets" / "generated" / "nl500_100bb_real_cfr"

PY_SCHEMA_FIELDS = [
    "spot_id",
    "street",
    "board",
    "position_oop",
    "position_ip",
    "pot",
    "effective_stack",
    "pot_type",
    "rake_percent",
    "rake_cap",
    "max_bets_per_node",
    "oop_range",
    "ip_range",
    "oop_ev",
    "ip_ev",
    "exploitability",
    "solve_time_ms",
    "overall_frequencies",
    "strategy",
]


def canonical_flops() -> List[List[str]]:
    """All 1,755 suit-isomorphic flops, as three-card lists."""
    deck = [r + s for r in RANKS for s in SUITS]
    seen: set[Tuple[str, ...]] = set()
    out: List[List[str]] = []
    for flop in combinations(deck, 3):
        best: Optional[Tuple[str, ...]] = None
        for perm in permutations(SUITS):
            mapping = dict(zip(SUITS, perm))
            key = tuple(sorted(c[0] + mapping[c[1]] for c in flop))
            if best is None or key < best:
                best = key
        if best is not None and best not in seen:
            seen.add(best)
            out.append(list(best))
    out.sort()
    return out


def ask_daemon(port: int, payload: Dict[str, Any], timeout: float = 120.0) -> Dict[str, Any]:
    sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    try:
        sock.sendall((json.dumps(payload) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(1 << 16)
            if not chunk:
                break
            buf += chunk
    finally:
        sock.close()
    if not buf.strip():
        raise RuntimeError("empty response")
    return json.loads(buf.decode().strip())


def make_record(board: List[str], res: Dict[str, Any], oop_range: Dict[str, float],
                ip_range: Dict[str, float], pot: float, stack: float,
                rake_pct: float, rake_cap: float, ante_bb: float = 0.0,
                num_folded_players: int = 4, use_bunching: bool = True,
                config_tag: str = "nl500_100bb") -> Dict[str, Any]:
    return {
        "spot_id": f"{' '.join(board)}__{config_tag}",
        "config_tag": config_tag,
        "street": "flop",
        "board": board,
        "position_oop": "BB",
        "position_ip": "BTN",
        "pot": pot,
        "effective_stack": stack,
        "ante_bb": ante_bb,
        "num_folded_players": num_folded_players,
        "use_bunching": use_bunching,
        "pot_type": "SRP",
        "rake_percent": rake_pct,
        "rake_cap": rake_cap,
        "max_bets_per_node": 1,
        "oop_range": oop_range,
        "ip_range": ip_range,
        "oop_ev": float(res["oop_ev"]),
        "ip_ev": float(res["ip_ev"]),
        "exploitability": float(res["exploitability"]),
        "exploitability_pct_pot": float(res.get("exploitability_pct_pot", 0.0)),
        "exploitability_bb": float(res.get("exploitability_bb", 0.0)),
        "solve_time_ms": int(res.get("solve_time_ms", 0)),
        "iterations": int(res.get("iterations", 0)),
        "converged": bool(res.get("converged", False)),
        "optimal_sizing": float(res.get("optimal_sizing", 0.0)),
        "engine": str(res.get("engine", "")),
        "overall_frequencies": res["overall_frequencies"],
        "strategy": res["strategy"],
        "strategy_detail": res.get("strategy_detail", {}),
        "hand_ev": res.get("hand_ev", {}),
        "tree_nodes": int(res.get("tree_nodes", 0)),
        "equity_samples": int(res.get("equity_samples", 0)),
        "leaf_samples": res.get("leaf_samples", []),
    }


def validate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    missing = sum(1 for r in records for f in PY_SCHEMA_FIELDS if f not in r)
    heuristic = [r["spot_id"] for r in records if "heuristic" in str(r.get("engine", "")).lower()]
    non_converged = [r["spot_id"] for r in records if not r.get("converged")]
    bad_norm = 0
    bad_conserve = 0
    for r in records:
        pot = float(r["pot"])
        rake_pct = float(r["rake_percent"])
        rake_cap = float(r["rake_cap"])
        net_pot = pot - min(pot * rake_pct / 100.0, rake_cap)
        for freqs in r["strategy"].values():
            s = freqs.get("fold", 0.0) + freqs.get("call", 0.0) + freqs.get("raise", 0.0)
            if abs(s - 1.0) > 1e-3:
                bad_norm += 1
        if abs(r["oop_ev"] + r["ip_ev"] - net_pot) > 0.25:
            bad_conserve += 1
    return {
        "records": len(records),
        "missing_fields": missing,
        "heuristic_rows": heuristic,
        "non_converged": non_converged,
        "normalization_errors": bad_norm,
        "conservation_errors": bad_conserve,
        "distinct_exploitability": len({round(r["exploitability_pct_pot"], 4) for r in records}),
        "distinct_ev_pairs": len({(round(r["oop_ev"], 3), round(r["ip_ev"], 3)) for r in records}),
        "engines": sorted({r["engine"] for r in records}),
    }


MULTI_CONFIGS = [
    {"tag": "nl500_100bb", "pot": 5.5, "stack": 100.0, "ante": 0.0,   "rake": 5.0, "cap": 0.6, "folded": 4, "bunching": True},
    {"tag": "nl500_100bb", "pot": 5.5, "stack": 100.0, "ante": 0.0,   "rake": 5.0, "cap": 0.6, "folded": 4, "bunching": True},
    {"tag": "nl50_100bb",  "pot": 5.5, "stack": 100.0, "ante": 0.0,   "rake": 5.0, "cap": 4.0, "folded": 4, "bunching": True},
    {"tag": "mtt_20bb",    "pot": 6.5, "stack": 20.0,  "ante": 0.125, "rake": 0.0, "cap": 0.0, "folded": 4, "bunching": True},
    {"tag": "mtt_40bb",    "pot": 6.5, "stack": 40.0,  "ante": 0.125, "rake": 0.0, "cap": 0.0, "folded": 4, "bunching": True},
    {"tag": "mtt_60bb",    "pot": 6.5, "stack": 60.0,  "ante": 0.125, "rake": 0.0, "cap": 0.0, "folded": 4, "bunching": True},
    {"tag": "mtt_100bb",   "pot": 6.5, "stack": 100.0, "ante": 0.125, "rake": 0.0, "cap": 0.0, "folded": 4, "bunching": True},
    {"tag": "hu_nobunch",  "pot": 5.5, "stack": 100.0, "ante": 0.0,   "rake": 5.0, "cap": 0.6, "folded": 0, "bunching": False},
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ports", default="9998", help="Comma-separated daemon ports")
    parser.add_argument("--pot", type=float, default=5.5)
    parser.add_argument("--stack", type=float, default=100.0)
    parser.add_argument("--ante", type=float, default=0.0)
    parser.add_argument("--rake-pct", type=float, default=5.0)
    parser.add_argument("--rake-cap", type=float, default=0.6)
    parser.add_argument("--folded", type=int, default=4)
    parser.add_argument("--no-bunching", action="store_true")
    parser.add_argument("--multi-config", action="store_true", help="Stratify across cash NL500/NL50, MTT 20-100bb, and HU/no-bunching")
    parser.add_argument("--max-iterations", type=int, default=2000)
    parser.add_argument("--time-limit-ms", type=int, default=5000)
    parser.add_argument("--target-dev", type=float, default=0.005)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()

    from backend.solutions.services.range_service import PreflopRangeService

    ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]
    oop_range, ip_range = PreflopRangeService.get_spot_ranges(
        "BTN_vs_BB_SRP", args.rake_pct, args.rake_cap
    )
    boards = canonical_flops()
    print(f"Canonical flops: {len(boards)} | workers(ports): {len(ports) or 1} | multi_config={args.multi_config}")
    print(f"Ranges: OOP {len(oop_range)} hands, IP {len(ip_range)} hands")

    jobs: List[Tuple[List[str], Dict[str, Any]]] = []
    for i, board in enumerate(boards):
        if args.multi_config:
            cfg = MULTI_CONFIGS[i % len(MULTI_CONFIGS)]
        else:
            cfg = {
                "tag": "custom",
                "pot": args.pot,
                "stack": args.stack,
                "ante": args.ante,
                "rake": args.rake_pct,
                "cap": args.rake_cap,
                "folded": 0 if args.no_bunching else args.folded,
                "bunching": not args.no_bunching,
            }
        jobs.append((board, cfg))

    shards: List[Tuple[int, List[Tuple[List[str], Dict[str, Any]]]]] = []
    for i, port in enumerate(ports):
        shards.append((port, jobs[i::len(ports)]))
    for port, shard in shards:
        print(f"  port {port}: {len(shard)} flops")

    records: List[Dict[str, Any]] = []
    errors: List[Tuple[str, str]] = []
    lock_records: List[Dict[str, Any]] = []

    def run_shard(port: int, shard: List[Tuple[List[str], Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
        local: List[Dict[str, Any]] = []
        local_errors: List[Tuple[str, str]] = []
        for n, (board, cfg) in enumerate(shard, 1):
            payload = {
                "spot": "BTN_vs_BB_SRP",
                "board": board,
                "pot": cfg["pot"],
                "effective_stack": cfg["stack"],
                "ante_bb": cfg["ante"],
                "rake_percent": cfg["rake"],
                "rake_cap": cfg["cap"],
                "num_folded_players": cfg["folded"],
                "use_bunching": cfg["bunching"],
                "max_bets_per_node": 1,
                "target_dEV": args.target_dev,
                "max_iterations": args.max_iterations,
                "time_limit_ms": args.time_limit_ms,
                "oop_range": oop_range,
                "ip_range": ip_range,
                "collect_leaves": True,
            }
            last_err = ""
            for attempt in range(args.retries + 1):
                try:
                    res = ask_daemon(port, payload)
                    if "error" in res:
                        raise RuntimeError(res["error"])
                    if "heuristic" in str(res.get("engine", "")).lower():
                        raise RuntimeError(f"heuristic response: {res.get('engine')}")
                    if res.get("oop_ev") is None or res.get("ip_ev") is None:
                        raise RuntimeError("missing EV")
                    local.append(make_record(
                        board, res, oop_range, ip_range,
                        cfg["pot"], cfg["stack"], cfg["rake"], cfg["cap"],
                        ante_bb=cfg["ante"], num_folded_players=cfg["folded"],
                        use_bunching=cfg["bunching"], config_tag=cfg["tag"],
                    ))
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = str(exc)
                    time.sleep(0.2)
            else:
                local_errors.append((" ".join(board), last_err))
            if n % 100 == 0:
                print(f"  port {port}: {n}/{len(shard)}")
        return local, local_errors

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, len(ports))) as pool:
        futures = [pool.submit(run_shard, port, shard) for port, shard in shards]
        for fut in futures:
            got, errs = fut.result()
            lock_records.extend(got)
            errors.extend(errs)

    wall = time.perf_counter() - started
    records = sorted(lock_records, key=lambda r: r["spot_id"])
    print(f"\nSolved {len(records)}/{len(boards)} flops in {wall:.1f}s "
          f"({len(records) / max(wall, 1e-9):.2f} solves/s)")
    if errors:
        print(f"ERRORS: {len(errors)}; first: {errors[:3]}")
    if len(records) != len(boards):
        print("Refusing to write an incomplete dataset.")
        return 1

    report = validate(records)
    print("\nValidation:")
    for k, v in report.items():
        if k in ("heuristic_rows", "non_converged") and isinstance(v, list):
            print(f"  {k}: {len(v)}")
        else:
            print(f"  {k}: {v}")
    if report["heuristic_rows"] or report["non_converged"] or report["missing_fields"]:
        print("Dataset rejected: heuristic rows, non-converged rows, or missing fields.")
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path = out.with_suffix(".jsonl")
    parquet_path = out.with_suffix(".parquet")

    with open(jsonl_path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")

    df = pd.DataFrame(records)
    df["board_str"] = df["board"].apply(lambda b: " ".join(b))
    for col in ("oop_range", "ip_range", "overall_frequencies", "strategy",
                "strategy_detail", "hand_ev", "leaf_samples"):
        df[f"{col}_json"] = df[col].apply(json.dumps)
    df.to_parquet(parquet_path, engine="pyarrow", compression="snappy", index=False)

    # Flatten and export dedicated leaf-value dataset
    leaf_records = []
    for r in records:
        board = r["board"]
        r_pot = float(r["pot"])
        r_stack = float(r["effective_stack"])
        r_ante = float(r.get("ante_bb", 0.0))
        r_rake_pct = float(r["rake_percent"])
        r_rake_cap = float(r["rake_cap"])
        r_folded = int(r.get("num_folded_players", 4)) if r.get("use_bunching", True) else 0
        for idx, ls in enumerate(r.get("leaf_samples", [])):
            inv_o = ls["invested"][0]
            inv_i = ls["invested"][1]
            tot_pot = r_pot + inv_o + inv_i
            rake = min(tot_pot * r_rake_pct / 100.0, r_rake_cap)
            net_p = tot_pot - rake
            leaf_records.append({
                "spot_id": f"{r['spot_id']}_leaf_{idx}",
                "board": board,
                "invested_oop": inv_o,
                "invested_ip": inv_i,
                "pot": tot_pot,
                "net_pot": net_p,
                "effective_stack": r_stack,
                "ante_bb": r_ante,
                "rake_percent": r_rake_pct,
                "rake_cap": r_rake_cap,
                "num_folded_players": r_folded,
                "reach_oop_json": json.dumps(ls["reach_oop"]),
                "reach_ip_json": json.dumps(ls["reach_ip"]),
                "v_oop_json": json.dumps(ls["v_oop"]),
                "v_ip_json": json.dumps(ls["v_ip"]),
            })

    leaf_parquet_path = out.parent / "nl500_100bb_leaf_cfr.parquet"
    leaf_df = pd.DataFrame(leaf_records)
    leaf_df.to_parquet(leaf_parquet_path, engine="pyarrow", compression="snappy", index=False)

    print(f"\nWrote {len(df)} root CFR rows")
    print(f"  {jsonl_path} ({jsonl_path.stat().st_size:,} bytes)")
    print(f"  {parquet_path} ({parquet_path.stat().st_size:,} bytes)")
    print(f"Wrote {len(leaf_df)} leaf CFR rows")
    print(f"  {leaf_parquet_path} ({leaf_parquet_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
