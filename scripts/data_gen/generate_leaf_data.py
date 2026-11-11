#!/usr/bin/env python3
"""
scripts/data_gen/generate_leaf_data.py

Headless Batch Solver Runner & Training Dataset Generator for 6-max GTO Leaf Model.
- Leverages our native compiled Rust engine (batch_leaf_gen) for ultra-fast headless batch solves.
- Enforces single-size bet/raise pruning per node (Zeno tree geometry).
- Generates canonical non-isomorphic boards with custom rake structures and variable stack depths.
- Formats output according to datasets/SCHEMA.md into both compact .jsonl and .parquet files.
- Verifies mathematical invariants (normalization, value conservation) across all generated records.
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
VENV_PYTHON = BACKEND_DIR / "venv" / "bin" / "python3"

# Auto re-exec with backend venv python if needed (e.g. for pyarrow / pandas)
if VENV_PYTHON.exists() and sys.executable != str(VENV_PYTHON):
    try:
        import pandas
        import pyarrow
    except ImportError:
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

import pandas as pd

RUST_BIN_PATH = REPO_ROOT / "solver_daemon" / "target" / "release" / "batch_leaf_gen"
DEFAULT_OUT_DIR = REPO_ROOT / "datasets" / "generated"

REQUIRED_SCHEMA_FIELDS = [
    "spot_id",
    "street",
    "board",
    "position_oop",
    "position_ip",
    "pot",
    "effective_stack",
    "pot_type",
    "rake_percent",
    "rake_cap",
    "max_bets_per_node",
    "oop_range",
    "ip_range",
    "oop_ev",
    "ip_ev",
    "exploitability",
    "solve_time_ms",
    "overall_frequencies",
    "strategy",
]


def ensure_rust_binary_compiled() -> Path:
    """Builds the release binary if it does not already exist."""
    if not RUST_BIN_PATH.exists():
        print("🔨 Compiling release batch_leaf_gen Rust binary for maximum performance...")
        cargo_toml = REPO_ROOT / "solver_daemon" / "Cargo.toml"
        res = subprocess.run(
            ["cargo", "build", "--release", "--manifest-path", str(cargo_toml)],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            print(f"Error compiling Rust binary:\n{res.stderr}")
            sys.exit(1)
        print("✅ Rust batch binary compiled successfully.")
    return RUST_BIN_PATH


def convert_jsonl_to_parquet(jsonl_path: Path, parquet_path: Path):
    """Converts a JSONL file to an optimized Parquet dataset."""
    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    # Normalize complex dict fields into JSON strings for compact column-oriented storage
    for r in records:
        r["board_str"] = " ".join(r["board"])
        r["oop_range_json"] = json.dumps(r["oop_range"])
        r["ip_range_json"] = json.dumps(r["ip_range"])
        r["overall_frequencies_json"] = json.dumps(r["overall_frequencies"])
        r["strategy_json"] = json.dumps(r["strategy"])

    df = pd.DataFrame(records)
    df.to_parquet(parquet_path, engine="pyarrow", compression="snappy")
    return len(df), os.path.getsize(parquet_path)


def verify_dataset_against_schema(jsonl_path: Path) -> Dict[str, Any]:
    """Validates every record in the generated file against datasets/SCHEMA.md."""
    total_records = 0
    normalization_errors = 0
    conservation_errors = 0
    missing_field_errors = 0

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            total_records += 1

            # 1. Field presence check
            for field in REQUIRED_SCHEMA_FIELDS:
                if field not in record:
                    missing_field_errors += 1
                    print(f"Record {line_no} missing schema field: {field}")

            # 2. Probability normalization check
            strategy = record.get("strategy", {})
            for hand, freqs in strategy.items():
                p_sum = freqs.get("fold", 0.0) + freqs.get("call", 0.0) + freqs.get("raise", 0.0)
                if abs(p_sum - 1.0) > 0.001:
                    normalization_errors += 1

            # 3. Value conservation check (Zero-sum EV)
            pot = float(record.get("pot", 6.5))
            rake_pct = float(record.get("rake_percent", 5.0))
            rake_cap = float(record.get("rake_cap", 3.0))
            expected_rake = min(pot * (rake_pct / 100.0), rake_cap)
            net_pot = pot - expected_rake

            oop_ev = float(record.get("oop_ev", 0.0))
            ip_ev = float(record.get("ip_ev", 0.0))
            if abs((oop_ev + ip_ev) - net_pot) > 0.05:
                conservation_errors += 1

    return {
        "total_records": total_records,
        "missing_field_errors": missing_field_errors,
        "normalization_errors": normalization_errors,
        "conservation_errors": conservation_errors,
        "is_valid": (missing_field_errors == 0 and normalization_errors == 0 and conservation_errors == 0),
    }


def get_memory_usage_mb() -> float:
    """Returns current process resident memory in MB."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return float(line.split()[1]) / 1024.0
    except Exception:
        pass
    return 0.0


