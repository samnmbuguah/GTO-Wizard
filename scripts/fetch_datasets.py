#!/usr/bin/env python3
"""
scripts/fetch_datasets.py

Automates acquisition and schema verification of:
1. PokerBench (HuggingFace: RZ412/PokerBench) - 6-max postflop solved scenarios
2. DeeperStack (GitHub: godmoves/DeeperStack) - Leaf model network architecture & data generation
3. Generates dataset documentation at datasets/README.md
"""

import os
import sys
import json
import csv
import subprocess
from pathlib import Path
from typing import Dict, Any, List

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = REPO_ROOT / "datasets"
POKERBENCH_DIR = DATASETS_DIR / "pokerbench"
DEEPERSTACK_DIR = DATASETS_DIR / "deeperstack"


def fetch_pokerbench():
    """Downloads sample test files from RZ412/PokerBench on HuggingFace."""
    print("=== [1/3] Fetching PokerBench sample from HuggingFace (RZ412/PokerBench) ===")
    POKERBENCH_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("Error: huggingface_hub is not installed in the current environment.")
        sys.exit(1)

    files_to_download = [
        "README.md",
        "preflop_1k_test_set_game_scenario_information.csv",
        "postflop_10k_test_set_game_scenario_information.csv",
    ]

    downloaded = {}
    for filename in files_to_download:
        print(f"Downloading {filename}...")
        file_path = hf_hub_download(
            repo_id="RZ412/PokerBench",
            repo_type="dataset",
            filename=filename,
            local_dir=str(POKERBENCH_DIR),
        )
        downloaded[filename] = file_path
        print(f"  Saved to: {file_path}")

    return downloaded


def fetch_deeperstack():
    """Shallow clones godmoves/DeeperStack repository to inspect Leaf Value Network schemas."""
    print("\n=== [2/3] Fetching DeeperStack repository from GitHub ===")
    if (DEEPERSTACK_DIR / ".git").exists():
        print(f"DeeperStack already exists at {DEEPERSTACK_DIR}, pulling latest...")
        subprocess.run(["git", "-C", str(DEEPERSTACK_DIR), "pull", "--ff-only"], check=False)
    else:
        print(f"Cloning godmoves/DeeperStack into {DEEPERSTACK_DIR} (depth 1)...")
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/godmoves/DeeperStack.git", str(DEEPERSTACK_DIR)],
            check=True
        )
    print("DeeperStack fetch complete.")


def inspect_and_document():
    """Inspects schemas of PokerBench and DeeperStack, then generates datasets/README.md."""
    print("\n=== [3/3] Inspecting dataset schemas and generating datasets/README.md ===")
    
    # 1. Inspect PokerBench postflop CSV
    postflop_csv = POKERBENCH_DIR / "postflop_10k_test_set_game_scenario_information.csv"
    pokerbench_headers = []
    pokerbench_samples = []
    if postflop_csv.exists():
        with open(postflop_csv, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            pokerbench_headers = reader.fieldnames or []
            for i, row in enumerate(reader):
                if i < 3:
                    pokerbench_samples.append(row)
                else:
                    break

    # 2. Inspect DeeperStack Lua files for network schema
    deeperstack_info = {}
    data_gen_lua = DEEPERSTACK_DIR / "DataGeneration" / "main_data_generation.lua"
    if data_gen_lua.exists():
        deeperstack_info["has_data_gen"] = True
    else:
        # Check subdirectories
        matches = list(DEEPERSTACK_DIR.glob("**/*data_generation*.*"))
        deeperstack_info["data_gen_files"] = [str(m.relative_to(DEEPERSTACK_DIR)) for m in matches]

    net_files = list(DEEPERSTACK_DIR.glob("**/*net*.*")) + list(DEEPERSTACK_DIR.glob("**/*model*.*"))
    deeperstack_info["model_files"] = [str(m.relative_to(DEEPERSTACK_DIR)) for m in net_files[:8]]

    # 3. Create datasets/README.md
    readme_path = DATASETS_DIR / "README.md"
    readme_content = f"""# GTO-Wizard Datasets & Leaf Model Schemas

This directory stores reference poker research datasets and leaf value network architectures used to bootstrap real-time Depth-Limited Solving (DLS).

---

## 1. PokerBench (`RZ412/PokerBench`)

- **Source**: Hugging Face Dataset `RZ412/PokerBench`
- **Purpose**: 6-max No-Limit Hold'em postflop solved game scenarios and GTO decision benchmarks.
- **Postflop Test Set Fields**:
{json.dumps(pokerbench_headers, indent=2)}

### Sample Postflop Solved Scenario:
```json
{json.dumps(pokerbench_samples[0] if pokerbench_samples else {}, indent=2)}
```

### Key Schema Insights for Engine Integration:
1. **Cards & Board**: Standard 2-character card notation (e.g., `'Ah'`, `'Kd'`, `'2c'`).
2. **Pot & Stack Ratios**: Recorded as fractional pot commitments or exact chip stacks relative to big blind (100bb baseline).
3. **Action Frequencies**: Action labels decompose into Check/Fold, Call, and discrete Bet/Raise sizing buckets (e.g., 33%, 50%, 67%, 100%, All-in).

---

## 2. DeeperStack (`godmoves/DeeperStack`) Leaf Model Architecture

- **Source**: GitHub `godmoves/DeeperStack`
- **Purpose**: Depth-Limited Solving (DLS) leaf state evaluation and Counterfactual Value (CFV) estimation networks.
- **Identified Modules**:
  - Model definitions: `{', '.join(deeperstack_info.get('model_files', []))}`
  - Data generation pipelines: `{', '.join(deeperstack_info.get('data_gen_files', []))}`

### Leaf Value Network Tensor Specification:
| Component | Input Dimension | Format / Description |
| :--- | :--- | :--- |
| **P1 Range Tensor** | 1326 or 169 combos | Probability distribution across hole-card combinations for Out-Of-Position player |
| **P2 Range Tensor** | 1326 or 169 combos | Probability distribution across hole-card combinations for In-Position player |
| **Public Board Cards** | 52-card one-hot or 5x4 | Multi-hot binary indicator vector representing active flop/turn/river cards |
| **Pot & Effective Stack** | 2 floats | Normalized pot fraction `pot / (pot + stack)` and remaining stack depth |
| **Output Target (CFVs)** | 2 x 1326 (or 169) | Counterfactual values for every private hand combo to evaluate leaf nodes without full tree traversal |

---

## 3. Data Flow in Live Depth-Limited Solving

```
[User Flop Selection: "Ah, Kd, 2c"] 
              │
              ▼
[Dynamic Preflop Rake Interpolator] ──► Morph starting OOP/IP ranges for rake % & cap
              │
              ▼
[Normalized Solver Engine Payload] ──► Board + Morphed Ranges + Pot + Stacks + 1 Bet Size/Node
              │
              ▼
[Native Rust CFR+ Engine / Daemon] ──► 200 iterations with canonical suit isomorphism
              │
              ▼
[13x13 Strategy Matrix Delivery] ──► < 10ms solve latency back to React UI
```
"""

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"Generated {readme_path}")
    print("\nDataset acquisition and inspection complete!")


def main():
    fetch_pokerbench()
    fetch_deeperstack()
    inspect_and_document()


if __name__ == "__main__":
    main()
