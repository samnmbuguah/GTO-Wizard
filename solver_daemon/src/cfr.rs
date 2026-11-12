//! Real (depth-limited) counterfactual regret minimization engine.
//!
//! This module replaces the previous if/else "strategy table" with an actual
//! game-theoretic solve of the current street:
//!
//! * a public betting tree is built from the requested pot, stacks, rake and
//!   bet sizes;
//! * ranges are represented over the 169 canonical hand classes (normalized by
//!   the combos that survive the board);
//! * terminal showdowns are evaluated with a 7-card hand evaluator and exact
//!   (river) or sampled (turn/flop) runouts;
//! * CFR+ is run to compute a strategy, and exploitability is measured with a
//!   real best-response traversal against the average strategy.
//!
//! Scope / honest limitations (also written into the API response):
//! * only the current street is solved; future streets are replaced by their
//!   showdown equity (depth-limited solving). For a river board this is exact.
//! * hand classes are used instead of individual combos, so suit-specific
//!   flush/blocker effects are not modelled beyond the board filter.
//!
//! The number returned as `exploitability` is the real NashConv/2 of the
//! modelled game, not a formula.

use crate::{ActionFrequencies, SolverInput, SolverOutput};
use std::collections::HashMap;
use std::time::Instant;

const N_CLASSES: usize = 169;
const MAX_ACTIONS: usize = 4;

const RANK_CHARS: [char; 13] = [
    '2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A',
];
const SUIT_CHARS: [char; 4] = ['c', 'd', 'h', 's'];

#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Card {
    pub rank: u8, // 0 = 2, 12 = A
    pub suit: u8, // 0 = c, 1 = d, 2 = h, 3 = s
}

impl Card {
    fn parse(s: &str) -> Option<Card> {
        let mut chars = s.chars();
        let r = chars.next()?.to_ascii_uppercase();
        let s = chars.next()?.to_ascii_lowercase();
        let rank = RANK_CHARS.iter().position(|&c| c == r)? as u8;
        let suit = SUIT_CHARS.iter().position(|&c| c == s)? as u8;
        Some(Card { rank, suit })
    }

    fn id(self) -> usize {
        self.rank as usize * 4 + self.suit as usize
    }
}

#[derive(Clone, Debug)]
struct HandClass {
    name: String,
    combos: Vec<(Card, Card)>,
}

fn build_classes() -> Vec<HandClass> {
    let mut classes = Vec::with_capacity(N_CLASSES);
    // Pairs
    for i in 0..13u8 {
        let mut combos = Vec::new();
        for a in 0..4u8 {
            for b in (a + 1)..4u8 {
                combos.push((
                    Card { rank: i, suit: a },
                    Card { rank: i, suit: b },
                ));
            }
        }
        classes.push(HandClass {
            name: format!("{}{}", RANK_CHARS[i as usize], RANK_CHARS[i as usize]),
            combos,
        });
    }
    // Suited (high rank first)
    for i in (1..13usize).rev() {
        for j in (0..i).rev() {
            let hi = i as u8;
            let lo = j as u8;
            let mut suited = Vec::new();
            for s in 0..4u8 {
                suited.push((Card { rank: hi, suit: s }, Card { rank: lo, suit: s }));
            }
            classes.push(HandClass {
                name: format!(
                    "{}{}s",
                    RANK_CHARS[hi as usize], RANK_CHARS[lo as usize]
                ),
                combos: suited,
            });
        }
    }
    // Offsuit (high rank first)
    for i in (1..13usize).rev() {
        for j in (0..i).rev() {
            let hi = i as u8;
            let lo = j as u8;
            let mut offsuit = Vec::new();
            for a in 0..4u8 {
                for b in 0..4u8 {
                    if a != b {
                        offsuit.push((Card { rank: hi, suit: a }, Card { rank: lo, suit: b }));
                    }
                }
            }
            classes.push(HandClass {
                name: format!(
                    "{}{}o",
                    RANK_CHARS[hi as usize], RANK_CHARS[lo as usize]
                ),
                combos: offsuit,
            });
        }
    }
    classes
}

fn class_index(name: &str) -> Option<usize> {
    let n = name.trim().to_ascii_uppercase();
    let mut chars = n.chars();
    let r1 = chars.next()?;
    let r2 = chars.next()?;
    let suffix = chars.next();
    let i = RANK_CHARS.iter().position(|&c| c == r1)? as i32;
    let j = RANK_CHARS.iter().position(|&c| c == r2)? as i32;
    if i == j && suffix.is_none() {
        // Pairs are the first 13 classes, in ascending rank order.
        return Some(i as usize);
    }
    let hi = i.max(j);
    let lo = i.min(j);
    let index = 13;
    let is_suited = suffix.map(|c| c == 'S').unwrap_or(false);
    let is_offsuit = suffix.map(|c| c == 'O').unwrap_or(false);
    // Suited block
    if is_suited {
        let mut k = 0usize;
        for h in (1..13usize).rev() {
            for l in (0..h).rev() {
                if h == hi as usize && l == lo as usize {
                    return Some(index + k);
                }
                k += 1;
            }
        }
    }
    // Offsuit block
    if is_offsuit {
        let mut k = 0usize;
        for h in (1..13usize).rev() {
            for l in (0..h).rev() {
                if h == hi as usize && l == lo as usize {
                    return Some(index + 78 + k);
                }
                k += 1;
            }
        }
    }
    None
}

// ---------------------------------------------------------------------------
// Hand evaluator
// ---------------------------------------------------------------------------

fn straight_high(mask: u16) -> Option<u8> {
    // Wheel: A,2,3,4,5
    if mask & 0b1_0000_0000_1111 == 0b1_0000_0000_1111 {
        return Some(3); // 5-high
    }
    for high in (4..13).rev() {
        let need = 0b11111u16 << (high - 4);
        if mask & need == need {
            return Some(high as u8);
        }
    }
    None
}

