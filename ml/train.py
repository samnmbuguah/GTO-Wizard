#!/usr/bin/env python3
"""
ml/train.py

Training pipeline for Oleg's Two-Model ZenoSolver Architecture:
- Model 1 (Bet Size Predictor): Single optimal bet sizing classifier for tree pruning.
- Model 2 (Leaf Value Net): Flop-to-turn counterfactual EV and equilibrium frequencies estimator.

Trains directly on the generated parquet dataset:
datasets/generated/zeno_baseline_100bb_nl500.parquet
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Tuple, List, Dict, Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ml.features import (
    encode_board,
    encode_range,
    determine_optimal_bet_size,
    CLASS_TO_SIZE,
    CANDIDATE_SIZES,
)
from ml.models.size_predictor import BetSizePredictor
from ml.models.leaf_value_net import LeafValueNet


class ZenoDataset(Dataset):
    """PyTorch Dataset loading generated solver leaves from Parquet."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.reset_index(drop=True)
        self.precomputed_features = []

        boards = self.df["board"].tolist()
        pots = self.df["pot"].to_numpy(dtype=np.float32)
        stacks = self.df["effective_stack"].to_numpy(dtype=np.float32)
        rake_pcts = self.df["rake_percent"].to_numpy(dtype=np.float32)
        rake_caps = self.df["rake_cap"].to_numpy(dtype=np.float32)
        oop_evs = self.df["oop_ev"].to_numpy(dtype=np.float32)
        ip_evs = self.df["ip_ev"].to_numpy(dtype=np.float32)

        # Check if oop_range and ip_range exist as columns
        oop_ranges = self.df["oop_range"].tolist() if "oop_range" in self.df.columns else [{}] * len(df)
        ip_ranges = self.df["ip_range"].tolist() if "ip_range" in self.df.columns else [{}] * len(df)
        overall_freqs = self.df["overall_frequencies"].tolist() if "overall_frequencies" in self.df.columns else [{}] * len(df)

        for i in range(len(df)):
            board = list(boards[i])
            pot = float(pots[i])
            stack = float(stacks[i])
            rake_pct = float(rake_pcts[i])
            rake_cap = float(rake_caps[i])

            # Model 1 features
            board_vec = encode_board(board)
            spr = stack / max(pot, 0.1)
            ctx_m1 = np.array([pot / 10.0, stack / 100.0, spr / 20.0, rake_pct / 10.0], dtype=np.float32)
            m1_x = np.concatenate([board_vec, ctx_m1])
            m1_y = determine_optimal_bet_size(board, pot)

            # Model 2 features
            oop_r = oop_ranges[i]
            if isinstance(oop_r, str):
                try:
                    oop_r = json.loads(oop_r)
                except Exception:
                    oop_r = {}
            ip_r = ip_ranges[i]
            if isinstance(ip_r, str):
                try:
                    ip_r = json.loads(ip_r)
                except Exception:
                    ip_r = {}

            oop_vec = encode_range(oop_r if isinstance(oop_r, dict) else {})
            ip_vec = encode_range(ip_r if isinstance(ip_r, dict) else {})
            ctx_m2 = np.array([pot, stack, rake_pct, rake_cap], dtype=np.float32)
            m2_x = np.concatenate([board_vec, oop_vec, ip_vec, ctx_m2])

            m2_ev_y = np.array([float(oop_evs[i]), float(ip_evs[i])], dtype=np.float32)

            freqs = overall_freqs[i]
            if isinstance(freqs, str):
                try:
                    freqs = json.loads(freqs)
                except Exception:
                    freqs = {}
            if isinstance(freqs, dict) and "fold" in freqs:
                m2_freq_y = np.array([
                    float(freqs.get("fold", 0.33)),
                    float(freqs.get("call", 0.33)),
                    float(freqs.get("raise", 0.34)),
                ], dtype=np.float32)
            else:
                m2_freq_y = np.array([0.33, 0.33, 0.34], dtype=np.float32)

            net_pot = pot - min(pot * (rake_pct / 100.0), rake_cap)

            self.precomputed_features.append({
                "m1_x": torch.from_numpy(m1_x),
                "m1_y": torch.tensor(m1_y, dtype=torch.long),
                "m2_x": torch.from_numpy(m2_x),
                "m2_ev_y": torch.from_numpy(m2_ev_y),
                "m2_freq_y": torch.from_numpy(m2_freq_y),
                "net_pot": net_pot,
            })

    def __len__(self) -> int:
        return len(self.precomputed_features)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        return self.precomputed_features[idx]


