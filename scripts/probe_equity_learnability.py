#!/usr/bin/env python3
"""
scripts/probe_equity_learnability.py

Quick experiment: how well can the exact 169x169 equity matrix be learned from
the board + context features?

Compares three parameterisations on the same split:
  A. current pair form  G = a_i - a_j + (U V^T - V U^T)/sqrt(R)
  B. bilinear form       G = a_i - a_j + sum_r (p^r_i q^r_j - p^r_j q^r_i),
                         with fixed class embeddings and board-conditioned
                         projections
  C. unconstrained direct output (no antisymmetry) - an upper bound on what a
     board-conditioned model can fit at all

Run:
    python scripts/probe_equity_learnability.py --boards 200 --epochs 40
"""

from __future__ import annotations

import argparse
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
from ml.models.pair_equity_net import PairEquityNet, ResidualBlock

N = 169


class BilinearPairNet(nn.Module):
    """G[i][j] = a_i - a_j + sum_r (p_r[i] q_r[j] - p_r[j] q_r[i])."""

    def __init__(self, hidden=256, blocks=2, rank=4, ctx_rank=24):
        super().__init__()
        self.rank, self.ctx_rank = rank, ctx_rank
        self.input_proj = nn.Sequential(
            nn.Linear(81, hidden), nn.LayerNorm(hidden), nn.GELU())
        self.blocks = nn.ModuleList([ResidualBlock(hidden) for _ in range(blocks)])
        self.strength_head = nn.Linear(hidden, N)
        self.p_head = nn.Linear(hidden, rank * ctx_rank)
        self.q_head = nn.Linear(hidden, rank * ctx_rank)
        self.cls_p = nn.Parameter(torch.randn(N, ctx_rank) * 0.05)
        self.cls_q = nn.Parameter(torch.randn(N, ctx_rank) * 0.05)

    def forward(self, x):
        h = self.input_proj(x)
        for b in self.blocks:
            h = b(h)
        a = self.strength_head(h)
        u = self.p_head(h).view(-1, self.rank, self.ctx_rank)
        v = self.q_head(h).view(-1, self.rank, self.ctx_rank)
        p = torch.einsum("brd,nd->brn", u, self.cls_p)
        q = torch.einsum("brd,nd->brn", v, self.cls_q)
        return a, p, q

    @staticmethod
    def equity_matrix(a, p, q):
        # skew[i][j] = Σ_r (p[r][i]·q[r][j] − q[r][i]·p[r][j])
        skew = (torch.einsum("brn,brm->bnm", p, q)
                - torch.einsum("brn,brm->bnm", q, p))
        g = a.unsqueeze(2) - a.unsqueeze(1) + skew
        return torch.sigmoid(g)


class DirectNet(nn.Module):
    """Unconstrained 169x169 sigmoid output (upper bound, no antisymmetry)."""

    def __init__(self, hidden=512):
        super().__init__()
        self.input_proj = nn.Sequential(
            nn.Linear(81, hidden), nn.LayerNorm(hidden), nn.GELU())
        self.blocks = nn.ModuleList([ResidualBlock(hidden) for _ in range(3)])
        self.out = nn.Linear(hidden, N * N)

    def forward(self, x):
        h = self.input_proj(x)
        for b in self.blocks:
            h = b(h)
        return torch.sigmoid(self.out(h).view(-1, N, N))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(REPO_ROOT / "datasets/generated/equity_labels_2000.parquet"))
    ap.add_argument("--boards", type=int, default=200)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--only", default="ABC", help="subset of architectures to run")
    args = ap.parse_args()

    df = pd.read_parquet(args.labels)
    boards = df["board"].apply(lambda b: " ".join(list(b)))
    uniq = boards.unique()[: args.boards]
    df = df[boards.isin(uniq)].reset_index(drop=True)
    boards = df["board"].apply(lambda b: " ".join(list(b)))

    n = len(df)
    x = np.zeros((n, 81), np.float32)
    y = np.zeros((n, N, N), np.float32)
    cache = {}
    for i, r in enumerate(df.itertuples(index=False)):
        b = list(r.board)
        key = " ".join(b)
        if key not in cache:
            cache[key] = encode_board(b)
        x[i, :75] = cache[key]
        x[i, 75] = float(r.effective_stack) / 100.0
        x[i, 76] = float(r.pot) / 10.0
        x[i, 77] = float(r.ante_bb)
        x[i, 78] = float(r.rake_percent) / 10.0
        x[i, 79] = float(r.rake_cap) / 5.0
        x[i, 80] = float(r.num_folded_players) / 6.0
        y[i] = np.asarray(r.equity, dtype=np.float32).reshape(N, N)

    rng = np.random.default_rng(0)
    uniq_b = np.unique(boards)
    rng.shuffle(uniq_b)
    val_b = set(uniq_b[: max(1, len(uniq_b) // 5)])
    is_val = np.array([b in val_b for b in boards])
    tr = np.where(~is_val)[0]
    va = np.where(is_val)[0]
    print(f"rows {n} | train {len(tr)} val {len(va)}", flush=True)

    xt, yt = torch.from_numpy(x), torch.from_numpy(y)

    def run(name, model, forward):
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
        t0 = time.perf_counter()
        for ep in range(1, args.epochs + 1):
            model.train()
            perm = rng.permutation(tr)
            tot = 0.0
            for s in range(0, len(perm), args.batch_size):
                idx = perm[s:s + args.batch_size]
                opt.zero_grad()
                E = forward(model(xt[idx]))
                loss = torch.mean((E - yt[idx]) ** 2)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                opt.step()
                tot += loss.item() * len(idx)
            if ep % 10 == 0 or ep == args.epochs:
                model.eval()
                with torch.no_grad():
                    E = forward(model(xt[va]))
                    mae = float((E - yt[va]).abs().mean())
                    mse = float(((E - yt[va]) ** 2).mean())
                print(f"  [{name}] ep {ep:>3} train mse {tot / len(tr):.5f} | "
                      f"val mse {mse:.5f} | val MAE {mae:.4f} | "
                      f"{(time.perf_counter() - t0):.0f}s", flush=True)

    if "A" in args.only:
        print("A. current pair form (rank 32)", flush=True)
        m1 = PairEquityNet(hidden_dim=256, num_res_blocks=2, rank=32)
        run("A", m1, lambda o: PairEquityNet.equity_matrix(*o))

    if "B" in args.only:
        print("B. bilinear pair form (rank 4 x ctx 24)", flush=True)
        m2 = BilinearPairNet()
        run("B", m2, lambda o: BilinearPairNet.equity_matrix(*o))

    if "C" in args.only:
        print("C. unconstrained direct output", flush=True)
        m3 = DirectNet()
        run("C", m3, lambda o: o)
    return 0


if __name__ == "__main__":
    sys.exit(main())
