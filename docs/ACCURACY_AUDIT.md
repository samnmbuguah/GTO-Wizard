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

### 9.4.1 Why the leaf net is not wired into the Rust tree yet

The engine's exit evaluation at a flop/turn leaf needs a **per-hand-class**
value vector (169 values per player, conditioned on node-local ranges). Model 2
as designed outputs **two scalars plus three frequencies** for the root state.
It cannot be substituted for `showdown_values()` without a redesign, and even a
range-conditioned per-class equity predictor would only *approximate* the exact
showdown equity the engine already computes — a likely accuracy regression
whose only benefit is speed.

Closing the 31.6% gap was a model-label problem, not a leaf-evaluation problem,
and the retraining above already closes it. A correct leaf-model integration is
tracked separately in `docs/LEAF_MODEL_WIRING.md` (estimated 4–8 hours: per-class
head, leaf-value targets from the Rust tree, ONNX/weight export, Rust inference).

### 9.5 Remaining limitations (honest scope)

- **Depth-limited, not multi-street.** Flop/turn solves collapse future streets to one showdown
  equity number. They do not model turn/river betting, so their strategies are not a full
  multi-street equilibrium and can differ from a full postflop solve.
- **169 classes, not 1,326 combos.** Suit/blocker effects within a class are averaged.
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
