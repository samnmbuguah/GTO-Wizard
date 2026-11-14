use serde::{Deserialize, Serialize};
use solver_daemon::{evaluate_and_solve, generate_canonical_flops, ActionFrequencies, SolverInput};
use std::collections::HashMap;
use std::env;
use std::fs::{create_dir_all, File};
use std::io::{BufWriter, Write};
use std::path::Path;
use std::time::Instant;

/// Full training dataset record adhering to datasets/SCHEMA.md
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct LeafDataRecord {
    pub spot_id: String,
    pub street: String,
    pub board: Vec<String>,
    pub position_oop: String,
    pub position_ip: String,
    pub pot: f64,
    pub effective_stack: f64,
    pub pot_type: String,
    pub rake_percent: f64,
    pub rake_cap: f64,
    pub max_bets_per_node: usize,
    pub oop_range: HashMap<String, f64>,
    pub ip_range: HashMap<String, f64>,
    pub oop_ev: f64,
    pub ip_ev: f64,
    pub exploitability: f64,
    pub solve_time_ms: u128,
    pub overall_frequencies: ActionFrequencies,
    pub strategy: HashMap<String, ActionFrequencies>,
}

#[derive(Clone, Copy, Debug)]
pub struct SpotDef {
    pub name: &'static str,
    pub pot_type: &'static str,
    pub pos_oop: &'static str,
    pub pos_ip: &'static str,
    pub pot: f64,
    pub effective_stack: f64,
}

pub const STANDARD_11_SPOTS: [SpotDef; 11] = [
    // 5 Single Raised Pots (SRP)
    SpotDef { name: "srp_btn_bb", pot_type: "SRP", pos_oop: "BB", pos_ip: "BTN", pot: 5.5, effective_stack: 97.5 },
    SpotDef { name: "srp_co_bb", pot_type: "SRP", pos_oop: "BB", pos_ip: "CO", pot: 5.5, effective_stack: 97.5 },
    SpotDef { name: "srp_mp_bb", pot_type: "SRP", pos_oop: "BB", pos_ip: "MP", pot: 5.5, effective_stack: 97.5 },
    SpotDef { name: "srp_utg_bb", pot_type: "SRP", pos_oop: "BB", pos_ip: "UTG", pot: 5.5, effective_stack: 97.5 },
    SpotDef { name: "srp_sb_bb", pot_type: "SRP", pos_oop: "SB", pos_ip: "BB", pot: 6.0, effective_stack: 97.0 },
    // 4 3-Bet Pots (3BP)
    SpotDef { name: "3bet_btn_sb", pot_type: "3BET", pos_oop: "SB", pos_ip: "BTN", pot: 21.0, effective_stack: 90.0 },
    SpotDef { name: "3bet_co_btn", pot_type: "3BET", pos_oop: "CO", pos_ip: "BTN", pot: 16.5, effective_stack: 92.5 },
    SpotDef { name: "3bet_bb_btn", pot_type: "3BET", pos_oop: "BB", pos_ip: "BTN", pot: 22.5, effective_stack: 89.0 },
    SpotDef { name: "3bet_bb_sb", pot_type: "3BET", pos_oop: "SB", pos_ip: "BB", pot: 18.0, effective_stack: 91.0 },
    // 2 4-Bet Pots (4BP)
    SpotDef { name: "4bet_btn_bb", pot_type: "4BET", pos_oop: "BB", pos_ip: "BTN", pot: 46.5, effective_stack: 77.0 },
    SpotDef { name: "4bet_sb_bb", pot_type: "4BET", pos_oop: "SB", pos_ip: "BB", pot: 44.0, effective_stack: 78.0 },
];

