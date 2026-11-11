"""
backend/tests/solver/test_canonical_boards.py

Canonical Board Strategy Sanity Checks for 6-max No-Limit Hold'em:
1. High Dry Texture (As 8d 3c):
   - BTN c-bet frequency > 65% (range advantage c-betting high frequency).
   - BB check frequency > 95% (OOP standard check to the raiser).
2. Dynamic / Wet Connected Texture (9s 8h 7d):
   - BTN checks back more frequently (> 40%) due to OOP equity retainment.
3. Paired Texture (8s 8h 2c):
   - Trips and full house combinations never fold (fold == 0.0) to standard c-bets.
"""

import pytest
from solutions.services.range_service import PreflopRangeService
from solutions.services.engine_bridge import engine_bridge


@pytest.mark.asyncio
async def test_high_dry_texture_cbet_frequency():
    """
    On As 8d 3c (Dry Ace-High):
    - Assert BTN c-bet frequency > 65%
    - Assert BB check frequency > 95%
    """
    oop_range, ip_range = PreflopRangeService.get_morphed_preflop_range(
        position_oop="BB",
        position_ip="BTN",
        stack_bb=100.0,
        rake_pct=5.0,
        rake_cap=3.0,
    )

    payload = {
        "board": ["As", "8d", "3c"],
        "oop_range": oop_range,
        "ip_range": ip_range,
        "pot": 6.5,
        "effective_stack": 97.0,
        "rake_percent": 5.0,
        "rake_cap": 3.0,
        "max_bets_per_node": 1,
    }

    result = await engine_bridge.solve(payload)

    btn_cbet = result.get("btn_cbet_frequency", 0.0)
    bb_check = result.get("bb_check_frequency", 0.0)

    assert btn_cbet > 0.65, (
        f"High dry texture As 8d 3c should have BTN c-bet frequency > 65%, got {btn_cbet * 100:.1f}%"
    )
    assert bb_check > 0.95, (
        f"High dry texture As 8d 3c should have BB check frequency > 95%, got {bb_check * 100:.1f}%"
    )


@pytest.mark.asyncio
async def test_dynamic_wet_texture_check_back_frequency():
    """
    On 9s 8h 7d (Dynamic Wet Connected):
    - Assert BTN checks back more frequently (> 40%) compared to dry textures
    """
    oop_range, ip_range = PreflopRangeService.get_morphed_preflop_range(
        position_oop="BB",
        position_ip="BTN",
        stack_bb=100.0,
        rake_pct=5.0,
        rake_cap=3.0,
    )

    payload = {
        "board": ["9s", "8h", "7d"],
        "oop_range": oop_range,
        "ip_range": ip_range,
        "pot": 6.5,
        "effective_stack": 97.0,
        "rake_percent": 5.0,
        "rake_cap": 3.0,
        "max_bets_per_node": 1,
    }

    result = await engine_bridge.solve(payload)

    btn_check = result.get("btn_check_frequency", 0.0)
    assert btn_check > 0.40, (
        f"Dynamic wet texture 9s 8h 7d should have BTN check back frequency > 40%, got {btn_check * 100:.1f}%"
    )


@pytest.mark.asyncio
async def test_paired_texture_trips_never_fold():
    """
    On 8s 8h 2c (Paired Texture):
    - Assert that trips and full house combos (hands with '8' or '22') never fold (fold == 0.0)
    """
    oop_range, ip_range = PreflopRangeService.get_morphed_preflop_range(
        position_oop="BB",
        position_ip="BTN",
        stack_bb=100.0,
        rake_pct=5.0,
        rake_cap=3.0,
    )

    payload = {
        "board": ["8s", "8h", "2c"],
        "oop_range": oop_range,
        "ip_range": ip_range,
        "pot": 6.5,
        "effective_stack": 97.0,
        "rake_percent": 5.0,
        "rake_cap": 3.0,
        "max_bets_per_node": 1,
    }

    result = await engine_bridge.solve(payload)
    strategy = result.get("strategy", {})

    assert len(strategy) > 0, "Strategy matrix should not be empty"

    trips_or_boat_hands = [h for h in strategy.keys() if "8" in h or h == "22"]
    assert len(trips_or_boat_hands) > 0, "Must contain trips/fullhouse combos in strategy"

    for hand in trips_or_boat_hands:
        fold_freq = strategy[hand]["fold"]
        assert fold_freq == 0.0, (
            f"Trips / Full house hand {hand} on paired board 8s 8h 2c should never fold, got fold={fold_freq}"
        )
