"""
backend/solutions/services/range_service.py

Dynamic Preflop Range & Rake Interpolation Service.
Provides 6-max starting ranges morphed based on rake percentage, rake cap, and stack depth.

Game Theory & Empirical Rake Mechanics:
- "No Flop, No Drop": Pots won preflop incur zero rake. Higher rake dramatically incentives 3-betting over flatting.
- Marginal / Offsuit Hands: High postflop rake drag imposes severe EV reduction on low-connectivity or offsuit broadways (e.g., KJo, QTo, 98o).
- Low / Zero Rake: Flatting ranges broaden significantly (defending wide from the Big Blind).
- Stack Depth: Deeper stacks (150bb+) increase implied odds, shifting value toward suited connectors; shallower stacks (40bb) compress ranges toward pairs and high card blockers.
"""

from typing import Dict, Any, Tuple, Optional

# Standard 169 canonical Hold'em hands
RANKS = 'AKQJT98765432'
PAIRS = [r + r for r in RANKS]
SUITED = [RANKS[i] + RANKS[j] + 's' for i in range(len(RANKS)) for j in range(i + 1, len(RANKS))]
OFFSUIT = [RANKS[i] + RANKS[j] + 'o' for i in range(len(RANKS)) for j in range(i + 1, len(RANKS))]
ALL_HANDS = PAIRS + SUITED + OFFSUIT

# ---------------------------------------------------------------------------
# Pre-solved Baseline Range Grids (6-Max NLHE)
# ---------------------------------------------------------------------------

# Baseline 1: Zero Rake (High Stakes / MTT unraked baseline)
BASELINE_0_RAKE: Dict[str, Dict[str, float]] = {
    "UTG_OPEN": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 1.0, "99": 0.85, "88": 0.65, "77": 0.40, "66": 0.20,
        "AKs": 1.0, "AQs": 1.0, "AJs": 1.0, "ATs": 1.0, "A9s": 0.70, "A5s": 0.90, "A4s": 0.80, "A3s": 0.50,
        "KQs": 1.0, "KJs": 1.0, "KTs": 0.85, "QJs": 1.0, "QTs": 0.80, "JTs": 1.0, "T9s": 0.85, "98s": 0.75, "87s": 0.60, "76s": 0.50,
        "AKo": 1.0, "AQo": 0.90, "AJo": 0.50, "KQo": 0.50
    },
    "BTN_OPEN": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 1.0, "99": 1.0, "88": 1.0, "77": 1.0, "66": 1.0, "55": 1.0, "44": 1.0, "33": 0.90, "22": 0.80,
        "AKs": 1.0, "AQs": 1.0, "AJs": 1.0, "ATs": 1.0, "A9s": 1.0, "A8s": 1.0, "A7s": 1.0, "A6s": 1.0, "A5s": 1.0, "A4s": 1.0, "A3s": 1.0, "A2s": 1.0,
        "KQs": 1.0, "KJs": 1.0, "KTs": 1.0, "K9s": 1.0, "K8s": 1.0, "K7s": 0.90, "K6s": 0.85, "K5s": 0.80, "K4s": 0.70, "K3s": 0.60, "K2s": 0.50,
        "QJs": 1.0, "QTs": 1.0, "Q9s": 1.0, "Q8s": 1.0, "Q7s": 0.85, "Q6s": 0.75, "Q5s": 0.65, "Q4s": 0.55,
        "JTs": 1.0, "J9s": 1.0, "J8s": 1.0, "J7s": 0.85, "J6s": 0.60,
        "T9s": 1.0, "T8s": 1.0, "T7s": 0.80, "98s": 1.0, "97s": 0.90, "87s": 1.0, "86s": 0.85, "76s": 1.0, "75s": 0.70, "65s": 1.0, "54s": 0.95, "43s": 0.70,
        "AKo": 1.0, "AQo": 1.0, "AJo": 1.0, "ATo": 1.0, "A9o": 0.90, "A8o": 0.80, "A7o": 0.70, "A6o": 0.50, "A5o": 0.60, "A4o": 0.50, "A3o": 0.35, "A2o": 0.25,
        "KQo": 1.0, "KJo": 1.0, "KTo": 1.0, "K9o": 0.80, "K8o": 0.55, "K7o": 0.35,
        "QJo": 1.0, "QTo": 0.95, "Q9o": 0.65, "Q8o": 0.35,
        "JTo": 0.95, "J9o": 0.60, "T9o": 0.60, "98o": 0.50, "87o": 0.35
    },
    "BB_DEFENSE": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 1.0, "99": 1.0, "88": 1.0, "77": 1.0, "66": 1.0, "55": 1.0, "44": 1.0, "33": 1.0, "22": 0.95,
        "AKs": 1.0, "AQs": 1.0, "AJs": 1.0, "ATs": 1.0, "A9s": 1.0, "A8s": 1.0, "A7s": 1.0, "A6s": 1.0, "A5s": 1.0, "A4s": 1.0, "A3s": 1.0, "A2s": 1.0,
        "KQs": 1.0, "KJs": 1.0, "KTs": 1.0, "K9s": 1.0, "K8s": 1.0, "K7s": 1.0, "K6s": 1.0, "K5s": 0.95, "K4s": 0.90, "K3s": 0.80, "K2s": 0.70,
        "QJs": 1.0, "QTs": 1.0, "Q9s": 1.0, "Q8s": 1.0, "Q7s": 1.0, "Q6s": 0.95, "Q5s": 0.90, "Q4s": 0.80, "Q3s": 0.65, "Q2s": 0.55,
        "JTs": 1.0, "J9s": 1.0, "J8s": 1.0, "J7s": 1.0, "J6s": 0.90, "J5s": 0.75, "J4s": 0.60,
        "T9s": 1.0, "T8s": 1.0, "T7s": 1.0, "T6s": 0.85, "98s": 1.0, "97s": 1.0, "96s": 0.90, "87s": 1.0, "86s": 1.0, "85s": 0.75, "76s": 1.0, "75s": 0.95, "65s": 1.0, "54s": 1.0, "43s": 0.80, "32s": 0.60,
        "AKo": 1.0, "AQo": 1.0, "AJo": 1.0, "ATo": 1.0, "A9o": 1.0, "A8o": 1.0, "A7o": 0.90, "A6o": 0.75, "A5o": 0.85, "A4o": 0.75, "A3o": 0.65, "A2o": 0.55,
        "KQo": 1.0, "KJo": 1.0, "KTo": 1.0, "K9o": 0.95, "K8o": 0.85, "K7o": 0.65, "K6o": 0.50,
        "QJo": 1.0, "QTo": 1.0, "Q9o": 0.90, "Q8o": 0.70, "Q7o": 0.45,
        "JTo": 1.0, "J9o": 0.85, "J8o": 0.65, "T9o": 0.95, "T8o": 0.75, "98o": 0.85, "87o": 0.70, "76o": 0.60, "65o": 0.45
    },
    "SB_DEFENSE": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 1.0, "99": 0.95, "88": 0.85, "77": 0.70, "66": 0.50, "55": 0.35,
        "AKs": 1.0, "AQs": 1.0, "AJs": 1.0, "ATs": 1.0, "A9s": 0.80, "A8s": 0.60, "A5s": 0.95, "A4s": 0.85, "A3s": 0.70, "A2s": 0.60,
        "KQs": 1.0, "KJs": 0.95, "KTs": 0.85, "K9s": 0.60, "QJs": 0.95, "QTs": 0.85, "JTs": 0.90, "T9s": 0.85, "98s": 0.75, "87s": 0.65, "76s": 0.55,
        "AKo": 1.0, "AQo": 1.0, "AJo": 0.85, "KQo": 0.80
    }
}

