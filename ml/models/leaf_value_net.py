"""
ml/models/leaf_value_net.py

Model 2 (Flop-to-Turn Counterfactual Leaf Value Network):
Predicts range-conditioned 169-class counterfactual EV vectors (v_oop, v_ip)
at flop-to-turn exit nodes directly inside the Rust solver.
Replaces raw showdown equity evaluation with learned GTO terminal values.
"""

from typing import List, Dict, Tuple, Optional, Union
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

from ml.features import encode_board, encode_range


class ResidualBlock(nn.Module):
    """Residual MLP block with LayerNorm, GELU, and skip connection."""

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


class LeafValueNet(nn.Module):
    """
    Model 2: range-conditioned leaf value estimator for flop/turn exit nodes.

    Input (422 dims):
      - Board features: 75
      - OOP reach, NORMALIZED to sum 1: 169
      - IP reach, NORMALIZED to sum 1: 169
      - Context: 9 (total_pot/10, invested_oop/10, invested_ip/10, net_pot/10,
                    effective_stack/100, ante_bb, rake_pct/10, rake_cap/5, num_folded_players/6)

    Output: two 169-dim LOGIT vectors. sigmoid(logit) is the per-class share of
    the net pot that a hand wins against the opponent's normalized range
    (an equity share in [0, 1]).

    Counterfactual values are rebuilt exactly from the shares (see
    ``reconstruct``), which makes them
      * linear in the opponent's reach mass (correct at any reach scale), and
      * zero-sum: sum(r_o * v_o) + sum(r_i * v_i) == m_o * m_i * net_pot - ...
        after a projection step on the shares.
    """

    def __init__(
        self,
        board_dim: int = 75,
        range_dim: int = 169,
        ctx_dim: int = 9,
        hidden_dim: int = 256,
        num_res_blocks: int = 3,
    ):
        super().__init__()
        self.total_input_dim = board_dim + (range_dim * 2) + ctx_dim

        self.input_proj = nn.Sequential(
            nn.Linear(self.total_input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )
        self.blocks = nn.ModuleList([
            ResidualBlock(hidden_dim) for _ in range(num_res_blocks)
        ])
        self.head_oop = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Linear(128, 169),
        )
        self.head_ip = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Linear(128, 169),
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Returns (logit_oop, logit_ip), each (batch, 169)."""
        h = self.input_proj(x)
        for block in self.blocks:
            h = block(h)
        return self.head_oop(h), self.head_ip(h)

    @staticmethod
    def zero_sum_shares(t_o, t_i, ro_n, ri_n):
        """Projects shares so sum(ro_n*t_o) + sum(ri_n*t_i) == 1 (works for numpy or torch)."""
        err = (ro_n * t_o).sum(-1, keepdims=True) + (ri_n * t_i).sum(-1, keepdims=True) - 1.0
        return t_o - err / 2.0, t_i - err / 2.0

    @staticmethod
    def build_input(
        board,
        ro_n,
        ri_n,
        invested_oop,
        invested_ip,
        pot,
        rake_pct,
        rake_cap,
        effective_stack: float = 100.0,
        ante_bb: float = 0.0,
        num_folded_players: int = 4,
    ):
        tot_pot = pot + invested_oop + invested_ip
        net_pot = tot_pot - min(tot_pot * rake_pct / 100.0, rake_cap)
        ctx = np.array([
            tot_pot / 10.0,
            invested_oop / 10.0,
            invested_ip / 10.0,
            net_pot / 10.0,
            effective_stack / 100.0,
            ante_bb,
            rake_pct / 10.0,
            rake_cap / 5.0,
            num_folded_players / 6.0,
        ], dtype=np.float32)
        return np.concatenate([encode_board(board), ro_n, ri_n, ctx]).astype(np.float32), net_pot

    @torch.no_grad()
    def evaluate_leaf(
        self,
        board: List[str],
        reach_oop: Union[Dict[str, float], np.ndarray, List[float]],
        reach_ip: Union[Dict[str, float], np.ndarray, List[float]],
        invested_oop: float = 0.0,
        invested_ip: float = 0.0,
        pot: float = 5.5,
        rake_pct: float = 5.0,
        rake_cap: float = 0.6,
        effective_stack: float = 100.0,
        ante_bb: float = 0.0,
        num_folded_players: int = 4,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns per-class counterfactual values (v_oop, v_ip) for UNNORMALIZED reaches,
        identical in meaning to the Rust engine's exact showdown_values().
        ``pot`` is the starting pot of the street (before invested amounts).
        """
        self.eval()
        ro = encode_range(reach_oop) if isinstance(reach_oop, dict) else np.asarray(reach_oop, dtype=np.float32)
        ri = encode_range(reach_ip) if isinstance(reach_ip, dict) else np.asarray(reach_ip, dtype=np.float32)
        if ro.sum() > 1.0001:
            ro = ro / ro.sum()
        if ri.sum() > 1.0001:
            ri = ri / ri.sum()
        m_o, m_i = float(ro.sum()), float(ri.sum())
        ro_n = ro / m_o if m_o > 1e-12 else np.zeros_like(ro)
        ri_n = ri / m_i if m_i > 1e-12 else np.zeros_like(ri)

        x, net_pot = self.build_input(
            board, ro_n, ri_n, invested_oop, invested_ip, pot, rake_pct, rake_cap,
            effective_stack=effective_stack, ante_bb=ante_bb, num_folded_players=num_folded_players,
        )
        lo, li = self.forward(torch.from_numpy(x).unsqueeze(0))
        t_o = torch.sigmoid(lo)[0].numpy().astype(np.float64)
        t_i = torch.sigmoid(li)[0].numpy().astype(np.float64)
        t_o, t_i = self.zero_sum_shares(t_o, t_i, ro_n.astype(np.float64), ri_n.astype(np.float64))

        v_o = (t_o * net_pot - invested_oop) * m_i
        v_i = (t_i * net_pot - invested_ip) * m_o
        return v_o, v_i
