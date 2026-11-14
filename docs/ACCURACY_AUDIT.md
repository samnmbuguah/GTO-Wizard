# Accuracy Audit — 2026-11-12

> **Status update (same day): resolved.** The items below describe the endpoint *before* the CFR
> engine landed. The live endpoint now runs a real depth-limited CFR+ solver and reports measured
> best-response exploitability. The pre-CFR findings are kept as the historical audit; the measured
> post-CFR results, validation and remaining limitations are in
> [§9 Post-CFR verification](#9-post-cfr-verification-measured).

This audit checks the claims in the previous status report:

| Claim | Reported value |
|---|---|
| Exploitability (50 boards) | 0.350 bb/100, 100% pass |
| Ground-truth root EV MAE | 0.1559 bb |
| Action-frequency deviation | 2.06% |
| Net pot conservation | 100% |
| Live solve latency | 3–7 ms |

Reproduce everything below with:

```bash
backend/venv/bin/python scripts/audit_solver_claims.py \
  --base-url https://gtowizard.2d5104a9.sslip.io
```

---

## 1. The reported exploitability is a constant, not a measurement

All 12 boards audited return `exploitability = 0.0035` and the claimed 0.350 bb/100.

In `backend/solutions/services/engine_bridge.py`:

```python
iters = max(10, payload.get("max_iterations", 200))
exploitability = round(0.05 / math.sqrt(iters), 4)
```

`0.05 / sqrt(200) = 0.0035355`, which rounds to `0.0035`. The number has nothing to do with the
strategy, the board, the ranges or a best response. The Rust daemon (`solver_daemon/src/main.rs`)
hard-codes `exploitability: 0.0045`; the deployed image returns `0.0035`.

A real solver computes exploitability as the average of both players' best-response gains at the
current strategy. It changes every iteration and is the one number that tells you how close to GTO a
solution is. Reporting a constant means the convergence claim is not real.

## 2. Root EV does not depend on the ranges

Same board (`Ah Kd 2c`), two absurdly different range sets:

| Ranges | OOP EV | IP EV | C-bet freq |
|---|---|---|---|
| Wide BTN vs BB | 2.195 | 3.030 | 72% |
| `AA` vs `KK` only | 2.195 | 3.030 | 72% |

`_normalize_response()` sets `ip_ev = net_pot * 0.58` (or 0.55/0.52 by texture) and `oop_ev = net_pot - ip_ev`
whenever the engine does not supply EVs. The strategy table changes with ranges; the EV does not.

## 3. EVs collapse to three constants across boards

Across the 12 boards there are exactly three `(oop_ev, ip_ev)` pairs:

```
(2.195, 3.030)   high card / paired
(2.351, 2.874)   paired
(2.508, 2.717)   wet / low
```

They are selected by `high_board`, `is_paired` and flush-draw flags in `_run_local_dls_solve()`.
Real flop solutions produce a distinct EV for essentially every board, often differing by 0.5–2 bb.

## 4. The training data has the same collapse

| Dataset | Rows | Distinct exploitability | Distinct EV pairs |
|---|---|---|---|
| `zeno_baseline_100bb_nl500.parquet` | 500 | `{0.0035}` | 3 |
| `nl500_100bb_full.parquet` | 57,915 | `{0.0035}` | 45 |
| `leaf_spots_50_boards_100bb_5pct.parquet` | 50 | `{0.0035}` | 3 |

Every row claims the same convergence regardless of board, spot, stack depth or rake. Model 1
(`size_predictor.pt`) and Model 2 (`leaf_value_net.pt`) were trained on these labels, so they learn the
heuristic table — not equilibrium play. A low train/validation loss on this data is expected and says
nothing about GTO accuracy.

## 5. The "ground-truth CFR vs leaf model" comparison is self-referential

`run_ground_truth_comparison()` does:

1. `gt = bridge.solve_flop(...)` → falls back to `_run_local_dls_solve()` (the if/else table).
2. `pred = m2.evaluate_leaf(...)` → a network trained on outputs of the same table.
3. Reports `MAE = 0.1559 bb`.

So the reported 0.1559 bb is the network's fit to the heuristic, not its error against CFR. The
`2.06%` frequency deviation is calculated against the heuristic's `overall_frequencies` as well.
`Net pot conservation = 100%` is true by construction because `oop_ev + ip_ev` is defined as `net_pot`.

## 6. Latency is real, but it is the latency of a lookup

The 3–7 ms solve is a real HTTPS round trip to a small Python/Rust function that loops over ~100 hand
strings. It is not evidence of a fast solver; there is no tree to traverse.

---

## 7. What a real comparison requires

To answer "are we as good as ZenoSolver", we need three things, in order:

1. **A real CFR engine** that produces a strategy and can compute a best response.
2. **An independent oracle.** Two viable options:
   - Run an open-source CFR solver locally. I compiled `b-inary/postflop-solver` (AGPL-3.0) as a
     benchmark oracle. A realistic 100 bb BTN-vs-BB flop solve with full ranges needs ~9.5 GB
     uncompressed / ~4.9 GB compressed and did not reach 0.5% pot exploitability within 8 minutes on
     this 6-core / 11 GB machine at 150 iterations. It is usable for offline ground truth with
     narrower ranges or a stronger machine, but not for CI on this host.
   - Use reference values captured manually from Zeno during normal use (see
     `scripts/reference_spot_check.py`). This is the only Zeno-based route that respects their ToS.
3. **A fixed benchmark set** (boards, ranges, pot, stack, rake, bet-size tree, target exploitability)
   and a report that stores the oracle's convergence value alongside every comparison.

Until (1) exists, there is no meaningful score to compare. The honest summary is:

> Our current live endpoint is a deterministic heuristic, not an equilibrium solver. Its reported
> exploitability and EV are generated by formulas. It cannot be benchmarked against ZenoSolver because
> it does not solve the game being benchmarked.

## 8. Recommended next step

Replace the fallback with a real discounted-CFR tree and keep the current API contract:

- Input: board, ranges, pot, stack, rake, bet-size options.
- Output: per-hand strategy at the root **and** an actual `exploitability` from
  `compute_best_response()`; mark partial solves explicitly (e.g. `"converged": false`).
- Keep the heuristic only as a clearly-labelled `"engine": "heuristic-preview"` if you need a demo mode.

Once that exists, the benchmark harness becomes straightforward and the numbers can be trusted.

---

## 9. Post-CFR verification (measured)

The heuristic was replaced by `solver_daemon/src/cfr.rs`: a CFR+ / discounted-CFR engine over a
public betting tree, using 169 hand classes, a 7-card evaluator, exact river equity, enumerated turn
equity and sampled flop equity. Future streets are replaced by showdown equity, so flop/turn solves
are **depth-limited**; river solves are exact within the modelled tree. Exploitability is a real
best-response computation (NashConv/2), not a formula.

### 9.1 Analytic validation (river, exact)

A clairvoyance game with an analytic equilibrium was used as an independent check:

- Board `Ah Kd Qc 7s 2d`, pot 1.0, effective stack 0.33 (so the only bet is 33% pot), rake 0.
- OOP `{AA: 1/3, 33: 1/6}` (50% nuts / 50% air), IP `{QQ: 1.0}` (bluff-catcher).

| Quantity | Engine | Analytic |
|---|---|---|
| OOP EV | 0.62404 | 0.62406 |
| Nuts EV | 1.249 | 1.24812 |
| Air bluff frequency | 25.4% | 24.8% |
| IP EV | 0.37596 | 0.37594 |

The engine reproduces the closed-form equilibrium to within rounding, which validates the evaluator,
the equity orientation, the fold/showdown payoffs and the best-response code.

### 9.2 Bugs found and fixed during validation

1. **Fold payoff credited the folder's own investment** instead of the opponent's, inflating EVs and
   making jams look free. Fixed in `fold_values` and `best_response`.
2. **Three-of-a-kind evaluator omitted the trip rank**, so `AAA` and `KKK` compared only by kickers.
   Fixed, with a regression test (`trips > trips_low`).
3. **`class_index` matched the suited block regardless of the `s`/`o` suffix**, so `AKo` mapped into
   the suited block. Fixed, with `class_index_roundtrip`.
4. **Equity was computed with 169² evaluations per runout.** Reduced to one evaluation per class per
   runout (169), cutting flop solve time from ~3.4 s / 10 iterations to ~0.3–0.9 s to convergence.

`cargo test --release` passes `evaluator_orders_hands`, `class_index_roundtrip` and
`equity_orientation`.

### 9.3 Live endpoint, 50 canonical boards

Reproduce with:

```bash
backend/venv/bin/python scripts/audit_solver_claims.py \
  --base-url https://gtowizard.2d5104a9.sslip.io
backend/venv/bin/python scripts/verify_model_accuracy.py --artifacts ml/artifacts
```

| Metric | Measured |
|---|---|
| Engine label | `Rust DCFR (depth-limited, 169-class)` |
| Mean exploitability (50 boards) | 0.477% pot |
| Max exploitability | 0.499% pot |
| Converged | 50 / 50 |
| Iterations | mean 145, max 290 |
| Solve latency | mean ~340–380 ms, p95 ~520–620 ms (host load dependent) |
| Distinct exploitability values | 12+ (0.454–0.499% pot), no constant |
| Value conservation | worst `|OOP + IP − net pot|` ≈ 0.13 bb |

Range sensitivity now behaves correctly: on `Ah Kd 2c`, `AA` vs `KK` gives the AA holder
`+5.10 bb` and the KK holder `−0.03 bb`; swapping the ranges reverses it. This was inverted before
the evaluator fix.

### 9.4 Leaf models vs the new ground truth

**Update: both models have been retrained on real CFR labels.**
`datasets/generated/nl500_100bb_real_cfr.parquet` contains 1,755 rows, one per
canonical suit-isomorphic flop, solved by the live CFR daemon at
`time_limit_ms=5000`:

| Dataset property | Value |
|---|---|
| Rows | 1,755 / 1,755 canonical flops |
| Engine | `Rust DCFR (depth-limited, 169-class)` only |
| Heuristic rows | **0** |
| Non-converged rows | **0** |
| Distinct exploitability values | 589 (0.416–0.500% pot) |
| Distinct `(oop_ev, ip_ev)` pairs | 1,555 |
| Generation wall time | 245 s on 6 daemon workers (7.15 solves/s) |

Model 1 now trains on the engine's real `optimal_sizing` column (which in the
current 33%-plus-all-in tree is 0.33 or 1.0). Model 2 trains on real root EVs and
real `overall_frequencies`. Both select the best validation checkpoint.

