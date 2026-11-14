# ZenoSolver vs. GTO-Wizard: Feature Gap & UI Review

Date: 2026-11-12
Reviewed surface: public pages of zenosolver.com (`/`, `/about`, `/browse`, `/study`, `/play.html`) and the
public screenshots on the About page. No solver output was scraped (see "Access constraints" below).

---

## 1. Access constraints (important)

ZenoSolver does **not** expose a public API. The browser app calls private endpoints such as
`/api/flop3`, `/api/play/*`, `/api/icmpre*`, `/api/library*` and `/api/bunch/*`, and the origin
actively blocks non-browser clients:

```
POST https://zenosolver.com/api/auth/invite-cookie -> 403
{"error":"Automated access is not allowed (see Terms)."}
```

Their Terms of Use (updated 2 Nov 2026), section 3, prohibit bots/AI agents/scripts from browsing,
querying or scraping the service, and section 4 prohibits benchmarking or analysing it to build or
improve a competing product. This project is a competing solver product, so we must not automate
comparison against them. Normal human browsing is free and needs no login (an invite code is set
automatically as a cookie).

**Consequence for the accuracy work:** direct automated A/B comparison against Zeno is off the table.
The legitimate ways to validate our engine are:

1. compare against an independent open-source CFR solver, or
2. compare against reference values a human reads from Zeno during normal use, and
3. compare against published/known reference solutions.

The harness in `scripts/reference_spot_check.py` implements (2) and works for any reference source.

---

## 2. What ZenoSolver actually ships

Observed from the public site, About page and screenshots:

| # | Feature | Notes |
|---|---------|-------|
| 1 | **Hold'em flop solver** | Full postflop tree, 2 s to 0.1% pot exploitability, 1.5-card bunching-aware. |
| 2 | **Automatic bet sizing** | Model picks one size in 20–150% pot per node; adds a second only if it gains ≥0.05% pot; all-in always available. |
| 3 | **Preflop library** | Pre-solved 6-max cash and tournament trees. |
| 4 | **Custom preflop / ICM** | Up to 9 players, stacks, antes, payout structure; re-solves with ICM. |
| 5 | **Preflop node-locking** | Lock a range frequency or specific hands, re-solve; toggle Node-locked/GTO. |
| 6 | **Postflop node-locking** | Includes aggregate frequencies across every river card (e.g. "3rd barrel 85% across all rivers"), re-solve in ~2.8 s. |
| 7 | **River reports** | Strategy for every river at once for a given turn line. |
| 8 | **Play vs. solver** | Full hands, solver frequencies + EV loss per action, mistake/history tracking, review, jump to strategy. |
| 9 | **Hand history analyzer** | Upload/analyze played hands. |
| 10 | **Card bunching** | Up to 4 folded players (6-max); compare with/without bunching. |
| 11 | **PLO** | Separate PLO/O8/PLO5 keys visible in the bundle. |
| 12 | **My trees** | Saved custom solves. |
| 13 | **Share links** | `Copy link` on every solution; shared/spots endpoints. |
| 14 | **Study UX** | Strategy / Strategy+EV / EV / Equity tabs, 13×13 range matrix, hand detail (combos, weight, EV, EV diff), category breakdown. |
| 15 | **Drills / library / presets / personas / history / inbox** | Full account feature set, but core study is usable without login. |
| 16 | **i18n + phone layout** | en/ja/ru, dedicated phone layout. |

### Zeno UI assessment

The design is a **dense study terminal**, not a dashboard:

- Near-black canvas, one primary screen; almost no chrome. Navigation is a thin top bar
  (Study / Reports / Play / Hand history analyzer) and the rest of the screen is the solution.
- The **tree path is the layout**: a horizontal strip of cards for flop → turn → river, each showing
  pot, effective stack, and the available actions with frequencies. Clicking a card moves the node.
- The **13×13 matrix** uses poker-standard semantics: red = bet/raise, green = check, blue = call,
  with the current action selected by a tab. Values are readable at 9–11 px because the palette
  carries the meaning.
- The **right rail** combines action summary (frequency + combos), EV, equity, and a hand-detail
  table sorted by EV, with an **EV diff vs. best action** column. Every hand can be expanded to combos.
- **Category breakdown** (trips/two pair/pair/high card) under the matrix, plus a range weight bar.
- **Play from here** turns any node into a training hand; Play mode shows the table, the advisor
  frequencies, EV loss per choice, and a "View strategy here" link.
- **Copy link** and "Looks wrong?" feedback sit in the footer; the app is share-first and keyboard-friendly.
- Solve latency is low enough that there are no loading states in the study flow.

What is worth borrowing (not copying):

1. The **action-history strip** as the primary navigation object.
2. The **EV diff column** and combo-level hand detail.
3. **Strategy / Strategy+EV / EV / Equity** as one-click views of the same data.
4. **Category breakdown** and range-weight bar.
5. **Play from here** + EV loss per action in Play mode.
6. **Copy link / share** for every spot.
7. **Colour semantics** (red bet, green check, blue call) and a darker, lower-chrome canvas.
8. **No-login free study** with an optional account for saving.

---

## 3. What we have today

