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
    Model 2: Counterfactual Value Estimator for postflop leaf nodes.
    Input:
      - Board features: 75 dims (card one-hots, rank/suit histograms, texture flags)
      - OOP Range reach: 169 dims
      - IP Range reach: 169 dims
      - Context: 5 dims (pot, invested_oop, invested_ip, net_pot, rake_pct)
      Total input dim = 75 + 169 + 169 + 5 = 418 dims.
    Outputs:
      - v_oop: (batch, 169) counterfactual EV vector for OOP
      - v_ip:  (batch, 169) counterfactual EV vector for IP
    """

    def __init__(
        self,
        board_dim: int = 75,
        range_dim: int = 169,
        ctx_dim: int = 5,
        hidden_dim: int = 256,
        num_res_blocks: int = 3,
    ):
        super().__init__()
        self.total_input_dim = board_dim + (range_dim * 2) + ctx_dim

        # Input projection
        self.input_proj = nn.Sequential(
            nn.Linear(self.total_input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )

        # Residual backbone
        self.blocks = nn.ModuleList([
            ResidualBlock(hidden_dim) for _ in range(num_res_blocks)
        ])

        # OOP Counterfactual Value Head (169 hand classes)
        self.head_oop = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Linear(128, 169),
        )

        # IP Counterfactual Value Head (169 hand classes)
        self.head_ip = nn.Sequential(
            nn.Linear(hidden_dim, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Linear(128, 169),
        )

    def forward(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.
        Returns:
          - v_oop: (batch, 169)
          - v_ip:  (batch, 169)
        """
        h = self.input_proj(x)
        for block in self.blocks:
            h = block(h)

        v_oop = self.head_oop(h)
        v_ip = self.head_ip(h)
        return v_oop, v_ip

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
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Evaluates a terminal leaf state during live solving in < 0.2ms.
        Returns (v_oop, v_ip) as numpy arrays of 169 values each.
        """
        self.eval()
        board_vec = encode_board(board)

        if isinstance(reach_oop, dict):
            oop_vec = encode_range(reach_oop)
        else:
            oop_vec = np.array(reach_oop, dtype=np.float32)

        if isinstance(reach_ip, dict):
            ip_vec = encode_range(reach_ip)
        else:
            ip_vec = np.array(reach_ip, dtype=np.float32)

        tot_pot = pot + invested_oop + invested_ip
        rake = min(tot_pot * (rake_pct / 100.0), rake_cap)
        net_pot = tot_pot - rake

        ctx_vec = np.array([
            tot_pot / 10.0,
            invested_oop / 10.0,
            invested_ip / 10.0,
            net_pot / 10.0,
            rake_pct / 10.0,
        ], dtype=np.float32)

        x_np = np.concatenate([board_vec, oop_vec, ip_vec, ctx_vec])
        x_tensor = torch.from_numpy(x_np).unsqueeze(0)

        v_oop_pred, v_ip_pred = self.forward(x_tensor)
        v_oop = v_oop_pred.squeeze(0).numpy()
        v_ip = v_ip_pred.squeeze(0).numpy()

        return v_oop, v_ip
