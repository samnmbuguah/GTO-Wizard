"""
backend/tests/solver/test_math_invariants.py

Mathematical Invariant Tests for the 6-max GTO Depth-Limited Solver Pipeline:
1. Probability Distribution Normalization: sum(action_frequencies) == 1.0 for every hand combo.
2. Conservation of Value (Root EV): Zero-sum EV conservation (OOP_EV + IP_EV == Pot - Expected_Rake).
3. Monotonic Exploitability Convergence: dEV monotonically decreases as iteration count increases.
"""

import math
import pytest
import asyncio
from typing import Dict, Any

from solutions.services.range_service import PreflopRangeService
from solutions.services.engine_bridge import engine_bridge


@pytest.mark.asyncio
async def test_probability_distribution_normalization():
    """
    Assert for every 13x13 hand combo in the returned strategy matrix:
    abs(fold + call + raise - 1.0) < 0.001
    """
    oop_range, ip_range = PreflopRangeService.get_morphed_preflop_range(
        position_oop="BB",
        position_ip="BTN",
        stack_bb=100.0,
        rake_pct=5.0,
        rake_cap=3.0
    )

    payload = {
        "board": ["Ah", "Kd", "2c"],
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

    for hand, freqs in strategy.items():
        total_prob = freqs["fold"] + freqs["call"] + freqs["raise"]
        assert abs(total_prob - 1.0) < 0.001, (
            f"Hand {hand} probability distribution violates normalization: "
            f"fold={freqs['fold']}, call={freqs['call']}, raise={freqs['raise']}, sum={total_prob}"
        )


@pytest.mark.asyncio
async def test_conservation_of_value_root_ev():
    """
    Zero-sum EV Conservation Property:
    For a pot of 6.5bb with 5% rake (cap 3.0bb):
    assert abs((oop_ev + ip_ev) - (pot - expected_rake)) < 0.05
    """
    pot = 6.5
    rake_pct = 5.0
    rake_cap = 3.0
    expected_rake = min(pot * (rake_pct / 100.0), rake_cap)  # 0.325bb
    net_pot = pot - expected_rake                           # 6.175bb

    oop_range, ip_range = PreflopRangeService.get_morphed_preflop_range(
        position_oop="BB",
        position_ip="BTN",
        stack_bb=97.0,
        rake_pct=rake_pct,
        rake_cap=rake_cap
    )

    payload = {
        "board": ["Qs", "Jd", "8c"],
        "oop_range": oop_range,
        "ip_range": ip_range,
        "pot": pot,
        "effective_stack": 97.0,
        "rake_percent": rake_pct,
        "rake_cap": rake_cap,
        "max_bets_per_node": 1,
    }

    result = await engine_bridge.solve(payload)

    oop_ev = result.get("oop_ev")
    ip_ev = result.get("ip_ev")

    assert oop_ev is not None, "Solver response must include oop_ev"
    assert ip_ev is not None, "Solver response must include ip_ev"

    total_ev = oop_ev + ip_ev
    assert abs(total_ev - net_pot) < 0.05, (
        f"Value conservation violated: oop_ev ({oop_ev}) + ip_ev ({ip_ev}) = {total_ev}, "
        f"expected net_pot = {net_pot} (pot={pot}, rake={expected_rake})"
    )


@pytest.mark.asyncio
async def test_monotonic_exploitability_convergence():
    """
    Assert that exploitability monotonically decreases as iteration count increases:
    T = 100, 200, 500, 1000 => dEV[i+1] <= dEV[i]
    """
    oop_range, ip_range = PreflopRangeService.get_morphed_preflop_range(
        position_oop="BB",
        position_ip="BTN",
        stack_bb=100.0,
        rake_pct=5.0,
        rake_cap=3.0
    )

    iterations_list = [100, 200, 500, 1000]
    dev_results = []

    for iters in iterations_list:
        payload = {
            "board": ["Kh", "7d", "2c"],
            "oop_range": oop_range,
            "ip_range": ip_range,
            "pot": 6.5,
            "effective_stack": 97.0,
            "rake_percent": 5.0,
            "rake_cap": 3.0,
            "max_bets_per_node": 1,
            "max_iterations": iters,
        }
        res = await engine_bridge.solve(payload)
        dev = res.get("exploitability")
        assert dev is not None, f"Response at {iters} iterations missing exploitability"
        dev_results.append((iters, dev))

    # Verify monotonic decrease
    for i in range(len(dev_results) - 1):
        t_curr, dev_curr = dev_results[i]
        t_next, dev_next = dev_results[i + 1]
        assert dev_next <= dev_curr, (
            f"Exploitability failed monotonic decrease between {t_curr} iters (dEV={dev_curr}) "
            f"and {t_next} iters (dEV={dev_next})"
        )
