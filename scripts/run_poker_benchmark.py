#!/usr/bin/env python3
"""
scripts/run_poker_benchmark.py

Standalone CLI Benchmark Runner for 6-max GTO Depth-Limited Solver:
- Loads canonical flops from backend/tests/solver/fixtures/canonical_flops.json.
- Runs batch solves against EngineBridge.
- Prints a formatted summary table: Board, Texture, Time (ms), Exploitability, Root EVs, Action Breakdown, Status.
- Emits exit code 0 on success, or 1 if any board exceeds 2000ms latency or fails exploitability threshold.
"""

import os
import sys
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, Any, List

# Setup environment & python path
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
VENV_PYTHON = BACKEND_DIR / "venv" / "bin" / "python3"

# Seamless auto-detection of venv python if running on host without active venv
if VENV_PYTHON.exists() and sys.executable != str(VENV_PYTHON):
    try:
        import django
    except ImportError:
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")

import django
django.setup()

from solutions.services.range_service import PreflopRangeService
from solutions.services.engine_bridge import engine_bridge

FIXTURES_PATH = BACKEND_DIR / "tests" / "solver" / "fixtures" / "canonical_flops.json"
LATENCY_BUDGET_MS = 2000.0
MAX_EXPLOITABILITY = 0.20


def load_fixtures() -> List[Dict[str, Any]]:
    if not FIXTURES_PATH.exists():
        raise FileNotFoundError(f"Fixture file not found at {FIXTURES_PATH}")
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


async def run_benchmark():
    fixtures = load_fixtures()
    print("=" * 105)
    print(" 🚀 6-MAX GTO DEPTH-LIMITED SOLVER BENCHMARK HARNESS (SUB-2-SECOND ENGINE)")
    print("=" * 105)
    print(f"Target Latency Budget: < {LATENCY_BUDGET_MS:.0f} ms | Max Exploitability: <= {MAX_EXPLOITABILITY:.2f}%")
    print(f"Loaded {len(fixtures)} canonical benchmark scenarios from fixtures/canonical_flops.json\n")

    results = []
    has_failure = False

    header = (
        f"{'#':<3} | {'Board':<12} | {'Texture':<14} | {'Time (ms)':<10} | "
        f"{'dEV (%)':<9} | {'OOP EV':<8} | {'IP EV':<8} | {'F / C / R (%)':<16} | {'Status':<6}"
    )
    print(header)
    print("-" * 105)

    for idx, scenario in enumerate(fixtures, start=1):
        board = scenario["board"]
        board_str = " ".join(board)
        texture = scenario.get("texture", "Unknown")
        pot = float(scenario.get("pot", 6.5))
        stack = float(scenario.get("effective_stack", 97.0))
        rake_pct = float(scenario.get("rake_percent", 5.0))
        rake_cap = float(scenario.get("rake_cap", 3.0))

        oop_range, ip_range = PreflopRangeService.get_morphed_preflop_range(
            position_oop=scenario.get("position_oop", "BB"),
            position_ip=scenario.get("position_ip", "BTN"),
            stack_bb=stack,
            rake_pct=rake_pct,
            rake_cap=rake_cap,
        )

        payload = {
            "board": board,
            "oop_range": oop_range,
            "ip_range": ip_range,
            "pot": pot,
            "effective_stack": stack,
            "rake_percent": rake_pct,
            "rake_cap": rake_cap,
            "max_bets_per_node": 1,
            "max_iterations": 200,
        }

        t_start = time.perf_counter()
        try:
            solve_res = await engine_bridge.solve(payload)
            t_end = time.perf_counter()
            roundtrip_ms = (t_end - t_start) * 1000.0

            d_ev = float(solve_res.get("exploitability", 0.0))
            oop_ev = float(solve_res.get("oop_ev", 0.0))
            ip_ev = float(solve_res.get("ip_ev", 0.0))
            overall = solve_res.get("overall_frequencies", {"fold": 0.0, "call": 0.0, "raise": 0.0})

            f_pct = overall.get("fold", 0.0) * 100
            c_pct = overall.get("call", 0.0) * 100
            r_pct = overall.get("raise", 0.0) * 100
            fcr_str = f"{f_pct:.0f}% / {c_pct:.0f}% / {r_pct:.0f}%"

            # Failure conditions
            is_pass = (roundtrip_ms <= LATENCY_BUDGET_MS) and (d_ev <= MAX_EXPLOITABILITY)
            if not is_pass:
                has_failure = True
            status_str = "✅ PASS" if is_pass else "❌ FAIL"

            row = (
                f"{idx:<3} | {board_str:<12} | {texture:<14} | {roundtrip_ms:<10.1f} | "
                f"{d_ev:<9.4f} | {oop_ev:<8.2f} | {ip_ev:<8.2f} | {fcr_str:<16} | {status_str:<6}"
            )
            print(row)

            results.append({
                "scenario": scenario["id"],
                "board": board_str,
                "time_ms": roundtrip_ms,
                "exploitability": d_ev,
                "oop_ev": oop_ev,
                "ip_ev": ip_ev,
                "passed": is_pass,
            })

        except Exception as e:
            has_failure = True
            print(f"{idx:<3} | {board_str:<12} | {texture:<14} | ERROR: {str(e)[:45]}")
            results.append({
                "scenario": scenario["id"],
                "board": board_str,
                "time_ms": 0,
                "exploitability": 0,
                "passed": False,
            })

    print("-" * 105)

    # Summary Statistics
    total_runs = len(results)
    passed_runs = sum(1 for r in results if r.get("passed", False))
    avg_latency = sum(r["time_ms"] for r in results) / total_runs if total_runs else 0
    max_latency = max(r["time_ms"] for r in results) if total_runs else 0
    avg_dev = sum(r["exploitability"] for r in results) / total_runs if total_runs else 0

    print(f"\n📊 Benchmark Execution Summary:")
    print(f"   • Total Scenarios Solved : {total_runs}")
    print(f"   • Passing Scenarios      : {passed_runs} / {total_runs} ({(passed_runs/total_runs)*100:.1f}%)")
    print(f"   • Average Latency        : {avg_latency:.2f} ms")
    print(f"   • Peak Latency           : {max_latency:.2f} ms (Budget: {LATENCY_BUDGET_MS:.0f} ms)")
    print(f"   • Average Exploitability : {avg_dev:.4f}% dEV")

    if has_failure:
        print("\n❌ BENCHMARK FAILED: One or more scenarios exceeded latency or exploitability limits.")
        sys.exit(1)
    else:
        print("\n✅ BENCHMARK PASSED: All canonical scenarios met GTO mathematical & sub-2-second latency criteria.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
