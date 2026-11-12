"""
ml/features.py

Feature encoding and tensor transformation utilities for:
- Model 1: Bet Size Predictor
- Model 2: Flop-to-Turn Leaf Counterfactual Value Net
"""

from typing import List, Dict, Tuple
import torch
import numpy as np

RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
SUITS = ["s", "h", "d", "c"]
RANK_TO_INT = {r: 14 - i for i, r in enumerate(RANKS)}
SUIT_TO_INT = {"s": 0, "h": 1, "d": 2, "c": 3}

# Canonical 169 poker hands in standard order
CANONICAL_169_HANDS: List[str] = []
for i, r1 in enumerate(RANKS):
    for j, r2 in enumerate(RANKS):
        if i == j:
            CANONICAL_169_HANDS.append(f"{r1}{r2}")
        elif i < j:
            CANONICAL_169_HANDS.append(f"{r1}{r2}s")
        else:
            CANONICAL_169_HANDS.append(f"{r2}{r1}o")
# Deduplicate preserving order
CANONICAL_169_HANDS = list(dict.fromkeys(CANONICAL_169_HANDS))
HAND_TO_IDX = {h: idx for idx, h in enumerate(CANONICAL_169_HANDS)}

# Candidate bet sizings for single-size tree pruning
CANDIDATE_SIZES = [0.33, 0.50, 0.75, 1.25]
SIZE_TO_CLASS = {0.33: 0, 0.50: 1, 0.75: 2, 1.25: 3}
CLASS_TO_SIZE = {v: k for k, v in SIZE_TO_CLASS.items()}


def encode_card_one_hot(card: str) -> np.ndarray:
    """Encodes a single card (e.g. 'As') into a 52-dim one-hot vector."""
    vec = np.zeros(52, dtype=np.float32)
    if len(card) >= 2:
        rank = card[0].upper()
        suit = card[1].lower()
        if rank in RANK_TO_INT and suit in SUIT_TO_INT:
            r_idx = 14 - RANK_TO_INT[rank]  # 0 for A, 12 for 2
            s_idx = SUIT_TO_INT[suit]
            vec[r_idx * 4 + s_idx] = 1.0
    return vec


def encode_board(board: List[str]) -> np.ndarray:
    """
    Encodes flop board (3 cards) into a rich feature vector:
    - 52-dim multi-hot card representation
    - 13-dim rank frequency vector
    - 4-dim suit frequency vector
    - Texture indicators: is_paired, is_trips, is_monotone, is_twotone, is_rainbow, high_card_norm
    Total dim = 52 + 13 + 4 + 6 = 75 dims.
    """
    card_52 = np.zeros(52, dtype=np.float32)
    rank_13 = np.zeros(13, dtype=np.float32)
    suit_4 = np.zeros(4, dtype=np.float32)

    rank_vals = []
    suit_vals = []

    for c in board:
        if len(c) >= 2:
            r = c[0].upper()
            s = c[1].lower()
            if r in RANK_TO_INT and s in SUIT_TO_INT:
                r_val = RANK_TO_INT[r]
                s_val = SUIT_TO_INT[s]
                rank_vals.append(r_val)
                suit_vals.append(s_val)

                card_52[(14 - r_val) * 4 + s_val] = 1.0
                rank_13[14 - r_val] += 1.0
                suit_4[s_val] += 1.0

    # Board texture scalars
    rank_counts = np.bincount(rank_vals, minlength=15)
    max_rank_count = rank_counts.max() if len(rank_vals) > 0 else 0
    is_paired = 1.0 if max_rank_count == 2 else 0.0
    is_trips = 1.0 if max_rank_count == 3 else 0.0

    suit_counts = np.bincount(suit_vals, minlength=4)
    max_suit_count = suit_counts.max() if len(suit_vals) > 0 else 0
    is_monotone = 1.0 if max_suit_count == 3 else 0.0
    is_twotone = 1.0 if max_suit_count == 2 else 0.0
    is_rainbow = 1.0 if max_suit_count <= 1 else 0.0

    high_card_norm = (max(rank_vals) / 14.0) if rank_vals else 0.0

    scalars = np.array(
        [is_paired, is_trips, is_monotone, is_twotone, is_rainbow, high_card_norm],
        dtype=np.float32,
    )

    return np.concatenate([card_52, rank_13, suit_4, scalars])


def encode_range(range_dict: Dict[str, float]) -> np.ndarray:
    """Encodes a range dict into a 169-dimensional reach probability vector."""
    vec = np.zeros(169, dtype=np.float32)
    for hand, weight in range_dict.items():
        idx = HAND_TO_IDX.get(hand)
        if idx is not None:
            vec[idx] = float(weight)
    return vec


def optimal_sizing_to_class(size: float) -> int:
    """Maps an engine-reported bet size (fraction of pot) to a candidate class."""
    return min(
        range(len(CANDIDATE_SIZES)),
        key=lambda i: abs(CANDIDATE_SIZES[i] - float(size)),
    )


def determine_optimal_bet_size(board: List[str], pot: float) -> int:
    """
    Ground-truth heuristic for optimal bet size selection (Model 1 target):
    - Paired/Dry boards: prefer small sizing (0.33)
    - Medium connected boards: prefer standard sizing (0.50)
    - Wet dynamic/draw-heavy boards: prefer geometric sizing (0.75)
    - Monotone/polar boards: prefer overbet sizing (1.25)
    """
    encoded = encode_board(board)
    is_paired = encoded[52 + 13 + 4 + 0]
    is_monotone = encoded[52 + 13 + 4 + 2]
    is_twotone = encoded[52 + 13 + 4 + 3]
    high_card = encoded[52 + 13 + 4 + 5]

    if is_monotone > 0.5:
        return SIZE_TO_CLASS[1.25]
    if is_paired > 0.5 or high_card > 0.90:
        return SIZE_TO_CLASS[0.33]
    if is_twotone > 0.5:
        return SIZE_TO_CLASS[0.75]
    return SIZE_TO_CLASS[0.50]