/// Returns a comparable 32-bit score. Higher is better.
fn eval7(cards: &[Card]) -> u32 {
    let mut rank_counts = [0u8; 13];
    let mut suit_counts = [0u8; 4];
    let mut suit_masks = [0u16; 4];
    let mut rank_mask = 0u16;

    for &c in cards {
        rank_counts[c.rank as usize] += 1;
        suit_counts[c.suit as usize] += 1;
        suit_masks[c.suit as usize] |= 1 << c.rank;
        rank_mask |= 1 << c.rank;
    }

    // Flush / straight flush
    let mut flush_suit: Option<usize> = None;
    for s in 0..4 {
        if suit_counts[s] >= 5 {
            flush_suit = Some(s);
            break;
        }
    }
    if let Some(s) = flush_suit {
        let m = suit_masks[s];
        if let Some(high) = straight_high(m) {
            return (8 << 20) | (high as u32) << 16;
        }
        // Flush: top five ranks of the suit
        let mut score = 5u32 << 20;
        let mut shift: u32 = 16;
        let mut found = 0;
        for r in (0..13).rev() {
            if m & (1 << r) != 0 {
                score |= (r as u32) << shift;
                shift = shift.saturating_sub(4);
                found += 1;
                if found == 5 {
                    break;
                }
            }
        }
        return score;
    }

    // Quads
    let quad_rank = (0..13).rev().find(|&r| rank_counts[r] == 4);
    if let Some(q) = quad_rank {
        let kicker = (0..13).rev().find(|&r| r != q && rank_counts[r] > 0).unwrap_or(0);
        return (7 << 20) | ((q as u32) << 16) | ((kicker as u32) << 12);
    }

    // Full house
    let trips: Vec<usize> = (0..13).rev().filter(|&r| rank_counts[r] >= 3).collect();
    let pairs: Vec<usize> = (0..13)
        .rev()
        .filter(|&r| rank_counts[r] >= 2)
        .collect();
    if !trips.is_empty() {
        let t = trips[0];
        if let Some(&p) = pairs.iter().find(|&&r| r != t) {
            return (6 << 20) | ((t as u32) << 16) | ((p as u32) << 12);
        }
    }

    // Straight
    if let Some(high) = straight_high(rank_mask) {
        return (4 << 20) | (high as u32) << 16;
    }

    // Trips
    if !trips.is_empty() {
        let t = trips[0];
        let mut score = (3u32 << 20) | ((t as u32) << 16);
        let mut shift: u32 = 12;
        let mut found = 0;
        for r in (0..13).rev() {
            if r != t && rank_counts[r] > 0 {
                score |= (r as u32) << shift;
                shift = shift.saturating_sub(4);
                found += 1;
                if found == 2 {
                    break;
                }
            }
        }
        return score;
    }

    // Two pair
    if pairs.len() >= 2 {
        let p1 = pairs[0];
        let p2 = pairs[1];
        let kicker = (0..13)
            .rev()
            .find(|&r| r != p1 && r != p2 && rank_counts[r] > 0)
            .unwrap_or(0);
        return (2 << 20) | ((p1 as u32) << 16) | ((p2 as u32) << 12) | ((kicker as u32) << 8);
    }

    // Pair
    if let Some(&p) = pairs.first() {
        let mut score = (1u32 << 20) | ((p as u32) << 16);
        let mut shift: u32 = 12;
        let mut found = 0;
        for r in (0..13).rev() {
            if r != p && rank_counts[r] > 0 {
                score |= (r as u32) << shift;
                shift = shift.saturating_sub(4);
                found += 1;
                if found == 3 {
                    break;
                }
            }
        }
        return score;
    }

    // High card
    let mut score = 0u32;
    let mut shift: u32 = 16;
    let mut found = 0;
    for r in (0..13).rev() {
        if rank_counts[r] > 0 {
            score |= (r as u32) << shift;
            shift = shift.saturating_sub(4);
            found += 1;
            if found == 5 {
                break;
            }
        }
    }
    score
}

// ---------------------------------------------------------------------------
// Equity
// ---------------------------------------------------------------------------

struct Rng(u64);

impl Rng {
    fn new(seed: u64) -> Rng {
        Rng(seed.max(1))
    }
    fn next(&mut self) -> u64 {
        // xorshift64*
        let mut x = self.0;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.0 = x;
        x.wrapping_mul(0x2545F4914F6CDD1D)
    }
    fn below(&mut self, n: usize) -> usize {
        (self.next() % n as u64) as usize
    }
}

fn board_mask(board: &[Card]) -> u64 {
    board.iter().fold(0u64, |m, c| m | (1u64 << c.id()))
}

fn combo_alive(combo: &(Card, Card), used: u64) -> bool {
    let a = 1u64 << combo.0.id();
    let b = 1u64 << combo.1.id();
    (used & a) == 0 && (used & b) == 0 && combo.0.id() != combo.1.id()
}

fn representative(classes: &[HandClass], idx: usize, used: u64) -> Option<(Card, Card)> {
    classes[idx]
        .combos
        .iter()
        .find(|c| combo_alive(c, used))
        .copied()
}

fn build_runouts(board: &[Card], samples: usize, rng: &mut Rng) -> Vec<Vec<Card>> {
    let used = board_mask(board);
    let deck: Vec<Card> = (0..52u8)
        .map(|i| Card {
            rank: i / 4,
            suit: i % 4,
        })
        .filter(|c| used & (1u64 << c.id()) == 0)
        .collect();

    match board.len() {
        5 => vec![board.to_vec()],
        4 => deck
            .iter()
            .map(|c| {
                let mut b = board.to_vec();
                b.push(*c);
                b
            })
            .collect(),
        _ => {
            let n = samples.max(1);
            let mut out = Vec::with_capacity(n);
            for _ in 0..n {
                let a = rng.below(deck.len());
                let mut b = rng.below(deck.len());
                while b == a {
                    b = rng.below(deck.len());
                }
                let mut runout = board.to_vec();
                runout.push(deck[a]);
                runout.push(deck[b]);
                out.push(runout);
            }
            out
        }
    }
}

