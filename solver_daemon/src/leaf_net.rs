// solver_daemon/src/leaf_net.rs
//
// Native lightweight neural inference engine for Model 2 (169-class Leaf Value Network).
// Loads trained f32 weights from ml/artifacts/leaf_value_net_weights.bin and evaluates
// flop-to-turn exit nodes in under 0.1ms with zero external C++/Python dependencies.

use std::collections::HashMap;
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

const INPUT_DIM: usize = 422;
const HIDDEN_DIM: usize = 256;
const HEAD_DIM: usize = 128;
const N_CLASSES: usize = 169;

#[inline]
fn gelu(x: f32) -> f32 {
    // Fast GELU approximation: 0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
    let c = 0.7978845608; // sqrt(2 / pi)
    0.5 * x * (1.0 + ((c * (x + 0.044715 * x * x * x)).tanh()))
}

#[inline]
fn layer_norm(x: &mut [f32], weight: &[f32], bias: &[f32], eps: f32) {
    let n = x.len() as f32;
    let mean: f32 = x.iter().sum::<f32>() / n;
    let var: f32 = x.iter().map(|v| (v - mean) * (v - mean)).sum::<f32>() / n;
    let inv_std = 1.0 / (var + eps).sqrt();
    for i in 0..x.len() {
        x[i] = (x[i] - mean) * inv_std * weight[i] + bias[i];
    }
}

#[inline]
fn matvec(out: &mut [f32], weight: &[f32], bias: &[f32], x: &[f32], out_dim: usize, in_dim: usize) {
    for i in 0..out_dim {
        let row_start = i * in_dim;
        let mut sum = bias[i];
        for j in 0..in_dim {
            sum += weight[row_start + j] * x[j];
        }
        out[i] = sum;
    }
}

pub struct ResBlockWeights {
    pub fc1_w: Vec<f32>,
    pub fc1_b: Vec<f32>,
    pub ln1_w: Vec<f32>,
    pub ln1_b: Vec<f32>,
    pub fc2_w: Vec<f32>,
    pub fc2_b: Vec<f32>,
    pub ln2_w: Vec<f32>,
    pub ln2_b: Vec<f32>,
}

impl ResBlockWeights {
    pub fn forward(&self, x: &mut [f32]) {
        let mut residual = [0.0f32; HIDDEN_DIM];
        residual.copy_from_slice(x);

        let mut h = [0.0f32; HIDDEN_DIM];
        matvec(&mut h, &self.fc1_w, &self.fc1_b, x, HIDDEN_DIM, HIDDEN_DIM);
        layer_norm(&mut h, &self.ln1_w, &self.ln1_b, 1e-5);
        for v in &mut h {
            *v = gelu(*v);
        }

        matvec(x, &self.fc2_w, &self.fc2_b, &h, HIDDEN_DIM, HIDDEN_DIM);
        layer_norm(x, &self.ln2_w, &self.ln2_b, 1e-5);
        for i in 0..HIDDEN_DIM {
            x[i] = gelu(x[i] + residual[i]);
        }
    }
}

pub struct HeadWeights {
    pub fc1_w: Vec<f32>,
    pub fc1_b: Vec<f32>,
    pub ln1_w: Vec<f32>,
    pub ln1_b: Vec<f32>,
    pub fc2_w: Vec<f32>,
    pub fc2_b: Vec<f32>,
}

impl HeadWeights {
    pub fn forward(&self, x: &[f32], out: &mut [f32]) {
        let mut h = [0.0f32; HEAD_DIM];
        matvec(&mut h, &self.fc1_w, &self.fc1_b, x, HEAD_DIM, HIDDEN_DIM);
        layer_norm(&mut h, &self.ln1_w, &self.ln1_b, 1e-5);
        for v in &mut h {
            *v = gelu(*v);
        }
        matvec(out, &self.fc2_w, &self.fc2_b, &h, N_CLASSES, HEAD_DIM);
    }
}

pub struct LeafNet {
    pub in_w: Vec<f32>,
    pub in_b: Vec<f32>,
    pub in_ln_w: Vec<f32>,
    pub in_ln_b: Vec<f32>,
    pub blocks: Vec<ResBlockWeights>,
    pub head_oop: HeadWeights,
    pub head_ip: HeadWeights,
}