| Area | Status | Evidence |
|------|--------|----------|
| React + Django + Rust daemon skeleton | Present | `frontend/`, `backend/`, `solver_daemon/` |
| Auth + demo user | Present | `LoginView`, token auth, `seed.py` |
| Solution library from DB | Present (seeded with 1–6 hands per solution) | `LibraryView`, `seed.py` |
| 13×13 strategy matrix | Present | `StrategyMatrix.tsx` |
| Equity chart | **Fabricated** (hard-coded arrays by texture) | `EquityDistributionView` in `views.py` |
| Decision tree | Present, DB-node based | `DecisionTree.tsx` |
| Node locking | Present in UI + DB, but **no re-solve** | `StrategyMatrix.tsx`, `StrategyLock` model |
| Drill/quiz mode | Present (Fold/Call/Raise quiz) | `StudyView.tsx` |
| Aggregate reports | Present over stored nodes | `AggregateReportView` |
| `.sif` upload | Present (zip `metadata.json` + `nodes.json`) | `utils.py` |
| Live flop solve | **Real depth-limited CFR+** (169 classes, river exact, future streets = showdown equity) | `solver_daemon/src/cfr.rs`, `engine_bridge.py` |
| Auto sizing | **Model retrained on real CFR `optimal_sizing`** (33% / all-in); still no live size search | `ml/models/size_predictor.py`, `ml/train.py` |
| Leaf EV model | **Wired into the Rust solver**: range-conditioned 169-class equity-share net with native inference; exact-showdown fallback if gates are missed | `ml/models/leaf_value_net.py`, `solver_daemon/src/leaf_net.rs` |
| Preflop library | Missing | — |
| Custom preflop / ICM | Missing | — |
| Real preflop / postflop node locking + re-solve | Missing (lock is cosmetic) | — |
| River reports | Missing | — |
| Play vs. solver with EV loss | Missing (quiz only) | — |
| Hand history analyzer | Missing | — |
| Card bunching | **Implemented** (rank-weighted removal via `num_folded_players`) | `solver_daemon/src/cfr.rs` (`card_bunching_weights`) |
| PLO | Missing | — |
| My trees / saved custom solves | Partial (solutions table) | — |
| Share links | Missing | — |
| i18n / phone-specific layout | Missing | — |

---

## 4. Gap priority

### P0 — make the product truthful and usable

1. ~~**Real CFR engine.**~~ **Done (depth-limited).** `solver_daemon/src/cfr.rs` now runs CFR+ on a
   public betting tree with a real best-response exploitability. Flop/turn solves collapse future
   streets to showdown equity and use 169 classes; river solves are exact. Measured: mean 0.477% pot
   over 50 boards, 50/50 converged, mean 341 ms (p95 522 ms). Remaining P0 work: multi-street tree,
   full-combo ranges, and searched bet sizes. See `docs/ACCURACY_AUDIT.md` §9.
2. **Multi-street tree + action-history navigation.** One screen, flop/turn/river strip, per-node
   strategy. This is the core study loop.
3. **Free/no-login study mode.** Zeno's biggest adoption advantage. Gate only saving/history behind auth.
4. **Real equity** instead of texture-based arrays.
5. **Remove or clearly label every fabricated number.** Exploitability, EV, per-hand EV, iterations
   and the engine label are now real. The equity chart is still texture-based and the fallback engine
   is labelled `heuristic-preview (daemon unavailable)`, never presented as GTO.

### P1 — close the study-experience gap

6. **Node locking with re-solve** (preflop and postflop), plus aggregate river frequency locking.
7. **Auto sizing that is actually searched** (train the size model on real solves, or run a small
   size search per node).
8. **River reports** (all rivers for a turn line).
9. **Play mode** with EV loss, mistakes, review, "view strategy here".
10. **Hand detail table** with combos, weight, EV, EV diff; category breakdown.
11. **Share/copy link** for every spot.
12. **UI refresh**: darker canvas, colour semantics, action strip, less decorative chrome.

### P2 — differentiation

13. Custom preflop + ICM (9-handed, payouts).
14. Card bunching.
15. PLO / PLO5 / O8.
16. Hand history analyzer.
17. i18n + phone layout.

---

## 5. UI review in one paragraph

Zeno is a purpose-built study terminal: extremely high information density, a single canvas, minimal
chrome, and a workflow built around the tree path and the 13×13 matrix. Typography is small but the
red/green/blue action semantics and the EV-diff sort do the work. Our current UI is a competent dark
"workstation" dashboard with a petroleum-teal palette and heavy borders; it looks designed, but it
shows one seeded node at a time, hides the tree, puts every control behind an auth wall, and spends
screen space on labels rather than on the solution. The highest-leverage UI changes are: action-history
strip, EV-diff column, one-click Strategy/EV/Equity views, category breakdown, and a share button.

---

## 6. Verdict

Feature-wise we are missing most of Zeno's moat: multi-street solving, preflop/ICM, node-locking with
re-solve, river reports, Play mode, bunching, PLO and HH analysis. The engine gap has narrowed: the
live endpoint now runs a real CFR solver with measured exploitability (0.477% pot mean over 50
boards, 50/50 converged, ~0.3–0.9 s per flop), validated against a closed-form river equilibrium. It
is still depth-limited and 169-class, so it is not yet a full postflop solver. The UI remains closer
in spirit than the engine, and it is still built around seeded data rather than a multi-street tree.
Measured details and limitations: `docs/ACCURACY_AUDIT.md` §9.
