# Leaf Value Network — Implemented Design and Measured Behaviour

Date: 2026-11-14
Status: **implemented and wired**; the dense antisymmetric pair-equity operator
(**V2**) is the runtime leaf evaluator, exact showdown remains the safety net.

This note replaces the earlier "not implemented" design study. It documents what
actually shipped, why the runtime shape is what it is, and where the accuracy
limits come from.

> **Runtime model: V2 (`ml/models/pair_equity_net_v2.py`).** The V1 low-rank
> operator is superseded but kept in the tree for comparison. Measured on
> held-out boards: V1 mean \|ΔE\| 0.134 → bilinear class embedding 0.112 →
> **V2 dense per-pair head 0.047**. See `docs/ACCURACY_AUDIT.md` §10.3.

## 1. What the engine needs at a leaf

At a depth-limited flop/turn exit, `solver_daemon/src/cfr.rs::showdown_values()`
needs, for every hand class `i` and opponent class `j`:

```
v_oop[i] = Σ_j reach_ip[j] * (equity[i][j] * net_pot - invested_oop)
v_ip[j]  = Σ_i reach_oop[i] * ((1 - equity[i][j]) * net_pot - invested_ip)
```

The exit evaluation is a **169-vector per player**, conditioned on the
node-local reach ranges. Exact `equity` is board-only and is computed once per
solve by `compute_equity()` (400 sampled runouts on the flop, all rivers on the
turn, exact on the river).

## 2. Models

Three leaf-model families exist; the engine uses the **pair operator** (V2 dense
first, V1 low-rank as a legacy fallback) when its weights are present and falls
back to the marginal-share net otherwise.

### 2.1 Runtime model — `DensePairEquityNet` (V2, `ml/models/pair_equity_net_v2.py`)

| Piece | Size |
|---|---|
| Board features (`encode_board`) | 75 |
| Generalized context (stack, starting pot, ante, rake %, rake cap, folded players) | 6 |
| **Input** | **81** |
| Trunk | 81 → 128 (Linear + LayerNorm + GELU) → 2 residual blocks (width 128) |
| Heads | per-pair logit `s_ij = w_ij · h + b_ij` for all 169×168/2 = **14,196** unordered pairs |

The generalized context is normalized exactly as the client contract requires:

```
[stack_bb/100, starting_pot_bb/10, ante_bb, rake_pct/10, rake_cap/5, num_folded_players/6]
```

The operator is

```
s[i][j] = w_ij · h + b_ij      (i < j)
s[j][i] = -s[i][j]              (antisymmetric by construction)
E[i][j] = sigmoid(s[i][j])
```

so `E[i][j] + E[j][i] = 1` **by construction** (the antisymmetric part cancels
in the sigmoid). Terminal values follow:

```
v_oop[i] = (E·r̂_ip)[i] * net_pot * m_ip - invested_oop * m_ip
v_ip[j] = (1 - r̂_oopᵀE)[j] * net_pot * m_oop - invested_ip * m_oop
```

Summing against the reaches cancels the equity terms identically:

```
Σ reach_oop·v_oop + Σ reach_ip·v_ip = m_oop · m_ip · (start_pot - rake)
```

for **any** pair of independent reaches. Pot conservation is structural, not
learned — this is the property the marginal-share net could not provide.

**Why V2 and not V1.** V1 parameterised the logit matrix as
`a[i] - a[j] + (U Vᵀ - V Uᵀ)[i][j]/√R`, i.e. a hand-strength score plus a
*low-rank* skew. That shape cannot represent the pair-specific blocker / suit
structure of the real equity matrix and plateaued at mean \|ΔE\| ≈ 0.13–0.16 —
far above the ≈0.018 label-noise floor — which made the learned-leaf CFR attempt
miss the 0.5%-pot exploitability gate. V2 gives every unordered hand-class pair
its own logit while keeping the matrix exactly antisymmetric, so pot
conservation stays structural.

**Training** (`ml/train_pair_equity_dense.py`): direct supervision on the exact
169×169 equity matrices in `datasets/generated/equity_labels_2000.parquet`
(1,755 boards × 2,000 sampled runouts per board). Loss is BCE + 5×MSE on
`E`, with the train/val split **by board** (unseen boards in validation).
Exports `ml/artifacts/pair_equity_net_v2.{pt,onnx,onnx.data}` and the native
Rust format `ml/artifacts/pair_equity_net_v2_weights.bin`.

