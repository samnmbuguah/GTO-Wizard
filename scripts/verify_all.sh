#!/usr/bin/env bash
# scripts/verify_all.sh
#
# One-command verification suite for the generalized engine.
#
#   1. Rust unit tests (pair-equity antisymmetry, pot conservation, bunching)
#   2. Generalization matrix: NL500 / NL50 cash + 20/40/60/100bb MTT ante,
#      exploitability, latency and zero-sum EV conservation - run twice:
#      once on the shipped (learned pair operator) daemon and once on the
#      exact-showdown oracle.
#   3. Card-bunching benchmark (on vs off, built-in and seat-derived profiles)
#   4. Leaf-model accuracy audit against exact ground truth
#   5. Python<->Rust parity for the native pair operator
#   6. Zeno parity harness: our side + exact-CFR oracle + capture sheet
#   7. Reference spot check: re-solve reproducibility + side-by-side
#
# Usage:
#   scripts/verify_all.sh                 # starts its own daemons
#   scripts/verify_all.sh 9989 9980       # use already-running daemons
#
# The suite starts the two daemons itself when the ports are free:
#   * learned port: default settings  -> V2 pair operator (ml/artifacts)
#   * exact port:   GTO_LEAF_NET=off   -> exact showdown equity
#
# Environment:
#   BOARDS=50        number of canonical boards per configuration
#   OUT_DIR=...      where the logs are written

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

LEARNED_PORT="${1:-}"
EXACT_PORT="${2:-}"
PY="${PY:-backend/venv/bin/python}"
OUT_DIR="${OUT_DIR:-/tmp/opencode/verify_all}"
BOARDS="${BOARDS:-50}"
mkdir -p "$OUT_DIR"

STARTED_LEARNED=""
STARTED_EXACT=""

banner() {
  echo
  echo "==================================================================="
  echo "== $1"
  echo "==================================================================="
}

port_open() {
  (echo >/dev/tcp/127.0.0.1/"$1") >/dev/null 2>&1
}

cleanup() {
  [ -n "$STARTED_LEARNED" ] && kill "$STARTED_LEARNED" 2>/dev/null
  [ -n "$STARTED_EXACT" ] && kill "$STARTED_EXACT" 2>/dev/null
}
trap cleanup EXIT

banner "0. Build"
(cd solver_daemon && PATH=/root/.cargo/bin:$PATH cargo build --release 2>&1 | tail -3) \
  | tee "$OUT_DIR/build.log"

if [ -z "$LEARNED_PORT" ]; then
  LEARNED_PORT=9989
fi
if [ -z "$EXACT_PORT" ]; then
  EXACT_PORT=9980
fi

if ! port_open "$LEARNED_PORT"; then
  setsid env PORT="$LEARNED_PORT" ./solver_daemon/target/release/solver_daemon \
    >"$OUT_DIR/daemon_learned.log" 2>&1 < /dev/null &
  STARTED_LEARNED=$!
  sleep 2
fi
if ! port_open "$EXACT_PORT"; then
  setsid env PORT="$EXACT_PORT" GTO_LEAF_NET=off ./solver_daemon/target/release/solver_daemon \
    >"$OUT_DIR/daemon_exact.log" 2>&1 < /dev/null &
  STARTED_EXACT=$!
  sleep 2
fi

banner "0b. Daemon health"
for p in "$LEARNED_PORT" "$EXACT_PORT"; do
  if port_open "$p"; then
    echo "port $p: open"
  else
    echo "port $p: CLOSED"
  fi
done

banner "1. Rust unit tests"
(cd solver_daemon && PATH=/root/.cargo/bin:$PATH cargo test --lib 2>&1 | tail -20) \
  | tee "$OUT_DIR/rust_tests.log"

banner "2. Generalization matrix (shipped engine: learned pair operator)"
$PY scripts/verify_generalization.py --port "$LEARNED_PORT" \
  --configs cash_nl500,cash_nl50,mtt_20bb,mtt_40bb,mtt_60bb,mtt_100bb \
  --boards "$BOARDS" 2>&1 | tee "$OUT_DIR/generalization_learned.log"

banner "3. Generalization matrix (exact-showdown oracle)"
$PY scripts/verify_generalization.py --port "$EXACT_PORT" \
  --configs cash_nl500,cash_nl50,mtt_20bb,mtt_40bb,mtt_60bb,mtt_100bb \
  --boards "$BOARDS" 2>&1 | tee "$OUT_DIR/generalization_exact.log"

banner "4. Card-bunching benchmark (built-in profile)"
$PY scripts/benchmark_bunching.py --port "$LEARNED_PORT" --configs cash,mtt40 \
  --mode builtin 2>&1 | tee "$OUT_DIR/bunching_builtin.log"

banner "5. Card-bunching benchmark (seat-derived profile)"
$PY scripts/benchmark_bunching.py --port "$LEARNED_PORT" --configs cash,mtt40 \
  --mode seat 2>&1 | tee "$OUT_DIR/bunching_seat.log"

banner "6. Leaf-model accuracy audit"
SOLVER_DAEMON_HOST=127.0.0.1 SOLVER_DAEMON_PORT="$LEARNED_PORT" \
  $PY scripts/verify_model_accuracy.py 2>&1 | tee "$OUT_DIR/model_accuracy.log"

banner "7. Python<->Rust parity (native pair operator)"
$PY scripts/check_pair_parity.py --port "$LEARNED_PORT" --boards 8 \
  2>&1 | tee "$OUT_DIR/pair_parity.log"

banner "8. Zeno parity harness (our side + exact oracle + capture sheet)"
$PY scripts/zeno_parity_harness.py solve --port "$LEARNED_PORT" \
  --oracle-port "$EXACT_PORT" --boards "$BOARDS" \
  2>&1 | tee "$OUT_DIR/zeno_parity_solve.log"

$PY scripts/zeno_parity_harness.py compare --source auto \
  2>&1 | tee "$OUT_DIR/zeno_parity_compare.log"

banner "9. Reference spot check (re-solve reproducibility)"
$PY scripts/reference_spot_check.py docs/reference_spots.example.csv \
  --port "$LEARNED_PORT" --source our \
  2>&1 | tee "$OUT_DIR/reference_spot_reproduce.log"

banner "10. Reference spot check (side-by-side vs exact oracle)"
$PY scripts/reference_spot_check.py docs/reference_spots.example.csv \
  --port "$LEARNED_PORT" --source oracle \
  2>&1 | tee "$OUT_DIR/reference_spot_check.log"

echo
echo "Logs written to $OUT_DIR"