def train_model1_size_predictor(
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int = 15,
    lr: float = 1e-3,
) -> BetSizePredictor:
    """Trains Model 1 (Bet Size Predictor)."""
    print("\n" + "=" * 70)
    print(" 🎯 TRAINING MODEL 1: BET SIZE PREDICTOR (1-SIZE TREE PRUNING)")
    print("=" * 70)

    model = BetSizePredictor(input_dim=79, hidden_dim=128, num_classes=4)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        train_correct = 0
        total_train = 0

        for batch in train_loader:
            x = batch["m1_x"]
            y = batch["m1_y"]
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * len(y)
            preds = torch.argmax(logits, dim=-1)
            train_correct += (preds == y).sum().item()
            total_train += len(y)

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        total_val = 0
        with torch.no_grad():
            for batch in val_loader:
                x = batch["m1_x"]
                y = batch["m1_y"]
                logits = model(x)
                loss = criterion(logits, y)
                val_loss += loss.item() * len(y)
                preds = torch.argmax(logits, dim=-1)
                val_correct += (preds == y).sum().item()
                total_val += len(y)

        train_acc = (train_correct / total_train) * 100.0
        val_acc = (val_correct / total_val) * 100.0
        avg_train_loss = train_loss / total_train
        avg_val_loss = val_loss / total_val

        if epoch % 5 == 0 or epoch == epochs:
            print(
                f"  Epoch [{epoch:>2}/{epochs:>2}] | Train Loss: {avg_train_loss:.4f} | "
                f"Train Acc: {train_acc:>5.1f}% | Val Loss: {avg_val_loss:.4f} | Val Acc: {val_acc:>5.1f}%"
            )

    print("✅ Model 1 (Bet Size Predictor) successfully trained.")
    return model


def train_model2_leaf_value_net(
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int = 20,
    lr: float = 1e-3,
) -> LeafValueNet:
    """Trains Model 2 (Flop-to-Turn Leaf Value Model)."""
    print("\n" + "=" * 70)
    print(" 🧠 TRAINING MODEL 2: FLOP-TO-TURN LEAF VALUE NET (COUNTERFACTUAL EV)")
    print("=" * 70)

    model = LeafValueNet(board_dim=75, range_dim=169, ctx_dim=4, hidden_dim=256, num_res_blocks=3)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    huber_loss = nn.HuberLoss(delta=0.05)
    freq_loss_fn = nn.KLDivLoss(reduction="batchmean")

    for epoch in range(1, epochs + 1):
        model.train()
        train_ev_loss = 0.0
        total_train = 0

        for batch in train_loader:
            x = batch["m2_x"]
            y_ev = batch["m2_ev_y"]
            y_freq = batch["m2_freq_y"]
            net_pot = batch["net_pot"]

            optimizer.zero_grad()
            pred_ev, pred_freq_logits = model(x)

            # 1. Counterfactual EV loss
            ev_loss = huber_loss(pred_ev, y_ev)

            # 2. Value conservation penalty: (OOP_EV + IP_EV - NetPot)^2
            pred_sum = pred_ev.sum(dim=-1)
            conservation_loss = torch.mean((pred_sum - net_pot) ** 2)

            # 3. Frequency alignment
            pred_log_probs = F.log_softmax(pred_freq_logits, dim=-1)
            freq_loss = freq_loss_fn(pred_log_probs, y_freq)

            total_loss = ev_loss + (0.1 * conservation_loss) + (0.05 * freq_loss)
            total_loss.backward()
            optimizer.step()

            train_ev_loss += ev_loss.item() * len(x)
            total_train += len(x)

        # Validation
        model.eval()
        val_ev_loss = 0.0
        val_conservation_err = 0.0
        total_val = 0
        with torch.no_grad():
            for batch in val_loader:
                x = batch["m2_x"]
                y_ev = batch["m2_ev_y"]
                net_pot = batch["net_pot"]
                pred_ev, _ = model(x)
                val_ev_loss += huber_loss(pred_ev, y_ev).item() * len(x)
                pred_sum = pred_ev.sum(dim=-1)
                val_conservation_err += torch.mean(torch.abs(pred_sum - net_pot)).item() * len(x)
                total_val += len(x)

        avg_train_loss = train_ev_loss / total_train
        avg_val_loss = val_ev_loss / total_val
        avg_cons_err = val_conservation_err / total_val

        if epoch % 5 == 0 or epoch == epochs:
            print(
                f"  Epoch [{epoch:>2}/{epochs:>2}] | Train EV Loss: {avg_train_loss:.5f} | "
                f"Val EV Loss: {avg_val_loss:.5f} | Net Pot Delta: {avg_cons_err:.4f} bb"
            )

    print("✅ Model 2 (Leaf Value Net) successfully trained.")
    return model


