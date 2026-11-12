#!/usr/bin/env python3
"""
ml/train_leaf_model.py

Trains Model 2 (169-class Counterfactual Leaf Value Network) directly on the
extracted real-CFR+ leaf values from:
datasets/generated/nl500_100bb_leaf_cfr.parquet

Validates zero-sum EV conservation and exports weights to both:
- PyTorch checkpoint: ml/artifacts/leaf_value_net.pt
- ONNX model: ml/artifacts/leaf_value_net.onnx
- Native f32 binary weights: ml/artifacts/leaf_value_net_weights.bin (for ultra-fast Rust inference)
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.features import encode_board, encode_range
from ml.models.leaf_value_net import LeafValueNet


class LeafDataset(Dataset):
    """Loads precomputed leaf features and 169-dim counterfactual targets."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True)
        self.samples = []

        boards = self.df["board"].tolist()
        pots = self.df["pot"].to_numpy(dtype=np.float32)
        inv_oops = self.df["invested_oop"].to_numpy(dtype=np.float32)
        inv_ips = self.df["invested_ip"].to_numpy(dtype=np.float32)
        net_pots = self.df["net_pot"].to_numpy(dtype=np.float32)
        rake_pcts = self.df["rake_percent"].to_numpy(dtype=np.float32)

        ro_json = self.df["reach_oop_json"].tolist()
        ri_json = self.df["reach_ip_json"].tolist()
        vo_json = self.df["v_oop_json"].tolist()
        vi_json = self.df["v_ip_json"].tolist()

        n = len(self.df)
        print(f"Precomputing {n} leaf feature tensors...")
        t0 = time.perf_counter()

        for i in range(n):
            board = list(boards[i])
            b_vec = encode_board(board)
            ro = np.array(json.loads(ro_json[i]), dtype=np.float32)
            ri = np.array(json.loads(ri_json[i]), dtype=np.float32)
            vo = np.array(json.loads(vo_json[i]), dtype=np.float32)
            vi = np.array(json.loads(vi_json[i]), dtype=np.float32)

            ctx = np.array([
                pots[i] / 10.0,
                inv_oops[i] / 10.0,
                inv_ips[i] / 10.0,
                net_pots[i] / 10.0,
                rake_pcts[i] / 10.0,
            ], dtype=np.float32)

            x = np.concatenate([b_vec, ro, ri, ctx])
            target_sum = float(np.dot(ro, vo) + np.dot(ri, vi))

            self.samples.append({
                "x": torch.from_numpy(x),
                "vo": torch.from_numpy(vo),
                "vi": torch.from_numpy(vi),
                "ro": torch.from_numpy(ro),
                "ri": torch.from_numpy(ri),
                "target_sum": target_sum,
            })

        print(f"✅ Tensors precomputed in {time.perf_counter() - t0:.2f}s.")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        return self.samples[idx]


class Model2Combined(nn.Module):
    """Wrapper that outputs a single (batch, 338) tensor for clean ONNX export."""

    def __init__(self, net: LeafValueNet):
        super().__init__()
        self.net = net

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        vo, vi = self.net(x)
        return torch.cat([vo, vi], dim=-1)