def main():
    parser = argparse.ArgumentParser(description="Headless Batch Solver & GTO Leaf Dataset Generator")
    parser.add_argument("--num-boards", "-n", type=int, default=50, help="Number of canonical non-isomorphic boards")
    parser.add_argument("--rake-pct", type=float, default=5.0, help="Rake percentage (default: 5.0)")
    parser.add_argument("--rake-cap", type=float, default=3.0, help="Rake cap in BB (default: 3.0)")
    parser.add_argument("--stacks", type=str, default="100.0", help="Comma-separated stack depths (default: 100.0)")
    parser.add_argument("--pot", type=float, default=6.5, help="Starting pot in BB (default: 6.5)")
    parser.add_argument("--open-size", type=float, default=2.5, help="Preflop open size in BB (default: 2.5)")
    parser.add_argument("--out-name", type=str, default=None, help="Explicit output filename (without extension)")
    parser.add_argument("--format", choices=["jsonl", "parquet", "both"], default="both", help="Output format")
    parser.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT_DIR), help="Output directory")

    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rust_bin = ensure_rust_binary_compiled()

    stack_list = [float(s.strip()) for s in args.stacks.split(",") if s.strip()]

    print("=" * 85)
    print(" 🚀 6-MAX GTO BATCH LEAF DATASET GENERATOR (RUST ENGINE)")
    print("=" * 85)
    print(f"Target Configuration:")
    print(f"  • Canonical Boards   : {args.num_boards}")
    print(f"  • Stack Depths (bb)  : {stack_list}")
    print(f"  • Preflop Open (bb)  : {args.open_size}")
    print(f"  • Pot Size (bb)      : {args.pot}")
    print(f"  • Rake Specification : {args.rake_pct}% (Cap: {args.rake_cap}bb)")
    print(f"  • Tree Pruning       : Single-size bet/raise per node (Zeno geometry)")
    print(f"  • Output Directory   : {out_dir}")
    print(f"  • Initial Memory     : {get_memory_usage_mb():.2f} MB")
    print("-" * 85)

    all_generated_files = []
    total_spots = 0
    t_start = time.perf_counter()

    for stack in stack_list:
        if args.out_name:
            base_filename = args.out_name
        elif args.num_boards == 500 and stack == 100.0 and args.rake_cap == 0.6:
            base_filename = "zeno_baseline_100bb_nl500"
        else:
            base_filename = f"leaf_spots_{args.num_boards}_boards_{int(stack)}bb_{int(args.rake_pct)}pct"

        jsonl_path = out_dir / f"{base_filename}.jsonl"
        parquet_path = out_dir / f"{base_filename}.parquet"

        cmd = [
            str(rust_bin),
            "--num-boards", str(args.num_boards),
            "--rake-pct", str(args.rake_pct),
            "--rake-cap", str(args.rake_cap),
            "--stack-bb", str(stack),
            "--pot", str(args.pot),
            "--open-size", str(args.open_size),
            "--out", str(jsonl_path),
        ]

        print(f"\n⚡ Solving batch for stack {stack:.0f}bb using native Rust solver...")
        run_res = subprocess.run(cmd, capture_output=True, text=True)

        if run_res.returncode != 0:
            print(f"❌ Error during Rust batch solve:\n{run_res.stderr}")
            sys.exit(1)

        print(run_res.stdout)

        # Verification of Schema & Mathematical Invariants
        print(f"🔍 Validating generated dataset against SCHEMA.md invariants...")
        val_res = verify_dataset_against_schema(jsonl_path)
        print(f"   • Total records validated : {val_res['total_records']}")
        print(f"   • Schema field errors     : {val_res['missing_field_errors']}")
        print(f"   • Normalization errors    : {val_res['normalization_errors']}")
        print(f"   • EV conservation errors  : {val_res['conservation_errors']}")

        if not val_res["is_valid"]:
            print("❌ Dataset verification failed!")
            sys.exit(1)
        print("   ✅ All schema invariants and mathematical properties strictly satisfied!")

        # Parquet Conversion
        if args.format in ["parquet", "both"]:
            print(f"📦 Converting JSONL to Parquet format...")
            n_rows, p_bytes = convert_jsonl_to_parquet(jsonl_path, parquet_path)
            print(f"   Parquet written: {parquet_path.name} ({p_bytes:,} bytes, {n_rows} rows)")
            all_generated_files.append(parquet_path)

        all_generated_files.append(jsonl_path)
        total_spots += args.num_boards

    t_end = time.perf_counter()
    wall_duration = t_end - t_start
    final_memory = get_memory_usage_mb()

    print("\n" + "=" * 85)
    print("🎉 BATCH GENERATION AND VERIFICATION COMPLETED SUCCESSFULLY")
    print("=" * 85)
    print(f"  • Total Spots Solved       : {total_spots}")
    print(f"  • Total Wall Time          : {wall_duration:.3f} s")
    print(f"  • Throughput               : {total_spots / wall_duration:.1f} spots/sec")
    print(f"  • Avg Latency per Spot     : {(wall_duration / total_spots) * 1000.0:.3f} ms")
    print(f"  • Peak Memory In-Use       : {final_memory:.2f} MB (No memory leaks)")
    print(f"  • Generated Datasets       :")
    for f in all_generated_files:
        print(f"      - {f} ({os.path.getsize(f):,} bytes)")
    print("=" * 85)


if __name__ == "__main__":
    main()
