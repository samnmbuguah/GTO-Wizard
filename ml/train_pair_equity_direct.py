#!/usr/bin/env python3
"""
ml/train_pair_equity_direct.py

Trains the pair-equity operator with **direct pair-level supervision**.

The original trainer (`ml/train_pair_equity.py`) learned the operator from
range-averaged share targets (`t_oop = E @ r̂_ip`). That under-determines the
matrix: only row averages against the sampled opponent ranges are constrained,
so individual pairs could be badly wrong (measured mean |ΔE| ~0.11-0.16 against
the exact matrix, max |ΔE| up to 0.97). The resulting payoff did not converge
in CFR.

This trainer instead regresses the exact 169x169 equity matrix produced by the
solver (`scripts/data_gen/generate_equity_labels.py`), while keeping the
antisymmetric parameterisation so `E[i][j] + E[j][i] = 1` holds exactly.

Exports:
  ml/artifacts/pair_equity_net.pt
  ml/artifacts/pair_equity_net.onnx (+ .onnx.data)
  ml/artifacts/pair_equity_net_weights.bin   (native Rust inference)
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.features import encode_board
from ml.models.pair_equity_net import PairEquityNet

N_CLASSES = PairEquityNet.N_CLASSES
BOARD_DIM = PairEquityNet.BOARD_DIM
CTX_DIM = PairEquityNet.CTX_DIM


def build_inputs(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    n = len(df)
    x = np.zeros((n, BOARD_DIM + CTX_DIM), np.float32)
    y = np.zeros((n, N_CLASSES, N_CLASSES), np.float32)
    board_cache: dict[str, np.ndarray] = {}
    for i, r in enumerate(df.itertuples(index=False)):
        board = list(r.board)
        key = " ".join(board)
        if key not in board_cache:
            board_cache[key] = encode_board(board)
        x[i, :BOARD_DIM] = board_cache[key]
        x[i, BOARD_DIM + 0] = float(r.effective_stack) / 100.0
        x[i, BOARD_DIM + 1] = float(r.pot) / 10.0
        x[i, BOARD_DIM + 2] = float(r.ante_bb)
        x[i, BOARD_DIM + 3] = float(r.rake_percent) / 10.0
        x[i, BOARD_DIM + 4] = float(r.rake_cap) / 5.0
        x[i, BOARD_DIM + 5] = float(r.num_folded_players) / 6.0
        y[i] = np.asarray(r.equity, dtype=np.float32).reshape(N_CLASSES, N_CLASSES)
    return x, y


def export_binary_weights(model: nn.Module, out_path: Path) -> None:
    state = model.state_dict()
    with open(out_path, "wb") as f:
        f.write(struct.pack("<I", len(state)))
        for name, tensor in state.items():
            t = tensor.detach().cpu().to(torch.float32).contiguous().numpy()
            nb = name.encode("utf-8")
            f.write(struct.pack("<I", len(nb)))
            f.write(nb)
            f.write(struct.pack("<I", t.ndim))
            for d in t.shape:
                f.write(struct.pack("<I", d))
            f.write(t.tobytes())
    print(f"Binary weights: {out_path} ({out_path.stat().st_size:,} bytes)", flush=True)


def main() -> int:
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(REPO_ROOT / "datasets/generated/equity_labels.parquet"))
    ap.add_argument("--epochs", type=int, default=150)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--hidden", type=int, default=256)
    ap.add_argument("--blocks", type=int, default=2)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--max-minutes", type=float, default=0.0)
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "ml/artifacts"))
    args = ap.parse_args()

    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    df = pd.read_parquet(args.labels)
    print(f"Loaded {len(df)} equity labels", flush=True)
    t0 = time.perf_counter()
    x, y = build_inputs(df)
    print(f"Arrays built in {time.perf_counter() - t0:.1f}s", flush=True)

    boards = np.array([" ".join(list(b)) for b in df["board"]])
    uniq = np.unique(boards)
    rng.shuffle(uniq)
    val_boards = set(uniq[: int(args.val_frac * len(uniq))])
    is_val = np.array([b in val_boards for b in boards])
    tr = np.where(~is_val)[0]
    va = np.where(is_val)[0]
    print(f"Split by board: train {len(tr)} / val {len(va)} ({len(val_boards)} unseen boards)",
          flush=True)

    model = PairEquityNet(hidden_dim=args.hidden, num_res_blocks=args.blocks, rank=args.rank)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=1e-5)

    xt = torch.from_numpy(x)
    yt = torch.from_numpy(y)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ckpt = out / "pair_equity_net.pt"

    best = float("inf")
    best_state = None
    started = time.perf_counter()
    for ep in range(1, args.epochs + 1):
        model.train()
        perm = rng.permutation(tr)
        tot = 0.0
        for s in range(0, len(perm), args.batch_size):
            idx = perm[s:s + args.batch_size]
            opt.zero_grad()
            a, u, v = model(xt[idx])
            E = PairEquityNet.equity_matrix(a, u, v)
            loss = torch.mean((E - yt[idx]) ** 2)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            tot += loss.item() * len(idx)
        sched.step()

        model.eval()
        with torch.no_grad():
            a, u, v = model(xt[va])
            E = PairEquityNet.equity_matrix(a, u, v)
            err = (E - yt[va]).abs()
            mae = float(err.mean())
            p95 = float(torch.quantile(err.flatten(), 0.95))
            mx = float(err.max())
            antisym = float((E + E.transpose(1, 2) - 1.0).abs().max())
        if mae < best:
            best = mae
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            torch.save(best_state, ckpt)
        print(f"ep {ep:>3}/{args.epochs} train mse {tot / len(tr):.6f} | "
              f"val |dE| MAE {mae:.4f} (p95 {p95:.4f}, max {mx:.4f}) | "
              f"antisym {antisym:.2e} | best {best:.4f} | "
              f"{(time.perf_counter() - started) / 60:.1f} min", flush=True)
        if args.max_minutes and (time.perf_counter() - started) / 60 >= args.max_minutes:
            print(f"Stopping early: {args.max_minutes:.0f} min budget reached.", flush=True)
            break

    model.load_state_dict(best_state)
    print(f"BEST validation |dE| MAE: {best:.4f}", flush=True)

    torch.save(model.state_dict(), out / "pair_equity_net.pt")

    class Equity(nn.Module):
        def __init__(self, net):
            super().__init__()
            self.net = net

        def forward(self, x):
            a, u, v = self.net(x)
            return PairEquityNet.equity_matrix(a, u, v)

    try:
        torch.onnx.export(
            Equity(model).eval(), torch.randn(1, model.total_input_dim),
            str(out / "pair_equity_net.onnx"),
            input_names=["board"], output_names=["equity_169x169"],
            dynamic_axes={"board": {0: "batch"}, "equity_169x169": {0: "batch"}},
            opset_version=18,
        )
    except Exception as exc:  # pragma: no cover
        print(f"ONNX export error: {exc}", flush=True)
    export_binary_weights(model, out / "pair_equity_net_weights.bin")

    art = REPO_ROOT / "backend/artifacts"
    art.mkdir(parents=True, exist_ok=True)
    for name in ("pair_equity_net.pt", "pair_equity_net.onnx",
                 "pair_equity_net.onnx.data", "pair_equity_net_weights.bin"):
        if (out / name).exists():
            shutil.copy2(out / name, art / name)
    print(json.dumps({"val_dE_mae": best}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
