#!/usr/bin/env python3
"""
scripts/data_gen/run_parallel_leaf_gen.py

Orchestrates multi-core parallel generation across 6 local solver daemon instances
to solve all 1,755 canonical flops and extract ground-truth per-class leaf counterfactual EV vectors.
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUST_DAEMON = REPO_ROOT / "solver_daemon" / "target" / "release" / "solver_daemon"
VENV_PYTHON = REPO_ROOT / "backend" / "venv" / "bin" / "python3"
GEN_SCRIPT = REPO_ROOT / "scripts" / "data_gen" / "generate_real_cfr_dataset.py"

PORTS = [9971, 9972, 9973, 9974, 9975, 9976]


def main():
    if not RUST_DAEMON.exists():
        print(f"Error: {RUST_DAEMON} does not exist. Run cargo build --release first.")
        sys.exit(1)

    print("=" * 80)
    print(" 🚀 PARALLEL REAL-CFR+ LEAF VALUE DATASET GENERATOR")
    print("=" * 80)
    print(f"Spawning {len(PORTS)} native solver daemon workers on ports {PORTS}...")

    daemons = []
    env_base = dict(os.environ, PATH="/usr/local/bin:/usr/bin:/bin")
    for port in PORTS:
        env = dict(env_base, PORT=str(port))
        p = subprocess.Popen(
            [str(RUST_DAEMON)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        daemons.append(p)

    time.sleep(1.0)
    print("✅ All 6 worker daemons successfully started.")

    try:
        ports_str = ",".join(str(p) for p in PORTS)
        cmd = [
            str(VENV_PYTHON),
            "-u",
            str(GEN_SCRIPT),
            "--ports", ports_str,
            "--out", str(REPO_ROOT / "datasets" / "generated" / "nl500_100bb_real_cfr"),
        ]
        print(f"Executing: {' '.join(cmd)}")
        res = subprocess.run(cmd, text=True)
        if res.returncode != 0:
            print(f"❌ Error during generation, returncode: {res.returncode}")
            sys.exit(res.returncode)
    finally:
        print("\nStopping worker daemons...")
        for p in daemons:
            p.terminate()
            try:
                p.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                p.kill()
        print("✅ Cleaned up all worker daemons.")


if __name__ == "__main__":
    main()