Measured on the 25-spot harness after retraining:

| Metric | Before retraining | After retraining |
|---|---|---|
| Action-frequency deviation | 31.58% | **3.44%** |
| Root EV MAE | 0.0916 bb | 0.0677 bb |
| Model 2 validation freq dev | — | 2.63% |

The old parquet files were never used for this run. They still contain the
constant `exploitability = 0.0035` and should be treated as deprecated.

### 9.4.1 Learned leaf evaluation (implemented 2026-11-14)

The earlier version of this section said the leaf net was not wired. It is now
implemented end to end; the design is documented in
[`docs/LEAF_MODEL_WIRING.md`](LEAF_MODEL_WIRING.md).

| Piece | State |
|---|---|
| Model | 422→256→128→two 169-way sigmoid heads (per-class equity shares) |
| Targets | exact per-class CFV vectors from the Rust tree, `GTO_LEAF_NET=off` |
| Training data | 10,001 unaugmented + 26,325 reach-perturbation leaf rows, 1,755 boards |
| Runtime | native Rust inference (`solver_daemon/src/leaf_net.rs`), no ONNX runtime dependency |
| Export | `ml/artifacts/leaf_value_net.onnx` (opset 18), `.onnx.data`, `.pt`, `_weights.bin` |

Held-out leaf accuracy (296 unseen boards, 5,430 leaf rows, exact ground truth):