fn build_spot_ranges(spot: &SpotDef) -> (HashMap<String, f64>, HashMap<String, f64>) {
    let mut oop_range = HashMap::new();
    let mut ip_range = HashMap::new();

    let ranks = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"];

    for (i, r1) in ranks.iter().enumerate() {
        for (j, r2) in ranks.iter().enumerate() {
            if i == j {
                let pair = format!("{}{}", r1, r2);
                let (w_oop, w_ip) = match spot.pot_type {
                    "SRP" => {
                        let ip_w = if spot.pos_ip == "UTG" { if i <= 4 { 1.0 } else { 0.2 } }
                                   else if spot.pos_ip == "MP" { if i <= 5 { 1.0 } else { 0.5 } }
                                   else if spot.pos_ip == "CO" { if i <= 8 { 1.0 } else { 0.7 } }
                                   else { 1.0 }; // BTN / SB
                        let oop_w = if i <= 1 { 0.15 } else if i <= 6 { 0.85 } else { 0.95 };
                        (oop_w, ip_w)
                    }
                    "3BET" => {
                        // 3-bettor has AA-QQ, AK at high frequency
                        if spot.pos_oop == "SB" || spot.pos_oop == "BB" {
                            let oop_w = if i <= 2 { 1.0 } else if i <= 6 { 0.60 } else { 0.10 };
                            let ip_w = if i <= 1 { 0.30 } else if i <= 6 { 0.80 } else { 0.20 };
                            (oop_w, ip_w)
                        } else {
                            let oop_w = if i <= 1 { 0.20 } else if i <= 5 { 0.75 } else { 0.20 };
                            let ip_w = if i <= 2 { 1.0 } else if i <= 6 { 0.50 } else { 0.10 };
                            (oop_w, ip_w)
                        }
                    }
                    "4BET" => {
                        let oop_w = if i <= 2 { 0.80 } else if i <= 4 { 0.60 } else { 0.05 };
                        let ip_w = if i <= 1 { 1.0 } else if i <= 3 { 0.75 } else { 0.05 };
                        (oop_w, ip_w)
                    }
                    _ => (0.5, 0.5),
                };
                oop_range.insert(pair.clone(), w_oop);
                ip_range.insert(pair, w_ip);
            } else if i < j {
                let suited = format!("{}{}s", r1, r2);
                let (w_oop, w_ip) = match spot.pot_type {
                    "SRP" => (0.70, if spot.pos_ip == "UTG" { 0.50 } else { 0.85 }),
                    "3BET" => (0.60, 0.60),
                    "4BET" => (if i == 0 && j <= 2 { 0.75 } else { 0.05 }, if i == 0 && j <= 2 { 0.90 } else { 0.05 }),
                    _ => (0.50, 0.50),
                };
                oop_range.insert(suited.clone(), w_oop);
                ip_range.insert(suited, w_ip);
            } else {
                let offsuit = format!("{}{}o", r2, r1);
                let (w_oop, w_ip) = match spot.pot_type {
                    "SRP" => (0.40, if spot.pos_ip == "UTG" { 0.20 } else { 0.50 }),
                    "3BET" => (0.25, 0.25),
                    "4BET" => (if i == 0 && j == 1 { 0.60 } else { 0.0 }, if i == 0 && j == 1 { 0.80 } else { 0.0 }),
                    _ => (0.20, 0.20),
                };
                oop_range.insert(offsuit.clone(), w_oop);
                ip_range.insert(offsuit, w_ip);
            }
        }
    }

    (oop_range, ip_range)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();

    let mut num_boards: usize = 50;
    let mut rake_pct: f64 = 5.0;
    let mut rake_cap: f64 = 3.0;
    let mut stack_bb: f64 = 100.0;
    let mut pot: f64 = 6.5;
    let mut open_size: f64 = 2.5;
    let mut all_spots_flag = false;
    let mut out_path = "datasets/generated/leaf_dataset_50_boards.jsonl".to_string();

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--num-boards" | "-n" => {
                if i + 1 < args.len() {
                    num_boards = args[i + 1].parse().unwrap_or(50);
                    i += 1;
                }
            }
            "--rake-pct" => {
                if i + 1 < args.len() {
                    rake_pct = args[i + 1].parse().unwrap_or(5.0);
                    i += 1;
                }
            }
            "--rake-cap" => {
                if i + 1 < args.len() {
                    rake_cap = args[i + 1].parse().unwrap_or(3.0);
                    i += 1;
                }
            }
            "--stack-bb" => {
                if i + 1 < args.len() {
                    stack_bb = args[i + 1].parse().unwrap_or(100.0);
                    i += 1;
                }
            }
            "--pot" => {
                if i + 1 < args.len() {
                    pot = args[i + 1].parse().unwrap_or(6.5);
                    i += 1;
                }
            }
            "--open-size" => {
                if i + 1 < args.len() {
                    open_size = args[i + 1].parse().unwrap_or(2.5);
                    i += 1;
                }
            }
            "--all-spots" => {
                all_spots_flag = true;
            }
            "--out" | "-o" => {
                if i + 1 < args.len() {
                    out_path = args[i + 1].clone();
                    i += 1;
                }
            }
            _ => {}
        }
        i += 1;
    }

    println!("===============================================================================");
    println!(" ⚡ HIGH-PERFORMANCE RUST HEADLESS BATCH SOLVER (DEPTH-LIMITED LEAF GENERATOR)");
    println!("===============================================================================");
    println!("  • Canonical Boards : {}", num_boards);
    println!("  • Mode             : {}", if all_spots_flag { "ALL 11 SPOTS x 3 TRANSITIONS (DLS LEAF NET)" } else { "SINGLE SPOT (SRP BTN vs BB)" });
    println!("  • Rake Structure   : {:.1}% (Cap: {:.2}bb)", rake_pct, rake_cap);
    println!("  • Baseline Stack   : {:.1}bb (Open: {:.1}bb)", stack_bb, open_size);
    println!("  • Output File      : {}", out_path);
    println!("-------------------------------------------------------------------------------");

    if let Some(parent) = Path::new(&out_path).parent() {
        create_dir_all(parent)?;
    }

    let file = File::create(&out_path)?;
    let mut writer = BufWriter::with_capacity(16 * 1024 * 1024, file);

    let canonical_boards = generate_canonical_flops(num_boards);
    let total_start = Instant::now();
    let mut total_records_written: usize = 0;

    let active_spots: Vec<SpotDef> = if all_spots_flag {
        STANDARD_11_SPOTS.to_vec()
    } else {
        vec![SpotDef {
            name: "srp_btn_bb",
            pot_type: "SRP",
            pos_oop: "BB",
            pos_ip: "BTN",
            pot,
            effective_stack: stack_bb,
        }]
    };

    println!("⚡ Solving across {} spot configurations...", active_spots.len());

    for spot in &active_spots {
        let (oop_range, ip_range) = build_spot_ranges(spot);

        for board in &canonical_boards {
            let board_tag = board.join("").to_lowercase();

            if all_spots_flag {
                // 3 Turn Exit Leaf Trajectories per spot x board:
                // 1. check_check
                // 2. bet_call
                // 3. check_bet_call
                let transitions = [
                    ("check_check", 0.0),
                    ("bet_call", 0.33),
                    ("check_bet_call", 0.33),
                ];

                for (trans_name, bet_pct) in &transitions {
                    let bet_size = (spot.pot * bet_pct * 10.0).round() / 10.0;
                    let leaf_pot = (spot.pot + (2.0 * bet_size) * 10.0).round() / 10.0;
                    let leaf_stack = ((spot.effective_stack - bet_size) * 10.0).round() / 10.0;

                    let input = SolverInput {
                        board: board.clone(),
                        oop_range: oop_range.clone(),
                        ip_range: ip_range.clone(),
                        pot: leaf_pot,
                        effective_stack: leaf_stack,
                        rake_percent: rake_pct,
                        rake_cap,
                        max_sizes_per_node: 1,
                        target_d_ev: 0.005,
                        max_iterations: 200,
                        time_limit_ms: 1500,
                        collect_leaves: false,
                        bet_fraction: None,
                        ante_bb: 0.0,
                        num_folded_players: 4,
                        use_bunching: true,
                    };

                    let solve_start = Instant::now();
                    let output = evaluate_and_solve(input);
                    let solve_elapsed = solve_start.elapsed().as_millis();

                    let spot_id = format!("{}_{}_{}_{:.0}bb", spot.name, board_tag, trans_name, stack_bb);

                    let record = LeafDataRecord {
                        spot_id,
                        street: "turn".to_string(),
                        board: board.clone(),
                        position_oop: spot.pos_oop.to_string(),
                        position_ip: spot.pos_ip.to_string(),
                        pot: leaf_pot,
                        effective_stack: leaf_stack,
                        pot_type: spot.pot_type.to_string(),
                        rake_percent: rake_pct,
                        rake_cap,
                        max_bets_per_node: 1,
                        oop_range: oop_range.clone(),
                        ip_range: ip_range.clone(),
                        oop_ev: output.oop_ev,
                        ip_ev: output.ip_ev,
                        exploitability: output.exploitability,
                        solve_time_ms: solve_elapsed.max(1),
                        overall_frequencies: output.overall_frequencies,
                        strategy: output.strategy,
                    };

                    serde_json::to_writer(&mut writer, &record)?;
                    writer.write_all(b"\n")?;
                    total_records_written += 1;

                    if total_records_written % 10000 == 0 {
                        println!(
                            "  • Solved {:>6} leaf records | Spot: {:<12} | Board: {:<9} | Leaf Pot: {:<5.1}bb",
                            total_records_written,
                            spot.name,
                            board.join(" "),
                            leaf_pot,
                        );
                    }
                }
            } else {
                let input = SolverInput {
                    board: board.clone(),
                    oop_range: oop_range.clone(),
                    ip_range: ip_range.clone(),
                    pot: spot.pot,
                    effective_stack: spot.effective_stack,
                    rake_percent: rake_pct,
                    rake_cap,
                    max_sizes_per_node: 1,
                    target_d_ev: 0.005,
                    max_iterations: 200,
                    time_limit_ms: 1500,
                    collect_leaves: false,
                    bet_fraction: None,
                    ante_bb: 0.0,
                    num_folded_players: 4,
                    use_bunching: true,
                };

                let solve_start = Instant::now();
                let output = evaluate_and_solve(input);
                let solve_elapsed = solve_start.elapsed().as_millis();

                let spot_id = format!("{}_{}_{:.0}bb", spot.name, board_tag, stack_bb);

                let record = LeafDataRecord {
                    spot_id,
                    street: "flop".to_string(),
                    board: board.clone(),
                    position_oop: spot.pos_oop.to_string(),
                    position_ip: spot.pos_ip.to_string(),
                    pot: spot.pot,
                    effective_stack: spot.effective_stack,
                    pot_type: spot.pot_type.to_string(),
                    rake_percent: rake_pct,
                    rake_cap,
                    max_bets_per_node: 1,
                    oop_range: oop_range.clone(),
                    ip_range: ip_range.clone(),
                    oop_ev: output.oop_ev,
                    ip_ev: output.ip_ev,
                    exploitability: output.exploitability,
                    solve_time_ms: solve_elapsed.max(1),
                    overall_frequencies: output.overall_frequencies,
                    strategy: output.strategy,
                };

                serde_json::to_writer(&mut writer, &record)?;
                writer.write_all(b"\n")?;
                total_records_written += 1;
            }
        }
    }

    writer.flush()?;
    let total_elapsed = total_start.elapsed();
    let avg_per_spot = if total_records_written > 0 {
        (total_elapsed.as_micros() as f64 / total_records_written as f64) / 1000.0
    } else {
        0.0
    };

    println!("-------------------------------------------------------------------------------");
    println!("✅ Batch generation successfully completed!");
    println!("  • Total records generated : {}", total_records_written);
    println!("  • Total wall time         : {:.2?}", total_elapsed);
    println!("  • Avg latency per solve   : {:.3} ms", avg_per_spot);
    println!("  • File written to         : {}", out_path);
    println!("===============================================================================");

    Ok(())
}
