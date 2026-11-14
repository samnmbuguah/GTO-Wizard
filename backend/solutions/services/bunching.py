"""
backend/solutions/services/bunching.py

Seat-aware preflop card-bunching (dead-card) profiles.

Preflop card bunching is the fact that folded players hold cards: the more
trash an early position folds, the more low-ranked cards are dead and the
richer the effective deck becomes for the remaining players. The solver applies
this in two places (see `solver_daemon/src/cfr.rs`):

* turn/river runout probabilities (rank-survival weighted sampling), and
* hole-card combo weights (`normalized_reach`).

The daemon has a built-in profile derived from the *number* of folded players.
This module derives a profile from the *seats* that folded, using the
pre-solved 6-max baselines: the complement of a seat's opening range is the set
of hands that seat folds, and every folded combo removes its cards from the
deck.

The result is a 13-value rank-survival profile (index 0 = '2' ... 12 = 'A'),
normalized to mean 1.0, ready to be passed to the solver as
`bunching_weights`.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

RANKS = "23456789TJQKA"  # ascending, index 0 = '2' ... 12 = 'A'
TOTAL_COMBOS = 1326     # 13*6 pairs + 78*4 suited + 78*12 offsuit


def _rank_counts(hand: str) -> Dict[str, int]:
    """Number of cards of each rank in a 169-class hand."""
    if len(hand) == 2:  # pair
        return {hand[0]: 2}
    return {hand[0]: 1, hand[1]: 1}


def _combos(hand: str) -> int:
    if len(hand) == 2:
        return 6
    return 4 if hand.endswith("s") else 12


def all_hand_classes() -> List[str]:
    from .range_service import ALL_HANDS
    return list(ALL_HANDS)


def expected_folded_cards_by_rank(
    seat_ranges: Sequence[Dict[str, float]],
) -> List[float]:
    """Expected number of folded cards per rank (2..A) for the given seats.

    `seat_ranges` holds, per folded seat, the range that seat *plays*
    (`{hand_class: frequency}`). Hands outside the range are folded with
    probability 1, hands inside with probability `1 - frequency`. Classes are
    weighted by their number of deck combinations so the expected card counts
    are unbiased.
    """
    removed = [0.0] * 13
    for rng in seat_ranges:
        for hand in all_hand_classes():
            freq = float(rng.get(hand, 0.0))
            freq = min(max(freq, 0.0), 1.0)
            fold_p = 1.0 - freq
            if fold_p <= 0.0:
                continue
            weight = _combos(hand) * fold_p / TOTAL_COMBOS
            for rank, n in _rank_counts(hand).items():
                removed[RANKS.index(rank)] += weight * n
    return removed


def rank_survival_weights(
    seat_ranges: Sequence[Dict[str, float]],
    deck_per_rank: int = 4,
) -> List[float]:
    """13 rank-survival weights (2..A) normalized to mean 1.0."""
    removed = expected_folded_cards_by_rank(seat_ranges)
    raw = []
    for r in range(13):
        surv = max(deck_per_rank - removed[r], 0.05) / deck_per_rank
        raw.append(surv)
    mean = sum(raw) / len(raw)
    return [w / mean for w in raw]


def seat_open_range(seat: str, rake_percent: float = 5.0,
                    rake_cap: float = 0.6) -> Dict[str, float]:
    """Opening range for a folded seat, from the pre-solved 6-max baselines."""
    from .range_service import BASELINE_0_RAKE, BASELINE_5_RAKE, PreflopRangeService

    seat = (seat or "").upper()
    key = None
    if seat in ("UTG", "UTG1", "EP"):
        key = "UTG_OPEN"
    elif seat in ("BTN", "BU"):
        key = "BTN_OPEN"
    elif seat in ("SB", "BTN?"):
        key = "SB_DEFENSE"
    if key:
        base = BASELINE_5_RAKE if rake_percent > 0 else BASELINE_0_RAKE
        return dict(base.get(key, {}))

    # Unknown middle seats: interpolate between the early and late open ranges
    # (HJ/MP/CO open a little wider than UTG).
    base = BASELINE_5_RAKE if rake_percent > 0 else BASELINE_0_RAKE
    utg = base.get("UTG_OPEN", {})
    btn = base.get("BTN_OPEN", {})
    merged: Dict[str, float] = {}
    for hand in all_hand_classes():
        merged[hand] = 0.5 * (float(utg.get(hand, 0.0)) + float(btn.get(hand, 0.0)))
    return merged


def derive_bunching_weights(
    folded_seats: Iterable[str],
    rake_percent: float = 5.0,
    rake_cap: float = 0.6,
    deck_per_rank: int = 4,
) -> List[float]:
    """Seat-derived 13-value bunching profile (mean 1.0)."""
    seats = [s for s in folded_seats if s]
    if not seats:
        return [1.0] * 13
    seat_ranges = [seat_open_range(s, rake_percent, rake_cap) for s in seats]
    return rank_survival_weights(seat_ranges, deck_per_rank=deck_per_rank)


def fallback_profile(num_folded_players: int) -> List[float]:
    """Mirror of the daemon's built-in profile (for comparisons)."""
    if num_folded_players <= 0:
        return [1.0] * 13
    fold_rates = [0.87, 0.87, 0.87, 0.87, 0.87, 0.84, 0.84, 0.80, 0.71, 0.67, 0.62, 0.55, 0.44]
    mean_fold = sum(fold_rates) / 13.0
    weights = []
    for r in range(13):
        p_removed = (2.0 / 50.0) * (fold_rates[r] / mean_fold)
        weights.append(max(1.0 - p_removed, 0.01) ** num_folded_players)
    mean_w = sum(weights) / 13.0
    return [w / mean_w for w in weights]
