use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::Instant;

pub mod cfr;
pub mod leaf_net;

/// Standard normalized input payload adhering to Task 2 contract & SCHEMA.md
#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct SolverInput {
    pub board: Vec<String>,
    #[serde(default)]
    pub oop_range: HashMap<String, f64>,
    #[serde(default)]
    pub ip_range: HashMap<String, f64>,
    #[serde(default = "default_pot")]
    pub pot: f64,
    #[serde(default = "default_stack")]
    pub effective_stack: f64,
    #[serde(default = "default_rake")]
    pub rake_percent: f64,
    #[serde(default = "default_cap")]
    pub rake_cap: f64,
    #[serde(default = "default_max_sizes", alias = "max_bets_per_node")]
    pub max_sizes_per_node: usize,
    #[serde(default = "default_dev", rename = "target_dEV", alias = "target_d_ev")]
    pub target_d_ev: f64,
    #[serde(default = "default_iters")]
    pub max_iterations: usize,
    /// Wall-clock cap for a single solve. The live API keeps the default so it
    /// stays interactive; offline dataset generation can raise it so hard
    /// boards reach the target instead of being cut off.
    #[serde(default = "default_time_limit")]
    pub time_limit_ms: u64,
    /// Ask the solver to return the per-class counterfactual values at every
    /// showdown (flop/turn exit) node, under the averaged strategy.
    #[serde(default)]
    pub collect_leaves: bool,
    /// If set, the tree uses this bet size (fraction of pot) instead of the
    /// default 33%. The Python bridge fills it from Model 1.
    #[serde(default)]
    pub bet_fraction: Option<f64>,
    /// Dead-money ante per player in bb (0.0 for cash, 0.125 for MTT).
    #[serde(default)]
    pub ante_bb: f64,
    /// Number of folded preflop players for card bunching (e.g., 4 in 6-max BTN vs BB).
    #[serde(default = "default_folded_players")]
    pub num_folded_players: usize,
    /// Whether preflop card bunching / removal is active.
    #[serde(default = "default_use_bunching")]
    pub use_bunching: bool,
}

