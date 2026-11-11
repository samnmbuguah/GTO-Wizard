#!/usr/bin/env python3
"""
scripts/download_pokerbench.py

Acquires and inspects the PokerBench baseline benchmark dataset (RZ412/PokerBench)
from Hugging Face into datasets/benchmark/.
Extracts schema information, feature definitions, and label targets.
"""

import os
import sys
import json
import csv
from pathlib import Path
from typing import Dict, Any, List

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = REPO_ROOT / "datasets" / "benchmark"
VENV_PYTHON = REPO_ROOT / "backend" / "venv" / "bin" / "python3"

# Auto re-exec with venv python if huggingface_hub is missing
if VENV_PYTHON.exists() and sys.executable != str(VENV_PYTHON):
    try:
        import huggingface_hub
    except ImportError:
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)


def download_pokerbench_files():
    """Download the 10k postflop benchmark scenario slice from Hugging Face."""
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import hf_hub_download

    repo_id = "RZ412/PokerBench"
    files = [
        "README.md",
        "postflop_10k_test_set_game_scenario_information.csv",
        "postflop_10k_test_set_prompt_and_label.json",
    ]

    downloaded_paths = {}
    print(f"📥 Downloading benchmark slices from HuggingFace ({repo_id}) to {BENCHMARK_DIR}...")
    for filename in files:
        print(f"  -> Fetching {filename}...")
        try:
            path = hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                filename=filename,
                local_dir=str(BENCHMARK_DIR),
            )
            downloaded_paths[filename] = path
            print(f"     Saved: {path} ({os.path.getsize(path):,} bytes)")
        except Exception as e:
            print(f"     Warning downloading {filename}: {e}")

    return downloaded_paths


def inspect_csv_dataset(csv_path: Path):
    """Inspects postflop CSV schema, fields, and types."""
    print("\n" + "=" * 80)
    print("📊 POKERBENCH CSV BENCHMARK SCHEMA INSPECTION")
    print("=" * 80)
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        first_row = next(reader, None)
        
        # Sample total rows
        total_rows = 1 + sum(1 for _ in f)

    print(f"Total Spots in Slice : {total_rows:,}")
    print(f"Field Names ({len(fields)} columns):")
    for idx, field in enumerate(fields, start=1):
        sample_val = first_row.get(field, "") if first_row else ""
        val_type = type(sample_val).__name__
        print(f"  {idx:2d}. {field:<24} | Sample: {str(sample_val):<40} | Type: {val_type}")

    return fields, first_row


def inspect_json_dataset(json_path: Path):
    """Inspects prompt and label JSON structure."""
    print("\n" + "=" * 80)
    print("📋 POKERBENCH PROMPT & LABEL JSON INSPECTION")
    print("=" * 80)

    if not json_path.exists():
        print(f"JSON file {json_path} does not exist.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        print(f"Total JSON entries: {len(data):,}")
        sample = data[0] if len(data) > 0 else {}
    elif isinstance(data, dict):
        print(f"JSON dictionary with {len(data.keys()):,} keys")
        sample_key = next(iter(data.keys()))
        sample = {"key": sample_key, "value": data[sample_key]}
    else:
        sample = str(data)[:200]

    print("Sample JSON Entry Structure:")
    if isinstance(sample, dict):
        for k, v in sample.items():
            print(f"  • {k}: {str(v)[:100]} (type: {type(v).__name__})")
    else:
        print(sample)


if __name__ == "__main__":
    downloaded = download_pokerbench_files()
    csv_file = BENCHMARK_DIR / "postflop_10k_test_set_game_scenario_information.csv"
    json_file = BENCHMARK_DIR / "postflop_10k_test_set_prompt_and_label.json"

    if csv_file.exists():
        inspect_csv_dataset(csv_file)
    if json_file.exists():
        inspect_json_dataset(json_file)