**Native inference** (`solver_daemon/src/leaf_net.rs::DensePairEquityNet`): the
daemon loads the `.bin` tensor map directly, runs the trunk natively in f32 and
evaluates the 169×169 matrix in Rust — no Python/ONNX runtime in the hot path.
Python↔Rust parity is ≤ 2.5e-4 per element (the residual is the tanh-GELU
approximation in Rust vs PyTorch's exact erf-GELU; check with
`scripts/check_pair_parity.py`).

### 2.2 Legacy model — `PairEquityNet` (V1, `ml/models/pair_equity_net.py`)

Low-rank skew operator (see the formula above). Still loadable
(`pair_equity_net_weights.bin`) and used only when the V2 weights are absent.
It no longer passes the 0.5%-pot gate on the verification matrix.

### 2.3 Fallback model — `LeafValueNet` (`ml/models/leaf_value_net.py`)

| Piece | Size |
|---|---|
| Board features | 75 |
| OOP reach, normalised | 169 |
| IP reach, normalised | 169 |
| Node context (pot, invested ×2, net pot, stack, ante, rake %, rake cap, folded) | 9 |
| **Input** | **422** |
| Trunk | 422 → 256 → 128 |
| Heads | two 169-way sigmoid heads (`t_oop`, `t_ip`) |

This model is reach-conditioned, so it needs a cached share per node and a
zero-sum projection; it is kept as a fallback (and for the `leaf-net` mode
without pair weights).

## 3. Targets and data

### 3.1 Pair-equity labels (V2)

The pair operator is supervised **directly on the equity matrix**, not on a
range-averaged share:

```
datasets/generated/equity_labels_2000.parquet
  1,755 boards × exact 169×169 equity matrix (2,000 sampled runouts per board)
```

generated by `scripts/data_gen/generate_equity_labels.py`. Range-averaged share
targets under-determine `E` (measured mean \|ΔE\| 0.106–0.161, max 0.97),
because a single scalar share per hand cannot pin down the pairwise matrix.

### 3.2 Marginal-share targets (V1 / fallback net)

Targets are exact, not a root aggregate:

```
t_oop[i] = (v_oop[i] / reach_ip_mass + invested_oop) / net_pot
t_ip[j]  = (v_ip[j]  / reach_oop_mass + invested_ip)  / net_pot
```

generated by the Rust solver with `GTO_LEAF_NET=off` (which disables **both**
learned evaluators).

| Dataset | Rows | Boards | Notes |
|---|---|---|---|
| `nl500_100bb_leaf_cfr.parquet` | 10,001 | 1,755 | one converged solve per board, stratified across rake/stack/ante/folded configurations |
| `leaf_cfr_aug_multiconfig.parquet` | 30,003 | 1,755 | 3 reach perturbations per board under the **same** per-board configuration |
| **Combined** | **40,004** | **1,755** | train/val split by board (263 unseen boards) |

Configuration coverage of the combined set:

| Stack | Ante | Rake | Cap | Folded | Rows |
|---|---|---|---|---|---|
| 20bb | 0.125 | 0% | 0 | 4 | 5,673 |
| 40bb | 0.125 | 0% | 0 | 4 | 4,017 |
| 60bb | 0.125 | 0% | 0 | 4 | 3,843 |
| 100bb | 0.125 | 0% | 0 | 4 | 3,285 |
| 100bb | 0 | 5% | 0.6 | 4 | 6,600 |
| 100bb | 0 | 5% | 0.6 | 0 | 3,285 |
| 100bb | 0 | 5% | 4.0 | 4 | 3,300 |

Training builds convex mixes of two leaves **on the same board *and* the same
context** (stack, pot, ante, rake, cap, folded). That is exact for this model:
the operator `E` must be identical for the mix to be a valid target, and `t` is
linear in the normalised opposing range.

## 4. Runtime path (`solver_daemon/src/cfr.rs`)

1. Resolves the bunching profile (`resolve_bunching_weights`): explicit
   `bunching_weights` if supplied, otherwise the built-in folded-count profile.
2. Computes the pair operator **once per solve** (it depends only on the board
   and the context, not on the reaches) —
   `leaf_net::DensePairEquityNet::equity_matrix` (V2), falling back to
   `leaf_net::PairEquityNet::equity_matrix` (V1) when only the V1 weights are
   present.
3. Every leaf then uses `leaf_net::pair_values(...)`, which is linear in the
   opponent's reach and conserves the pot exactly.
4. If no pair weights are loaded, the marginal-share net is used with the
   warm-up/cache/refine path described in the previous revision.