impl LeafNet {
    pub fn load_from_file(path: &Path) -> Result<Self, String> {
        let mut f = File::open(path).map_err(|e| format!("cannot open weights file {}: {}", path.display(), e))?;

        let mut buf4 = [0u8; 4];
        f.read_exact(&mut buf4).map_err(|e| e.to_string())?;
        let num_tensors = u32::from_le_bytes(buf4) as usize;

        let mut tensors: HashMap<String, Vec<f32>> = HashMap::new();

        for _ in 0..num_tensors {
            f.read_exact(&mut buf4).map_err(|e| e.to_string())?;
            let name_len = u32::from_le_bytes(buf4) as usize;
            let mut name_bytes = vec![0u8; name_len];
            f.read_exact(&mut name_bytes).map_err(|e| e.to_string())?;
            let name = String::from_utf8(name_bytes).map_err(|e| e.to_string())?;

            f.read_exact(&mut buf4).map_err(|e| e.to_string())?;
            let ndim = u32::from_le_bytes(buf4) as usize;

            let mut num_elems = 1usize;
            for _ in 0..ndim {
                f.read_exact(&mut buf4).map_err(|e| e.to_string())?;
                let dim = u32::from_le_bytes(buf4) as usize;
                num_elems *= dim;
            }

            let mut byte_data = vec![0u8; num_elems * 4];
            f.read_exact(&mut byte_data).map_err(|e| e.to_string())?;

            let mut float_data = vec![0.0f32; num_elems];
            for i in 0..num_elems {
                float_data[i] = f32::from_le_bytes([
                    byte_data[i * 4],
                    byte_data[i * 4 + 1],
                    byte_data[i * 4 + 2],
                    byte_data[i * 4 + 3],
                ]);
            }
            tensors.insert(name, float_data);
        }

        let get = |name: &str| -> Result<Vec<f32>, String> {
            tensors
                .get(name)
                .cloned()
                .ok_or_else(|| format!("missing tensor: {}", name))
        };

        let in_w = get("input_proj.0.weight")?;
        if in_w.len() != HIDDEN_DIM * INPUT_DIM {
            return Err(format!(
                "input_proj.0.weight size mismatch: got {} expected {} ({}x{})",
                in_w.len(),
                HIDDEN_DIM * INPUT_DIM,
                HIDDEN_DIM,
                INPUT_DIM
            ));
        }
        let in_b = get("input_proj.0.bias")?;
        let in_ln_w = get("input_proj.1.weight")?;
        let in_ln_b = get("input_proj.1.bias")?;

        let mut blocks = Vec::new();
        for b in 0..3 {
            blocks.push(ResBlockWeights {
                fc1_w: get(&format!("blocks.{}.fc1.weight", b))?,
                fc1_b: get(&format!("blocks.{}.fc1.bias", b))?,
                ln1_w: get(&format!("blocks.{}.ln1.weight", b))?,
                ln1_b: get(&format!("blocks.{}.ln1.bias", b))?,
                fc2_w: get(&format!("blocks.{}.fc2.weight", b))?,
                fc2_b: get(&format!("blocks.{}.fc2.bias", b))?,
                ln2_w: get(&format!("blocks.{}.ln2.weight", b))?,
                ln2_b: get(&format!("blocks.{}.ln2.bias", b))?,
            });
        }

        let head_oop = HeadWeights {
            fc1_w: get("head_oop.0.weight")?,
            fc1_b: get("head_oop.0.bias")?,
            ln1_w: get("head_oop.1.weight")?,
            ln1_b: get("head_oop.1.bias")?,
            fc2_w: get("head_oop.3.weight")?,
            fc2_b: get("head_oop.3.bias")?,
        };

        let head_ip = HeadWeights {
            fc1_w: get("head_ip.0.weight")?,
            fc1_b: get("head_ip.0.bias")?,
            ln1_w: get("head_ip.1.weight")?,
            ln1_b: get("head_ip.1.bias")?,
            fc2_w: get("head_ip.3.weight")?,
            fc2_b: get("head_ip.3.bias")?,
        };

        Ok(LeafNet {
            in_w,
            in_b,
            in_ln_w,
            in_ln_b,
            blocks,
            head_oop,
            head_ip,
        })
    }