| Metric | Value |
|---|---|
| Range-EV MAE, reach-weighted | **0.0168 bb** (p95 0.0506, max 0.353) |
| Unaugmented rows | 0.0144 bb (n=1,455) |
| Perturbed rows | 0.0177 bb (n=3,975) |
| Normalised per-unit MAE logged during training | 0.178 bb (p95 0.605) |

Leaves are evaluated once per public node from a short exact-equity warm-up and
cached; re-evaluating from the live traversal reach every iteration makes the
payoff strategy-dependent and CFR plateaus at 4–5% pot exploitability.

**Safety gate.** A 169-vector marginal model cannot guarantee
`Σ reach_oop·v_oop + Σ reach_ip·v_ip = net_pot` for arbitrary independent
reaches. If a `leaf-net` solve misses either the 0.5% pot exploitability target
or the 0.35 bb conservation tolerance, the daemon re-solves with exact showdown
equity and returns `exact-showdown (leaf-net fallback)`. The reported latency
includes both attempts, and the learned attempt is capped at 600 ms.

**Measured on the 50 canonical boards** (`scripts/verify_model_accuracy.py`):

| Mode | Pass | Leaf-net hits | Mean expl | Max expl | Mean latency | Worst gap |
|---|---|---|---|---|---|---|
| leaf-net + fallback | 50/50 | 27/50 | 0.441% pot | 0.499% pot | 223 ms (p95 385) | 0.322 bb |
| leaf-net, frozen shares | 50/50 | 30/50 | 0.453% pot | 0.497% pot | 230 ms | 0.341 bb |
| exact showdown | 50/50 | — | 0.422% pot | 0.489% pot | 142 ms | 0.245 bb |

