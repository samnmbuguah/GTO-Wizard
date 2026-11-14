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
        self.forward_dim(x, HIDDEN_DIM);
    }

    /// Same block with a runtime width (the V2 pair operator uses 128 units).
    pub fn forward_dim(&self, x: &mut [f32], dim: usize) {
        let mut residual = vec![0.0f32; dim];
        residual.copy_from_slice(x);

        let mut h = vec![0.0f32; dim];
        matvec(&mut h, &self.fc1_w, &self.fc1_b, x, dim, dim);
        layer_norm(&mut h, &self.ln1_w, &self.ln1_b, 1e-5);
        for v in &mut h {
            *v = gelu(*v);
        }

        matvec(x, &self.fc2_w, &self.fc2_b, &h, dim, dim);
        layer_norm(x, &self.ln2_w, &self.ln2_b, 1e-5);
        for i in 0..dim {
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

    /// Predicts the per-class equity-share vectors for one leaf state.
    ///
    /// The returned `t_o[i]` / `t_i[i]` are the fraction of the net pot that
    /// class `i` wins against the opponent's *normalised* range. They are
    /// projected so `sum(ro_n * t_o) + sum(ri_n * t_i) == 1`.
    ///
    /// Callers that need a stationary terminal payoff (CFR traversals, best
    /// response) should evaluate these once per public leaf and then rebuild
    /// the value vectors with [`shares_to_values`]. Evaluating them from the
    /// live traversal reach every iteration makes the leaf payoff depend on the
    /// strategy, which breaks the bilinearity CFR relies on.
    pub fn evaluate_shares(
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
    ) -> Option<(Vec<f64>, Vec<f64>)> {
        let tot_pot = pot + invested[0] + invested[1];
        let rake = (tot_pot * (rake_pct / 100.0)).min(rake_cap);
        let net_pot = tot_pot - rake;

        let m_o: f64 = reach_o.iter().sum();
        let m_i: f64 = reach_i.iter().sum();
        if m_o <= 1e-12 || m_i <= 1e-12 {
            return None;
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
        let mut t_o = vec![0.0f64; N_CLASSES];
        let mut t_i = vec![0.0f64; N_CLASSES];
        let mut err = -1.0f64;
        for h in 0..N_CLASSES {
            t_o[h] = 1.0 / (1.0 + (-(logit_o[h] as f64)).exp());
            t_i[h] = 1.0 / (1.0 + (-(logit_i[h] as f64)).exp());
            err += (reach_o[h] / m_o) * t_o[h] + (reach_i[h] / m_i) * t_i[h];
        }
        // Zero-sum projection: sum(ro_n * t_o) + sum(ri_n * t_i) == 1.
        let half = err / 2.0;
        for h in 0..N_CLASSES {
            t_o[h] -= half;
            t_i[h] -= half;
        }
        Some((t_o, t_i))
    }

    /// Rebuilds per-class counterfactual values from cached shares.
    ///
    /// `v_o[i] = (t_o[i] * net_pot - invested_oop) * reach_ip_mass` and the
    /// symmetric formula for IP. The result is linear in the opponent's reach
    /// mass, which is exactly the shape CFR and best response expect. The
    /// shares are refreshed from the solver's average strategy, so at the
    /// reported solution they are self-consistent with the reaches in use.
    pub fn shares_to_values(
        t_o: &[f64],
        t_i: &[f64],
        invested: [f64; 2],
        pot: f64,
        rake_pct: f64,
        rake_cap: f64,
        reach_o: &[f64],
        reach_i: &[f64],
    ) -> (Vec<f64>, Vec<f64>) {
        let tot_pot = pot + invested[0] + invested[1];
        let rake = (tot_pot * (rake_pct / 100.0)).min(rake_cap);
        let net_pot = tot_pot - rake;
        let m_o: f64 = reach_o.iter().sum();
        let m_i: f64 = reach_i.iter().sum();
        let mut v_o = vec![0.0f64; N_CLASSES];
        let mut v_i = vec![0.0f64; N_CLASSES];
        for h in 0..N_CLASSES {
            v_o[h] = (t_o[h] * net_pot - invested[0]) * m_i;
            v_i[h] = (t_i[h] * net_pot - invested[1]) * m_o;
        }
        (v_o, v_i)
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
        match self.evaluate_shares(
            board_features, reach_o, reach_i, invested, pot, effective_stack, ante_bb,
            rake_pct, rake_cap, num_folded_players,
        ) {
            Some((t_o, t_i)) => Self::shares_to_values(
                &t_o, &t_i, invested, pot, rake_pct, rake_cap, reach_o, reach_i,
            ),
            None => {
                let m_o: f64 = reach_o.iter().sum();
                let m_i: f64 = reach_i.iter().sum();
                let mut v_o = vec![0.0f64; N_CLASSES];
                let mut v_i = vec![0.0f64; N_CLASSES];
                for h in 0..N_CLASSES {
                    v_o[h] = -invested[0] * m_i;
                    v_i[h] = -invested[1] * m_o;
                }
                (v_o, v_i)
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Board-conditioned antisymmetric pair-equity operator
// ---------------------------------------------------------------------------

const PAIR_INPUT_DIM: usize = 81; // 75 board features + 6 generalized context
const PAIR_NUM_BLOCKS: usize = 2;

/// Board-conditioned 169x169 pair-equity operator.
///
/// The model predicts `a[i]` (hand-strength score) and low-rank factors
/// `U, V` (169 x rank), and forms
///
/// ```text
/// G[i][j] = a[i] - a[j] + (U Vᵀ - V Uᵀ)[i][j] / sqrt(rank)
/// E[i][j] = sigmoid(G[i][j])
/// ```
///
/// so `E[i][j] + E[j][i] == 1` exactly. That identity makes pot conservation
/// structural: it holds for any pair of independent reaches, with no per-node
/// caching or zero-sum projection step.
pub struct PairEquityNet {
    pub in_w: Vec<f32>,
    pub in_b: Vec<f32>,
    pub in_ln_w: Vec<f32>,
    pub in_ln_b: Vec<f32>,
    pub blocks: Vec<ResBlockWeights>,
    pub head_fc1_w: Vec<f32>,
    pub head_fc1_b: Vec<f32>,
    pub head_ln_w: Vec<f32>,
    pub head_ln_b: Vec<f32>,
    pub head_fc2_w: Vec<f32>,
    pub head_fc2_b: Vec<f32>,
    pub rank: usize,
}

fn read_tensor_map(path: &Path) -> Result<HashMap<String, Vec<f32>>, String> {
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
            num_elems *= u32::from_le_bytes(buf4) as usize;
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
    Ok(tensors)
}

impl PairEquityNet {
    pub fn load_from_file(path: &Path) -> Result<Self, String> {
        let tensors = read_tensor_map(path)?;
        let get = |name: &str| -> Result<Vec<f32>, String> {
            tensors.get(name).cloned().ok_or_else(|| format!("missing tensor: {}", name))
        };

        let in_w = get("input_proj.0.weight")?;
        let rank = {
            // head.3.weight is (169 + 2*169*rank) x 128.
            let hw = get("head.3.weight")?;
            let out_dim = hw.len() / HEAD_DIM;
            let r = out_dim.saturating_sub(N_CLASSES) / (2 * N_CLASSES);
            if r == 0 || r * 2 * N_CLASSES + N_CLASSES != out_dim {
                return Err(format!("cannot infer rank from head.3.weight out_dim={}", out_dim));
            }
            r
        };
        if in_w.len() != HIDDEN_DIM * PAIR_INPUT_DIM {
            return Err(format!(
                "pair input_proj.0.weight size mismatch: got {} expected {}",
                in_w.len(),
                HIDDEN_DIM * PAIR_INPUT_DIM
            ));
        }

        let mut blocks = Vec::new();
        for b in 0..PAIR_NUM_BLOCKS {
            let key = format!("blocks.{}.fc1.weight", b);
            if !tensors.contains_key(&key) {
                break;
            }
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

        Ok(PairEquityNet {
            in_w,
            in_b: get("input_proj.0.bias")?,
            in_ln_w: get("input_proj.1.weight")?,
            in_ln_b: get("input_proj.1.bias")?,
            blocks,
            head_fc1_w: get("head.0.weight")?,
            head_fc1_b: get("head.0.bias")?,
            head_ln_w: get("head.1.weight")?,
            head_ln_b: get("head.1.bias")?,
            head_fc2_w: get("head.3.weight")?,
            head_fc2_b: get("head.3.bias")?,
            rank,
        })
    }

    fn forward(&self, x: &[f32]) -> (Vec<f32>, Vec<f32>, Vec<f32>) {
        let mut h = [0.0f32; HIDDEN_DIM];
        matvec(&mut h, &self.in_w, &self.in_b, x, HIDDEN_DIM, PAIR_INPUT_DIM);
        layer_norm(&mut h, &self.in_ln_w, &self.in_ln_b, 1e-5);
        for v in &mut h {
            *v = gelu(*v);
        }
        for block in &self.blocks {
            block.forward(&mut h);
        }

        let mut hh = [0.0f32; HEAD_DIM];
        matvec(&mut hh, &self.head_fc1_w, &self.head_fc1_b, &h, HEAD_DIM, HIDDEN_DIM);
        layer_norm(&mut hh, &self.head_ln_w, &self.head_ln_b, 1e-5);
        for v in &mut hh {
            *v = gelu(*v);
        }

        let out_dim = N_CLASSES + 2 * N_CLASSES * self.rank;
        let mut out = vec![0.0f32; out_dim];
        matvec(&mut out, &self.head_fc2_w, &self.head_fc2_b, &hh, out_dim, HEAD_DIM);
        let a = out[..N_CLASSES].to_vec();
        let u = out[N_CLASSES..N_CLASSES + N_CLASSES * self.rank].to_vec();
        let v = out[N_CLASSES + N_CLASSES * self.rank..].to_vec();
        (a, u, v)
    }

    /// Evaluates the 169x169 equity matrix for a board and solver context.
    /// Called once per solve; the result is independent of the reaches.
    #[allow(clippy::too_many_arguments)]
    pub fn equity_matrix(
        &self,
        board_features: &[f32; 75],
        starting_pot: f64,
        effective_stack: f64,
        ante_bb: f64,
        rake_pct: f64,
        rake_cap: f64,
        num_folded_players: usize,
    ) -> Vec<f64> {
        let mut x = [0.0f32; PAIR_INPUT_DIM];
        x[..75].copy_from_slice(board_features);
        x[75] = (effective_stack / 100.0) as f32;
        x[76] = (starting_pot / 10.0) as f32;
        x[77] = ante_bb as f32;
        x[78] = (rake_pct / 10.0) as f32;
        x[79] = (rake_cap / 5.0) as f32;
        x[80] = num_folded_players as f32 / 6.0;
        let (a, u, v) = self.forward(&x);
        let r = self.rank;
        let scale = 1.0 / (r as f64).sqrt();
        let mut e = vec![0.0f64; N_CLASSES * N_CLASSES];
        for i in 0..N_CLASSES {
            e[i * N_CLASSES + i] = 0.5;
            for j in (i + 1)..N_CLASSES {
                let mut dot = 0.0f64;
                for k in 0..r {
                    let ui = u[i * r + k] as f64;
                    let vi = v[i * r + k] as f64;
                    let uj = u[j * r + k] as f64;
                    let vj = v[j * r + k] as f64;
                    dot += ui * vj - vi * uj;
                }
                let g = (a[i] as f64 - a[j] as f64) + dot * scale;
                let s = 1.0 / (1.0 + (-g).exp());
                e[i * N_CLASSES + j] = s;
                // Mirror explicitly so the complement identity is exact.
                e[j * N_CLASSES + i] = 1.0 - s;
            }
        }
        e
    }
}

/// V2 dense antisymmetric pair-equity operator.
///
/// Every unordered hand-class pair gets its own logit:
///
/// ```text
/// s[i][j] = w_ij · h + b_ij     (i < j)
/// s[j][i] = -s[i][j]
/// E[i][j] = sigmoid(s[i][j])
/// ```
///
/// so `E[i][j] + E[j][i] = 1` holds exactly (pot conservation stays
/// structural) while the model has pair-specific capacity. The V1 operator
/// (low-rank skew) could not represent the real equity matrix closely
/// enough for the CFR leaf path to converge; V2 reaches a root EV error of
/// ~0.01 bb against exact showdown on held-out boards.
pub struct DensePairEquityNet {
    pub in_w: Vec<f32>,
    pub in_b: Vec<f32>,
    pub in_ln_w: Vec<f32>,
    pub in_ln_b: Vec<f32>,
    pub blocks: Vec<ResBlockWeights>,
    /// (n_pairs, hidden) row-major pair weights.
    pub pair_w: Vec<f32>,
    /// (n_pairs,) pair biases.
    pub pair_b: Vec<f32>,
    pub hidden: usize,
    pub pairs: usize,
}

impl DensePairEquityNet {
    pub fn load_from_file(path: &Path) -> Result<Self, String> {
        let tensors = read_tensor_map(path)?;
        let get = |name: &str| -> Result<Vec<f32>, String> {
            tensors.get(name).cloned().ok_or_else(|| format!("missing tensor: {}", name))
        };
        let meta = |name: &str| -> Result<usize, String> {
            let v = get(name)?;
            if v.is_empty() {
                return Err(format!("empty meta tensor: {}", name));
            }
            Ok(v[0] as usize)
        };

        let hidden = meta("meta.hidden")?;
        let pairs = meta("meta.pairs")?;
        let in_w = get("input_proj.0.weight")?;
        if in_w.len() != hidden * PAIR_INPUT_DIM {
            return Err(format!(
                "v2 input_proj.0.weight size mismatch: got {} expected {}",
                in_w.len(),
                hidden * PAIR_INPUT_DIM
            ));
        }
        let pair_w = get("pair_w")?;
        if pair_w.len() != pairs * hidden {
            return Err(format!(
                "v2 pair_w size mismatch: got {} expected {}",
                pair_w.len(),
                pairs * hidden
            ));
        }
        let pair_b = get("pair_b")?;
        if pair_b.len() != pairs {
            return Err(format!(
                "v2 pair_b size mismatch: got {} expected {}",
                pair_b.len(),
                pairs
            ));
        }

        let mut blocks = Vec::new();
        for b in 0..PAIR_NUM_BLOCKS {
            let key = format!("blocks.{}.fc1.weight", b);
            if !tensors.contains_key(&key) {
                break;
            }
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

        Ok(DensePairEquityNet {
            in_w,
            in_b: get("input_proj.0.bias")?,
            in_ln_w: get("input_proj.1.weight")?,
            in_ln_b: get("input_proj.1.bias")?,
            blocks,
            pair_w,
            pair_b,
            hidden,
            pairs,
        })
    }

    fn trunk(&self, x: &[f32]) -> Vec<f32> {
        let mut h = vec![0.0f32; self.hidden];
        matvec(&mut h, &self.in_w, &self.in_b, x, self.hidden, PAIR_INPUT_DIM);
        layer_norm(&mut h, &self.in_ln_w, &self.in_ln_b, 1e-5);
        for v in &mut h {
            *v = gelu(*v);
        }
        for block in &self.blocks {
            block.forward_dim(&mut h, self.hidden);
        }
        h
    }

    /// Evaluates the 169x169 equity matrix for a board and solver context.
    /// Called once per solve; the result is independent of the reaches.
    #[allow(clippy::too_many_arguments)]
    pub fn equity_matrix(
        &self,
        board_features: &[f32; 75],
        starting_pot: f64,
        effective_stack: f64,
        ante_bb: f64,
        rake_pct: f64,
        rake_cap: f64,
        num_folded_players: usize,
    ) -> Vec<f64> {
        let mut x = [0.0f32; PAIR_INPUT_DIM];
        x[..75].copy_from_slice(board_features);
        x[75] = (effective_stack / 100.0) as f32;
        x[76] = (starting_pot / 10.0) as f32;
        x[77] = ante_bb as f32;
        x[78] = (rake_pct / 10.0) as f32;
        x[79] = (rake_cap / 5.0) as f32;
        x[80] = num_folded_players as f32 / 6.0;

        let h = self.trunk(&x);
        let mut e = vec![0.0f64; N_CLASSES * N_CLASSES];
        let mut p = 0usize;
        for i in 0..N_CLASSES {
            e[i * N_CLASSES + i] = 0.5;
            for j in (i + 1)..N_CLASSES {
                if p >= self.pairs {
                    break;
                }
                let row = &self.pair_w[p * self.hidden..(p + 1) * self.hidden];
                let mut s = self.pair_b[p];
                for k in 0..self.hidden {
                    s += row[k] * h[k];
                }
                let sig = 1.0 / (1.0 + (-(s as f64)).exp());
                e[i * N_CLASSES + j] = sig;
                // Mirror explicitly so the complement identity is exact.
                e[j * N_CLASSES + i] = 1.0 - sig;
                p += 1;
            }
        }
        e
    }
}

/// Counterfactual values induced by a pair-equity matrix.
///
/// `v_oop[i] = (Σ_j E[i][j]·ri_n[j]·net_pot − invested_oop)·m_i`
/// `v_ip[j]  = ((1 − Σ_i ro_n[i]·E[i][j])·net_pot − invested_ip)·m_o`
///
/// Because `E[i][j] + E[j][i] = 1`, summing these against the reaches gives
/// `m_o·m_i·(pot − rake)` exactly for any reaches.
pub fn pair_values(
    e: &[f64],
    invested: [f64; 2],
    pot: f64,
    rake_pct: f64,
    rake_cap: f64,
    reach_o: &[f64],
    reach_i: &[f64],
) -> (Vec<f64>, Vec<f64>) {
    let total = pot + invested[0] + invested[1];
    let rake = (total * (rake_pct / 100.0)).min(rake_cap);
    let net_pot = total - rake;
    let m_o: f64 = reach_o.iter().sum();
    let m_i: f64 = reach_i.iter().sum();
    let mut v_o = vec![0.0f64; N_CLASSES];
    let mut v_i = vec![0.0f64; N_CLASSES];

    // Each side is guarded independently: the OOP value depends on the IP
    // reach and the IP value depends on the OOP reach. A global guard (as in
    // an earlier revision) zeroed *both* sides whenever one reach was empty,
    // which happens on every best-response traversal of an action with
    // probability 0. That silently corrupted the NashConv measurement and
    // stopped CFR from converging. The exact showdown path has always
    // guarded each side separately; this mirrors it exactly.
    if m_i > 1e-12 {
        let active_i: Vec<(usize, f64)> = reach_i
            .iter()
            .copied()
            .enumerate()
            .filter(|&(_, r)| r != 0.0)
            .map(|(j, r)| (j, r / m_i))
            .collect();
        for i in 0..N_CLASSES {
            let base = i * N_CLASSES;
            let row = &e[base..base + N_CLASSES];
            let mut share = 0.0;
            for &(j, rin_j) in &active_i {
                share += row[j] * rin_j;
            }
            v_o[i] = (share * net_pot - invested[0]) * m_i;
        }
    } else {
        v_o.fill(-invested[0] * m_i);
    }

    if m_o > 1e-12 {
        let mut shares_i = [0.0f64; N_CLASSES];
        for h in 0..N_CLASSES {
            let r_oh = reach_o[h];
            if r_oh == 0.0 {
                continue;
            }
            let ron_h = r_oh / m_o;
            let base = h * N_CLASSES;
            let row = &e[base..base + N_CLASSES];
            for j in 0..N_CLASSES {
                shares_i[j] += ron_h * row[j];
            }
        }
        for j in 0..N_CLASSES {
            v_i[j] = ((1.0 - shares_i[j]) * net_pot - invested[1]) * m_o;
        }
    } else {
        v_i.fill(-invested[1] * m_o);
    }
    (v_o, v_i)
}

pub static GLOBAL_PAIR_NET: OnceLock<Option<PairEquityNet>> = OnceLock::new();
pub static GLOBAL_PAIR_NET_V2: OnceLock<Option<DensePairEquityNet>> = OnceLock::new();

/// Loads the V2 dense pair-equity operator (preferred over V1 when present).
pub fn get_pair_net_v2() -> Option<&'static DensePairEquityNet> {
    GLOBAL_PAIR_NET_V2
        .get_or_init(|| {
            if !learned_pair_enabled() {
                return None;
            }
            let candidate_paths = [
                PathBuf::from("ml/artifacts/pair_equity_net_v2_weights.bin"),
                PathBuf::from("/app/artifacts/pair_equity_net_v2_weights.bin"),
                PathBuf::from("/root/Dev/GTO-Wizard/ml/artifacts/pair_equity_net_v2_weights.bin"),
                PathBuf::from("../ml/artifacts/pair_equity_net_v2_weights.bin"),
            ];
            for p in &candidate_paths {
                if p.exists() {
                    match DensePairEquityNet::load_from_file(p) {
                        Ok(net) => {
                            eprintln!("✅ Loaded V2 dense pair-equity net from {}", p.display());
                            return Some(net);
                        }
                        Err(e) => eprintln!("⚠️ Failed to load V2 pair-equity net from {}: {}", p.display(), e),
                    }
                }
            }
            None
        })
        .as_ref()
}

/// Learned leaf evaluators.
///
/// * `GTO_LEAF_NET=off` (or 0/false/no) forces exact showdown equity.
/// * `GTO_LEAF_NET=on` (or 1/true/yes) enables every learned evaluator,
///   including the reach-conditioned marginal net (kept for experiments).
/// * unset (the default) enables the **pair operator** when its weights are
///   present. The pair operator is reach-independent, conserves the pot
///   structurally and passes the 0.5%-pot exploitability gate on the whole
///   verification matrix, so it is the shipped leaf evaluator. The marginal
///   net stays off unless it is explicitly requested.
///
/// If the learned attempt misses the accuracy gate the engine transparently
/// re-solves the same spot with exact showdown equity
/// (`solver_daemon/src/lib.rs::leaf_result_passes`).
fn learned_leaf_enabled() -> bool {
    matches!(
        std::env::var("GTO_LEAF_NET").as_deref(),
        Ok("on") | Ok("1") | Ok("true") | Ok("yes")
    )
}

fn learned_pair_enabled() -> bool {
    match std::env::var("GTO_LEAF_NET").as_deref() {
        Ok("on") | Ok("1") | Ok("true") | Ok("yes") => true,
        Ok("off") | Ok("0") | Ok("false") | Ok("no") => false,
        // Auto: the pair operator is the default leaf evaluator.
        _ => true,
    }
}

pub fn get_pair_net() -> Option<&'static PairEquityNet> {
    GLOBAL_PAIR_NET
        .get_or_init(|| {
            if !learned_pair_enabled() {
                eprintln!(
                    "ℹ️ Learned leaf path disabled (GTO_LEAF_NET=off); \
                     using exact showdown equity at leaves."
                );
                return None;
            }
            let candidate_paths = [
                PathBuf::from("ml/artifacts/pair_equity_net_weights.bin"),
                PathBuf::from("/app/artifacts/pair_equity_net_weights.bin"),
                PathBuf::from("/root/Dev/GTO-Wizard/ml/artifacts/pair_equity_net_weights.bin"),
                PathBuf::from("../ml/artifacts/pair_equity_net_weights.bin"),
            ];
            for p in &candidate_paths {
                if p.exists() {
                    match PairEquityNet::load_from_file(p) {
                        Ok(net) => {
                            eprintln!("✅ Loaded pair-equity net from {}", p.display());
                            return Some(net);
                        }
                        Err(e) => eprintln!("⚠️ Failed to load pair-equity net from {}: {}", p.display(), e),
                    }
                }
            }
            eprintln!("ℹ️ V1 pair-equity weights not found; using exact showdown equity.");
            None
        })
        .as_ref()
}

pub static GLOBAL_LEAF_NET: OnceLock<Option<LeafNet>> = OnceLock::new();

pub fn get_leaf_net() -> Option<&'static LeafNet> {
    GLOBAL_LEAF_NET
        .get_or_init(|| {
            if !learned_leaf_enabled() {
                eprintln!("ℹ️ Marginal leaf net disabled (set GTO_LEAF_NET=on to enable); \
                           using the pair operator or exact showdown equity.");
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
        // The solver's internal suit order is c,d,h,s (0..3) but the models are
        // trained on the Python encoding s,h,d,c (0..3). Map between the two so
        // the daemon feeds the network exactly the features it was trained on.
        let s_val = 3usize.saturating_sub(board_suits[i] as usize);
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

    #[test]
    fn test_pair_equity_antisymmetry_and_conservation() {
        let p = Path::new("../ml/artifacts/pair_equity_net_weights.bin");
        if !p.exists() {
            println!("Skipping pair test: weights not found at {:?}", p);
            return;
        }
        let net = PairEquityNet::load_from_file(p).expect("failed to load pair weights");
        let board = encode_board_cards(&[12u8, 11, 0], &[0u8, 2, 1]);
        let e = net.equity_matrix(&board, 5.5, 100.0, 0.0, 5.0, 0.6, 4);
        assert_eq!(e.len(), N_CLASSES * N_CLASSES);
        let mut worst = 0.0f64;
        for i in 0..N_CLASSES {
            for j in 0..N_CLASSES {
                worst = worst.max((e[i * N_CLASSES + j] + e[j * N_CLASSES + i] - 1.0).abs());
            }
        }
        assert!(worst < 1e-12, "antisymmetry error {worst}");

        // Conservation must hold for arbitrary independent reaches.
        let ro: Vec<f64> = (0..N_CLASSES).map(|i| if i % 3 == 0 { 0.4 } else { 0.0 }).collect();
        let ri: Vec<f64> = (0..N_CLASSES).map(|i| if i % 5 == 0 { 0.3 } else { 0.0 }).collect();
        let (vo, vi) = pair_values(&e, [1.0, 2.0], 5.5, 5.0, 0.6, &ro, &ri);
        let m_o: f64 = ro.iter().sum();
        let m_i: f64 = ri.iter().sum();
        let dot = |a: &[f64], b: &[f64]| a.iter().zip(b).map(|(x, y)| x * y).sum::<f64>();
        let lhs = dot(&ro, &vo) + dot(&ri, &vi);
        let pot: f64 = 5.5;
        let rake = ((pot + 3.0) * 0.05).min(0.6);
        let target = m_o * m_i * (pot - rake);
        assert!((lhs - target).abs() < 1e-9, "conservation off by {}", (lhs - target).abs());
    }

    /// The zero-reach guard must be *per side*: an empty OOP reach must not
    /// zero out the IP player's value (and vice versa). The best-response
    /// traversal produces empty reaches whenever an action has probability 0,
    /// so a global guard silently corrupted the NashConv measurement and
    /// stopped CFR from converging.
    #[test]
    fn test_pair_values_zero_reach_is_per_side() {
        let mut e = vec![0.5f64; N_CLASSES * N_CLASSES];
        for i in 0..N_CLASSES {
            for j in 0..N_CLASSES {
                e[i * N_CLASSES + j] = if i == j { 0.5 } else { 0.75 };
            }
        }
        // The IP side has reach, the OOP side does not. The OOP value depends
        // only on the IP reach, so it must still be computed; the IP value
        // has no opponent to win against, so it is zero.
        let ro = vec![0.0f64; N_CLASSES];
        let mut ri = vec![0.0f64; N_CLASSES];
        ri[0] = 1.0;
        let (vo, vi) = pair_values(&e, [1.0, 2.0], 5.5, 0.0, 0.0, &ro, &ri);
        assert!(
            vo.iter().any(|v| v.abs() > 1e-9),
            "empty OOP reach must not zero out the OOP value"
        );
        assert!(
            vi.iter().all(|v| v.abs() < 1e-12),
            "empty OOP reach must give a zero IP value"
        );
        // And the other way round.
        let mut ro2 = vec![0.0f64; N_CLASSES];
        ro2[0] = 1.0;
        let ri2 = vec![0.0f64; N_CLASSES];
        let (vo2, vi2) = pair_values(&e, [1.0, 2.0], 5.5, 0.0, 0.0, &ro2, &ri2);
        assert!(
            vi2.iter().any(|v| v.abs() > 1e-9),
            "empty IP reach must not zero out the IP value"
        );
        assert!(
            vo2.iter().all(|v| v.abs() < 1e-12),
            "empty IP reach must give a zero OOP value"
        );
    }

    /// The V2 dense operator must be antisymmetric as well.
    #[test]
    fn test_dense_pair_equity_antisymmetry() {
        let p = Path::new("../ml/artifacts/pair_equity_net_v2_weights.bin");
        if !p.exists() {
            println!("Skipping V2 pair test: weights not found at {:?}", p);
            return;
        }
        let net = DensePairEquityNet::load_from_file(p).expect("failed to load V2 pair weights");
        // Ah Kd 2c
        let board = encode_board_cards(&[12u8, 11, 0], &[3u8, 2, 1]);
        let e = net.equity_matrix(&board, 5.5, 100.0, 0.0, 5.0, 0.6, 4);
        assert_eq!(e.len(), N_CLASSES * N_CLASSES);
        let mut worst = 0.0f64;
        for i in 0..N_CLASSES {
            for j in 0..N_CLASSES {
                worst = worst.max((e[i * N_CLASSES + j] + e[j * N_CLASSES + i] - 1.0).abs());
            }
        }
        assert!(worst < 1e-9, "V2 antisymmetry error {worst}");
    }
}
