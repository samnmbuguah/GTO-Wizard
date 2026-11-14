#!/usr/bin/env python3
"""
ml/train_leaf_model.py

Trains Model 2 (range-conditioned leaf value net) on
datasets/generated/nl500_100bb_leaf_cfr.parquet.

Formulation (scale-invariant, zero-sum by construction):
  inputs : board(75) + normalized OOP reach(169) + normalized IP reach(169) + ctx(5)
  targets: per-class equity share of the net pot against the opponent's
           normalized range,  t_o[h] = (v_o[h] / m_i + inv_o) / net_pot  in [0, 1]
  values : v_o[h] = (t_o[h] * net_pot - inv_o) * m_i   (rebuilt exactly)

Because t_o is linear in the opponent's normalized range, convex mixtures of
two leaves on the same board give exact new training samples; we use that as
augmentation so the net sees the intermediate ranges CFR visits mid-solve.

Exports:
  ml/artifacts/leaf_value_net.pt
  ml/artifacts/leaf_value_net.onnx
  ml/artifacts/leaf_value_net_weights.bin   (native Rust inference)
"""

import sys
import json
import time
import shutil
import struct
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.features import encode_board
from ml.models.leaf_value_net import LeafValueNet

EPS = 1e-9


def load_arrays(df: pd.DataFrame):
    n = len(df)
    board_feat = np.zeros((n, 75), np.float32)
    ro_n = np.zeros((n, 169), np.float32)
    ri_n = np.zeros((n, 169), np.float32)
    ctx = np.zeros((n, 9), np.float32)
    t_o = np.zeros((n, 169), np.float32)
    t_i = np.zeros((n, 169), np.float32)
    m_o = np.zeros(n, np.float64)
    m_i = np.zeros(n, np.float64)
    inv = np.zeros((n, 2), np.float64)
    net = np.zeros(n, np.float64)
    vo_true = np.zeros((n, 169), np.float64)
    vi_true = np.zeros((n, 169), np.float64)
    board_key = []

    cache = {}
    for k, r in enumerate(df.itertuples(index=False)):
        b = list(r.board)
        key = " ".join(b)
        if key not in cache:
            cache[key] = encode_board(b)
        board_feat[k] = cache[key]
        folded = int(getattr(r, "num_folded_players", 4))
        board_key.append(f"{key}_{folded}")
        ro = np.array(json.loads(r.reach_oop_json), np.float64)
        ri = np.array(json.loads(r.reach_ip_json), np.float64)
        vo = np.array(json.loads(r.v_oop_json), np.float64)
        vi = np.array(json.loads(r.v_ip_json), np.float64)
        mo, mi = ro.sum(), ri.sum()
        m_o[k], m_i[k] = mo, mi
        inv[k] = (r.invested_oop, r.invested_ip)
        net[k] = r.net_pot
        vo_true[k], vi_true[k] = vo, vi
        if mo > EPS:
            ro_n[k] = ro / mo
            t_i[k] = (vi / mo + r.invested_ip) / r.net_pot
        if mi > EPS:
            ri_n[k] = ri / mi
            t_o[k] = (vo / mi + r.invested_oop) / r.net_pot
        ctx[k] = (
            r.pot / 10.0,
            r.invested_oop / 10.0,
            r.invested_ip / 10.0,
            r.net_pot / 10.0,
            float(getattr(r, "effective_stack", 100.0)) / 100.0,
            float(getattr(r, "ante_bb", 0.0)),
            r.rake_percent / 10.0,
            float(getattr(r, "rake_cap", 0.6)) / 5.0,
            folded / 6.0,
        )

    valid = (m_o > EPS) & (m_i > EPS)
    return dict(board_feat=board_feat, ro_n=ro_n, ri_n=ri_n, ctx=ctx, t_o=np.clip(t_o, 0, 1),
                t_i=np.clip(t_i, 0, 1), m_o=m_o, m_i=m_i, inv=inv, net=net,
                vo_true=vo_true, vi_true=vi_true, board_key=np.array(board_key), valid=valid)


