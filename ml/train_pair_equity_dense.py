#!/usr/bin/env python3
"""
ml/train_pair_equity_dense.py

Trains the V2 dense antisymmetric pair-equity operator with direct pair-level
supervision on the exact 169x169 equity matrices produced by
`scripts/data_gen/generate_equity_labels.py`.

Why this exists
---------------
The V1 operator (`a_i - a_j + low-rank skew`) plateaus at mean |dE| ~ 0.11-0.13
on held-out boards (`scripts/probe_equity_learnability.py`), which is far above
the ~0.018 label-noise floor and makes the learned-leaf CFR attempt miss the
0.5%-pot exploitability gate. V2 gives every unordered hand-class pair its own
logit while keeping the matrix exactly antisymmetric, so pot conservation
remains structural.

Metrics reported
----------------
* `val_dE_mae`  - mean |E_model - E_exact| over the held-out boards.
* `root_ev_err` - |EV_oop(model) - EV_oop(exact)| (bb) for the real BTN vs BB
  ranges at the root. This is the number that actually drives the CFR
  convergence: an E error only matters when it is weighted by a live reach.

Exports:
  ml/artifacts/pair_equity_net_v2.pt
  ml/artifacts/pair_equity_net_v2.onnx (+ .onnx.data)
  ml/artifacts/pair_equity_net_v2_weights.bin   (native Rust inference)
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

from ml.features import encode_board, encode_range
from ml.models.pair_equity_net_v2 import DensePairEquityNet, INPUT_DIM, N_CLASSES

EPS = 0.002


def build_inputs(df: pd.DataFrame):
    n = len(df)
    x = np.zeros((n, INPUT_DIM), np.float32)
    y = np.zeros((n, N_CLASSES, N_CLASSES), np.float32)
    cache: dict[str, np.ndarray] = {}
    for i, r in enumerate(df.itertuples(index=False)):
        board = list(r.board)
        key = " ".join(board)
        if key not in cache:
            cache[key] = encode_board(board)
        x[i, :75] = cache[key]
        x[i, 75] = float(r.effective_stack) / 100.0
        x[i, 76] = float(r.pot) / 10.0
        x[i, 77] = float(r.ante_bb)
        x[i, 78] = float(r.rake_percent) / 10.0
        x[i, 79] = float(r.rake_cap) / 5.0
        x[i, 80] = float(r.num_folded_players) / 6.0
        y[i] = np.asarray(r.equity, dtype=np.float32).reshape(N_CLASSES, N_CLASSES)
    return x, y


def export_binary_weights(model: nn.Module, out_path: Path) -> None:
    """Writes the Rust-compatible tensor map.

    Layout: <u32 tensor_count> then per tensor
    <u32 name_len><name><u32 ndim><dims...><f32 data>
    """
    state = model.state_dict()
    tensors = {
        k: v.detach().cpu().to(torch.float32).contiguous()
        for k, v in state.items()
        # Index buffers are implicit in the Rust loader (upper-triangle order).
        if k not in ("pair_i", "pair_j")
    }
    tensors["meta.hidden"] = torch.tensor([float(model.hidden_dim)], dtype=torch.float32)
    tensors["meta.pairs"] = torch.tensor([float(model.n_pairs)], dtype=torch.float32)
    with open(out_path, "wb") as f:
        f.write(struct.pack("<I", len(tensors)))
        for name, tensor in tensors.items():
            nb = name.encode("utf-8")
            f.write(struct.pack("<I", len(nb)))
            f.write(nb)
            f.write(struct.pack("<I", tensor.ndim))
            for d in tensor.shape:
                f.write(struct.pack("<I", d))
            f.write(tensor.numpy().tobytes())
    print(f"Binary weights: {out_path} ({out_path.stat().st_size:,} bytes)", flush=True)


def root_ev(error_matrix: np.ndarray, ro: np.ndarray, ri: np.ndarray, net_pot: float):
    """Root EV (oop, ip) for a given equity matrix and the two ranges."""
    ron = ro / ro.sum()
    rin = ri / ri.sum()
    share_o = error_matrix @ rin
    share_i = 1.0 - ron @ error_matrix
    return float(ron @ (share_o * net_pot)), float(rin @ (share_i * net_pot))


def main() -> int:
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(REPO_ROOT / "datasets/generated/equity_labels_2000.parquet"))
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden", type=int, default=128)
    ap.add_argument("--blocks", type=int, default=2)
    ap.add_argument("--dropout", type=float, default=0.10)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--max-minutes", type=float, default=0.0)
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "ml/artifacts"))
    ap.add_argument("--name", default="pair_equity_net_v2")
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

    # Real ranges for the EV-error metric.
    from backend.solutions.services.range_service import PreflopRangeService
    range_cache: dict[tuple[float, float], tuple[np.ndarray, np.ndarray]] = {}

    def ranges_for(rake: float, cap: float):
        key = (round(float(rake), 4), round(float(cap), 4))
        if key not in range_cache:
            oop, ip = PreflopRangeService.get_spot_ranges("BTN_vs_BB_SRP", rake, cap)
            range_cache[key] = (encode_range(oop).astype(np.float64),
                                encode_range(ip).astype(np.float64))
        return range_cache[key]

    model = DensePairEquityNet(hidden_dim=args.hidden, num_res_blocks=args.blocks,
                                dropout=args.dropout)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"model params: {n_params/1e6:.2f}M", flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=1e-5)

    xt = torch.from_numpy(x)
    yt = torch.from_numpy(y)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ckpt = out / f"{args.name}.pt"

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
            logits = model(xt[idx])
            target = yt[idx]
            pred = torch.sigmoid(logits)
            bce = nn.functional.binary_cross_entropy_with_logits(
                logits, target.clamp(EPS, 1.0 - EPS))
            mse = torch.mean((pred - target) ** 2)
            loss = bce + 5.0 * mse
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            tot += float(loss) * len(idx)
        sched.step()

        model.eval()
        with torch.no_grad():
            logits = model(xt[va])
            pred = torch.sigmoid(logits)
            err = (pred - yt[va]).abs()
            mae = float(err.mean())
            p95 = float(torch.quantile(err.flatten(), 0.95))
            mx = float(err.max())
            antisym = float((pred + pred.transpose(1, 2) - 1.0).abs().max())
        if mae < best:
            best = mae
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            torch.save(best_state, ckpt)
        print(f"ep {ep:>3}/{args.epochs} train loss {tot/len(tr):.5f} | "
              f"val |dE| MAE {mae:.4f} (p95 {p95:.4f}, max {mx:.4f}) | "
              f"antisym {antisym:.2e} | best {best:.4f} | "
              f"{(time.perf_counter()-started)/60:.1f} min", flush=True)
        if args.max_minutes and (time.perf_counter() - started) / 60 >= args.max_minutes:
            print(f"Stopping early: {args.max_minutes:.0f} min budget reached.", flush=True)
            break

    model.load_state_dict(best_state)
    print(f"BEST validation |dE| MAE: {best:.4f}", flush=True)

    # ------------------------------------------------------------------ #
    # Root EV error against the exact labels for the real preflop ranges.
    # ------------------------------------------------------------------ #
    model.eval()
    with torch.no_grad():
        pred = torch.sigmoid(model(xt[va]))
    ev_errs = []
    per_board = []
    val_rows = df.iloc[va].reset_index(drop=True)
    for i in range(len(va)):
        ro, ri = ranges_for(val_rows.at[i, "rake_percent"], val_rows.at[i, "rake_cap"])
        pot = float(val_rows.at[i, "pot"])
        rake = float(val_rows.at[i, "rake_percent"])
        cap = float(val_rows.at[i, "rake_cap"])
        net_pot = pot - min(pot * rake / 100.0, cap)
        e_model = pred[i].numpy().astype(np.float64)
        e_exact = yt[va][i].numpy().astype(np.float64)
        mo_ev, mi_ev = root_ev(e_model, ro, ri, net_pot)
        eo_ev, ei_ev = root_ev(e_exact, ro, ri, net_pot)
        ev_errs.append(max(abs(mo_ev - eo_ev), abs(mi_ev - ei_ev)))
        per_board.append((abs(mo_ev - eo_ev), abs(mi_ev - ei_ev)))
    ev_errs = np.array(ev_errs)
    print(f"root EV error (bb): mean {ev_errs.mean():.4f} | p95 "
          f"{np.percentile(ev_errs, 95):.4f} | max {ev_errs.max():.4f}", flush=True)

    torch.save(model.state_dict(), out / f"{args.name}.pt")

    class Equity(nn.Module):
        def __init__(self, net):
            super().__init__()
            self.net = net

        def forward(self, x):
            return torch.sigmoid(self.net(x))

    try:
        torch.onnx.export(
            Equity(model).eval(), torch.randn(1, INPUT_DIM),
            str(out / f"{args.name}.onnx"),
            input_names=["board"], output_names=["equity_169x169"],
            dynamic_axes={"board": {0: "batch"}, "equity_169x169": {0: "batch"}},
            opset_version=18,
        )
    except Exception as exc:  # pragma: no cover
        print(f"ONNX export error: {exc}", flush=True)
    export_binary_weights(model, out / f"{args.name}_weights.bin")

    art = REPO_ROOT / "backend/artifacts"
    art.mkdir(parents=True, exist_ok=True)
    for suffix in (".pt", ".onnx", ".onnx.data", "_weights.bin"):
        name = f"{args.name}{suffix}"
        if (out / name).exists():
            shutil.copy2(out / name, art / name)

    print(json.dumps({
        "val_dE_mae": best,
        "root_ev_err_mean_bb": float(ev_errs.mean()),
        "root_ev_err_p95_bb": float(np.percentile(ev_errs, 95)),
        "root_ev_err_max_bb": float(ev_errs.max()),
    }), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