def export_binary_weights(model: LeafValueNet, out_path: Path):
    """
    Exports all model weights as continuous f32 arrays in a structured binary format
    for ultra-fast pure-Rust matrix inference with zero external dependencies.
    Format:
    - num_tensors (uint32)
    For each tensor:
    - name_len (uint32), name_bytes
    - ndims (uint32), shape (uint32 * ndims)
    - data (f32 * num_elements)
    """
    import struct
    state = model.state_dict()
    with open(out_path, "wb") as f:
        f.write(struct.pack("<I", len(state)))
        for name, tensor in state.items():
            t = tensor.detach().cpu().to(torch.float32).contiguous().numpy()
            name_bytes = name.encode("utf-8")
            f.write(struct.pack("<I", len(name_bytes)))
            f.write(name_bytes)
            f.write(struct.pack("<I", t.ndim))
            for dim in t.shape:
                f.write(struct.pack("<I", dim))
            f.write(t.tobytes())
    print(f"📦 Native f32 binary weights exported to: {out_path} ({out_path.stat().st_size:,} bytes)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default=str(REPO_ROOT / "datasets" / "generated" / "nl500_100bb_leaf_cfr.parquet"),
    )
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--out-dir", default=str(REPO_ROOT / "ml" / "artifacts"))
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Error: {dataset_path} does not exist.")
        sys.exit(1)

    print("=" * 80)
    print(" 🧠 TRAINING MODEL 2: 169-CLASS COUNTERFACTUAL LEAF VALUE NETWORK")
    print("=" * 80)
    print(f"Dataset : {dataset_path}")
    df = pd.read_parquet(dataset_path)
    print(f"Loaded  : {len(df)} leaf records")

    # Split train / val
    np.random.seed(42)
    idx = np.random.permutation(len(df))
    split = int(0.85 * len(df))
    train_df = df.iloc[idx[:split]]
    val_df = df.iloc[idx[split:]]
    print(f"Splits  : Train = {len(train_df)}, Val = {len(val_df)}")

    train_ds = LeafDataset(train_df)
    val_ds = LeafDataset(val_df)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    model = LeafValueNet(board_dim=75, range_dim=169, ctx_dim=5, hidden_dim=256, num_res_blocks=3)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-5)
    huber = nn.HuberLoss(delta=0.05)

    best_val_loss = float("inf")
    best_weights = None

    t_start = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        model.train()
        train_loss = 0.0
        n_train = 0

        for batch in train_loader:
            x = batch["x"]
            vo_true = batch["vo"]
            vi_true = batch["vi"]
            ro = batch["ro"]
            ri = batch["ri"]
            target_sum = batch["target_sum"]

            optimizer.zero_grad()
            vo_pred, vi_pred = model(x)

            loss_vo = huber(vo_pred, vo_true)
            loss_vi = huber(vi_pred, vi_true)

            # Zero-sum net value conservation penalty
            pred_sum = torch.sum(ro * vo_pred, dim=-1) + torch.sum(ri * vi_pred, dim=-1)
            loss_conserve = torch.mean((pred_sum - target_sum) ** 2)

            loss = loss_vo + loss_vi + 0.1 * loss_conserve
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * len(x)
            n_train += len(x)

        scheduler.step()

        # Validation
        model.eval()
        val_loss = 0.0
        val_mae_vo = 0.0
        val_mae_vi = 0.0
        val_conserve_err = 0.0
        n_val = 0

        with torch.no_grad():
            for batch in val_loader:
                x = batch["x"]
                vo_true = batch["vo"]
                vi_true = batch["vi"]
                ro = batch["ro"]
                ri = batch["ri"]
                target_sum = batch["target_sum"]

                vo_pred, vi_pred = model(x)
                l_vo = huber(vo_pred, vo_true)
                l_vi = huber(vi_pred, vi_true)
                pred_sum = torch.sum(ro * vo_pred, dim=-1) + torch.sum(ri * vi_pred, dim=-1)
                l_c = torch.mean((pred_sum - target_sum) ** 2)

                total_l = l_vo + l_vi + 0.1 * l_c
                val_loss += total_l.item() * len(x)
                val_mae_vo += torch.mean(torch.abs(vo_pred - vo_true)).item() * len(x)
                val_mae_vi += torch.mean(torch.abs(vi_pred - vi_true)).item() * len(x)
                val_conserve_err += torch.mean(torch.abs(pred_sum - target_sum)).item() * len(x)
                n_val += len(x)

        avg_train = train_loss / n_train
        avg_val = val_loss / n_val
        mae_vo = val_mae_vo / n_val
        mae_vi = val_mae_vi / n_val
        cons_err = val_conserve_err / n_val

        if avg_val < best_val_loss:
            best_val_loss = avg_val
            best_weights = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        if epoch % 5 == 0 or epoch == args.epochs:
            print(
                f"  Epoch [{epoch:>2}/{args.epochs:>2}] | Train Loss: {avg_train:.5f} | "
                f"Val Loss: {avg_val:.5f} | MAE(OOP): {mae_vo:.4f} | MAE(IP): {mae_vi:.4f} | Conserve: {cons_err:.4f} bb"
            )

    model.load_state_dict(best_weights)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pt_path = out_dir / "leaf_value_net.pt"
    torch.save(model.state_dict(), pt_path)
    print(f"\n💾 Model 2 weights saved to: {pt_path}")

    # Export ONNX model
    onnx_path = out_dir / "leaf_value_net.onnx"
    try:
        combined = Model2Combined(model)
        combined.eval()
        dummy_x = torch.randn(1, 418, dtype=torch.float32)
        torch.onnx.export(
            combined,
            dummy_x,
            str(onnx_path),
            input_names=["input"],
            output_names=["ev_vectors_338"],
            dynamic_axes={"input": {0: "batch_size"}, "ev_vectors_338": {0: "batch_size"}},
            opset_version=14,
            export_params=True,
        )
        print(f"📦 Model 2 ONNX exported to: {onnx_path} ({onnx_path.stat().st_size:,} bytes)")
    except Exception as exc:
        print(f"⚠️ ONNX export error: {exc}")

    # Export binary weights for native Rust inference
    bin_path = out_dir / "leaf_value_net_weights.bin"
    export_binary_weights(model, bin_path)

    # Copy to backend artifacts
    backend_art = REPO_ROOT / "backend" / "artifacts"
    backend_art.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(pt_path, backend_art / "leaf_value_net.pt")
    if onnx_path.exists():
        shutil.copy2(onnx_path, backend_art / "leaf_value_net.onnx")
    if bin_path.exists():
        shutil.copy2(bin_path, backend_art / "leaf_value_net_weights.bin")

    total_time = time.perf_counter() - t_start
    print(f"\n🎉 Model 2 training complete in {total_time:.2f}s | Best Val Loss: {best_val_loss:.5f}")


if __name__ == "__main__":
    main()