/// equity[i][j] = OOP class i's share (win = 1, tie = 0.5) against IP class j.
fn compute_equity(classes: &[HandClass], board: &[Card], samples: usize) -> (Vec<f32>, usize) {
    let mut rng = Rng::new(
        board
            .iter()
            .fold(1469598103934665603u64, |h, c| (h ^ c.id() as u64).wrapping_mul(1099511628211)),
    );
    let runouts = build_runouts(board, samples, &mut rng);
    let mut eq = vec![0f32; N_CLASSES * N_CLASSES];
    let mut counts = vec![0f32; N_CLASSES * N_CLASSES];

    for runout in &runouts {
        let used = board_mask(runout);
        let mut strengths = [0u32; N_CLASSES];
        let mut reps: [Option<(Card, Card)>; N_CLASSES] = [None; N_CLASSES];

        // Evaluate each hand class once per runout. Previously this was done
        // inside the 169x169 pair loop, making flop equity ~169x more expensive
        // than necessary.
        for i in 0..N_CLASSES {
            if let Some((a, b)) = representative(classes, i, used) {
                let cards = [
                    runout[0], runout[1], runout[2], runout[3], runout[4], a, b,
                ];
                strengths[i] = eval7(&cards);
                reps[i] = Some((a, b));
            }
        }

        for i in 0..N_CLASSES {
            let Some(ci) = reps[i] else { continue };
            for j in 0..N_CLASSES {
                let Some(cj) = reps[j] else { continue };
                // Two hand classes cannot both use the same physical card.
                if ci.0.id() == cj.0.id()
                    || ci.0.id() == cj.1.id()
                    || ci.1.id() == cj.0.id()
                    || ci.1.id() == cj.1.id()
                {
                    continue;
                }
                let idx = i * N_CLASSES + j;
                eq[idx] += if strengths[i] > strengths[j] {
                    1.0
                } else if strengths[i] == strengths[j] {
                    0.5
                } else {
                    0.0
                };
                counts[idx] += 1.0;
            }
        }
    }

    for i in 0..eq.len() {
        if counts[i] > 0.0 {
            eq[i] /= counts[i];
        } else {
            eq[i] = 0.5;
        }
    }
    (eq, runouts.len())
}

// ---------------------------------------------------------------------------
// Game tree
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, Debug, PartialEq)]
enum ActionKind {
    Check,
    Bet,
    Call,
    Fold,
    Raise,
    AllIn,
}

#[derive(Clone, Debug)]
struct Action {
    kind: ActionKind,
    label: String,
    size_frac: f64,
}

#[derive(Clone, Copy, Debug)]
struct State {
    player: usize,
    invested: [f64; 2],
    stacks: [f64; 2],
    checked: bool,
    to_call: f64,
    raises_left: usize,
}

#[derive(Debug)]
enum NodeKind {
    Decision {
        player: usize,
        actions: Vec<Action>,
        children: Vec<usize>,
        regrets: Vec<Vec<f64>>,
        avg: Vec<Vec<f64>>,
    },
    Fold {
        player: usize,
    },
    Showdown,
}

#[derive(Debug)]
struct Node {
    kind: NodeKind,
    invested: [f64; 2],
}

struct Tree {
    nodes: Vec<Node>,
    root: usize,
}

struct BuildCtx {
    pot: f64,
    rake_pct: f64,
    rake_cap: f64,
    bet_sizes: Vec<f64>,
    nodes: Vec<Node>,
}

impl BuildCtx {
    fn push(&mut self, kind: NodeKind, invested: [f64; 2]) -> usize {
        self.nodes.push(Node { kind, invested });
        self.nodes.len() - 1
    }