def make_batch(A, idx, groups, rng, mix_prob):
    """Builds a batch; with prob mix_prob replaces a sample by an exact convex mix with another leaf on the same board."""
    ro = A["ro_n"][idx].copy(); ri = A["ri_n"][idx].copy()
    to = A["t_o"][idx].copy(); ti = A["t_i"][idx].copy()
    for row, i in enumerate(idx):
        if rng.random() < mix_prob:
            g = groups[A["board_key"][i]]
            j = g[rng.integers(len(g))]
            lam, mu = rng.random(), rng.random()
            ri[row] = lam * A["ri_n"][i] + (1 - lam) * A["ri_n"][j]
            to[row] = lam * A["t_o"][i] + (1 - lam) * A["t_o"][j]
            ro[row] = mu * A["ro_n"][i] + (1 - mu) * A["ro_n"][j]
            ti[row] = mu * A["t_i"][i] + (1 - mu) * A["t_i"][j]
    x = np.concatenate([A["board_feat"][idx], ro, ri, A["ctx"][idx]], axis=1)
    return (torch.from_numpy(x), torch.from_numpy(ro), torch.from_numpy(ri),
            torch.from_numpy(to), torch.from_numpy(ti))


def share_loss(model, x, ro, ri, to, ti):
    lo, li = model(x)
    po, pi = torch.sigmoid(lo), torch.sigmoid(li)
    po, pi = LeafValueNet.zero_sum_shares(po, pi, ro, ri)
    # Uniform per-class error plus extra weight on classes actually in range.
    w_o = 1.0 + 169.0 * ro
    w_i = 1.0 + 169.0 * ri
    return ((w_o * (po - to) ** 2).mean() + (w_i * (pi - ti) ** 2).mean())


@torch.no_grad()
def evaluate_bb(model, A, idx):
    """Rebuilds counterfactual values and compares to ground truth in bb."""
    model.eval()
    x = np.concatenate([A["board_feat"][idx], A["ro_n"][idx], A["ri_n"][idx], A["ctx"][idx]], axis=1)
    lo, li = model(torch.from_numpy(x))
    ro_n = A["ro_n"][idx].astype(np.float64); ri_n = A["ri_n"][idx].astype(np.float64)
    to = torch.sigmoid(lo).numpy().astype(np.float64); ti = torch.sigmoid(li).numpy().astype(np.float64)
    to, ti = LeafValueNet.zero_sum_shares(to, ti, ro_n, ri_n)
    net = A["net"][idx][:, None]; inv = A["inv"][idx]
    vo = (to * net - inv[:, :1]) * A["m_i"][idx][:, None]
    vi = (ti * net - inv[:, 1:]) * A["m_o"][idx][:, None]
    # Per-unit (normalized) EV error of each player's whole range at the leaf, in bb.
    ev_o_pred = (ro_n * (to * net - inv[:, :1])).sum(1); ev_o_true = (ro_n * (A["t_o"][idx] * net - inv[:, :1])).sum(1)
    ev_i_pred = (ri_n * (ti * net - inv[:, 1:])).sum(1); ev_i_true = (ri_n * (A["t_i"][idx] * net - inv[:, 1:])).sum(1)
    ro_raw = ro_n * A["m_o"][idx][:, None]; ri_raw = ri_n * A["m_i"][idx][:, None]
    cons = np.abs((ro_raw * vo).sum(1) + (ri_raw * vi).sum(1)
                  - ((ro_raw * A["vo_true"][idx]).sum(1) + (ri_raw * A["vi_true"][idx]).sum(1)))
    share_mae = 0.5 * (np.abs(to - A["t_o"][idx]).mean() + np.abs(ti - A["t_i"][idx]).mean())
    return dict(share_mae=share_mae,
                range_ev_mae_bb=0.5 * (np.abs(ev_o_pred - ev_o_true).mean() + np.abs(ev_i_pred - ev_i_true).mean()),
                range_ev_p95_bb=float(np.percentile(np.abs(np.r_[ev_o_pred - ev_o_true, ev_i_pred - ev_i_true]), 95)),
                conservation_err_bb=float(cons.max()))