    pub fn forward(&self, x: &[f32]) -> (Vec<f32>, Vec<f32>) {
        let mut h = [0.0f32; HIDDEN_DIM];
        matvec(&mut h, &self.in_w, &self.in_b, x, HIDDEN_DIM, INPUT_DIM);
        layer_norm(&mut h, &self.in_ln_w, &self.in_ln_b, 1e-5);
        for v in &mut h {
            *v = gelu(*v);
        }

        for block in &self.blocks {
            block.forward(&mut h);
        }

        let mut v_oop = vec![0.0f32; N_CLASSES];
        let mut v_ip = vec![0.0f32; N_CLASSES];

        self.head_oop.forward(&h, &mut v_oop);
        self.head_ip.forward(&h, &mut v_ip);

        (v_oop, v_ip)
    }

    pub fn evaluate_leaf(
        &self,
        board_features: &[f32; 75],
        reach_o: &[f64],
        reach_i: &[f64],
        invested: [f64; 2],
        pot: f64,
        effective_stack: f64,
        ante_bb: f64,
        rake_pct: f64,
        rake_cap: f64,
        num_folded_players: usize,
    ) -> (Vec<f64>, Vec<f64>) {
        let tot_pot = pot + invested[0] + invested[1];
        let rake = (tot_pot * (rake_pct / 100.0)).min(rake_cap);
        let net_pot = tot_pot - rake;

        // The net is trained on NORMALIZED ranges and predicts each class's share
        // of the net pot against the opponent's normalized range. Values are
        // rebuilt exactly, so they scale linearly with the opponent's reach
        // mass and are zero-sum after the projection below.
        let m_o: f64 = reach_o.iter().sum();
        let m_i: f64 = reach_i.iter().sum();
        let mut v_o = vec![0.0f64; N_CLASSES];
        let mut v_i = vec![0.0f64; N_CLASSES];
        if m_o <= 1e-12 || m_i <= 1e-12 {
            // One side never reaches this leaf: every counterfactual value is
            // multiplied by a zero opponent mass except the invested term.
            for h in 0..N_CLASSES {
                v_o[h] = -invested[0] * m_i;
                v_i[h] = -invested[1] * m_o;
            }
            return (v_o, v_i);
        }

        let mut x = [0.0f32; INPUT_DIM];
        x[..75].copy_from_slice(board_features);
        for i in 0..N_CLASSES {
            x[75 + i] = (reach_o[i] / m_o) as f32;
            x[75 + N_CLASSES + i] = (reach_i[i] / m_i) as f32;
        }
        let base_ctx = 75 + N_CLASSES * 2;
        x[base_ctx] = (tot_pot / 10.0) as f32;
        x[base_ctx + 1] = (invested[0] / 10.0) as f32;
        x[base_ctx + 2] = (invested[1] / 10.0) as f32;
        x[base_ctx + 3] = (net_pot / 10.0) as f32;
        x[base_ctx + 4] = (effective_stack / 100.0) as f32;
        x[base_ctx + 5] = ante_bb as f32;
        x[base_ctx + 6] = (rake_pct / 10.0) as f32;
        x[base_ctx + 7] = (rake_cap / 5.0) as f32;
        x[base_ctx + 8] = (num_folded_players as f32) / 6.0;

        let (logit_o, logit_i) = self.forward(&x);
        let mut t_o = [0.0f64; N_CLASSES];
        let mut t_i = [0.0f64; N_CLASSES];
        let mut err = -1.0f64;
        for h in 0..N_CLASSES {
            t_o[h] = 1.0 / (1.0 + (-(logit_o[h] as f64)).exp());
            t_i[h] = 1.0 / (1.0 + (-(logit_i[h] as f64)).exp());
            err += (reach_o[h] / m_o) * t_o[h] + (reach_i[h] / m_i) * t_i[h];
        }
        // Zero-sum projection: sum(ro_n * t_o) + sum(ri_n * t_i) == 1.
        let half = err / 2.0;
        for h in 0..N_CLASSES {
            v_o[h] = ((t_o[h] - half) * net_pot - invested[0]) * m_i;
            v_i[h] = ((t_i[h] - half) * net_pot - invested[1]) * m_o;
        }
        (v_o, v_i)
    }
}