# Baseline 2: Standard Rake (5% rake, 3.0bb cap baseline)
BASELINE_5_RAKE: Dict[str, Dict[str, float]] = {
    "UTG_OPEN": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 1.0, "99": 0.80, "88": 0.55, "77": 0.30,
        "AKs": 1.0, "AQs": 1.0, "AJs": 1.0, "ATs": 0.90, "A5s": 0.80, "A4s": 0.60,
        "KQs": 1.0, "KJs": 0.90, "KTs": 0.70, "QJs": 0.90, "JTs": 0.85, "T9s": 0.70, "98s": 0.55,
        "AKo": 1.0, "AQo": 0.80
    },
    "BTN_OPEN": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 1.0, "99": 1.0, "88": 1.0, "77": 1.0, "66": 1.0, "55": 0.90, "44": 0.80, "33": 0.65, "22": 0.50,
        "AKs": 1.0, "AQs": 1.0, "AJs": 1.0, "ATs": 1.0, "A9s": 1.0, "A8s": 1.0, "A7s": 0.90, "A6s": 0.80, "A5s": 1.0, "A4s": 0.90, "A3s": 0.80, "A2s": 0.70,
        "KQs": 1.0, "KJs": 1.0, "KTs": 1.0, "K9s": 0.90, "K8s": 0.80, "K7s": 0.65, "K6s": 0.55, "K5s": 0.50, "K4s": 0.40, "K3s": 0.30,
        "QJs": 1.0, "QTs": 1.0, "Q9s": 0.90, "Q8s": 0.75, "Q7s": 0.55, "Q6s": 0.40,
        "JTs": 1.0, "J9s": 0.90, "J8s": 0.75, "J7s": 0.50,
        "T9s": 1.0, "T8s": 0.85, "T7s": 0.50, "98s": 1.0, "97s": 0.70, "87s": 0.90, "86s": 0.60, "76s": 0.85, "65s": 0.80, "54s": 0.70, "43s": 0.40,
        "AKo": 1.0, "AQo": 1.0, "AJo": 1.0, "ATo": 0.90, "A9o": 0.65, "A8o": 0.45, "A7o": 0.35, "A5o": 0.35,
        "KQo": 1.0, "KJo": 0.90, "KTo": 0.75, "K9o": 0.40,
        "QJo": 0.90, "QTo": 0.65, "JTo": 0.65, "T9o": 0.35, "98o": 0.25
    },
    "BB_DEFENSE": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 1.0, "99": 1.0, "88": 1.0, "77": 1.0, "66": 1.0, "55": 0.90, "44": 0.80, "33": 0.70, "22": 0.60,
        "AKs": 1.0, "AQs": 1.0, "AJs": 1.0, "ATs": 1.0, "A9s": 1.0, "A8s": 1.0, "A7s": 0.95, "A6s": 0.85, "A5s": 1.0, "A4s": 0.95, "A3s": 0.85, "A2s": 0.80,
        "KQs": 1.0, "KJs": 1.0, "KTs": 1.0, "K9s": 0.95, "K8s": 0.90, "K7s": 0.80, "K6s": 0.70, "K5s": 0.65, "K4s": 0.55, "K3s": 0.45, "K2s": 0.35,
        "QJs": 1.0, "QTs": 1.0, "Q9s": 0.95, "Q8s": 0.85, "Q7s": 0.70, "Q6s": 0.60, "Q5s": 0.50, "Q4s": 0.35,
        "JTs": 1.0, "J9s": 0.95, "J8s": 0.85, "J7s": 0.70, "J6s": 0.50,
        "T9s": 1.0, "T8s": 0.95, "T7s": 0.70, "98s": 1.0, "97s": 0.80, "87s": 1.0, "86s": 0.75, "76s": 0.95, "75s": 0.65, "65s": 0.90, "54s": 0.80, "43s": 0.50,
        "AKo": 1.0, "AQo": 1.0, "AJo": 1.0, "ATo": 0.90, "A9o": 0.75, "A8o": 0.60, "A7o": 0.45, "A6o": 0.30, "A5o": 0.40, "A4o": 0.30,
        "KQo": 1.0, "KJo": 0.95, "KTo": 0.80, "K9o": 0.60, "K8o": 0.35,
        "QJo": 0.95, "QTo": 0.75, "Q9o": 0.45, "JTo": 0.75, "J9o": 0.45, "T9o": 0.55, "98o": 0.40, "87o": 0.30
    },
    "SB_DEFENSE": {
        "AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 1.0, "99": 0.85, "88": 0.70, "77": 0.50, "66": 0.30,
        "AKs": 1.0, "AQs": 1.0, "AJs": 1.0, "ATs": 0.90, "A9s": 0.60, "A5s": 0.80, "A4s": 0.70, "A3s": 0.50,
        "KQs": 1.0, "KJs": 0.85, "KTs": 0.70, "K9s": 0.40, "QJs": 0.85, "QTs": 0.70, "JTs": 0.80, "T9s": 0.70, "98s": 0.60, "87s": 0.50, "76s": 0.40,
        "AKo": 1.0, "AQo": 0.90, "AJo": 0.70, "KQo": 0.60
    }
}


