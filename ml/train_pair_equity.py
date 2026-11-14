#!/usr/bin/env python3
"""
ml/train_pair_equity.py

Trains the board-conditioned antisymmetric pair-equity operator
(ml/models/pair_equity_net.py) on exact leaf CFV vectors.

The model sees only the board (and folded-player count). It predicts a
169x169 matrix E with E[i][j] + E[j][i] = 1 by construction, so the terminal
values it induces conserve the pot for any reaches:

    sum(ro * v_oop) + sum(ri * v_ip) = m_o * m_i * (start_pot - rake)

Loss is the reach-weighted error between the induced per-class shares and the
exact shares recovered from the Rust solver's CFV vectors:

    t_oop[i] = (v_oop[i] / m_i + invested_oop) / net_pot
    t_ip[j]  = (v_ip[j]  / m_o + invested_ip)  / net_pot

Since t_oop = E @ ri_n and t_ip = 1 - ro_n^T E, convex mixes of two leaves on
the same board are still exact training samples and are used to augment.

Exports:
  ml/artifacts/pair_equity_net.pt
  ml/artifacts/pair_equity_net.onnx
  ml/artifacts/pair_equity_net_weights.bin   (native Rust inference)
"""

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

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.train_leaf_model import load_arrays
from ml.models.pair_equity_net import PairEquityNet


def pair_inputs(A, idx):
    """Board + the six generalized, normalized context features."""
    ctx = A["ctx"][idx]
    # ctx: [total_pot/10, inv_o/10, inv_i/10, net/10, stack/100, ante,
    #       rake_pct/10, rake_cap/5, folded/6]
    starting_pot = ctx[:, 0] - ctx[:, 1] - ctx[:, 2]  # already /10
    pair_ctx = np.stack([
        ctx[:, 4],   # stack_bb / 100
        starting_pot,
        ctx[:, 5],   # ante_bb
        ctx[:, 6],   # rake_pct / 10
        ctx[:, 7],   # rake_cap / 5
        ctx[:, 8],   # folded / 6
    ], axis=1)
    x = np.concatenate([A["board_feat"][idx], pair_ctx], axis=1)
    return torch.from_numpy(x)


def make_batch(A, idx, groups, rng, mix_prob):
    """Convex mixes of two leaves on the same board are exact for this model."""
    ro = A["ro_n"][idx]
    ri = A["ri_n"][idx]
    to = A["t_o"][idx]
    ti = A["t_i"][idx]
    for row, i in enumerate(idx):
        if rng.random() < mix_prob:
            g = groups[A["mix_key"][i]]
            j = g[rng.integers(len(g))]
            lam, mu = rng.random(), rng.random()
            ri[row] = lam * A["ri_n"][i] + (1 - lam) * A["ri_n"][j]
            to[row] = lam * A["t_o"][i] + (1 - lam) * A["t_o"][j]
            ro[row] = mu * A["ro_n"][i] + (1 - mu) * A["ro_n"][j]
            ti[row] = mu * A["t_i"][i] + (1 - mu) * A["t_i"][j]
    return (pair_inputs(A, idx), torch.from_numpy(ro), torch.from_numpy(ri),
            torch.from_numpy(to), torch.from_numpy(ti))


def pair_loss(model, x, ro, ri, to, ti):
    a, u, v = model(x)
    E = PairEquityNet.equity_matrix(a, u, v)
    # s_oop = E @ ri_n ; s_ip = 1 - ro_n^T E
    s_o = torch.einsum("bij,bj->bi", E, ri)
    s_i = 1.0 - torch.einsum("bij,bi->bj", E, ro)
    w_o = 1.0 + 169.0 * ro
    w_i = 1.0 + 169.0 * ri
    return ((w_o * (s_o - to) ** 2).mean() + (w_i * (s_i - ti) ** 2).mean())


@torch.no_grad()
def evaluate_bb(model, A, idx, chunk: int = 256):
    """Reach-weighted per-class EV error in bb, plus the structural conservation check."""
    model.eval()
    ev_o_err, ev_i_err, cons, share_abs = [], [], [], []
    for s in range(0, len(idx), chunk):
        sel = idx[s:s + chunk]
        x = pair_inputs(A, sel)
        a, u, v = model(x)
        E = PairEquityNet.equity_matrix(a, u, v).double().numpy()
        ro = A["ro_n"][sel].astype(np.float64)
        ri = A["ri_n"][sel].astype(np.float64)
        net = A["net"][sel][:, None]
        inv = A["inv"][sel]
        mo = A["m_o"][sel][:, None]
        mi = A["m_i"][sel][:, None]

        s_o = np.einsum("bij,bj->bi", E, ri)
        s_i = 1.0 - np.einsum("bij,bi->bj", E, ro)
        vo = (s_o * net - inv[:, :1]) * mi
        vi = (s_i * net - inv[:, 1:]) * mo

        # Unit EV of each player's whole range at this leaf.
        evo_p = (ro * (s_o * net - inv[:, :1])).sum(1)
        evo_t = (ro * (A["t_o"][sel] * net - inv[:, :1])).sum(1)
        evi_p = (ri * (s_i * net - inv[:, 1:])).sum(1)
        evi_t = (ri * (A["t_i"][sel] * net - inv[:, 1:])).sum(1)
        ev_o_err.append(np.abs(evo_p - evo_t))
        ev_i_err.append(np.abs(evi_p - evi_t))

        ro_raw, ri_raw = ro * mo, ri * mi
        cons.append(np.abs((ro_raw * vo).sum(1) + (ri_raw * vi).sum(1)
                           - ((ro_raw * A["vo_true"][sel]).sum(1)
                              + (ri_raw * A["vi_true"][sel]).sum(1))))
        share_abs.append(0.5 * (np.abs(s_o - A["t_o"][sel]).mean(1)
                                + np.abs(s_i - A["t_i"][sel]).mean(1)))

    ev_o = np.concatenate(ev_o_err)
    ev_i = np.concatenate(ev_i_err)
    both = np.abs(np.r_[ev_o, ev_i])
    return dict(
        share_mae=float(np.concatenate(share_abs).mean()),
        range_ev_mae_bb=float(0.5 * (ev_o.mean() + ev_i.mean())),
        range_ev_p95_bb=float(np.percentile(both, 95)),
        conservation_err_bb=float(np.concatenate(cons).max()),
    )


