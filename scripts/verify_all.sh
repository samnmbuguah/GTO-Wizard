#!/usr/bin/env bash
# scripts/verify_all.sh
#
# One-command verification suite for the generalized engine.
#
#   1. Rust unit tests (pair-equity antisymmetry + pot conservation, bunching)
#   2. Generalization matrix: NL500 / NL50 cash + 20/40/60/100bb MTT ante,
#      exploitability, latency and zero-sum EV conservation
#   3. Card-bunching benchmark (on vs off, built-in and seat-derived profiles)
#   4. Leaf-model accuracy audit against exact ground truth
#   5. Zeno parity harness: our side + exact-CFR oracle + capture sheet
#
# Usage:
#   scripts/verify_all.sh [learned_port] [exact_port]
#
# Default ports: learned daemon 9998, exact oracle daemon 9971.
# The exact oracle must be started with GTO_LEAF_NET=off.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LEARNED_PORT="${1:-9998}"
EXACT_PORT="${2:-9971}"
PY="${PY:-backend/venv/bin/python}"
OUT_DIR="${OUT_DIR:-/tmp/opencode/verify_all}"
mkdir -p "$OUT_DIR"

banner() {
  echo
  echo "==================================================================="
  echo "== $1"
  echo "==================================================================="
}

banner "0. Daemon health"
for p in "$LEARNED_PORT" "$EXACT_PORT"; do
  if (echo >/dev/tcp/127.0.0.1/"$p") >/dev/null 2>&1; then
    echo "port $p: open"
  else
    echo "port $p: CLOSED (start the daemon before running this suite)"
  fi
done

banner "1. Rust unit tests"
(cd solver_daemon && PATH=/root/.cargo/bin:$PATH cargo test --lib 2>&1 | tail -20) \
  | tee "$OUT_DIR/rust_tests.log"

banner "2. Generalization matrix (learned engine)"
$PY scripts/verify_generalization.py --port "$LEARNED_PORT" \
  --configs cash_nl500,cash_nl50,mtt_20bb,mtt_40bb,mtt_60bb,mtt_100bb \
  --boards "${BOARDS:-50}" 2>&1 | tee "$OUT_DIR/generalization_learned.log"

banner "3. Generalization matrix (exact oracle)"
$PY scripts/verify_generalization.py --port "$EXACT_PORT" \
  --configs cash_nl500,cash_nl50,mtt_20bb,mtt_40bb,mtt_60bb,mtt_100bb \
  --boards "${BOARDS:-50}" 2>&1 | tee "$OUT_DIR/generalization_exact.log"

banner "4. Card-bunching benchmark (built-in profile)"
$PY scripts/benchmark_bunching.py --port "$LEARNED_PORT" --configs cash,mtt40 \
  --mode builtin 2>&1 | tee "$OUT_DIR/bunching_builtin.log"

banner "5. Card-bunching benchmark (seat-derived profile)"
$PY scripts/benchmark_bunching.py --port "$LEARNED_PORT" --configs cash,mtt40 \
  --mode seat 2>&1 | tee "$OUT_DIR/bunching_seat.log"

banner "6. Leaf-model accuracy audit"
$PY scripts/verify_model_accuracy.py 2>&1 | tee "$OUT_DIR/model_accuracy.log"

banner "7. Zeno parity harness (our side + exact oracle + capture sheet)"
$PY scripts/zeno_parity_harness.py solve --port "$LEARNED_PORT" \
  --oracle-port "$EXACT_PORT" --boards "${BOARDS:-50}" \
  2>&1 | tee "$OUT_DIR/zeno_parity_solve.log"

$PY scripts/zeno_parity_harness.py compare --source auto \
  2>&1 | tee "$OUT_DIR/zeno_parity_compare.log"

banner "8. Reference spot check (side-by-side)"
$PY scripts/reference_spot_check.py docs/reference_spots.example.csv \
  --port "$LEARNED_PORT" --source auto \
  2>&1 | tee "$OUT_DIR/reference_spot_check.log"

echo
echo "Logs written to $OUT_DIR"