class PreflopRangeService:
    """
    Interpolates preflop ranges according to custom rake percentage, rake cap, and stack depth.
    """

    @classmethod
    def get_morphed_preflop_range(
        cls,
        position_oop: str = "BB",
        position_ip: str = "BTN",
        stack_bb: float = 100.0,
        rake_pct: float = 5.0,
        rake_cap: float = 3.0
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Calculates morphed preflop ranges for both OOP and IP positions.
        
        Args:
            position_oop: Position of OOP player (e.g., 'BB', 'SB')
            position_ip: Position of IP player (e.g., 'BTN', 'CO', 'HJ', 'UTG')
            stack_bb: Stack depth in big blinds (e.g., 40.0, 100.0, 150.0)
            rake_pct: Rake percentage (0.0 to 15.0)
            rake_cap: Rake cap in big blinds (e.g., 3.0)

        Returns:
            Tuple of (oop_range, ip_range) mapping hand strings to weights [0.0, 1.0]
        """
        # Resolve table identifiers
        ip_spot = f"{position_ip.upper()}_OPEN" if f"{position_ip.upper()}_OPEN" in BASELINE_5_RAKE else "BTN_OPEN"
        oop_spot = f"{position_oop.upper()}_DEFENSE" if f"{position_oop.upper()}_DEFENSE" in BASELINE_5_RAKE else "BB_DEFENSE"

        oop_range = cls._interpolate_range(oop_spot, stack_bb, rake_pct, rake_cap, is_defense=True)
        ip_range = cls._interpolate_range(ip_spot, stack_bb, rake_pct, rake_cap, is_defense=False)

        return oop_range, ip_range

    @classmethod
    def _interpolate_range(
        cls,
        spot_key: str,
        stack_bb: float,
        rake_pct: float,
        rake_cap: float,
        is_defense: bool = False
    ) -> Dict[str, float]:
        """
        Performs bilinear interpolation across rake (0% vs 5%) and stack depth (40bb vs 100bb vs 150bb).
        """
        base_0 = BASELINE_0_RAKE.get(spot_key, BASELINE_0_RAKE["BTN_OPEN"])
        base_5 = BASELINE_5_RAKE.get(spot_key, BASELINE_5_RAKE["BTN_OPEN"])

        # Rake weight: 0% -> 0.0, 5% -> 1.0, 10% -> 2.0
        # Incorporate cap scaling relative to standard 3bb cap
        cap_factor = min(max(rake_cap / 3.0, 0.2), 2.5)
        rake_alpha = (rake_pct / 5.0) * cap_factor

        # Stack depth multiplier
        # 100bb is baseline 1.0; 150bb boosts suited connectors; 40bb penalizes speculative hands
        stack_factor = min(max(stack_bb / 100.0, 0.4), 2.0)

        morphed: Dict[str, float] = {}

        for hand in ALL_HANDS:
            w0 = base_0.get(hand, 0.0)
            w5 = base_5.get(hand, 0.0)

            # If hand not in either baseline, skip
            if w0 <= 0.0 and w5 <= 0.0:
                continue

            # Premium hands remain 100% playable regardless of rake
            if hand in ["AA", "KK", "QQ", "AKs", "AKo"]:
                morphed[hand] = 1.0
                continue

            is_suited = hand.endswith('s')
            is_pair = len(hand) == 2
            is_offsuit = hand.endswith('o')

            # 1. Base rake interpolation
            if rake_alpha <= 1.0:
                # Interpolate between 0% and 5% baseline
                w = w0 + rake_alpha * (w5 - w0)
            else:
                # Extrapolate beyond 5% rake (e.g. 7-10% microstakes)
                penalty_slope = (w0 - w5) if w0 > w5 else 0.15
                w = w5 - (rake_alpha - 1.0) * penalty_slope

            # 2. Hand category elasticity
            if is_defense and is_offsuit:
                # Offsuit calling hands suffer hardest under high rake (defense flatting penalty)
                if rake_alpha > 1.0:
                    w *= (1.0 - (rake_alpha - 1.0) * 0.35)
            elif is_suited and not is_pair:
                # Suited hands scale with stack depth (implied odds)
                if stack_factor > 1.0:
                    w = min(1.0, w * (1.0 + (stack_factor - 1.0) * 0.15))
                else:
                    w *= (0.8 + 0.2 * stack_factor)
            elif is_pair and hand not in ["AA", "KK", "QQ", "JJ"]:
                # Small pairs scale with stack depth (set mining value)
                if stack_factor < 0.8:
                    w *= 0.65  # Short stack set mining is -EV

            w = round(max(0.0, min(1.0, w)), 3)
            if w >= 0.02:
                morphed[hand] = w

        return morphed

    # Backward compatibility alias
    @classmethod
    def get_interpolated_range(
        cls,
        position_spot: str,
        rake_percent: float = 5.0,
        rake_cap: float = 3.0,
        baseline_spot: str = "BTN_OPEN"
    ) -> Dict[str, float]:
        """Backward compatible signature."""
        spot = position_spot if position_spot in BASELINE_5_RAKE else baseline_spot
        is_def = "DEFENSE" in spot or "BB" in spot
        return cls._interpolate_range(spot, stack_bb=100.0, rake_pct=rake_percent, rake_cap=rake_cap, is_defense=is_def)

    @classmethod
    def get_spot_ranges(
        cls,
        spot: str = "BTN_vs_BB_SRP",
        rake_percent: float = 5.0,
        rake_cap: float = 3.0
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Backward compatible signature."""
        if "BTN_vs_BB" in spot or "SRP" in spot:
            return cls.get_morphed_preflop_range("BB", "BTN", 100.0, rake_percent, rake_cap)
        elif "SB_vs_BB" in spot:
            return cls.get_morphed_preflop_range("SB", "BB", 100.0, rake_percent, rake_cap)
        else:
            return cls.get_morphed_preflop_range("BB", "BTN", 100.0, rake_percent, rake_cap)
