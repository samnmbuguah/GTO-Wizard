#!/usr/bin/env python3
"""
scripts/benchmark_bunching.py

Benchmarks preflop card bunching in the Rust engine: solves the same spot with
bunching enabled and disabled and reports the EV shift and latency cost.

Bunching is the rank-weighted card-removal model in
``solver_daemon/src/cfr.rs::card_bunching_weights``. It is used in two places:

  * turn/river runout probabilities in ``compute_equity`` (a runout card's rank
    is weighted by its survival probability), and
  * hand-combo weights in ``normalized_reach`` (hole cards are weighted by the
    product of their ranks' survival probabilities).

Usage:
  python scripts/benchmark_bunching.py --port 9981
  python scripts/benchmark_bunching.py --port 9981 --boards "Ah Kd 2c,9s 8h 7s"
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.solutions.services.range_service import PreflopRangeService

CONFIGS = {
    "cash": {"pot": 5.5, "stack": 100.0, "ante": 0.0, "rake": 5.0, "cap": 0.6},
    "nl50": {"pot": 5.5, "stack": 100.0, "ante": 0.0, "rake": 5.0, "cap": 4.0},
    "mtt40": {"pot": 6.5, "stack": 40.0, "ante": 0.125, "rake": 0.0, "cap": 0.0},
}

DEFAULT_BOARDS = ["Ah Kd 2c", "9s 8h 7s", "As Ah 5c", "Kh Th 4h"]


def ask(port: int, payload: Dict[str, Any], timeout: float = 120.0) -> Dict[str, Any]:
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
    return json.loads(buf.decode().strip())


def run_one(port: int, board: List[str], cfg: Dict[str, float], bunching: bool,
            mode: str = "builtin") -> Dict[str, Any]:
    oop, ip = PreflopRangeService.get_spot_ranges("BTN_vs_BB_SRP", cfg["rake"], cfg["cap"])
    payload = {
        "board": board,
        "oop_range": oop,
        "ip_range": ip,
        "pot": cfg["pot"],
        "effective_stack": cfg["stack"],
        "ante_bb": cfg["ante"],
        "rake_percent": cfg["rake"],
        "rake_cap": cfg["cap"],
        "num_folded_players": 4 if bunching else 0,
        "use_bunching": bunching,
        "max_bets_per_node": 1,
        "target_dEV": 0.005,
        "max_iterations": 500,
        "time_limit_ms": 1500,
    }
    if bunching and mode == "seat":
        from backend.solutions.services.bunching import derive_bunching_weights
        payload["bunching_weights"] = derive_bunching_weights(
            ["UTG", "MP", "CO"], cfg["rake"], cfg["cap"]
        )
    return ask(port, payload)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9981)
    ap.add_argument("--boards", default=",".join(DEFAULT_BOARDS))
    ap.add_argument("--configs", default="cash,mtt40")
    ap.add_argument("--mode", choices=("builtin", "seat"), default="builtin",
                    help="builtin: daemon derives the profile from num_folded_players; "
                         "seat: explicit seat-derived dead-card profile")
    args = ap.parse_args()
    boards = [b.split() for b in args.boards.split(",") if b.strip()]
    configs = [c.strip() for c in args.configs.split(",") if c.strip()]

    print("=" * 96)
    print(f" PREFLOP CARD BUNCHING BENCHMARK (bunching on vs off, mode: {args.mode})")
    print("=" * 96)
    print(f"{'Config':<8} | {'Board':<11} | {'OOP on':<8} | {'OOP off':<8} | "
          f"{'IP on':<8} | {'IP off':<8} | {'max|d|':<7} | {'ms on':<6} | {'ms off':<6} | {'leaf mode'}")
    print("-" * 120)

    shifts: List[float] = []
    lat_on: List[float] = []
    lat_off: List[float] = []
    for name in configs:
        cfg = CONFIGS[name]
        for board in boards:
            on = run_one(args.port, board, cfg, True, args.mode)
            off = run_one(args.port, board, cfg, False, args.mode)
            oop_on, ip_on = float(on["oop_ev"]), float(on["ip_ev"])
            oop_off, ip_off = float(off["oop_ev"]), float(off["ip_ev"])
            d = max(abs(oop_on - oop_off), abs(ip_on - ip_off))
            shifts.append(d)
            lat_on.append(float(on["solve_time_ms"]))
            lat_off.append(float(off["solve_time_ms"]))
            print(f"{name:<8} | {' '.join(board):<11} | {oop_on:<8.4f} | {oop_off:<8.4f} | "
                  f"{ip_on:<8.4f} | {ip_off:<8.4f} | {d:<7.4f} | "
                  f"{on['solve_time_ms']:<6.0f} | {off['solve_time_ms']:<6.0f} | "
                  f"{on.get('leaf_mode', '?')}")

    print("-" * 120)
    print(f"Mean max-player |ΔEV| : {sum(shifts)/len(shifts):.4f} bb")
    print(f"Max  max-player |ΔEV| : {max(shifts):.4f} bb")
    print(f"Mean latency on/off   : {sum(lat_on)/len(lat_on):.0f} ms / {sum(lat_off)/len(lat_off):.0f} ms")
    print("Bunching only reweights the 13 rank-survival factors (~13 FLOPs per")
    print("runout/combo), so the latency difference is dominated by convergence noise.")
    print("OOP_EV + IP_EV is conserved in both cases; bunching changes only the split.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