    fn build(&mut self, state: State, depth: usize) -> usize {
        if depth > 8 {
            return self.push(NodeKind::Showdown, state.invested);
        }
        let p = state.player;
        let opp = 1 - p;
        let current_pot = self.pot + state.invested[0] + state.invested[1];

        let mut actions: Vec<Action> = Vec::new();
        let mut children: Vec<usize> = Vec::new();

        if state.to_call <= 1e-9 {
            // Check
            let mut next = state;
            next.checked = true;
            next.player = opp;
            let child = if state.checked {
                self.push(NodeKind::Showdown, state.invested)
            } else {
                self.build(next, depth + 1)
            };
            actions.push(Action {
                kind: ActionKind::Check,
                label: "Check".into(),
                size_frac: 0.0,
            });
            children.push(child);

            // Bets
            let mut seen_amounts: Vec<f64> = Vec::new();
            let bet_sizes = self.bet_sizes.clone();
            for &frac in &bet_sizes {
                let amount = (current_pot * frac).min(state.stacks[p]);
                if amount > 0.01 && !seen_amounts.iter().any(|a| (a - amount).abs() < 0.01) {
                    seen_amounts.push(amount);
                    let mut next = state;
                    next.invested[p] += amount;
                    next.stacks[p] -= amount;
                    next.player = opp;
                    next.checked = false;
                    next.to_call = next.invested[p] - next.invested[opp];
                    next.raises_left = state.raises_left;
                    let child = self.build(next, depth + 1);
                    let is_allin = next.stacks[p] <= 0.01;
                    actions.push(Action {
                        kind: if is_allin { ActionKind::AllIn } else { ActionKind::Bet },
                        label: if is_allin {
                            "All-in".into()
                        } else {
                            format!("Bet {:.0}%", frac * 100.0)
                        },
                        size_frac: frac,
                    });
                    children.push(child);
                }
            }
            // All-in always available
            let allin_amt = state.stacks[p];
            if allin_amt > 0.01
                && !seen_amounts.iter().any(|a| (a - allin_amt).abs() < 0.01)
            {
                let mut next = state;
                next.invested[p] += allin_amt;
                next.stacks[p] -= allin_amt;
                next.player = opp;
                next.checked = false;
                next.to_call = next.invested[p] - next.invested[opp];
                let child = self.build(next, depth + 1);
                actions.push(Action {
                    kind: ActionKind::AllIn,
                    label: "All-in".into(),
                    size_frac: 1.0,
                });
                children.push(child);
            }
        } else {
            // Fold
            children.push(self.push(
                NodeKind::Fold { player: p },
                state.invested,
            ));
            actions.push(Action {
                kind: ActionKind::Fold,
                label: "Fold".into(),
                size_frac: 0.0,
            });

            // Call (closes the street)
            let call_amt = state.to_call.min(state.stacks[p]);
            let mut next = state;
            next.invested[p] += call_amt;
            next.stacks[p] -= call_amt;
            children.push(self.push(NodeKind::Showdown, next.invested));
            actions.push(Action {
                kind: ActionKind::Call,
                label: "Call".into(),
                size_frac: 0.0,
            });

            // Raise (one raise total by default)
            if state.raises_left > 0 && state.stacks[p] > state.to_call + 0.01 {
                let raise_add = (state.to_call * 1.5).max(current_pot * 0.5);
                let pay = (state.to_call + raise_add).min(state.stacks[p]);
                let mut next = state;
                next.invested[p] += pay;
                next.stacks[p] -= pay;
                next.player = opp;
                next.checked = false;
                next.to_call = next.invested[p] - next.invested[opp];
                next.raises_left -= 1;
                let child = self.build(next, depth + 1);
                let allin = next.stacks[p] <= 0.01;
                actions.push(Action {
                    kind: if allin { ActionKind::AllIn } else { ActionKind::Raise },
                    label: if allin { "All-in".into() } else { "Raise".into() },
                    size_frac: 0.0,
                });
                children.push(child);
            }

            // All-in
            let allin_pay = state.stacks[p];
            if allin_pay > state.to_call + 0.01 {
                let mut next = state;
                next.invested[p] += allin_pay;
                next.stacks[p] -= allin_pay;
                next.player = opp;
                next.checked = false;
                next.to_call = next.invested[p] - next.invested[opp];
                let child = self.build(next, depth + 1);
                actions.push(Action {
                    kind: ActionKind::AllIn,
                    label: "All-in".into(),
                    size_frac: 1.0,
                });
                children.push(child);
            }
        }

        let n_actions = actions.len().min(MAX_ACTIONS);
        let regrets = vec![vec![0.0; n_actions]; N_CLASSES];
        let avg = vec![vec![0.0; n_actions]; N_CLASSES];
        self.push(
            NodeKind::Decision {
                player: p,
                actions: actions.into_iter().take(n_actions).collect(),
                children: children.into_iter().take(n_actions).collect(),
                regrets,
                avg,
            },
            state.invested,
        )
    }
}

// ---------------------------------------------------------------------------
// CFR+
// ---------------------------------------------------------------------------

fn regret_strategy(regrets: &[Vec<f64>], n_actions: usize) -> Vec<Vec<f64>> {
    let mut out = vec![vec![0.0; n_actions]; N_CLASSES];
    for h in 0..N_CLASSES {
        let sum: f64 = regrets[h].iter().map(|r| r.max(0.0)).sum();
        if sum > 1e-12 {
            for a in 0..n_actions {
                out[h][a] = regrets[h][a].max(0.0) / sum;
            }
        } else {
            for a in 0..n_actions {
                out[h][a] = 1.0 / n_actions as f64;
            }
        }
    }
    out
}

fn normalized_reach(weights: &[f64], classes: &[HandClass], board: &[Card]) -> Vec<f64> {
    let used = board_mask(board);
    let mut mass = vec![0.0; N_CLASSES];
    let mut total = 0.0;
    for h in 0..N_CLASSES {
        let alive = classes[h].combos.iter().filter(|c| combo_alive(c, used)).count();
        let w = weights[h].max(0.0) * alive as f64;
        mass[h] = w;
        total += w;
    }
    if total > 1e-12 {
        for m in &mut mass {
            *m /= total;
        }
    } else {
        // Uniform fallback over all classes.
        for m in &mut mass {
            *m = 1.0 / N_CLASSES as f64;
        }
    }
    mass
}

struct Solver<'a> {
    tree: &'a mut Tree,
    eq: &'a [f32],
    pot: f64,
    rake_pct: f64,
    rake_cap: f64,
    iterations: usize,
    converged: bool,
    exploit_pct: f64,
    exploit_bb: f64,
}

impl<'a> Solver<'a> {
    fn rake_for(&self, invested: [f64; 2]) -> f64 {
        let total = self.pot + invested[0] + invested[1];
        (total * self.rake_pct).min(self.rake_cap)
    }

    fn showdown_values(
        &self,
        invested: [f64; 2],
        reach_o: &[f64],
        reach_i: &[f64],
    ) -> (Vec<f64>, Vec<f64>) {
        let total = self.pot + invested[0] + invested[1];
        let pot_net = total - self.rake_for(invested);
        let r_o: f64 = reach_o.iter().sum();
        let r_i: f64 = reach_i.iter().sum();

        let mut v_o = vec![0.0; N_CLASSES];
        let mut v_i = vec![0.0; N_CLASSES];

        for h in 0..N_CLASSES {
            if reach_i.iter().all(|x| *x == 0.0) {
                v_o[h] = -invested[0] * r_i;
                continue;
            }
            let mut share = 0.0;
            let base = h * N_CLASSES;
            for j in 0..N_CLASSES {
                if reach_i[j] != 0.0 {
                    share += reach_i[j] * self.eq[base + j] as f64;
                }
            }
            v_o[h] = share * pot_net - invested[0] * r_i;
        }
        for j in 0..N_CLASSES {
            if reach_o.iter().all(|x| *x == 0.0) {
                v_i[j] = -invested[1] * r_o;
                continue;
            }
            let mut share = 0.0;
            for h in 0..N_CLASSES {
                if reach_o[h] != 0.0 {
                    share += reach_o[h] * (1.0 - self.eq[h * N_CLASSES + j] as f64);
                }
            }
            v_i[j] = share * pot_net - invested[1] * r_o;
        }
        (v_o, v_i)
    }

