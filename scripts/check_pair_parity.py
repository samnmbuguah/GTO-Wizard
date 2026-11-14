#!/usr/bin/env python3
"""
scripts/check_pair_parity.py

Python <-> Rust parity check for the pair-equity operator.

The Rust daemon loads the native `.bin` weights and evaluates the 169x169
equity matrix natively; this script evaluates the same matrix in Python from
the exported `.pt` and compares the two element by element.

The daemon returns the matrix it actually used in `pair_equity_matrix` (the
learned operator) and the sampled exact matrix in `equity_matrix`.

Usage:
    python scripts/check_pair_parity.py --port 9984 --boards 12
    python scripts/check_pair_parity.py --port 9984 --weights ml/artifacts/pair_equity_net_v2.pt
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path

import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.models.pair_equity_net_v2 import DensePairEquityNet

N = 169


def ask(port: int, payload: dict, timeout: float = 300.0) -> dict:
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--weights", default=str(REPO_ROOT / "ml/artifacts/pair_equity_net_v2.pt"))
    ap.add_argument("--boards", type=int, default=12)
    ap.add_argument("--context", default="100.0,5.5,0.0,5.0,0.6,4",
                    help="effective_stack,pot,ante,rake_pct,rake_cap,num_folded")
    args = ap.parse_args()

    stack, pot, ante, rake, cap, folded = [float(v) for v in args.context.split(",")]

    model = DensePairEquityNet(hidden_dim=128, num_res_blocks=2)
    state = torch.load(args.weights, map_location="cpu")
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing or unexpected:
        print(f"WARNING missing={missing} unexpected={unexpected}", file=sys.stderr)
    model.eval()

    from scripts.canonical_boards import CANONICAL_50_BOARDS

    worst = 0.0
    worst_board = None
    missing = 0
    for board in list(CANONICAL_50_BOARDS)[: args.boards]:
        res = ask(args.port, {
            "board": list(board),
            "oop_range": {},
            "ip_range": {},
            "pot": pot,
            "effective_stack": stack,
            "ante_bb": ante,
            "rake_percent": rake,
            "rake_cap": cap,
            "num_folded_players": int(folded),
            "use_bunching": True,
            "max_bets_per_node": 1,
            "collect_equity": True,
            "deterministic": True,
            # Enough iterations for the learned solve to pass the 0.5%-pot
            # gate. With a low cap the daemon transparently falls back to
            # exact showdown and the learned matrix is not returned at all.
            "max_iterations": 500,
        })
        rust = np.asarray(res.get("pair_equity_matrix") or [], dtype=np.float64)
        if rust.size != N * N:
            print(f"  !! {' '.join(board)}: daemon returned no pair matrix "
                  f"(leaf_mode={res.get('leaf_mode')})")
            missing += 1
            continue
        rust = rust.reshape(N, N)
        py = model.evaluate_equity(
            list(board),
            effective_stack=stack,
            starting_pot=pot,
            ante_bb=ante,
            rake_pct=rake,
            rake_cap=cap,
            num_folded_players=int(folded),
        )
        d = np.abs(py - rust)
        md = float(d.mean())
        mx = float(d.max())
        antisym = float(np.abs(rust + rust.T - 1.0).max())
        print(f"  {' '.join(board):<16} mean|dE| {md:.2e}  max {mx:.2e}  "
              f"antisym(rust) {antisym:.2e}")
        if mx > worst:
            worst = mx
            worst_board = " ".join(board)

    print("-" * 72)
    print(f"worst element-wise |python - rust| = {worst:.3e}"
          + (f" on {worst_board}" if worst_board else ""))
    if missing:
        print(f"{missing} board(s) returned no learned matrix (learned solve fell back)")
    # The Rust engine uses the fast tanh approximation of GELU while PyTorch
    # uses the exact erf form, so a residual difference of a few 1e-4 is
    # expected (and harmless: it is far below the 0.018 label-noise floor).
    ok = worst < 1e-3 and missing == 0
    print("PARITY: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
