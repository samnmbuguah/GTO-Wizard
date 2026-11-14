"""
ml/models/size_predictor.py

Model 1 (Bet Size Predictor):
Selects the single optimal bet/raise size per texture to prune the tree down to 1-size geometry.
Lightweight classifier given board texture embeddings and pot/stack context.
"""

from typing import List, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

from ml.features import encode_board, CANDIDATE_SIZES, CLASS_TO_SIZE


class BetSizePredictor(nn.Module):
    """
    Model 1: Predicts single optimal bet/raise size among [0.33, 0.50, 0.75, 1.25].
    Input:
      - Board features: 75 dims (card one-hot, rank/suit hist, texture indicators)
      - Generalized context: 7 dims
        [stack_bb/100, pot_bb/10, spr/20, ante_bb, rake_pct/10, rake_cap/5, num_folded_players/6]
      Total input dim = 82 dims.
    Output:
      - 4-dim logits over candidate sizes.
    """

    def __init__(self, input_dim: int = 82, hidden_dim: int = 128, num_classes: int = 4):
        super().__init__()
        self.input_dim = input_dim
        self.num_classes = num_classes

        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, 64),
            nn.LayerNorm(64),
            nn.GELU(),
            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass returning unnormalized class logits."""
        return self.net(x)

    @torch.no_grad()
    def predict_size(
        self,
        board: List[str],
        pot: float = 5.5,
        effective_stack: float = 100.0,
        ante_bb: float = 0.0,
        rake_pct: float = 5.0,
        rake_cap: float = 0.6,
        num_folded_players: int = 4,
    ) -> Tuple[float, np.ndarray]:
        """
        Inference helper: predicts single optimal sizing fraction and probability distribution.
        Runs in < 0.1ms on CPU.
        """
        self.eval()
        board_feats = encode_board(board)
        spr = effective_stack / max(pot, 0.1)
        ctx_feats = np.array([
            effective_stack / 100.0,
            pot / 10.0,
            spr / 20.0,
            ante_bb,
            rake_pct / 10.0,
            rake_cap / 5.0,
            num_folded_players / 6.0,
        ], dtype=np.float32)
        x_np = np.concatenate([board_feats, ctx_feats])

        x_tensor = torch.from_numpy(x_np).unsqueeze(0)
        logits = self.forward(x_tensor)
        probs = F.softmax(logits, dim=-1).squeeze(0).numpy()
        pred_idx = int(np.argmax(probs))
        chosen_size = CLASS_TO_SIZE[pred_idx]

        return chosen_size, probs
