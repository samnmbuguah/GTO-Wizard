"""
backend/tests/solver/test_latency.py

Performance & Latency Benchmark Tests for the 6-max GTO Solver Pipeline:
1. Executes 10 consecutive postflop solves across diverse boards.
2. Tracks engine_compute_ms, ipc_overhead_ms, and total_roundtrip_ms.
3. Asserts total_roundtrip_ms < 2000 ms strictly for every request.
4. Asserts exploitability <= 0.20 (% of pot).
"""

import json
import time
from pathlib import Path
import pytest
from typing import List, Dict, Any

from solutions.services.range_service import PreflopRangeService
from solutions.services.engine_bridge import engine_bridge


FIXTURES_PATH = Path(__file__).parent / "fixtures" / "canonical_flops.json"


def load_canonical_flops() -> List[Dict[str, Any]]:
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.asyncio
async def test_sub_two_second_latency_and_exploitability():
    """
    Fire 10 consecutive postflop solve requests across diverse canonical boards.
    Measure engine_compute_ms, ipc_overhead_ms, and total_roundtrip_ms.
    Strictly assert total_roundtrip_ms < 2000 ms and exploitability <= 0.20.
    """
    canonical_flops = load_canonical_flops()
    assert len(canonical_flops) > 0, "Canonical flops fixture must not be empty"

    # Generate 10 test board scenarios cycling through canonical flops
    test_scenarios = (canonical_flops * 2)[:10]

    benchmark_records = []

    for idx, scenario in enumerate(test_scenarios, start=1):
        board = scenario["board"]
        pot = float(scenario.get("pot", 6.5))
        effective_stack = float(scenario.get("effective_stack", 97.0))
        rake_pct = float(scenario.get("rake_percent", 5.0))
        rake_cap = float(scenario.get("rake_cap", 3.0))

        oop_range, ip_range = PreflopRangeService.get_morphed_preflop_range(
            position_oop=scenario.get("position_oop", "BB"),
            position_ip=scenario.get("position_ip", "BTN"),
            stack_bb=effective_stack,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
        )

        payload = {
            "board": board,
            "oop_range": oop_range,
            "ip_range": ip_range,
            "pot": pot,
            "effective_stack": effective_stack,
            "rake_percent": rake_pct,
            "rake_cap": rake_cap,
            "max_bets_per_node": 1,
            "max_iterations": 200,
        }

        t_start = time.perf_counter()
        result = await engine_bridge.solve(payload)
        t_end = time.perf_counter()

        total_roundtrip_ms = round((t_end - t_start) * 1000.0, 2)
        engine_compute_ms = float(result.get("solve_time_ms", 0.0))
        ipc_overhead_ms = round(max(0.0, total_roundtrip_ms - engine_compute_ms), 2)
        exploitability = float(result.get("exploitability", 1.0))

        benchmark_records.append({
            "run": idx,
            "board": " ".join(board),
            "engine_compute_ms": engine_compute_ms,
            "ipc_overhead_ms": ipc_overhead_ms,
            "total_roundtrip_ms": total_roundtrip_ms,
            "exploitability": exploitability,
        })

        # Strict Assertions
        assert total_roundtrip_ms < 2000.0, (
            f"Run {idx} ({' '.join(board)}) exceeded 2.0s latency budget: {total_roundtrip_ms}ms"
        )
        assert exploitability <= 0.20, (
            f"Run {idx} ({' '.join(board)}) exceeded exploitability threshold: {exploitability} > 0.20"
        )

    # Print summary metrics for verification
    avg_total = sum(r["total_roundtrip_ms"] for r in benchmark_records) / len(benchmark_records)
    avg_engine = sum(r["engine_compute_ms"] for r in benchmark_records) / len(benchmark_records)
    avg_ipc = sum(r["ipc_overhead_ms"] for r in benchmark_records) / len(benchmark_records)
    max_total = max(r["total_roundtrip_ms"] for r in benchmark_records)

    print(f"\n--- Latency Benchmark Summary (10 Runs) ---")
    print(f"Avg Roundtrip: {avg_total:.2f}ms | Avg Engine: {avg_engine:.2f}ms | Avg IPC: {avg_ipc:.2f}ms")
    print(f"Max Roundtrip: {max_total:.2f}ms (Budget: 2000ms)")
