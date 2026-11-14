"""
ml/models/pair_equity_net.py

Board-conditioned antisymmetric pair-equity operator (169x169).

For each board we predict a logit matrix ``G`` with ``G[i][j] = -G[j][i]`` and
define the pair equilibrium share

    E[i][j] = sigmoid(G[i][j])

so that ``E[i][j] + E[j][i] == 1`` holds exactly for every pair of hand classes.
``E[i][j]`` is the fraction of the pot class ``i`` wins against class ``j``
(ties split 0.5), which is exactly the convention of the Rust evaluator's
``compute_equity`` matrix.

Why this shape matters: the terminal counterfactual values are

    v_oop[i] = (sum_j E[i][j] * ri_n[j]) * net_pot * m_i - invested_oop * m_i
    v_ip[j]  = (1 - sum_i ro_n[i] * E[i][j]) * net_pot * m_o - invested_ip * m_o

Summing those against the reaches cancels the equity terms identically, leaving

    sum(ro * v_oop) + sum(ri * v_ip) = m_o * m_i * (start_pot - rake)

for ANY pair of independent reaches. Pot conservation is structural, not learned.

``G`` is parameterised with a strong inductive bias:

    G[i][j] = a[i] - a[j] + (U V^T - V U^T)[i][j]

where ``a`` is a board-conditioned hand-strength score per class (equity is
mostly monotone in strength) and the low-rank term captures non-transitive
blocker/suit effects.
"""

from typing import Tuple, Union, List

import numpy as np
import torch
import torch.nn as nn

from ml.features import encode_board


class ResidualBlock(nn.Module):
    """Residual MLP block with LayerNorm, GELU, and a skip connection."""

    def __init__(self, dim: int, dropout: float = 0.02):
        super().__init__()
        self.fc1 = nn.Linear(dim, dim)
        self.ln1 = nn.LayerNorm(dim)
        self.act1 = nn.GELU()
        self.fc2 = nn.Linear(dim, dim)
        self.ln2 = nn.LayerNorm(dim)
        self.act2 = nn.GELU()
        self.drop = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = self.act1(self.ln1(self.fc1(x)))
        out = self.drop(out)
        out = self.ln2(self.fc2(out))
        out = self.act2(out + residual)
        return out


class PairEquityNet(nn.Module):
    """Predicts a 169x169 antisymmetric pair-equity operator from the board."""

    N_CLASSES = 169
    BOARD_DIM = 75
    # Generalized context, normalized:
    # [stack_bb/100, starting_pot_bb/10, ante_bb, rake_pct/10, rake_cap/5,
    #  num_folded_players/6]
    CTX_DIM = 6

    def __init__(self, hidden_dim: int = 256, num_res_blocks: int = 2, rank: int = 8):
        super().__init__()
        self.rank = rank
        self.total_input_dim = self.BOARD_DIM + self.CTX_DIM

        self.input_proj = nn.Sequential(
            nn.Linear(self.total_input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )
        self.blocks = nn.ModuleList([ResidualBlock(hidden_dim) for _ in range(num_res_blocks)])
        head_out = self.N_CLASSES + 2 * self.N_CLASSES * rank
        self.head = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Linear(128, head_out),
        )

        # Start close to 0.5 everywhere; training moves it.
        nn.init.zeros_(self.head[-1].weight)
        nn.init.zeros_(self.head[-1].bias)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Returns (a, U, V), with a (B,169), U/V (B,169,rank)."""
        h = self.input_proj(x)
        for block in self.blocks:
            h = block(h)
        out = self.head(h)
        a = out[:, : self.N_CLASSES]
        rest = out[:, self.N_CLASSES :].view(-1, 2, self.N_CLASSES, self.rank)
        return a, rest[:, 0], rest[:, 1]

    @staticmethod
    def equity_matrix(a: torch.Tensor, u: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
        """Builds ``E = sigmoid(a_i - a_j + (U V^T - V U^T)/sqrt(R))``."""
        av = torch.matmul(u, v.transpose(1, 2))
        g = (a.unsqueeze(2) - a.unsqueeze(1)) + (av - av.transpose(1, 2)) / (u.shape[-1] ** 0.5)
        return torch.sigmoid(g)

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
        """Board + normalized generalized context. `starting_pot` is the pot at
        the start of the street (before the leaf's invested chips)."""
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
        """Returns the 169x169 pair-equity matrix as float64."""
        self.eval()
        x = self.build_input(
            board, effective_stack, starting_pot, ante_bb, rake_pct, rake_cap,
            num_folded_players,
        )
        a, u, v = self.forward(torch.from_numpy(x).unsqueeze(0))
        return self.equity_matrix(a, u, v)[0].double().numpy()

    @torch.no_grad()
    def evaluate_leaf(
        self,
        board: List[str],
        reach_oop: Union[dict, np.ndarray, List[float]],
        reach_ip: Union[dict, np.ndarray, List[float]],
        invested_oop: float = 0.0,
        invested_ip: float = 0.0,
        pot: float = 5.5,
        rake_pct: float = 5.0,
        rake_cap: float = 0.6,
        effective_stack: float = 100.0,
        ante_bb: float = 0.0,
        num_folded_players: int = 4,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Per-class counterfactual values for UNNORMALIZED reaches (bb)."""
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
