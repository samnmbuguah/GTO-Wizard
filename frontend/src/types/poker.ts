export type Hand = string; // 'AA', 'AKs', 'AKo', etc.

export interface ActionFrequencies {
  [action: string]: number; // action name -> frequency (0.0 to 1.0)
}

export interface StrategyNode {
  id: number;
  path: string;
  hand: Hand;
  actions: ActionFrequencies;
  ev?: number;
  equity?: number;
  weight?: number;
  combos?: number;
}

export interface Solution {
  id: number;
  name: string;
  ante?: number;
  game_type?: string;
  rake?: number;
  stack_depth?: number;
  solver_config_id?: number;
}

export interface LiveSolvePayload {
  board: string[];
  spot?: string;
  pot?: number;
  effective_stack?: number;
  rake_percent?: number;
  rake_cap?: number;
  oop_range?: Record<string, number>;
  ip_range?: Record<string, number>;
}

export interface LiveSolveResponse {
  exploitability: number;
  solve_time_ms: number;
  iterations: number;
  strategy: Record<string, { fold: number; call: number; raise: number }>;
  overall_frequencies: { fold: number; call: number; raise: number };
  optimal_sizing: number;
  engine: string;
  oop_ev?: number;
  ip_ev?: number;
  pot?: number;
  rake_percent?: number;
  rake_cap?: number;
  btn_cbet_frequency?: number;
  bb_check_frequency?: number;
  btn_check_frequency?: number;
  street?: string;
  acting_player?: string;
  available_actions?: string[];
  action_frequencies?: Record<string, number>;
  street_closed?: boolean;
  terminal_fold?: boolean;
  next_street_pot?: number;
  next_street_stack?: number;
  posterior_oop_range?: Record<string, number>;
  posterior_ip_range?: Record<string, number>;
  alive_combos?: Record<string, number>;
  active_reach?: Record<string, number>;
  starting_oop_range?: Record<string, number>;
  starting_ip_range?: Record<string, number>;
}

