#!/usr/bin/env python3
"""
scripts/eval_pair_model.py

Evaluates a pair-equity operator on the held-out board split (same split as
`ml/train_pair_equity.py`: 15% of boards, deterministic seed).

Usage:
    python scripts/eval_pair_model.py ml/artifacts/pair_equity_net.pt
    python scripts/eval_pair_model.py ml/artifacts/pair_equity_net_weights.bin --from-bin
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.train_leaf_model import load_arrays
from ml.train_pair_equity import evaluate_bb
from ml.models.pair_equity_net import PairEquityNet

DEFAULT_DATASETS = ",".join([
    str(REPO_ROOT / "datasets/generated/nl500_100bb_leaf_cfr.parquet"),
    str(REPO_ROOT / "datasets/generated/leaf_cfr_aug_multiconfig.parquet"),
])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("weights", type=Path)
    ap.add_argument("--from-bin", action="store_true",
                    help="the weights file is the native .bin tensor map")
    ap.add_argument("--dataset", default=DEFAULT_DATASETS)
    args = ap.parse_args()

    df = pd.concat([pd.read_parquet(p.strip()) for p in args.dataset.split(",") if p.strip()],
                   ignore_index=True)
    A = load_arrays(df)

    # Same deterministic split as the trainer.
    rng = np.random.default_rng(0)
    boards = np.unique(A["board_key"])
    rng.shuffle(boards)
    val_boards = set(boards[: int(0.15 * len(boards))])
    is_val = np.array([b in val_boards for b in A["board_key"]])
    va_idx = np.where(is_val & A["valid"])[0]

    model = PairEquityNet()
    if args.from_bin:
        from scripts.bin_weights_to_pt import read_tensor_map
        tensors = read_tensor_map(args.weights)
        model.load_state_dict({k: v for k, v in tensors.items()
                               if k in model.state_dict()}, strict=False)
    else:
        model.load_state_dict(torch.load(args.weights, map_location="cpu"))
    model.eval()

    m = evaluate_bb(model, A, va_idx)
    print(json.dumps({k: round(float(v), 6) for k, v in m.items()}, indent=2))
    print(f"rows={len(va_idx)} boards={len(val_boards)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