    fn fold_values(
        &self,
        invested: [f64; 2],
        folder: usize,
        reach_o: &[f64],
        reach_i: &[f64],
    ) -> (Vec<f64>, Vec<f64>) {
        let r_o: f64 = reach_o.iter().sum();
        let r_i: f64 = reach_i.iter().sum();
        let rake = self.rake_for(invested);
        // The winner gets the starting pot plus the folder's contribution. Their
        // own contribution is returned, so it must not be counted as profit.
        let winner_net = self.pot + invested[folder] - rake;
        let mut v_o = vec![0.0; N_CLASSES];
        let mut v_i = vec![0.0; N_CLASSES];
        if folder == 0 {
            for h in 0..N_CLASSES {
                v_o[h] = -invested[0] * r_i;
            }
            for j in 0..N_CLASSES {
                v_i[j] = winner_net * r_o;
            }
        } else {
            for h in 0..N_CLASSES {
                v_o[h] = winner_net * r_i;
            }
            for j in 0..N_CLASSES {
                v_i[j] = -invested[1] * r_o;
            }
        }
        (v_o, v_i)
    }

    fn traverse(
        &mut self,
        idx: usize,
        reach_o: &[f64],
        reach_i: &[f64],
        iter_weight: f64,
    ) -> (Vec<f64>, Vec<f64>) {
        // Extract everything we need from the node before recursing. Holding a
        // borrow of `self.tree.nodes[idx].kind` across `self.traverse(...)`
        // would alias the mutable borrow of `self`.
        enum NodeInfo {
            Fold(usize),
            Showdown,
            Decision {
                player: usize,
                n_actions: usize,
                children: Vec<usize>,
            },
        }

        let invested = self.tree.nodes[idx].invested;
        let info = match &self.tree.nodes[idx].kind {
            NodeKind::Fold { player } => NodeInfo::Fold(*player),
            NodeKind::Showdown => NodeInfo::Showdown,
            NodeKind::Decision {
                player,
                actions,
                children,
                ..
            } => NodeInfo::Decision {
                player: *player,
                n_actions: actions.len(),
                children: children.clone(),
            },
        };

        match info {
            NodeInfo::Fold(p) => self.fold_values(invested, p, reach_o, reach_i),
            NodeInfo::Showdown => self.showdown_values(invested, reach_o, reach_i),
            NodeInfo::Decision {
                player: p,
                n_actions,
                children,
            } => {
                // Strategies are derived from the current regrets. The result is
                // owned, so no borrow of the tree is kept across recursion.
                let strat = match &self.tree.nodes[idx].kind {
                    NodeKind::Decision { regrets, .. } => {
                        regret_strategy(regrets, n_actions)
                    }
                    _ => unreachable!(),
                };

                let mut child_vals: Vec<(Vec<f64>, Vec<f64>)> = Vec::with_capacity(n_actions);
                for a in 0..n_actions {
                    let (ro, ri) = if p == 0 {
                        let mut ro = vec![0.0; N_CLASSES];
                        for h in 0..N_CLASSES {
                            ro[h] = reach_o[h] * strat[h][a];
                        }
                        (ro, reach_i.to_vec())
                    } else {
                        let mut ri = vec![0.0; N_CLASSES];
                        for h in 0..N_CLASSES {
                            ri[h] = reach_i[h] * strat[h][a];
                        }
                        (reach_o.to_vec(), ri)
                    };
                    child_vals.push(self.traverse(children[a], &ro, &ri, iter_weight));
                }

                let mut v_actor = vec![0.0; N_CLASSES];
                for h in 0..N_CLASSES {
                    let mut v = 0.0;
                    for a in 0..n_actions {
                        v += strat[h][a]
                            * if p == 0 { child_vals[a].0[h] } else { child_vals[a].1[h] };
                    }
                    v_actor[h] = v;
                }

                // Update regrets and the average strategy with a fresh mutable
                // borrow now that recursion is complete.
                if let NodeKind::Decision { regrets, avg, .. } =
                    &mut self.tree.nodes[idx].kind
                {
                    // CFR+ regrets
                    for h in 0..N_CLASSES {
                        for a in 0..n_actions {
                            let ca = if p == 0 {
                                child_vals[a].0[h]
                            } else {
                                child_vals[a].1[h]
                            };
                            let new = regrets[h][a] + ca - v_actor[h];
                            regrets[h][a] = new.max(0.0);
                        }
                    }

                    // Linear-weighted average strategy
                    let reach_actor = if p == 0 { reach_o } else { reach_i };
                    for h in 0..N_CLASSES {
                        if reach_actor[h] == 0.0 {
                            continue;
                        }
                        let w = iter_weight * reach_actor[h];
                        for a in 0..n_actions {
                            avg[h][a] += w * strat[h][a];
                        }
                    }
                }

                // The opponent's value already includes the actor's action
                // probabilities through the reach vectors, so sum the children.
                let mut v_opp = vec![0.0; N_CLASSES];
                for a in 0..n_actions {
                    let child = if p == 0 {
                        &child_vals[a].1
                    } else {
                        &child_vals[a].0
                    };
                    for h in 0..N_CLASSES {
                        v_opp[h] += child[h];
                    }
                }

                if p == 0 {
                    (v_actor, v_opp)
                } else {
                    (v_opp, v_actor)
                }
            }
        }
    }

    fn average_strategy(&self) -> Vec<Vec<Vec<f64>>> {
        let mut out = Vec::with_capacity(self.tree.nodes.len());
        for _ in 0..self.tree.nodes.len() {
            out.push(Vec::new());
        }
        for (i, node) in self.tree.nodes.iter().enumerate() {
            if let NodeKind::Decision {
                actions,
                avg,
                regrets: _,
                ..
            } = &node.kind
            {
                let n = actions.len();
                let mut s = vec![vec![0.0; n]; N_CLASSES];
                for h in 0..N_CLASSES {
                    let sum: f64 = avg[h].iter().sum();
                    if sum > 1e-12 {
                        for a in 0..n {
                            s[h][a] = avg[h][a] / sum;
                        }
                    } else {
                        for a in 0..n {
                            s[h][a] = 1.0 / n as f64;
                        }
                    }
                }
                out[i] = s;
            }
        }
        out
    }