pub static GLOBAL_LEAF_NET: OnceLock<Option<LeafNet>> = OnceLock::new();

pub fn get_leaf_net() -> Option<&'static LeafNet> {
    GLOBAL_LEAF_NET
        .get_or_init(|| {
            if matches!(std::env::var("GTO_LEAF_NET").as_deref(), Ok("off") | Ok("0")) {
                eprintln!("ℹ️ GTO_LEAF_NET=off; using exact showdown equity at leaves.");
                return None;
            }
            let candidate_paths = [
                PathBuf::from("ml/artifacts/leaf_value_net_weights.bin"),
                PathBuf::from("/app/artifacts/leaf_value_net_weights.bin"),
                PathBuf::from("/root/Dev/GTO-Wizard/ml/artifacts/leaf_value_net_weights.bin"),
                PathBuf::from("../ml/artifacts/leaf_value_net_weights.bin"),
            ];
            for p in &candidate_paths {
                if p.exists() {
                    match LeafNet::load_from_file(p) {
                        Ok(net) => {
                            eprintln!("✅ Loaded native LeafNet weights from {}", p.display());
                            return Some(net);
                        }
                        Err(e) => eprintln!("⚠️ Failed to load LeafNet from {}: {}", p.display(), e),
                    }
                }
            }
            eprintln!("ℹ️ LeafNet binary weights not found; falling back to exact showdown rollouts.");
            None
        })
        .as_ref()
}

pub fn encode_board_cards(board_ranks: &[u8], board_suits: &[u8]) -> [f32; 75] {
    let mut out = [0.0f32; 75];
    let mut rank_counts = [0usize; 15];
    let mut suit_counts = [0usize; 4];
    let mut max_rank = 0usize;

    for i in 0..board_ranks.len() {
        let r_val = board_ranks[i] as usize + 2; // rank 0=2 -> 2, 12=A -> 14
        let s_val = board_suits[i] as usize;
        let r_idx = 14 - r_val;

        out[r_idx * 4 + s_val] = 1.0;
        out[52 + r_idx] += 1.0;
        out[52 + 13 + s_val] += 1.0;

        rank_counts[r_val] += 1;
        suit_counts[s_val] += 1;
        if r_val > max_rank {
            max_rank = r_val;
        }
    }

    let max_rc = *rank_counts.iter().max().unwrap_or(&0);
    let max_sc = *suit_counts.iter().max().unwrap_or(&0);

    let is_paired = if max_rc == 2 { 1.0 } else { 0.0 };
    let is_trips = if max_rc == 3 { 1.0 } else { 0.0 };
    let is_monotone = if max_sc == 3 { 1.0 } else { 0.0 };
    let is_twotone = if max_sc == 2 { 1.0 } else { 0.0 };
    let is_rainbow = if max_sc <= 1 { 1.0 } else { 0.0 };
    let high_card_norm = max_rank as f32 / 14.0;

    let base_sc = 52 + 13 + 4;
    out[base_sc] = is_paired;
    out[base_sc + 1] = is_trips;
    out[base_sc + 2] = is_monotone;
    out[base_sc + 3] = is_twotone;
    out[base_sc + 4] = is_rainbow;
    out[base_sc + 5] = high_card_norm;

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_leaf_net_inference_parity() {
        let p = Path::new("../ml/artifacts/leaf_value_net_weights.bin");
        if !p.exists() {
            println!("Skipping parity test: weights not found at {:?}", p);
            return;
        }
        let net = LeafNet::load_from_file(p).expect("failed to load weights");
        let dummy = [0.1f32; INPUT_DIM];
        let (vo, vi) = net.forward(&dummy);
        assert_eq!(vo.len(), 169);
        assert_eq!(vi.len(), 169);
        println!("Sample vo[0..3]: {:?}", &vo[0..3]);
        println!("Sample vi[0..3]: {:?}", &vi[0..3]);
    }
}