def main():
    parser = argparse.ArgumentParser(description="Train Oleg's Two-Model ZenoSolver Pipeline")
    parser.add_argument(
        "--dataset",
        type=str,
        default="datasets/generated/nl500_100bb_full.parquet",
        help="Path to generated parquet dataset",
    )
    parser.add_argument("--epochs-m1", type=int, default=15, help="Epochs for Bet Size Predictor")
    parser.add_argument("--epochs-m2", type=int, default=20, help="Epochs for Leaf Value Net")
    parser.add_argument("--batch-size", type=int, default=128, help="Batch size")
    parser.add_argument("--checkpoint-dir", type=str, default="ml/artifacts", help="Directory to save weights")
    args = parser.parse_args()

    dataset_path = REPO_ROOT / args.dataset
    if not dataset_path.exists():
        print(f"❌ Error: Dataset {dataset_path} does not exist!")
        sys.exit(1)

    print("=" * 80)
    print(" 🚀 ZENOSOLVER TWO-MODEL PIPELINE TRAINING")
    print("=" * 80)
    print(f"Loading dataset: {dataset_path}")
    df = pd.read_parquet(dataset_path)
    print(f"Dataset successfully loaded: {len(df)} spots")

    # Train / Val Split (80 / 20)
    np.random.seed(42)
    indices = np.random.permutation(len(df))
    split_idx = int(0.80 * len(df))
    train_df = df.iloc[indices[:split_idx]]
    val_df = df.iloc[indices[split_idx:]]

    print(f"Splits: Train = {len(train_df)} spots, Val = {len(val_df)} spots")

    train_ds = ZenoDataset(train_df)
    val_ds = ZenoDataset(val_df)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    ckpt_dir = REPO_ROOT / args.checkpoint_dir
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    alt_dir = REPO_ROOT / "ml" / "checkpoints"
    alt_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.perf_counter()

    # 1. Train Model 1 (Bet Size Predictor)
    model1 = train_model1_size_predictor(train_loader, val_loader, epochs=args.epochs_m1)
    m1_ckpt_path = ckpt_dir / "size_predictor.pt"
    torch.save(model1.state_dict(), m1_ckpt_path)
    torch.save(model1.state_dict(), alt_dir / "size_predictor.pt")
    print(f"💾 Model 1 weights saved to: {m1_ckpt_path}")

    # Export Model 1 ONNX
    try:
        dummy_m1 = torch.randn(1, 79, dtype=torch.float32)
        torch.onnx.export(
            model1,
            dummy_m1,
            str(ckpt_dir / "size_predictor.onnx"),
            input_names=["input"],
            output_names=["logits"],
            dynamic_axes={"input": {0: "batch_size"}, "logits": {0: "batch_size"}},
        )
        print(f"📦 Model 1 ONNX exported to: {ckpt_dir / 'size_predictor.onnx'}")
    except Exception as e:
        print(f"⚠️ ONNX export for Model 1 skipped: {e}")

    # 2. Train Model 2 (Leaf Value Net)
    model2 = train_model2_leaf_value_net(train_loader, val_loader, epochs=args.epochs_m2)
    m2_ckpt_path = ckpt_dir / "leaf_value_net.pt"
    torch.save(model2.state_dict(), m2_ckpt_path)
    torch.save(model2.state_dict(), alt_dir / "leaf_value_net.pt")
    print(f"💾 Model 2 weights saved to: {m2_ckpt_path}")

    # Export Model 2 ONNX
    try:
        dummy_m2 = torch.randn(1, 417, dtype=torch.float32)
        torch.onnx.export(
            model2,
            dummy_m2,
            str(ckpt_dir / "leaf_value_net.onnx"),
            input_names=["input"],
            output_names=["ev", "freq_logits"],
            dynamic_axes={"input": {0: "batch_size"}, "ev": {0: "batch_size"}, "freq_logits": {0: "batch_size"}},
        )
        print(f"📦 Model 2 ONNX exported to: {ckpt_dir / 'leaf_value_net.onnx'}")
    except Exception as e:
        print(f"⚠️ ONNX export for Model 2 skipped: {e}")

    total_time = time.perf_counter() - t_start

    # Quick inference sanity check
    print("\n" + "=" * 80)
    print(" 🧪 PIPELINE INFERENCE VERIFICATION (TEST SPOT)")
    print("=" * 80)
    test_board = ["Ah", "Kd", "2c"]
    pred_size, size_probs = model1.predict_size(test_board, pot=5.5, effective_stack=100.0)
    print(f"Test Spot Board: {' '.join(test_board)} (Dry Ace-High)")
    print(f"  • Model 1 Predicted Bet Size: {pred_size * 100:.0f}% pot (probs: {np.round(size_probs, 3)})")

    # Mock ranges for test spot
    mock_oop = {"AA": 0.05, "KK": 0.10, "AKs": 0.30, "72o": 0.0}
    mock_ip = {"AA": 1.0, "KK": 1.0, "AKs": 1.0, "72o": 0.0}
    leaf_res = model2.evaluate_leaf(test_board, mock_oop, mock_ip, pot=5.5, effective_stack=100.0, rake_pct=5.0, rake_cap=0.6)
    print(f"  • Model 2 Leaf Evaluation:")
    print(f"      - OOP EV: {leaf_res['oop_ev']} bb")
    print(f"      - IP EV : {leaf_res['ip_ev']} bb")
    print(f"      - Net Pot Conservation: {leaf_res['oop_ev'] + leaf_res['ip_ev']:.3f} == {leaf_res['net_pot']:.3f} bb")
    print(f"      - Frequencies: Fold {leaf_res['fold_freq']*100:.1f}%, Call {leaf_res['call_freq']*100:.1f}%, Raise {leaf_res['raise_freq']*100:.1f}%")
    print(f"  • Total Training & Verification Wall Time: {total_time:.2f} s")
    print("=" * 80)


if __name__ == "__main__":
    main()
