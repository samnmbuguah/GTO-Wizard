"""
ml/models/pair_equity_net_v2.py

Dense antisymmetric pair-equity operator (V2).

Why V2 exists
-------------
The V1 operator (`ml/models/pair_equity_net.py`) parameterises the pair logit
matrix as

    G[i][j] = a[i] - a[j] + (U Vᵀ - V Uᵀ)[i][j] / sqrt(R)

i.e. a hand-strength score plus a *low-rank* skew term. Measured on held-out
boards (`scripts/probe_equity_learnability.py`) that form reaches
mean |ΔE| ≈ 0.13, far above the ≈0.018 label-noise floor: the low-rank skew
cannot represent the pair-specific blocker / suit structure of the real equity
matrix.

V2 gives every unordered hand-class pair its own logit:

    s[i][j] = w_ij · h + b_ij          (i < j)
    s[j][i] = -s[i][j]                 (antisymmetric by construction)

so `E = sigmoid(s)` still satisfies `E[i][j] + E[j][i] = 1` exactly (pot
conservation stays structural), but the model has pair-specific capacity.

The per-pair weights live in a shared trunk's output space, so the weights are
small enough to stay board-conditioned: `h` is the same board+context
embedding used by V1.

Tensor layout (mirrors the Rust loader in `solver_daemon/src/leaf_net.rs`):

    input_proj.0.{weight,bias}   (hidden, 81)
    input_proj.1.{weight,bias}   LayerNorm(hidden)
    blocks.{k}.fc1/fc2.{weight,bias}, blocks.{k}.ln1/ln2.{weight,bias}
    pair_w                        (n_pairs, hidden)  f32
    pair_b                        (n_pairs,)         f32
    meta.hidden                   scalar (hidden dim)
    meta.pairs                    scalar (number of unordered pairs)
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
import torch
import torch.nn as nn

from ml.features import encode_board
from ml.models.pair_equity_net import ResidualBlock

N_CLASSES = 169
BOARD_DIM = 75
CTX_DIM = 6
INPUT_DIM = BOARD_DIM + CTX_DIM


def pair_index() -> Tuple[torch.Tensor, torch.Tensor]:
    """Upper-triangular (i, j) index vectors for the 169x169 class matrix."""
    iu, ju = torch.triu_indices(N_CLASSES, N_CLASSES, offset=1)
    return iu, ju


class DensePairEquityNet(nn.Module):
    """Antisymmetric pair-equity operator with a per-pair logit head."""

    N_CLASSES = N_CLASSES
    BOARD_DIM = BOARD_DIM
    CTX_DIM = CTX_DIM
    total_input_dim = INPUT_DIM

    def __init__(self, hidden_dim: int = 128, num_res_blocks: int = 2, dropout: float = 0.1):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_res_blocks = num_res_blocks

        self.input_proj = nn.Sequential(
            nn.Linear(INPUT_DIM, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )
        self.blocks = nn.ModuleList([ResidualBlock(hidden_dim) for _ in range(num_res_blocks)])
        self.dropout = nn.Dropout(dropout)

        iu, ju = pair_index()
        self.register_buffer("pair_i", iu)
        self.register_buffer("pair_j", ju)
        n_pairs = iu.numel()
        self.n_pairs = n_pairs

        self.pair_w = nn.Parameter(torch.randn(n_pairs, hidden_dim) * 0.02)
        self.pair_b = nn.Parameter(torch.zeros(n_pairs))

    # ------------------------------------------------------------------ #
    def trunk(self, x: torch.Tensor) -> torch.Tensor:
        h = self.input_proj(x)
        for block in self.blocks:
            h = block(h)
        return h

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Returns the full (B, 169, 169) antisymmetric logit matrix."""
        h = self.trunk(x)
        h = self.dropout(h)
        s = h @ self.pair_w.t() + self.pair_b          # (B, n_pairs)
        b = s.shape[0]
        full = torch.zeros(b, N_CLASSES, N_CLASSES, dtype=s.dtype, device=s.device)
        full[:, self.pair_i, self.pair_j] = s
        full[:, self.pair_j, self.pair_i] = -s
        return full

    @staticmethod
    def equity_from_logits(s: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(s)

    def equity_matrix(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.forward(x))

    # ------------------------------------------------------------------ #
    @staticmethod
    def build_input(
        board: List[str],
        effective_stack: float = 100.0,
        starting_pot: float = 5.5,
        ante_bb: float = 0.0,
        rake_pct: float = 5.0,
        rake_cap: float = 0.6,
        num_folded_players: int = 4,
    ) -> np.ndarray:
        """Board + normalized generalized context (same convention as V1)."""
        return np.concatenate([
            encode_board(board),
            np.array([
                effective_stack / 100.0,
                starting_pot / 10.0,
                ante_bb,
                rake_pct / 10.0,
                rake_cap / 5.0,
                num_folded_players / 6.0,
            ], dtype=np.float32),
        ]).astype(np.float32)

    @torch.no_grad()
    def evaluate_equity(
        self,
        board: List[str],
        effective_stack: float = 100.0,
        starting_pot: float = 5.5,
        ante_bb: float = 0.0,
        rake_pct: float = 5.0,
        rake_cap: float = 0.6,
        num_folded_players: int = 4,
    ) -> np.ndarray:
        self.eval()
        x = self.build_input(
            board, effective_stack, starting_pot, ante_bb, rake_pct, rake_cap,
            num_folded_players,
        )
        logits = self.forward(torch.from_numpy(x).unsqueeze(0))
        return torch.sigmoid(logits)[0].double().numpy()

    @torch.no_grad()
    def evaluate_leaf(
        self,
        board: List[str],
        reach_oop,
        reach_ip,
        invested_oop: float = 0.0,
        invested_ip: float = 0.0,
        pot: float = 5.5,
        rake_pct: float = 5.0,
        rake_cap: float = 0.6,
        effective_stack: float = 100.0,
        ante_bb: float = 0.0,
        num_folded_players: int = 4,
    ) -> Tuple[np.ndarray, np.ndarray]:
        from ml.features import encode_range

        ro = encode_range(reach_oop) if isinstance(reach_oop, dict) else np.asarray(reach_oop, np.float64)
        ri = encode_range(reach_ip) if isinstance(reach_ip, dict) else np.asarray(reach_ip, np.float64)
        ro = ro.astype(np.float64)
        ri = ri.astype(np.float64)
        m_o, m_i = float(ro.sum()), float(ri.sum())
        if m_o <= 1e-12 or m_i <= 1e-12:
            return np.zeros(169), np.zeros(169)
        ro_n, ri_n = ro / m_o, ri / m_i
        E = self.evaluate_equity(
            board,
            effective_stack=effective_stack,
            starting_pot=pot,
            ante_bb=ante_bb,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
            num_folded_players=num_folded_players,
        )
        tot_pot = pot + invested_oop + invested_ip
        net_pot = tot_pot - min(tot_pot * rake_pct / 100.0, rake_cap)
        share_o = E @ ri_n
        share_i = 1.0 - ro_n @ E
        v_o = (share_o * net_pot - invested_oop) * m_i
        v_i = (share_i * net_pot - invested_ip) * m_o
        return v_o, v_i
