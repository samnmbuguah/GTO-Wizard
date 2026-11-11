# 6-Max GTO Leaf & Postflop Dataset Specification (`SCHEMA.md`)

This document defines the standardized ground-truth schema for local training dataset generation and batch headless solves in our real-time 6-max GTO engine.

---

## 1. Overview & Architecture

To train our real-time Leaf Value Network (Counterfactual Value Estimator) for Depth-Limited Solving (DLS), we generate solved postflop spots directly on-machine. This allows strict control over:
- **Canonical suit isomorphism** (reducing duplicate board topologies from 22,100 to 1,755 canonical flops).
- **Custom rake structures** (e.g. 5% with 3.0bb cap vs. microstakes 5% with 5.0bb cap vs. rake-free 0%).
- **Single-size tree pruning** (1 bet/raise size per decision node mirroring ZenoSolver tree geometry).

---

## 2. Standard Feature & Target Schema

Each generated data record represents a solved postflop state (node) with preflop range context, board cards, pot configuration, and full strategy/EV outputs.

### 2.1 Input Features (Leaf State Encoding)

| Field Name | Type | Unit / Format | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `spot_id` | `str` | UUID / hash | Unique spot identifier | `"srp_btn_bb_as8d3c_100bb"` |
| `street` | `str` | Enum | Current postflop street (`"flop"`, `"turn"`, `"river"`) | `"flop"` |
| `board` | `List[str]` | 2-char card notation | Active community cards `[Rank][Suit]` | `["As", "8d", "3c"]` |
| `position_oop` | `str` | Table position | Out-Of-Position player position | `"BB"` |
| `position_ip` | `str` | Table position | In-Position player position | `"BTN"` |
| `pot` | `float` | Big Blinds (bb) | Total chips in pot at node start | `6.50` |
| `effective_stack`| `float` | Big Blinds (bb) | Remaining stack behind | `97.00` |
| `pot_type` | `str` | Enum | Pot classification (`"SRP"`, `"3BET"`, `"4BET"`) | `"SRP"` |
| `rake_percent` | `float` | Percent ($0.0 - 10.0$) | Rake taken from pot | `5.00` |
| `rake_cap` | `float` | Big Blinds (bb) | Maximum rake taken | `3.00` |
| `max_bets_per_node`| `int` | Integer | Branch pruning parameter (1 for Zeno DLS) | `1` |
| `oop_range` | `Dict[str, float]` | 169 combo reach | Starting range reach distribution for OOP player $[0.0, 1.0]$ | `{"AA": 0.0, "AKs": 0.15, ...}` |
| `ip_range` | `Dict[str, float]` | 169 combo reach | Starting range reach distribution for IP player $[0.0, 1.0]$ | `{"AA": 1.0, "AKs": 1.0, ...}` |

---

### 2.2 Output Targets (Ground-Truth Solved Values)

| Target Field | Type | Unit / Range | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `oop_ev` | `float` | Big Blinds (bb) | Counterfactual Expected Value for OOP player | `2.59` |
| `ip_ev` | `float` | Big Blinds (bb) | Counterfactual Expected Value for IP player | `3.58` |
| `exploitability` | `float` | Big Blinds / % pot | Convergence quality ($dEV \le 0.005$) | `0.0035` |
| `solve_time_ms` | `float` | Milliseconds | Compute time taken by native CFR engine | `1.42` |
| `overall_frequencies` | `Dict[str, float]` | Probabilities | Aggregate action distribution across entire range | `{"fold": 0.30, "call": 0.42, "raise": 0.28}` |
| `strategy` | `Dict[str, Dict[str, float]]` | 169 combos | Per-hand GTO action frequencies $\sum(\text{fold, call, raise}) = 1.0$ | See below |

#### Per-Hand Strategy Target Format:
```json
{
  "AA": { "fold": 0.00, "call": 0.20, "raise": 0.80 },
  "KK": { "fold": 0.00, "call": 0.20, "raise": 0.80 },
  "AKs": { "fold": 0.00, "call": 0.65, "raise": 0.35 },
  "72o": { "fold": 1.00, "call": 0.00, "raise": 0.00 }
}
```

---

## 3. Mathematical Constraints & Invariants

All datasets produced by our headless batch pipeline strictly conform to the following mathematical properties:

1. **Probability Normalization**:
   $$\forall h \in \text{Range}, \quad p_{\text{fold}}(h) + p_{\text{call}}(h) + p_{\text{raise}}(h) = 1.0000 \pm 0.0001$$
2. **Zero-Sum Net Value Conservation**:
   $$\text{EV}_{\text{OOP}} + \text{EV}_{\text{IP}} = \text{Pot} - \min\left(\text{Pot} \times \frac{\text{Rake}\%}{100}, \text{RakeCap}\right)$$
3. **Exploitability Threshold**:
   $$\text{Exploitability} \le 0.20\% \text{ of pot}$$

---

## 4. Comparison: PokerBench vs. Our Local DLS Schema

| Dimension | PokerBench (`RZ412/PokerBench`) | Our Local DLS Ground-Truth Schema |
| :--- | :--- | :--- |
| **Primary Use Case** | LLM benchmark evaluation (text prompt $\to$ discrete decision) | Neural network leaf value training (tensor input $\to$ EV & strategy tensor) |
| **Range Representation** | Implicit (only hero holding specified, e.g. `8h8c`) | Explicit 169/1326 range distribution vectors for both OOP & IP |
| **Board Texture** | Individual instances (flop, turn, river text) | Canonical non-isomorphic card representations with suit isomorphism |
| **Rake Modeling** | Undefined / unmodeled | Parametric rake percentage and cap (0%–10% and 0–5bb) |
| **Output Type** | Single discrete action (`"Check"`, `"Call"`, `"Fold"`, `"Bet 24"`) | Continuous mixed strategy frequencies and exact Root Counterfactual Values ($EV$) |