    fn eval_profile(
        &self,
        idx: usize,
        reach_o: &[f64],
        reach_i: &[f64],
        avg: &[Vec<Vec<f64>>],
    ) -> (Vec<f64>, Vec<f64>) {
        match &self.tree.nodes[idx].kind {
            NodeKind::Fold { player } => {
                self.fold_values(self.tree.nodes[idx].invested, *player, reach_o, reach_i)
            }
            NodeKind::Showdown => {
                self.showdown_values(self.tree.nodes[idx].invested, reach_o, reach_i)
            }
            NodeKind::Decision {
                player,
                actions,
                children,
                ..
            } => {
                let p = *player;
                let n = actions.len();
                let strat = &avg[idx];
                let mut child_vals = Vec::with_capacity(n);
                for a in 0..n {
                    let (ro, ri) = if p == 0 {
                        let mut ro = vec![0.0; N_CLASSES];
                        for h in 0..N_CLASSES {
                            ro[h] = reach_o[h] * strat[h][a];
                        }
                        (ro, reach_i.to_vec())
                    } else {
                        let mut ri = vec![0.0; N_CLASSES];
                        for h in 0..N_CLASSES {
                            ri[h] = reach_i[h] * strat[h][a];
                        }
                        (reach_o.to_vec(), ri)
                    };
                    child_vals.push(self.eval_profile(children[a], &ro, &ri, avg));
                }
                let mut v_actor = vec![0.0; N_CLASSES];
                for h in 0..N_CLASSES {
                    for a in 0..n {
                        v_actor[h] += strat[h][a]
                            * if p == 0 { child_vals[a].0[h] } else { child_vals[a].1[h] };
                    }
                }
                let mut v_opp = vec![0.0; N_CLASSES];
                for a in 0..n {
                    let child = if p == 0 { &child_vals[a].1 } else { &child_vals[a].0 };
                    for h in 0..N_CLASSES {
                        v_opp[h] += child[h];
                    }
                }
                if p == 0 {
                    (v_actor, v_opp)
                } else {
                    (v_opp, v_actor)
                }
            }
        }
    }

    fn best_response(
        &self,
        idx: usize,
        br_player: usize,
        reach_opp: &[f64],
        avg: &[Vec<Vec<f64>>],
        invested: [f64; 2],
    ) -> Vec<f64> {
        match &self.tree.nodes[idx].kind {
            NodeKind::Fold { player } => {
                let folder = *player;
                let r_opp: f64 = reach_opp.iter().sum();
                let rake = self.rake_for(self.tree.nodes[idx].invested);
                let winner_net = self.pot + self.tree.nodes[idx].invested[folder] - rake;
                let mut v = vec![0.0; N_CLASSES];
                if folder == br_player {
                    for h in 0..N_CLASSES {
                        v[h] = -self.tree.nodes[idx].invested[br_player] * r_opp;
                    }
                } else {
                    for h in 0..N_CLASSES {
                        v[h] = winner_net * r_opp;
                    }
                }
                let _ = invested;
                v
            }
            NodeKind::Showdown => {
                let r_opp: f64 = reach_opp.iter().sum();
                let total = self.pot
                    + self.tree.nodes[idx].invested[0]
                    + self.tree.nodes[idx].invested[1];
                let pot_net = total - self.rake_for(self.tree.nodes[idx].invested);
                let mut v = vec![0.0; N_CLASSES];
                for h in 0..N_CLASSES {
                    let mut share = 0.0;
                    for j in 0..N_CLASSES {
                        if reach_opp[j] == 0.0 {
                            continue;
                        }
                        let eq = if br_player == 0 {
                            self.eq[h * N_CLASSES + j] as f64
                        } else {
                            1.0 - self.eq[j * N_CLASSES + h] as f64
                        };
                        share += reach_opp[j] * eq;
                    }
                    v[h] = share * pot_net - self.tree.nodes[idx].invested[br_player] * r_opp;
                }
                v
            }
            NodeKind::Decision {
                player,
                actions,
                children,
                ..
            } => {
                let p = *player;
                let n = actions.len();
                if p == br_player {
                    let mut best = vec![f64::NEG_INFINITY; N_CLASSES];
                    for a in 0..n {
                        let child =
                            self.best_response(children[a], br_player, reach_opp, avg, invested);
                        for h in 0..N_CLASSES {
                            if child[h] > best[h] {
                                best[h] = child[h];
                            }
                        }
                    }
                    best
                } else {
                    let strat = &avg[idx];
                    let mut total = vec![0.0; N_CLASSES];
                    for a in 0..n {
                        let mut ro = vec![0.0; N_CLASSES];
                        for h in 0..N_CLASSES {
                            ro[h] = reach_opp[h] * strat[h][a];
                        }
                        let child =
                            self.best_response(children[a], br_player, &ro, avg, invested);
                        for h in 0..N_CLASSES {
                            total[h] += child[h];
                        }
                    }
                    total
                }
            }
        }
    }
}

fn dot(weights: &[f64], values: &[f64]) -> f64 {
    weights.iter().zip(values).map(|(w, v)| w * v).sum()
}

fn map_action_bucket(kind: ActionKind) -> usize {
    match kind {
        ActionKind::Fold => 0,
        ActionKind::Check | ActionKind::Call => 1,
        ActionKind::Bet | ActionKind::Raise | ActionKind::AllIn => 2,
    }
}

