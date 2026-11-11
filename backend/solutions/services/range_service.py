"""
Dynamic Preflop Range & Rake Interpolation Service.
Provides 6-max starting ranges morphed based on rake percentage and rake cap.
Higher rake -> tighter opening ranges, higher 3-bet frequency vs flatting, decreased offsuit connectivity.
"""
from typing import Dict, Any, Tuple

# All 169 canonical Hold'em hands
RANKS = 'AKQJT98765432'
PAIRS = [r + r for r in RANKS]
SUITED = [RANKS[i] + RANKS[j] + 's' for i in range(len(RANKS)) for j in range(i + 1, len(RANKS))]
OFFSUIT = [RANKS[i] + RANKS[j] + 'o' for i in range(len(RANKS)) for j in range(i + 1, len(RANKS))]
ALL_HANDS = PAIRS + SUITED + OFFSUIT

# Baseline 100bb Opening / Calling Ranges (Base: 5% rake, 3bb cap)
BASE_RANGES: Dict[str, Dict[str, float]] = {
    # Button Opening Range (~43% of hands)
    "BTN_OPEN": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 1.0, "99": 1.0, "88": 1.0, "77": 1.0, "66": 1.0, "55": 1.0, "44": 1.0, "33": 0.8, "22": 0.6,
        "AKs": 1.0, "AQs": 1.0, "AJs": 1.0, "ATs": 1.0, "A9s": 1.0, "A8s": 1.0, "A7s": 1.0, "A6s": 1.0, "A5s": 1.0, "A4s": 1.0, "A3s": 1.0, "A2s": 1.0,
        "KQs": 1.0, "KJs": 1.0, "KTs": 1.0, "K9s": 1.0, "K8s": 0.9, "K7s": 0.8, "K6s": 0.7, "K5s": 0.6, "K4s": 0.5, "K3s": 0.4, "K2s": 0.3,
        "QJs": 1.0, "QTs": 1.0, "Q9s": 1.0, "Q8s": 0.9, "Q7s": 0.7, "Q6s": 0.5, "Q5s": 0.4, "Q4s": 0.3,
        "JTs": 1.0, "J9s": 1.0, "J8s": 0.9, "J7s": 0.7, "J6s": 0.4,
        "T9s": 1.0, "T8s": 0.9, "T7s": 0.6, "98s": 1.0, "97s": 0.8, "87s": 1.0, "86s": 0.7, "76s": 1.0, "75s": 0.5, "65s": 0.9, "54s": 0.8, "43s": 0.5,
        "AKo": 1.0, "AQo": 1.0, "AJo": 1.0, "ATo": 1.0, "A9o": 0.8, "A8o": 0.6, "A7o": 0.5, "A6o": 0.3, "A5o": 0.4, "A4o": 0.3,
        "KQo": 1.0, "KJo": 1.0, "KTo": 0.9, "K9o": 0.6, "K8o": 0.3,
        "QJo": 1.0, "QTo": 0.8, "Q9o": 0.4,
        "JTo": 0.8, "J9o": 0.4, "T9o": 0.4, "98o": 0.3
    },
    # Big Blind Defense vs BTN 2.5bb Open (Call + 3-Bet)
    "BB_DEFENSE": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 1.0, "99": 1.0, "88": 1.0, "77": 1.0, "66": 1.0, "55": 1.0, "44": 0.9, "33": 0.8, "22": 0.7,
        "AKs": 1.0, "AQs": 1.0, "AJs": 1.0, "ATs": 1.0, "A9s": 1.0, "A8s": 1.0, "A7s": 1.0, "A6s": 1.0, "A5s": 1.0, "A4s": 1.0, "A3s": 1.0, "A2s": 1.0,
        "KQs": 1.0, "KJs": 1.0, "KTs": 1.0, "K9s": 1.0, "K8s": 1.0, "K7s": 1.0, "K6s": 0.9, "K5s": 0.8, "K4s": 0.7, "K3s": 0.6, "K2s": 0.5,
        "QJs": 1.0, "QTs": 1.0, "Q9s": 1.0, "Q8s": 1.0, "Q7s": 0.9, "Q6s": 0.8, "Q5s": 0.7, "Q4s": 0.5, "Q3s": 0.4, "Q2s": 0.3,
        "JTs": 1.0, "J9s": 1.0, "J8s": 1.0, "J7s": 0.9, "J6s": 0.7, "J5s": 0.5,
        "T9s": 1.0, "T8s": 1.0, "T7s": 0.9, "T6s": 0.6, "98s": 1.0, "97s": 0.9, "96s": 0.7, "87s": 1.0, "86s": 0.9, "85s": 0.5, "76s": 1.0, "75s": 0.8, "65s": 1.0, "54s": 0.9, "43s": 0.6,
        "AKo": 1.0, "AQo": 1.0, "AJo": 1.0, "ATo": 1.0, "A9o": 0.9, "A8o": 0.8, "A7o": 0.7, "A6o": 0.5, "A5o": 0.6, "A4o": 0.5, "A3o": 0.4, "A2o": 0.3,
        "KQo": 1.0, "KJo": 1.0, "KTo": 0.9, "K9o": 0.8, "K8o": 0.6, "K7o": 0.4,
        "QJo": 1.0, "QTo": 0.9, "Q9o": 0.7, "Q8o": 0.4,
        "JTo": 0.9, "J9o": 0.7, "J8o": 0.4,
        "T9o": 0.8, "T8o": 0.5, "98o": 0.7, "87o": 0.5, "76o": 0.4
    },
    # Small Blind 3-Bet / Flat vs BTN
    "SB_DEFENSE": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 1.0, "99": 0.85, "88": 0.7, "77": 0.5, "66": 0.3,
        "AKs": 1.0, "AQs": 1.0, "AJs": 1.0, "ATs": 0.9, "A9s": 0.6, "A5s": 0.8, "A4s": 0.7, "A3s": 0.5,
        "KQs": 1.0, "KJs": 0.85, "KTs": 0.7, "K9s": 0.4, "QJs": 0.85, "QTs": 0.7, "JTs": 0.8, "T9s": 0.7, "98s": 0.6, "87s": 0.5, "76s": 0.4,
        "AKo": 1.0, "AQo": 0.9, "AJo": 0.7, "KQo": 0.6
    }
}