def export_binary_weights(model, out_path: Path):
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


def main():
    torch.set_num_threads(1)
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=",".join([
        str(REPO_ROOT / "datasets/generated/nl500_100bb_leaf_cfr.parquet"),
        str(REPO_ROOT / "datasets/generated/leaf_cfr_aug_multiconfig.parquet"),
    ]))
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--mix-prob", type=float, default=0.5)
    ap.add_argument("--rank", type=int, default=8)
    ap.add_argument("--hidden", type=int, default=256)
    ap.add_argument("--blocks", type=int, default=2)
    ap.add_argument("--max-minutes", type=float, default=0.0,
                    help="Stop training after this many minutes and export the best model")
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "ml/artifacts"))
    args = ap.parse_args()

    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    df = pd.concat(
        [pd.read_parquet(p.strip()) for p in args.dataset.split(",") if p.strip()],
        ignore_index=True,
    )
    print(f"Loaded {len(df)} leaf records", flush=True)
    t0 = time.perf_counter()
    A = load_arrays(df)
    print(f"Arrays built in {time.perf_counter() - t0:.1f}s; valid rows {int(A['valid'].sum())}", flush=True)

    boards = np.unique(A["board_key"])
    rng.shuffle(boards)
    val_boards = set(boards[: int(0.15 * len(boards))])
    is_val = np.array([b in val_boards for b in A["board_key"]])
    tr_idx = np.where(~is_val & A["valid"])[0]
    va_idx = np.where(is_val & A["valid"])[0]
    print(f"Split by board: train {len(tr_idx)} / val {len(va_idx)} ({len(val_boards)} unseen boards)", flush=True)

    # Convex mixing of two leaves is exact for the pair operator only when the
    # operator itself is identical, i.e. the board *and* the six context
    # features (stack, starting pot, ante, rake, cap, folded) match.
    mix_keys = [
        (A["board_key"][i],) + tuple(np.round(A["ctx"][i][4:9], 4).tolist())
        for i in range(len(A["board_key"]))
    ]
    A["mix_key"] = mix_keys
    groups = {}
    for i in tr_idx:
        groups.setdefault(mix_keys[i], []).append(i)
    groups = {k: np.array(v) for k, v in groups.items()}

    model = PairEquityNet(hidden_dim=args.hidden, num_res_blocks=args.blocks, rank=args.rank)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=1e-5)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ckpt_path = out / "pair_equity_net.pt"

    best, best_state = float("inf"), None
    started = time.perf_counter()
    for ep in range(1, args.epochs + 1):
        model.train()
        perm = rng.permutation(tr_idx)
        tot = 0.0
        for s in range(0, len(perm), args.batch_size):
            b = make_batch(A, perm[s:s + args.batch_size], groups, rng, args.mix_prob)
            opt.zero_grad()
            loss = pair_loss(model, *b)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            tot += loss.item() * len(b[0])
        sched.step()
        m = evaluate_bb(model, A, va_idx)
        if m["range_ev_mae_bb"] < best:
            best = m["range_ev_mae_bb"]
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            # Checkpoint every improvement so a wall-clock stop never loses work.
            torch.save(best_state, ckpt_path)
        print(f"ep {ep:>2}/{args.epochs} train {tot / len(perm):.5f} | "
              f"val share MAE {m['share_mae']:.4f} | "
              f"range-EV MAE {m['range_ev_mae_bb']:.4f} bb (p95 {m['range_ev_p95_bb']:.4f}) | "
              f"conservation err {m['conservation_err_bb']:.2e} bb | best {best:.4f} | "
              f"elapsed {(time.perf_counter() - started) / 60:.1f} min", flush=True)
        if args.max_minutes and (time.perf_counter() - started) / 60 >= args.max_minutes:
            print(f"Stopping early: wall-clock budget of {args.max_minutes:.0f} min reached.",
                  flush=True)
            break

    model.load_state_dict(best_state)
    final = evaluate_bb(model, A, va_idx)
    print("FINAL (unseen boards):", json.dumps({k: round(float(v), 6) for k, v in final.items()}), flush=True)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
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


if __name__ == "__main__":
    main()