5. `leaf_mode` is reported as `leaf-net-pair-v2`, `leaf-net-pair`, `leaf-net` or
   `exact-showdown`.

The pair path needs no warm-up and no refinement: there is nothing to cache and
nothing to refine, because the payoff is already reach-linear and conserving.

**Environment switches** (`solver_daemon/src/leaf_net.rs`):

| `GTO_LEAF_NET` | Behaviour |
|---|---|
| unset (default) | pair operator (V2 → V1) when weights are present, else exact showdown |
| `on` | same, plus the reach-conditioned marginal net is enabled |
| `off` | exact showdown equity only (used by the oracle daemon) |

Diagnostics: `GTO_LEAF_FALLBACK=off` keeps the learned result even when it
misses the gate (so the learned equity matrix can be inspected);
`GTO_PAIR_USE_EXACT=on` routes the *exact* sampled equity through the pair
code path to separate "the learned matrix is wrong" from "the pair code path
is wrong".

## 5. Card bunching

Bunching is applied in two places in `solver_daemon/src/cfr.rs`:

* **Runout probabilities** — `compute_equity()` weights each sampled turn/river
  runout by the product of its ranks' survival weights.
* **Combo weights** — `normalized_reach()` weights each hole-card combo by the
  product of its ranks' survival weights.

The built-in profile derives a per-rank survival curve from the number of folded
players, using a 6-max fold-rate profile (early positions fold more trash, so
aces survive more often than deuces). A caller can supply an explicit 13-value
profile (`bunching_weights`, index 0 = '2' … 12 = 'A', mean 1.0) — the backend
derives a seat-aware profile from the folded seats' opening ranges
(`backend/solutions/services/bunching.py`).

## 6. Exact-showdown fallback and safety gate

```rust
// solver_daemon/src/lib.rs
fn conservation_violation(input: &SolverInput, ev_sum: f64) -> f64 {
    // Rake is charged on the *final* pot (including the players' bets), so a
    // raked game must have paid between rake(start pot) and the cap; a
    // zero-rake game must have paid exactly zero.
    let rake_paid = input.pot - ev_sum;
    if input.rake_percent <= 0.0 || input.rake_cap <= 0.0 {
        return rake_paid.abs();
    }
    let lo = input.rake_cap.min(input.pot * input.rake_percent / 100.0);
    let hi = input.rake_cap;
    if rake_paid < lo { lo - rake_paid }
    else if rake_paid > hi { rake_paid - hi }
    else { 0.0 }
}

fn leaf_result_passes(out: &SolverOutput, input: &SolverInput) -> bool {
    out.converged
        && out.exploitability_pct_pot <= 0.5
        && conservation_violation(input, out.oop_ev + out.ip_ev) <= 0.35
}
```

If a learned-leaf solve misses either gate, `evaluate_and_solve` re-solves the
same spot with exact showdown equity and labels the result
`"exact-showdown (leaf-net fallback)"`. `GTO_LEAF_NET=off` forces exact mode.

With the V2 operator the gate is met on **300/300** spots of the verification
matrix, so the fallback is only a safety net (see
`docs/ACCURACY_AUDIT.md` §10).

## 7. Measured behaviour

See `docs/ACCURACY_AUDIT.md` §10 for the generalized-engine run (rake / stack /
ante / bunching matrix, latency, exploitability, EV conservation) and
`docs/ZENO_PARITY_REPORT.md` for the side-by-side reference comparison.

Headline numbers (50 boards × 6 configurations, learned V2 path):

| Metric | Value |
|---|---|
| Spots at ≤0.5% pot exploitability | 300 / 300 |
| Mean exploitability | 0.386–0.432% pot |
| Mean latency | 150–213 ms |
| EV conservation error | 0 (raked) / ≈7e-15 (zero-rake) |
| Pair-operator validation mean \|ΔE\| | 0.0472 |
| Root EV error vs exact | 0.0045 bb mean (p95 0.0146, max 0.0277) |
| Python ↔ Rust parity | ≤ 2.5e-4 per element |

## 8. Remaining limitations

* **Depth-limited, not multi-street.** Future streets collapse to one showdown
  equity number, so the strategies are not a full multi-street equilibrium.
* **169 classes, not 1,326 combos.** Suit/blocker effects inside a class are
  averaged.
* **Learned leaves are approximate.** The pair operator conserves the pot
  exactly, but the *equity values* it predicts are learned from sampled
  runouts; the exact-showdown fallback remains available.
* **Single bet size plus all-in.** The tree uses a 33% pot bet.
* **No ICM, no PLO, no node locking.**