def export_binary_weights(model: LeafValueNet, out_path: Path):
    state = model.state_dict()
    with open(out_path, "wb") as f:
        f.write(struct.pack("<I", len(state)))
        for name, tensor in state.items():
            t = tensor.detach().cpu().to(torch.float32).contiguous().numpy()
            nb = name.encode("utf-8")
            f.write(struct.pack("<I", len(nb))); f.write(nb)
            f.write(struct.pack("<I", t.ndim))
            for d in t.shape:
                f.write(struct.pack("<I", d))
            f.write(t.tobytes())
    print(f"Binary weights: {out_path} ({out_path.stat().st_size:,} bytes)", flush=True)


def main():
    torch.set_num_threads(1)
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(REPO_ROOT / "datasets/generated/nl500_100bb_leaf_cfr.parquet"))
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--mix-prob", type=float, default=0.6)
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "ml/artifacts"))
    args = ap.parse_args()

    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    df = pd.read_parquet(args.dataset)
    print(f"Loaded {len(df)} leaf records", flush=True)
    t0 = time.perf_counter()
    A = load_arrays(df)
    print(f"Arrays built in {time.perf_counter() - t0:.1f}s; valid rows {A['valid'].sum()}", flush=True)

    boards = np.unique(A["board_key"])
    rng.shuffle(boards)
    val_boards = set(boards[: int(0.15 * len(boards))])
    is_val = np.array([b in val_boards for b in A["board_key"]])
    tr_idx = np.where(~is_val & A["valid"])[0]
    va_idx = np.where(is_val & A["valid"])[0]
    print(f"Split by board: train {len(tr_idx)} rows / val {len(va_idx)} rows ({len(val_boards)} unseen boards)", flush=True)

    groups = {}
    for i in tr_idx:
        groups.setdefault(A["board_key"][i], []).append(i)
    groups = {k: np.array(v) for k, v in groups.items()}

    model = LeafValueNet()
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=1e-5)

    best, best_state = float("inf"), None
    for ep in range(1, args.epochs + 1):
        model.train()
        perm = rng.permutation(tr_idx)
        tot = 0.0
        for s in range(0, len(perm), args.batch_size):
            b = make_batch(A, perm[s:s + args.batch_size], groups, rng, args.mix_prob)
            opt.zero_grad()
            loss = share_loss(model, *b)
            loss.backward()
            opt.step()
            tot += loss.item() * len(b[0])
        sched.step()
        m = evaluate_bb(model, A, va_idx)
        if m["range_ev_mae_bb"] < best:
            best = m["range_ev_mae_bb"]
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        print(f"ep {ep:>2}/{args.epochs} train {tot / len(perm):.5f} | val share MAE {m['share_mae']:.4f} | "
              f"range-EV MAE {m['range_ev_mae_bb']:.4f} bb (p95 {m['range_ev_p95_bb']:.4f}) | "
              f"max conservation err {m['conservation_err_bb']:.2e} bb", flush=True)

    model.load_state_dict(best_state)
    final = evaluate_bb(model, A, va_idx)
    print("FINAL (unseen boards):", json.dumps({k: round(float(v), 5) for k, v in final.items()}), flush=True)

    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / "leaf_value_net.pt")

    class Shares(nn.Module):
        def __init__(self, net):
            super().__init__(); self.net = net
        def forward(self, x):
            lo, li = self.net(x)
            return torch.cat([torch.sigmoid(lo), torch.sigmoid(li)], dim=-1)

    try:
        torch.onnx.export(Shares(model).eval(), torch.randn(1, model.total_input_dim), str(out / "leaf_value_net.onnx"),
                          input_names=["input"], output_names=["equity_shares_338"],
                          dynamic_axes={"input": {0: "batch"}, "equity_shares_338": {0: "batch"}},
                          opset_version=14)
    except Exception as exc:
        print(f"ONNX export error: {exc}")
    export_binary_weights(model, out / "leaf_value_net_weights.bin")

    art = REPO_ROOT / "backend/artifacts"; art.mkdir(parents=True, exist_ok=True)
    for name in ("leaf_value_net.pt", "leaf_value_net.onnx", "leaf_value_net.onnx.data", "leaf_value_net_weights.bin"):
        if (out / name).exists():
            shutil.copy2(out / name, art / name)


if __name__ == "__main__":
    main()