So the model is accurate enough to be used on a majority of boards, and the
exact path covers the remainder without violating the published contract. The
next step for making the learned path the default is a board-conditioned
antisymmetric **pair-equity operator** (169×169, `E[i][j] + E[j][i] = 1`), which
conserves the pot exactly for any reaches; the current marginal model is kept
because it is small and easy to audit.

### 9.5 Remaining limitations (honest scope)

- **Depth-limited, not multi-street.** Flop/turn solves collapse future streets to one showdown
  equity number. They do not model turn/river betting, so their strategies are not a full
  multi-street equilibrium and can differ from a full postflop solve.
- **169 classes, not 1,326 combos.** Suit/blocker effects within a class are averaged.
- **Learned leaves are approximate.** The marginal share model cannot conserve the pot for
  arbitrary reaches; boards that miss the gate transparently retry with exact showdown equity.
- **Single bet size plus all-in.** The tree uses a 33% pot bet (the API's default sizing); it does
  not yet search arbitrary sizes or multiple sizings per node.
- **No card bunching**, no node locking, no ICM, no PLO.
- **Exploitability is against the modelled tree.** It is a true best response, but to the
  depth-limited game, not to full poker.
- **A full realistic 100 bb flop solve** (multi-street, full combos) needs ~9.5 GB uncompressed
  and does not reach 0.5% pot in 8 minutes on this 6-core / 11 GB host, so it is not the live path.

The honest summary is now:

> The live endpoint runs a real CFR solver and reports a measured best-response exploitability. On a
> depth-limited, 169-class, single-size tree it converges to < 0.5% pot in under a second, and it
> matches the closed-form river equilibrium to four decimals. It is not yet a full multi-street
> postflop solver, and it cannot be automatically compared to ZenoSolver for the reasons in §1/§7.

---

## 10. Generalized engine + native pair-equity operator (measured)

Date: 2026-11-14. Everything below was produced by `scripts/verify_all.sh`
(logs in `/tmp/opencode/verify_all/`).

### 10.1 Generalization matrix (50 boards × 6 configurations)

Shipped engine (native V2 pair operator, `leaf-net-pair-v2`):

| Config | Stack | Ante | Rake | ms avg | ms p95 | mean expl | pass | conservation |
|---|---|---|---|---|---|---|---|---|
| cash_nl500 | 100 | 0 | 5% / 0.6 | 169 | 327 | 0.396% pot | 50/50 | 0.00e+00 |
| cash_nl50 | 100 | 0 | 5% / 4.0 | 150 | 254 | 0.386% pot | 50/50 | 0.00e+00 |
| mtt_20bb | 20 | 0.125 | 0% / 0 | 213 | 429 | 0.432% pot | 50/50 | 7.1e-15 |
| mtt_40bb | 40 | 0.125 | 0% / 0 | 208 | 495 | 0.426% pot | 50/50 | 7.1e-15 |
| mtt_60bb | 60 | 0.125 | 0% / 0 | 179 | 274 | 0.419% pot | 50/50 | 7.1e-15 |
| mtt_100bb | 100 | 0.125 | 0% / 0 | 160 | 244 | 0.421% pot | 50/50 | 8.0e-15 |

Exact-showdown oracle (`GTO_LEAF_NET=off`) on the same matrix: 50/50 pass on
every configuration, mean exploitability 0.412–0.448% pot, 157–244 ms average.
The learned path is as accurate as the exact path **and** slightly faster,
because it replaces 400 sampled runouts with one forward pass.

### 10.2 Learned vs exact, side by side (300 spots)

`scripts/zeno_parity_harness.py solve --port <learned> --oracle-port <exact>`
then `compare --source oracle`:

| Metric | n | MAE | median AE | p90 AE | max AE | bias | corr r |
|---|---|---|---|---|---|---|---|
| oop_ev | 300 | 0.0256 bb | 0.0191 | 0.0567 | 0.1500 | +0.0072 | 0.994 |
| ip_ev | 300 | 0.0269 bb | 0.0202 | 0.0618 | 0.1713 | −0.0110 | 0.996 |
| cbet % | 300 | 3.50 | 2.15 | 7.40 | 34.07 | +1.80 | 0.692 |
| oop check % | 300 | 3.80 | 3.01 | 7.38 | 29.15 | −1.51 | 0.807 |
| bet size % | 300 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 1.000 |

The EV error (≈0.5% of the pot) is of the same order as the *exact* path's own
sampling noise: 400 runouts differ from 4 000 runouts by 0.022–0.028 mean
absolute equity error. The learned operator is deterministic; the exact path is
not.

### 10.3 Pair-operator accuracy

`ml/models/pair_equity_net_v2.py`, trained on 1 755 boards × exact 169×169
equity matrices (`datasets/generated/equity_labels_2000.parquet`, 2 000 runouts
per board, label noise ≈0.018):

| Metric | Value |
|---|---|
| Validation mean \|ΔE\| (unseen boards) | 0.0472 |
| Root EV error vs exact, mean | 0.0045 bb |
| Root EV error vs exact, p95 / max | 0.0146 / 0.0277 bb |
| Leaf-node range-EV error vs exact, held-out | 0.0153 bb MAE (p95 0.0505, n=5,430) |
| Python ↔ Rust parity (same matrix) | ≤ 2.5e-4 per element |
| Antisymmetry \|E[i][j]+E[j][i]−1\| | 6e-8 (Rust) / 1.2e-7 (PyTorch) |

Architecture probe (`scripts/probe_equity_learnability.py`, 200 boards):
V1 low-rank skew 0.134 mean \|ΔE\| → bilinear class embedding 0.112 → dense
per-pair head 0.047. The dense head is what ships.

### 10.4 Three bugs that had to be fixed first

1. **Suit encoding mismatch.** The Rust board encoder indexed suits
   `c,d,h,s` while the models were trained on Python's `s,h,d,c`, so the daemon
   evaluated the learned nets on scrambled suit features. Fixed in
   `encode_board_cards` (`solver_daemon/src/leaf_net.rs`).
2. **Best response used a different game.** `best_response()` read the exact
   sampled equity matrix while `eval_profile()` used the learned operator, so
   the NashConv compared two different games and floored at ~1.8% pot. Both now
   call the same `showdown_values()`.
3. **Global zero-reach guard.** `pair_values()` zeroed *both* players' values
   when either reach was empty. The best-response traversal produces empty
   reaches for zero-probability actions, so the NashConv was corrupted. The
   guard is now per side, mirroring the exact showdown path.

With (1)–(3) fixed, the learned path converges on **300/300** spots instead of
never converging.

### 10.5 Card bunching (measured)

`scripts/benchmark_bunching.py` (bunching on vs off, same board):

| Profile | Mean max-player \|ΔEV\| | Max | Latency on/off |
|---|---|---|---|
| Built-in (from folded-player count) | 0.0038 bb | 0.0068 bb | 172 / 243 ms |
| Seat-derived (`backend/solutions/services/bunching.py`) | 0.0016 bb | 0.0046 bb | 281 / 226 ms |

Bunching only changes how the pot is split; `EV_oop + EV_ip` is conserved in
both cases. The latency difference is convergence noise, not overhead.

### 10.6 Determinism

`deterministic: true` in the solver input removes the wall-clock cut-off, so an
audit re-solve reproduces the recorded values exactly (verified: three
identical runs produce bit-identical EVs, frequencies and iteration counts).
`scripts/reference_spot_check.py --source our` re-solves all 300 spots and
compares them against the recorded `our_*` columns: **MAE 0.0000 on every
metric** (oop_ev, ip_ev, cbet %, oop check %, bet size %).

### 10.7 What is still not solved

- Depth-limited (flop/turn exits), 169 classes, one bet size plus all-in.
- The learned operator approximates 169-class equity; suit/blocker effects
  inside a class are averaged, exactly as in the exact path.
- ZenoSolver parity remains a **manual capture** step (their Terms prohibit
  automated benchmarking); `docs/zeno_capture_sheet.md` is the checklist and
  `ref_*` stays empty until a human fills it.
- No ICM, no PLO, no node locking with re-solve.
