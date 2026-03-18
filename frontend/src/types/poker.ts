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
}

export interface Solution {
  id: number;
  name: string;
  rake?: number;
  stack_depth?: number;
}