class PreflopRangeService:
    """
    Interpolates preflop ranges according to custom rake percentage and rake cap.
    Follows game theory principles:
    - High rake imposes a severe penalty on low EV flatting hands (offsuit broadways, small pairs).
    - Opening ranges compress linearly with higher rake.
    - Low rake / rake-free environments broaden calling frequencies.
    """

    @staticmethod
    def get_interpolated_range(
        position_spot: str,
        rake_percent: float = 5.0,
        rake_cap: float = 3.0,
        baseline_spot: str = "BTN_OPEN"
    ) -> Dict[str, float]:
        """
        Calculates hand frequencies for the given spot morphed by rake parameters.
        Returns a dictionary mapping hand strings (e.g. 'AA', 'AKs') to weight [0.0, 1.0].
        """
        # Select closest baseline
        base_map = BASE_RANGES.get(position_spot, BASE_RANGES.get(baseline_spot, BASE_RANGES["BTN_OPEN"]))
        
        # Reference anchor: 5% rake, 3.0bb cap (rake_impact factor = 1.0)
        # Low rake: 0% rake -> rake_impact = 0.0
        # High rake: 10% rake, 5bb cap -> rake_impact = ~2.2
        effective_rake_factor = (rake_percent / 5.0) * min(max(rake_cap / 3.0, 0.3), 2.5)
        rake_penalty_multiplier = max(0.0, (effective_rake_factor - 1.0))

        adjusted_range: Dict[str, float] = {}

        for hand in ALL_HANDS:
            base_weight = base_map.get(hand, 0.0)
            if base_weight <= 0.0:
                continue

            # Premium hands remain 100% playable regardless of rake
            if hand in ["AA", "KK", "QQ", "AKs", "AKo"]:
                adjusted_range[hand] = 1.0
                continue

            is_suited = hand.endswith('s')
            is_pair = len(hand) == 2
            is_offsuit = hand.endswith('o')

            # Elasticity coefficients per hand category
            # Offsuit hands are most sensitive to rake due to negative playability postflop
            if is_offsuit:
                elasticity = 0.32
            elif is_pair:
                elasticity = 0.18
            elif is_suited:
                elasticity = 0.12
            else:
                elasticity = 0.20

            if effective_rake_factor >= 1.0:
                # Shrink marginal hands under higher rake
                new_weight = base_weight * (1.0 - (rake_penalty_multiplier * elasticity))
            else:
                # Expand slightly in lower rake / zero rake environments
                expansion_benefit = (1.0 - effective_rake_factor) * 0.15
                new_weight = min(1.0, base_weight * (1.0 + expansion_benefit))

            new_weight = round(max(0.0, min(1.0, new_weight)), 3)
            if new_weight > 0.01:
                adjusted_range[hand] = new_weight

        return adjusted_range

    @classmethod
    def get_spot_ranges(
        cls,
        spot: str = "BTN_vs_BB_SRP",
        rake_percent: float = 5.0,
        rake_cap: float = 3.0
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Returns (oop_range, ip_range) for postflop solver calculation.
        """
        if "BTN_vs_BB" in spot or "SRP" in spot:
            oop_range = cls.get_interpolated_range("BB_DEFENSE", rake_percent, rake_cap)
            ip_range = cls.get_interpolated_range("BTN_OPEN", rake_percent, rake_cap)
        elif "SB_vs_BB" in spot:
            oop_range = cls.get_interpolated_range("SB_DEFENSE", rake_percent, rake_cap)
            ip_range = cls.get_interpolated_range("BB_DEFENSE", rake_percent, rake_cap)
        else:
            oop_range = cls.get_interpolated_range("BB_DEFENSE", rake_percent, rake_cap)
            ip_range = cls.get_interpolated_range("BTN_OPEN", rake_percent, rake_cap)

        return oop_range, ip_range
