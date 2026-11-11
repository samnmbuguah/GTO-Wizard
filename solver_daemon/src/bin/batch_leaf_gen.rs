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

fn build_standard_ranges() -> (HashMap<String, f64>, HashMap<String, f64>) {
    let mut oop_range = HashMap::new();
    let mut ip_range = HashMap::new();

    // Standard 169 canonical hands
    let ranks = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"];
    for (i, r1) in ranks.iter().enumerate() {
        for (j, r2) in ranks.iter().enumerate() {
            if i == j {
                let pair = format!("{}{}", r1, r2);
                oop_range.insert(pair.clone(), if i <= 1 { 0.20 } else { 0.85 }); // BB flats TT-22, 3-bets AA-KK often
                ip_range.insert(pair, 1.0); // BTN opens all pairs
            } else if i < j {
                let suited = format!("{}{}s", r1, r2);
                oop_range.insert(suited.clone(), 0.70);
                ip_range.insert(suited, 0.90);
            } else {
                let offsuit = format!("{}{}o", r2, r1);
                oop_range.insert(offsuit.clone(), 0.40);
                ip_range.insert(offsuit, 0.50);
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
    println!("  • Boards to Solve  : {}", num_boards);
    println!("  • Rake Structure   : {:.1}% (Cap: {:.1}bb)", rake_pct, rake_cap);
    println!("  • Effective Stack  : {:.1}bb | Pot: {:.1}bb (Open: {:.1}bb)", stack_bb, pot, open_size);
    println!("  • Output File      : {}", out_path);
    println!("-------------------------------------------------------------------------------");

    if let Some(parent) = Path::new(&out_path).parent() {
        create_dir_all(parent)?;
    }

    let file = File::create(&out_path)?;
    let mut writer = BufWriter::new(file);

    let (oop_range, ip_range) = build_standard_ranges();
    let canonical_boards = generate_canonical_flops(num_boards);

    let total_start = Instant::now();
    let mut total_compute_ms: u128 = 0;

    for (idx, board) in canonical_boards.iter().enumerate() {
        let board_tag = board.join("").to_lowercase();
        let spot_id = format!("srp_btn_bb_{}_{:.0}bb", board_tag, stack_bb);

        let input = SolverInput {
            board: board.clone(),
            oop_range: oop_range.clone(),
            ip_range: ip_range.clone(),
            pot,
            effective_stack: stack_bb,
            rake_percent: rake_pct,
            rake_cap,
            max_sizes_per_node: 1,
            target_d_ev: 0.005,
            max_iterations: 200,
        };

        let solve_start = Instant::now();
        let output = evaluate_and_solve(input);
        let solve_elapsed = solve_start.elapsed().as_millis();
        total_compute_ms += solve_elapsed;

        let record = LeafDataRecord {
            spot_id,
            street: "flop".to_string(),
            board: board.clone(),
            position_oop: "BB".to_string(),
            position_ip: "BTN".to_string(),
            pot,
            effective_stack: stack_bb,
            pot_type: "SRP".to_string(),
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

        let line = serde_json::to_string(&record)?;
        writeln!(writer, "{}", line)?;

        if (idx + 1) % 10 == 0 || (idx + 1) == canonical_boards.len() {
            println!(
                "  [{:>3}/{:>3}] Board: {:<10} | OOP EV: {:<5.2} | IP EV: {:<5.2} | dEV: {:.4} | Solve: {}ms",
                idx + 1,
                canonical_boards.len(),
                board.join(" "),
                record.oop_ev,
                record.ip_ev,
                record.exploitability,
                record.solve_time_ms,
            );
        }
    }

    writer.flush()?;
    let total_elapsed = total_start.elapsed();
    let avg_per_board = (total_elapsed.as_micros() as f64 / num_boards as f64) / 1000.0;

    println!("-------------------------------------------------------------------------------");
    println!("✅ Batch generation successfully completed!");
    println!("  • Total spots generated : {}", num_boards);
    println!("  • Total compute time    : {} ms", total_compute_ms);
    println!("  • Total wall time       : {:.2?}", total_elapsed);
    println!("  • Avg latency per board : {:.3} ms", avg_per_board);
    println!("  • File written to       : {}", out_path);
    println!("===============================================================================");

    Ok(())
}