pub fn default_pot() -> f64 { 6.5 }
pub fn default_stack() -> f64 { 97.0 }
pub fn default_rake() -> f64 { 5.0 }
pub fn default_cap() -> f64 { 3.0 }
pub fn default_max_sizes() -> usize { 1 }
pub fn default_dev() -> f64 { 0.005 }
pub fn default_iters() -> usize { 500 }
pub fn default_time_limit() -> u64 { 1500 }
pub fn default_folded_players() -> usize { 4 }
pub fn default_use_bunching() -> bool { true }

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ActionFrequencies {
    pub fold: f64,
    pub call: f64,
    #[serde(rename = "raise")]
    pub bet_raise: f64,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct LeafSample {
    pub invested: [f64; 2],
    pub reach_oop: Vec<f64>,
    pub reach_ip: Vec<f64>,
    pub v_oop: Vec<f64>,
    pub v_ip: Vec<f64>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct SolverOutput {
    pub exploitability: f64,
    pub solve_time_ms: u128,
    pub iterations: usize,
    pub strategy: HashMap<String, ActionFrequencies>,
    pub overall_frequencies: ActionFrequencies,
    pub optimal_sizing: f64,
    pub engine: String,
    pub oop_ev: f64,
    pub ip_ev: f64,
    pub btn_cbet_frequency: f64,
    pub bb_check_frequency: f64,
    pub btn_check_frequency: f64,
    /// Per-hand action frequencies with the real action labels (Check / Bet 33% / ...).
    #[serde(default)]
    pub strategy_detail: HashMap<String, HashMap<String, f64>>,
    /// Root-player EV per hand class, in bb.
    #[serde(default)]
    pub hand_ev: HashMap<String, f64>,
    /// Exploitability in bb (NashConv / 2).
    #[serde(default)]
    pub exploitability_bb: f64,
    /// Exploitability as a percentage of the starting pot.
    #[serde(default)]
    pub exploitability_pct_pot: f64,
    /// Whether the target dEV was reached before the iteration/time budget.
    #[serde(default)]
    pub converged: bool,
    /// Number of public nodes in the solved tree.
    #[serde(default)]
    pub tree_nodes: usize,
    /// Number of turn/river runouts used for the equity leaves.
    #[serde(default)]
    pub equity_samples: usize,
    /// Per-class counterfactual values at every showdown leaf, when requested.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub leaf_samples: Vec<LeafSample>,
    /// `exact-showdown` or `leaf-net`, depending on which exit evaluator ran.
    #[serde(default)]
    pub leaf_mode: String,
}

/// Runs the real CFR engine, falling back to the historical heuristic if the
/// input cannot be solved (e.g. an invalid board). The fallback is explicitly
/// labelled so a caller cannot mistake it for a solved strategy.
pub fn evaluate_and_solve(input: SolverInput) -> SolverOutput {
    match cfr::solve(&input) {
        Ok(out) => out,
        Err(err) => {
            eprintln!("CFR solve failed ({err}); returning heuristic preview");
            let mut out = evaluate_and_solve_heuristic(input);
            out.engine = "heuristic-preview (CFR failed)".to_string();
            out.converged = false;
            out
        }
    }
}

/// Historical heuristic table kept only as a clearly-labelled preview fallback.
pub fn evaluate_and_solve_heuristic(input: SolverInput) -> SolverOutput {
    let start = Instant::now();

    let ranks = "23456789TJQKA";
    let mut board_ranks: Vec<char> = Vec::new();
    let mut board_suits: Vec<char> = Vec::new();

    for card in &input.board {
        let mut chars = card.chars();
        if let (Some(r), Some(s)) = (chars.next(), chars.next()) {
            board_ranks.push(r);
            board_suits.push(s);
        }
    }

    let high_board = board_ranks.iter().any(|&r| r == 'A' || r == 'K' || r == 'Q');
    let is_paired = {
        let mut r_sorted = board_ranks.clone();
        r_sorted.sort();
        let len_before = r_sorted.len();
        r_sorted.dedup();
        r_sorted.len() < len_before
    };

    let mut paired_rank: Option<char> = None;
    if is_paired {
        let mut counts: HashMap<char, usize> = HashMap::new();
        for &r in &board_ranks {
            *counts.entry(r).or_insert(0) += 1;
        }
        for (r, cnt) in counts {
            if cnt >= 2 {
                paired_rank = Some(r);
                break;
            }
        }
    }

    let mut sorted_suits = board_suits.clone();
    sorted_suits.sort();
    sorted_suits.dedup();
    let flush_draw = sorted_suits.len() <= 2;

    let spr = input.effective_stack / input.pot.max(1.0);
    let optimal_sizing = if high_board || is_paired {
        0.33
    } else if flush_draw || spr < 4.0 {
        0.50
    } else {
        0.67
    };

    let rake_drag = (input.rake_percent / 100.0).clamp(0.0, 0.15);
    let mut strategy: HashMap<String, ActionFrequencies> = HashMap::new();

    let mut all_hands: Vec<String> = input.oop_range.keys().cloned().collect();
    for k in input.ip_range.keys() {
        if !all_hands.contains(k) {
            all_hands.push(k.clone());
        }
    }

    if all_hands.is_empty() {
        all_hands = vec![
            "AA".into(), "KK".into(), "QQ".into(), "JJ".into(), "TT".into(),
            "AKs".into(), "AQs".into(), "AKo".into(), "AQo".into(),
            "76s".into(), "87s".into(), "22".into(), "33".into()
        ];
    }

    let mut sum_f = 0.0;
    let mut sum_c = 0.0;
    let count = all_hands.len().max(1);

    for hand in &all_hands {
        let r1 = hand.chars().next().unwrap_or('2');
        let pair = hand.len() == 2;
        let hits_top_pair = board_ranks.contains(&r1);
        
        let max_board_rank_idx = board_ranks.iter()
            .map(|&c| ranks.find(c).unwrap_or(0))
            .max()
            .unwrap_or(0);
        let hand_rank_idx = ranks.find(r1).unwrap_or(0);
        let is_overpair = pair && hand_rank_idx > max_board_rank_idx;

        let is_trips_or_fullhouse = if let Some(pr) = paired_rank {
            hand.contains(pr) || (pair && board_ranks.contains(&r1))
        } else {
            false
        };

        let (mut f, mut c, _) = if is_trips_or_fullhouse {
            (0.00, 0.45, 0.55)
        } else if is_overpair || hand == "AA" || hand == "KK" {
            (0.00, 0.20, 0.80)
        } else if hits_top_pair {
            (0.00, 0.65, 0.35)
        } else if pair {
            (0.86, 0.07, 0.07)
        } else {
            (0.368, 0.380, 0.252)
        };

        if !is_trips_or_fullhouse && f > 0.05 && f < 0.95 {
            let penalty = rake_drag * 0.3;
            f = (f + penalty).min(0.95);
            c = (c - penalty * 0.7).max(0.02);
        }

        let f_rounded = (f * 1000.0).round() / 1000.0;
        let c_rounded = (c * 1000.0).round() / 1000.0;
        let r_rounded = ((1.0 - f_rounded - c_rounded) * 1000.0).round() / 1000.0;

        strategy.insert(
            hand.clone(),
            ActionFrequencies {
                fold: f_rounded,
                call: c_rounded,
                bet_raise: r_rounded,
            },
        );

        sum_f += f_rounded;
        sum_c += c_rounded;
    }

    let elapsed = start.elapsed().as_millis();
    let n = count as f64;

    let expected_rake = (input.pot * (input.rake_percent / 100.0)).min(input.rake_cap);
    let net_pot = (input.pot - expected_rake).max(0.0);
    let ip_share = if high_board { 0.58 } else if is_paired { 0.55 } else { 0.52 };
    let ip_ev = (net_pot * ip_share * 1000.0).round() / 1000.0;
    let oop_ev = ((net_pot - ip_ev) * 1000.0).round() / 1000.0;

    let iters = input.max_iterations.max(10);
    let exploitability = ((0.05 / (iters as f64).sqrt()) * 10000.0).round() / 10000.0;

    let is_dry_ace = board_ranks.contains(&'A') && !flush_draw && !is_paired;
    let is_wet_connected = board_ranks.contains(&'9') && board_ranks.contains(&'8') && board_ranks.contains(&'7');

    let (btn_cbet_frequency, btn_check_frequency, bb_check_frequency) = if is_dry_ace {
        (0.72, 0.28, 0.98)
    } else if is_wet_connected {
        (0.52, 0.48, 0.96)
    } else if is_paired {
        (0.62, 0.38, 0.97)
    } else {
        (0.58, 0.42, 0.96)
    };

    let avg_f = (sum_f / n * 1000.0).round() / 1000.0;
    let avg_c = (sum_c / n * 1000.0).round() / 1000.0;
    let avg_r = ((1.0 - avg_f - avg_c) * 1000.0).round() / 1000.0;

    SolverOutput {
        exploitability,
        solve_time_ms: elapsed.max(1),
        iterations: iters,
        strategy,
        overall_frequencies: ActionFrequencies {
            fold: avg_f,
            call: avg_c,
            bet_raise: avg_r,
        },
        optimal_sizing,
        engine: "Rust DCFR Depth-Limited Engine".to_string(),
        oop_ev,
        ip_ev,
        btn_cbet_frequency,
        bb_check_frequency,
        btn_check_frequency,
        strategy_detail: HashMap::new(),
        hand_ev: HashMap::new(),
        exploitability_bb: exploitability * input.pot,
        exploitability_pct_pot: exploitability * 100.0,
        converged: false,
        tree_nodes: 0,
        equity_samples: 0,
        leaf_samples: Vec::new(),
        leaf_mode: "heuristic".to_string(),
    }
}

/// Generates the complete set of all 1,755 canonical non-isomorphic flops in Hold'em
pub fn get_all_canonical_flops() -> Vec<Vec<String>> {
    let ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];
    let mut flops: Vec<Vec<String>> = Vec::with_capacity(1755);

    // 1. Unpaired flops (13 choose 3 = 286 rank combinations, 5 suit patterns each = 1,430 flops)
    for i in 0..ranks.len() {
        for j in (i + 1)..ranks.len() {
            for k in (j + 1)..ranks.len() {
                let r1 = ranks[i];
                let r2 = ranks[j];
                let r3 = ranks[k];

                // Rainbow: s, h, d
                flops.push(vec![format!("{}s", r1), format!("{}h", r2), format!("{}d", r3)]);
                // Two-tone (r1 and r2 suited): s, s, h
                flops.push(vec![format!("{}s", r1), format!("{}s", r2), format!("{}h", r3)]);
                // Two-tone (r1 and r3 suited): s, h, s
                flops.push(vec![format!("{}s", r1), format!("{}h", r2), format!("{}s", r3)]);
                // Two-tone (r2 and r3 suited): h, s, s
                flops.push(vec![format!("{}h", r1), format!("{}s", r2), format!("{}s", r3)]);
                // Monotone: s, s, s
                flops.push(vec![format!("{}s", r1), format!("{}s", r2), format!("{}s", r3)]);
            }
        }
    }

    // 2. Paired flops (13 * 12 = 156 rank combinations, 2 suit patterns each = 312 flops)
    for i in 0..ranks.len() {
        for k in 0..ranks.len() {
            if i == k {
                continue;
            }
            let r1 = ranks[i];
            let r2 = ranks[k];
            // Rainbow kicker: pair s, h; kicker d
            flops.push(vec![format!("{}s", r1), format!("{}h", r1), format!("{}d", r2)]);
            // Suited kicker: pair s, h; kicker s
            flops.push(vec![format!("{}s", r1), format!("{}h", r1), format!("{}s", r2)]);
        }
    }

    // 3. Trips flops (13 rank combinations = 13 flops)
    for i in 0..ranks.len() {
        let r1 = ranks[i];
        flops.push(vec![format!("{}s", r1), format!("{}h", r1), format!("{}d", r1)]);
    }

    flops
}

/// Generates a representative set of canonical non-isomorphic flops with canonical suit mapping
pub fn generate_canonical_flops(count: usize) -> Vec<Vec<String>> {
    let all_flops = get_all_canonical_flops();
    if count >= all_flops.len() {
        return all_flops;
    }

    let step = (all_flops.len() as f64 / count as f64).max(1.0);
    let mut sampled: Vec<Vec<String>> = Vec::with_capacity(count);
    for i in 0..count {
        let idx = ((i as f64 * step) as usize) % all_flops.len();
        sampled.push(all_flops[idx].clone());
    }
    sampled
}
