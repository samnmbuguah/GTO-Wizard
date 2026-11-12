# Leaf Model Wiring — Design Note

Date: 2026-11-12
Status: **not implemented** (blocked on an interface change, not on data)

## 1. What the engine needs at a leaf

At a depth-limited flop/turn exit, `solver_daemon/src/cfr.rs::showdown_values()`
computes, for every hand class `i` and opponent class `j`:

```
v_oop[i] = Σ_j reach_ip[j] * (equity[i][j] * net_pot - invested_oop)
v_ip[j]  = Σ_i reach_oop[i] * ((1 - equity[i][j]) * net_pot - invested_ip)
```

So the exit evaluation is a **169-vector per player**, conditioned on the
node-local reach ranges. A drop-in replacement must produce that shape.

## 2. What Model 2 produces today

`ml/models/leaf_value_net.py` outputs:

- `ev[2]` — scalar OOP and IP EV for the whole root state
- `freq_logits[3]` — fold / call / raise

That is a root-level aggregate, not a leaf value vector. It cannot be plugged
into `showdown_values()` without changing both the model and the trainer.

## 3. Viable designs

### A. Range-conditioned per-class equity predictor (recommended if speed matters)

- Input: board features (75) + opponent reach vector (169) → 244 dims.
- Output: 169 equity values for hero's classes.
- Targets: exact `Σ_j eq[i][j] * reach[j]` from the Rust evaluator for many
  (board, reach) pairs. Reach perturbations around the BTN/BB root ranges give
  ~50 samples per board; 1,755 boards → ~87k rows.
- Runtime: export the MLP to ONNX and add `tract-onnx` to the daemon, **or**
  implement the small MLP (244→256→169) directly in Rust and load weights from
  a binary blob.
- Honest expectation: this **approximates** exact equity, so it can only trade
  accuracy for speed. It is worth doing to remove the 400-runout flop sampling
  cost, not to "improve GTO accuracy".

### B. Learned counterfactual value at the exact leaf states (research-grade)

- Requires the Rust tree to emit, for a sample of leaves, `(board, node-local
  ranges, invested, per-class values)` tuples.
- Train a per-class value head on those tuples.
- Use it only where the model is in distribution (same board family, same
  ranges); otherwise fall back to exact equity.
- Highest potential, highest risk; the dataset must be regenerated per tree
  geometry.

## 4. Why it was not wired in this pass

The 31.58% frequency gap was caused by training Models 1/2 on the retired
heuristic's labels. Regenerating the dataset from real CFR and retraining
reduced it to **3.44%** without touching the leaf evaluation. Replacing exact
showdown equity with a scalar root EV would *break* the solver, and replacing
it with a learned approximation is a performance change, not an accuracy fix.

## 5. Estimate

| Piece | Estimated effort |
|---|---|
| Per-class head + targets export from Rust | 2–3 h |
| Range-perturbation dataset (~87k rows) + training | 1–2 h |
| Rust inference (ONNX or native MLP) + feature parity tests | 2–3 h |
| Verification (exploitability must not regress) | 1 h |
| **Total** | **6–9 h** |

Decision gate: only proceed if flop solve latency needs to drop below the
current ~0.4 s. Accuracy is already at the depth-limited model's ceiling.
