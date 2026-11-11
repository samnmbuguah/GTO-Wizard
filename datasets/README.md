# GTO-Wizard Datasets & Leaf Model Schemas

This directory stores reference poker research datasets and leaf value network architectures used to bootstrap real-time Depth-Limited Solving (DLS).

---

## 1. PokerBench (`RZ412/PokerBench`)

- **Source**: Hugging Face Dataset `RZ412/PokerBench`
- **Purpose**: 6-max No-Limit Hold'em postflop solved game scenarios and GTO decision benchmarks.
- **Postflop Test Set Fields**:
[
  "",
  "preflop_action",
  "board_flop",
  "board_turn",
  "board_river",
  "aggressor_position",
  "postflop_action",
  "evaluation_at",
  "available_moves",
  "pot_size",
  "hero_position",
  "holding",
  "correct_decision"
]

### Sample Postflop Solved Scenario:
```json
{
  "": "0",
  "preflop_action": "HJ/2.0bb/BB/call",
  "board_flop": "Ks7h2d",
  "board_turn": "Jc",
  "board_river": "7c",
  "aggressor_position": "OOP",
  "postflop_action": "OOP_CHECK/IP_CHECK/dealcards/Jc/OOP_CHECK/IP_BET_5/OOP_RAISE_14/IP_CALL/dealcards/7c/OOP_CHECK",
  "evaluation_at": "River",
  "available_moves": "['Check', 'Bet 24']",
  "pot_size": "32",
  "hero_position": "IP",
  "holding": "8h8c",
  "correct_decision": "Check"
}
```

### Key Schema Insights for Engine Integration:
1. **Cards & Board**: Standard 2-character card notation (e.g., `'Ah'`, `'Kd'`, `'2c'`).
2. **Pot & Stack Ratios**: Recorded as fractional pot commitments or exact chip stacks relative to big blind (100bb baseline).
3. **Action Frequencies**: Action labels decompose into Check/Fold, Call, and discrete Bet/Raise sizing buckets (e.g., 33%, 50%, 67%, 100%, All-in).

---

## 2. DeeperStack (`godmoves/DeeperStack`) Leaf Model Architecture

- **Source**: GitHub `godmoves/DeeperStack`
- **Purpose**: Depth-Limited Solving (DLS) leaf state evaluation and Counterfactual Value (CFV) estimation networks.
- **Identified Modules**:
  - Model definitions: `ACPCServer/net.c, ACPCServer/net.h, Source/ACPC/network_communication.lua, Source/Nn/net_builder.lua, doc/modules/net_builder.html, doc/classes/network_communication.html, Source/Nn/cpu_gpu_model_converter.lua, doc/scripts/cpu_gpu_model_converter.html`
  - Data generation pipelines: `Source/DataGeneration/aux_data_generation.lua, Source/DataGeneration/data_generation.lua, Source/DataGeneration/main_data_generation.lua, doc/scripts/main_data_generation.html, doc/modules/aux_data_generation.html, doc/modules/data_generation_call.html, doc/modules/data_generation.html`

### Leaf Value Network Tensor Specification:
| Component | Input Dimension | Format / Description |
| :--- | :--- | :--- |
| **P1 Range Tensor** | 1326 or 169 combos | Probability distribution across hole-card combinations for Out-Of-Position player |
| **P2 Range Tensor** | 1326 or 169 combos | Probability distribution across hole-card combinations for In-Position player |
| **Public Board Cards** | 52-card one-hot or 5x4 | Multi-hot binary indicator vector representing active flop/turn/river cards |
| **Pot & Effective Stack** | 2 floats | Normalized pot fraction `pot / (pot + stack)` and remaining stack depth |
| **Output Target (CFVs)** | 2 x 1326 (or 169) | Counterfactual values for every private hand combo to evaluate leaf nodes without full tree traversal |

---

## 3. Data Flow in Live Depth-Limited Solving

```
[User Flop Selection: "Ah, Kd, 2c"] 
              │
              ▼
[Dynamic Preflop Rake Interpolator] ──► Morph starting OOP/IP ranges for rake % & cap
              │
              ▼
[Normalized Solver Engine Payload] ──► Board + Morphed Ranges + Pot + Stacks + 1 Bet Size/Node
              │
              ▼
[Native Rust CFR+ Engine / Daemon] ──► 200 iterations with canonical suit isomorphism
              │
              ▼
[13x13 Strategy Matrix Delivery] ──► < 10ms solve latency back to React UI
```
