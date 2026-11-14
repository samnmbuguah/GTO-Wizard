#!/usr/bin/env python3
"""
scripts/bin_weights_to_pt.py

Rebuilds a PyTorch state dict from the native Rust binary weight format
(`<I` tensor count, then per tensor: name length, name, ndim, dims, f32 data)
and saves it as a `.pt` file.

This lets the Python tooling (accuracy audit, ONNX export, parity harness) use
the exact weights the Rust daemon is running, without keeping two copies of a
trained model in sync.

Usage:
    python scripts/bin_weights_to_pt.py ml/artifacts/pair_equity_net_weights.bin \
        --out /tmp/pair_from_bin.pt --model pair
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def read_tensor_map(path: Path) -> dict[str, torch.Tensor]:
    tensors: dict[str, torch.Tensor] = {}
    with path.open("rb") as f:
        (num_tensors,) = struct.unpack("<I", f.read(4))
        for _ in range(num_tensors):
            (name_len,) = struct.unpack("<I", f.read(4))
            name = f.read(name_len).decode("utf-8")
            (ndim,) = struct.unpack("<I", f.read(4))
            dims = []
            for _ in range(ndim):
                (d,) = struct.unpack("<I", f.read(4))
                dims.append(d)
            data = f.read(4 * int(torch.tensor(dims).prod().item()) if dims else 4)
            arr = torch.frombuffer(bytearray(data), dtype=torch.float32).clone()
            tensors[name] = arr.reshape(dims) if dims else arr
    return tensors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bin_path", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", choices=("pair", "leaf"), default="pair")
    args = ap.parse_args()

    tensors = read_tensor_map(args.bin_path)
    print(f"read {len(tensors)} tensors from {args.bin_path}")

    if args.model == "pair":
        from ml.models.pair_equity_net import PairEquityNet
        model = PairEquityNet()
        state = model.state_dict()
        missing = [k for k in state if k not in tensors]
        extra = [k for k in tensors if k not in state]
        if missing or extra:
            print(f"WARNING missing={missing} extra={extra}", file=sys.stderr)
        model.load_state_dict({k: v for k, v in tensors.items() if k in state}, strict=False)
    else:
        from ml.models.leaf_value_net import LeafValueNet
        model = LeafValueNet()
        model.load_state_dict({k: v for k, v in tensors.items()}, strict=False)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
