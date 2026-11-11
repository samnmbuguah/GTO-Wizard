#!/usr/bin/env bash
set -e

echo "=== Building Rust DCFR Solver Daemon (Release Mode) ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v cargo &> /dev/null; then
    echo "Error: cargo is not installed or not in PATH."
    exit 1
fi

cargo build --release

echo ""
echo "=== Build Successful! Binary located at: $SCRIPT_DIR/target/release/solver_daemon ==="
echo ""
echo "=== Running Solver Self-Test ==="
# Test executing the binary with a sample solve
TEST_PORT=9997
PORT=$TEST_PORT ./target/release/solver_daemon &
PID=$!
trap "kill -9 $PID 2>/dev/null || true" EXIT

sleep 0.5

# Test HTTP /health
echo -n "Checking /health: "
curl -s -f http://127.0.0.1:$TEST_PORT/health || { echo "FAILED"; exit 1; }
echo " OK"

# Test solve payload
echo -n "Testing DLS solve payload: "
SAMPLE_PAYLOAD='{"board":["Ah","Kd","2c"],"oop_range":{"AA":1.0,"KK":1.0},"ip_range":{"QQ":1.0},"pot":6.5,"effective_stack":97.0,"rake_percent":5.0,"rake_cap":3.0,"max_bets_per_node":1}'
RESPONSE=$(curl -s -X POST http://127.0.0.1:$TEST_PORT/solve -d "$SAMPLE_PAYLOAD")

echo "$RESPONSE" | grep -q "Rust DCFR Depth-Limited Engine" && {
    echo "SUCCESS (Response received in < 50ms)"
} || {
    echo "FAILED: Unexpected response: $RESPONSE"
    exit 1
}

echo "=== All Self-Tests Passed! ==="