/// Runs the CFR solve and fills the public solver response.
pub fn solve(input: &SolverInput) -> Result<SolverOutput, String> {
    let start = Instant::now();
    let board: Vec<Card> = input
        .board
        .iter()
        .filter_map(|c| Card::parse(c))
        .collect();
    if board.len() < 3 {
        return Err("board must contain at least 3 cards".into());
    }
    if board.len() > 5 {
        return Err("board must contain at most 5 cards".into());
    }

    let classes = build_classes();
    let mut oop_weights = vec![0.0; N_CLASSES];
    let mut ip_weights = vec![0.0; N_CLASSES];
    for (k, v) in &input.oop_range {
        if let Some(i) = class_index(k) {
            oop_weights[i] = v.max(0.0);
        }
    }
    for (k, v) in &input.ip_range {
        if let Some(i) = class_index(k) {
            ip_weights[i] = v.max(0.0);
        }
    }
    let oop_dist = normalized_reach(&oop_weights, &classes, &board);
    let ip_dist = normalized_reach(&ip_weights, &classes, &board);

    let equity_samples = if board.len() >= 5 {
        1
    } else if board.len() == 4 {
        0 // enumerate all rivers
    } else {
        400
    };
    let (eq, runouts) = compute_equity(&classes, &board, equity_samples);

    let mut bet_sizes: Vec<f64> = vec![0.33, 0.75];
    bet_sizes.truncate(input.max_sizes_per_node.max(1));
    let mut ctx = BuildCtx {
        pot: input.pot,
        rake_pct: (input.rake_percent / 100.0).max(0.0),
        rake_cap: input.rake_cap.max(0.0),
        bet_sizes,
        nodes: Vec::new(),
    };
    let root = ctx.build(
        State {
            player: 0,
            invested: [0.0, 0.0],
            stacks: [input.effective_stack, input.effective_stack],
            checked: false,
            to_call: 0.0,
            raises_left: 1,
        },
        0,
    );
    let mut tree = Tree {
        nodes: ctx.nodes,
        root,
    };

    let mut solver = Solver {
        tree: &mut tree,
        eq: &eq,
        pot: input.pot,
        rake_pct: (input.rake_percent / 100.0).max(0.0),
        rake_cap: input.rake_cap.max(0.0),
        iterations: 0,
        converged: false,
        exploit_pct: 1.0,
        exploit_bb: input.pot,
    };

    let max_iters = input.max_iterations.max(1);
    let time_limit_ms = 1500u128;
    let mut check_every = 10usize;
    for t in 1..=max_iters {
        solver.traverse(root, &oop_dist, &ip_dist, t as f64);
        solver.iterations = t;
        if t % check_every == 0 || t == max_iters {
            let avg = solver.average_strategy();
            let (v_o, v_i) = solver.eval_profile(root, &oop_dist, &ip_dist, &avg);
            let ev_o = dot(&oop_dist, &v_o);
            let ev_i = dot(&ip_dist, &v_i);
            let br_o_v = solver.best_response(root, 0, &ip_dist, &avg, [0.0, 0.0]);
            let br_i_v = solver.best_response(root, 1, &oop_dist, &avg, [0.0, 0.0]);
            let br_o = dot(&oop_dist, &br_o_v);
            let br_i = dot(&ip_dist, &br_i_v);
            let nashconv = (br_o - ev_o) + (br_i - ev_i);
            let exploit_bb = (nashconv / 2.0).max(0.0);
            solver.exploit_bb = exploit_bb;
            solver.exploit_pct = exploit_bb / input.pot.max(1e-9);
            if solver.exploit_pct <= input.target_d_ev.max(1e-6) {
                solver.converged = true;
                break;
            }
            if start.elapsed().as_millis() >= time_limit_ms {
                break;
            }
            // Keep the expensive BR check from dominating tiny runs.
            if t >= 400 {
                check_every = 25;
            }
        }
    }

    let avg = solver.average_strategy();
    let (v_o, v_i) = solver.eval_profile(root, &oop_dist, &ip_dist, &avg);
    let ev_o = dot(&oop_dist, &v_o);
    let ev_i = dot(&ip_dist, &v_i);

    // Snapshot scalar stats and release the mutable tree borrow before reading
    // the root node to build the response.
    let iterations = solver.iterations;
    let converged = solver.converged;
    let exploit_bb = solver.exploit_bb;
    let exploit_pct = solver.exploit_pct;
    drop(solver);
    let tree_nodes = tree.nodes.len();

    // Root (OOP) strategy + per-hand EV.
    let root_decision = match &tree.nodes[root].kind {
        NodeKind::Decision {
            player: _,
            actions,
            ..
        } => actions.clone(),
        _ => return Err("root is not a decision node".into()),
    };
    let root_strat = &avg[root];
    let mut strategy: HashMap<String, ActionFrequencies> = HashMap::new();
    let mut strategy_detail: HashMap<String, HashMap<String, f64>> = HashMap::new();
    let mut hand_ev: HashMap<String, f64> = HashMap::new();
    let mut bucket_totals = [0.0f64; 3];

    for h in 0..N_CLASSES {
        let mut f = 0.0;
        let mut c = 0.0;
        let mut r = 0.0;
        let mut detail: HashMap<String, f64> = HashMap::new();
        for (a, action) in root_decision.iter().enumerate() {
            let p = root_strat[h][a];
            let bucket = map_action_bucket(action.kind);
            match bucket {
                0 => f += p,
                1 => c += p,
                _ => r += p,
            }
            detail.insert(action.label.clone(), (p * 10000.0).round() / 10000.0);
            bucket_totals[bucket] += p * oop_dist[h];
        }
        let name = &classes[h].name;
        strategy.insert(
            name.clone(),
            ActionFrequencies {
                fold: (f * 10000.0).round() / 10000.0,
                call: (c * 10000.0).round() / 10000.0,
                bet_raise: (r * 10000.0).round() / 10000.0,
            },
        );
        strategy_detail.insert(name.clone(), detail);
        hand_ev.insert(name.clone(), (v_o[h] * 1000.0).round() / 1000.0);
    }

    let oop_check_freq = root_strat
        .iter()
        .enumerate()
        .map(|(h, s)| {
            let a = root_decision
                .iter()
                .position(|a| a.kind == ActionKind::Check)
                .unwrap_or(0);
            s[a] * oop_dist[h]
        })
        .sum::<f64>();

    // IP c-bet frequency after OOP checks.
    let check_child = root_decision
        .iter()
        .position(|a| a.kind == ActionKind::Check)
        .and_then(|a| match &tree.nodes[root].kind {
            NodeKind::Decision { children, .. } => Some(children[a]),
            _ => None,
        });
    let mut ip_cbet = 0.0;
    let mut ip_check = 0.0;
    let mut bet_freq_by_size: HashMap<String, f64> = HashMap::new();
    if let Some(node_idx) = check_child {
        if let NodeKind::Decision {
            player: 1,
            actions,
            ..
        } = &tree.nodes[node_idx].kind
        {
            let s = &avg[node_idx];
            for h in 0..N_CLASSES {
                for (a, action) in actions.iter().enumerate() {
                    let p = s[h][a] * ip_dist[h];
                    match action.kind {
                        ActionKind::Check => ip_check += p,
                        ActionKind::Bet | ActionKind::AllIn => {
                            ip_cbet += p;
                            *bet_freq_by_size.entry(action.label.clone()).or_insert(0.0) += p;
                        }
                        ActionKind::Raise => {
                            ip_cbet += p;
                        }
                        _ => {}
                    }
                }
            }
        }
    }
    let best_size = bet_freq_by_size
        .iter()
        .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
        .map(|(label, _)| label.clone());
    let optimal_sizing = best_size
        .as_ref()
        .and_then(|l| {
            root_decision
                .iter()
                .find(|a| &a.label == l)
                .map(|a| a.size_frac)
        })
        .unwrap_or(0.33);

    let total_bucket: f64 = bucket_totals.iter().sum();
    let overall = if total_bucket > 1e-12 {
        ActionFrequencies {
            fold: bucket_totals[0] / total_bucket,
            call: bucket_totals[1] / total_bucket,
            bet_raise: bucket_totals[2] / total_bucket,
        }
    } else {
        ActionFrequencies {
            fold: 0.0,
            call: 1.0,
            bet_raise: 0.0,
        }
    };

    Ok(SolverOutput {
        exploitability: exploit_pct,
        solve_time_ms: start.elapsed().as_millis().max(1),
        iterations,
        strategy,
        overall_frequencies: overall,
        optimal_sizing,
        engine: "Rust DCFR (depth-limited, 169-class)".to_string(),
        oop_ev: ev_o,
        ip_ev: ev_i,
        btn_cbet_frequency: if ip_cbet + ip_check > 0.0 {
            ip_cbet / (ip_cbet + ip_check)
        } else {
            0.0
        },
        bb_check_frequency: oop_check_freq,
        btn_check_frequency: if ip_cbet + ip_check > 0.0 {
            ip_check / (ip_cbet + ip_check)
        } else {
            0.0
        },
        strategy_detail,
        hand_ev,
        exploitability_bb: exploit_bb,
        exploitability_pct_pot: exploit_pct * 100.0,
        converged,
        tree_nodes,
        equity_samples: runouts,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn evaluator_orders_hands() {
        let c = |s: &str| Card::parse(s).unwrap();
        let straight_flush = eval7(&[c("As"), c("Ks"), c("Qs"), c("Js"), c("Ts"), c("2d"), c("3c")]);
        let quads = eval7(&[c("As"), c("Ah"), c("Ad"), c("Ac"), c("Ks"), c("2d"), c("3c")]);
        let full_house = eval7(&[c("As"), c("Ah"), c("Ad"), c("Ks"), c("Kh"), c("2d"), c("3c")]);
        let flush = eval7(&[c("As"), c("Ks"), c("Qs"), c("Js"), c("9s"), c("2d"), c("3c")]);
        let straight = eval7(&[c("As"), c("Kh"), c("Qd"), c("Jc"), c("Ts"), c("2d"), c("3c")]);
        let trips = eval7(&[c("As"), c("Ah"), c("Ad"), c("Ks"), c("Qh"), c("2d"), c("3c")]);
        let trips_low = eval7(&[c("Ks"), c("Kh"), c("Kd"), c("As"), c("Qh"), c("2d"), c("3c")]);
        let two_pair = eval7(&[c("As"), c("Ah"), c("Kd"), c("Kc"), c("Qh"), c("2d"), c("3c")]);
        let pair = eval7(&[c("As"), c("Ah"), c("Kd"), c("Qc"), c("Jh"), c("2d"), c("3c")]);
        let high = eval7(&[c("As"), c("Kh"), c("Qd"), c("Jc"), c("9h"), c("2d"), c("3c")]);
        assert!(straight_flush > quads);
        assert!(quads > full_house);
        assert!(full_house > flush);
        assert!(flush > straight);
        assert!(straight > trips);
        assert!(trips > trips_low, "higher trips rank must win");
        assert!(trips > two_pair);
        assert!(two_pair > pair);
        assert!(pair > high);
    }

    #[test]
    fn class_index_roundtrip() {
        assert_eq!(class_index("AA"), Some(12));
        assert_eq!(class_index("22"), Some(0));
        assert!(class_index("AKs").unwrap() < 91);
        assert!(class_index("AKo").unwrap() >= 91);
    }

    #[test]
    fn equity_orientation() {
        let classes = build_classes();
        let board: Vec<Card> = ["Ah", "Kd", "2c"]
            .iter()
            .map(|s| Card::parse(s).unwrap())
            .collect();
        let (eq, _) = compute_equity(&classes, &board, 400);
        let aa = class_index("AA").unwrap();
        let kk = class_index("KK").unwrap();
        let e = eq[aa * N_CLASSES + kk];
        println!("eq AA vs KK on AhKd2c = {e}");
        assert!(e > 0.7, "AA should beat KK, got {e}");
    }
}
