#!/usr/bin/env python3
"""
scripts/zeno_parity_harness.py

Side-by-side parity harness for comparing this engine against ZenoSolver.

What this automates
-------------------
1. **Our side (fully automated).** Every spot in the matrix is solved by the
   running Rust daemon and the resulting values are written into the reference
   CSV (`our_*` columns).
2. **Independent oracle (fully automated).** The same spot is re-solved by a
   daemon started with `GTO_LEAF_NET=off`, i.e. with exact showdown equity and
   no learned model. Those values are written into `oracle_*` columns and act
   as a *reference implementation* for the learned path (they are NOT Zeno
   numbers and are labelled as such).
3. **The capture sheet.** A human-readable sheet (`docs/zeno_capture_sheet.md`
   and `.csv`) is generated listing exactly which numbers to read off the
   ZenoSolver UI for each spot, so a human can capture dozens of spots in one
   pass.
4. **Import + compare.** `--import` merges a filled capture sheet into the
   `ref_*` columns of the reference CSV; `--compare` produces the parity table
   (per-metric MAE, median/p90/max absolute error, signed bias, correlation)
   and writes `docs/ZENO_PARITY_REPORT.md`.

ToS note (important)
--------------------
ZenoSolver has no public API and their Terms of Use prohibit bots, scripts and
benchmarking against the service. This harness therefore **never** contacts
zenosolver.com. Reference values can only enter through
  (a) a human reading them from the Zeno UI during normal use, or
  (b) a data export the user is permitted to use.
Nothing here fabricates or scrapes Zeno output.

Usage
-----
    # 1. populate our side + oracle for the whole matrix (background friendly)
    python scripts/zeno_parity_harness.py solve --port 9998 --oracle-port 9971

    # 2. (human) fill docs/zeno_capture_sheet.csv from the Zeno UI

    # 3. merge the captured values and report parity
    python scripts/zeno_parity_harness.py import --capture docs/zeno_capture_sheet.csv
    python scripts/zeno_parity_harness.py compare --source auto
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import socket
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_CSV = REPO_ROOT / "docs/reference_spots.example.csv"
DEFAULT_SHEET_CSV = REPO_ROOT / "docs/zeno_capture_sheet.csv"
DEFAULT_SHEET_MD = REPO_ROOT / "docs/zeno_capture_sheet.md"
DEFAULT_REPORT = REPO_ROOT / "docs/ZENO_PARITY_REPORT.md"

# name: (pot, stack_bb, ante_bb, rake_pct, rake_cap, folded, bunching)
CONFIGS: Dict[str, Dict[str, Any]] = {
    "cash_nl500": dict(pot=5.5, stack=100.0, ante=0.0, rake=5.0, cap=0.6, folded=4, bunching=True),
    "cash_nl50": dict(pot=5.5, stack=100.0, ante=0.0, rake=5.0, cap=4.0, folded=4, bunching=True),
    "mtt_20bb": dict(pot=6.5, stack=20.0, ante=0.125, rake=0.0, cap=0.0, folded=4, bunching=True),
    "mtt_40bb": dict(pot=6.5, stack=40.0, ante=0.125, rake=0.0, cap=0.0, folded=4, bunching=True),
    "mtt_60bb": dict(pot=6.5, stack=60.0, ante=0.125, rake=0.0, cap=0.0, folded=4, bunching=True),
    "mtt_100bb": dict(pot=6.5, stack=100.0, ante=0.125, rake=0.0, cap=0.0, folded=4, bunching=True),
}

METRICS = ("oop_ev", "ip_ev", "cbet_pct", "oop_check_pct", "bet_size_pct")

FIELDNAMES = [
    "label", "board", "pot", "effective_stack", "rake_percent", "rake_cap",
    "ante_bb", "num_folded_players", "use_bunching",
    "ref_oop_ev", "ref_ip_ev", "ref_cbet_pct", "ref_oop_check_pct", "ref_bet_size_pct",
    "source",
    "oracle_oop_ev", "oracle_ip_ev", "oracle_cbet_pct", "oracle_oop_check_pct",
    "oracle_bet_size_pct",
    "our_oop_ev", "our_ip_ev", "our_cbet_pct", "our_oop_check_pct", "our_bet_size_pct",
    "our_exploitability_pct", "our_solve_ms", "our_leaf_mode",
]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def canonical_boards() -> List[List[str]]:
    try:
        from scripts.canonical_boards import CANONICAL_50_BOARDS
        return [list(b) for b in CANONICAL_50_BOARDS]
    except Exception:
        return [
            ["Ah", "Kd", "2c"], ["9s", "8h", "7s"], ["As", "Ah", "5c"],
            ["Kh", "Th", "4h"], ["Qd", "Jc", "2s"], ["7d", "7h", "3c"],
        ]


def ask_daemon(port: int, payload: Dict[str, Any], timeout: float = 120.0) -> Dict[str, Any]:
    sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    try:
        sock.sendall((json.dumps(payload) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(1 << 20)
            if not chunk:
                break
            buf += chunk
    finally:
        sock.close()
    return json.loads(buf.decode().strip())


def get_ranges(rake_pct: float, rake_cap: float) -> Tuple[Dict[str, float], Dict[str, float]]:
    from backend.solutions.services.range_service import PreflopRangeService
    return PreflopRangeService.get_spot_ranges("BTN_vs_BB_SRP", rake_pct, rake_cap)


def solve_spot(port: int, board: List[str], cfg: Dict[str, Any],
               ranges: Tuple[Dict[str, float], Dict[str, float]]) -> Dict[str, Any]:
    oop, ip = ranges
    payload = {
        "board": board,
        "oop_range": oop,
        "ip_range": ip,
        "pot": cfg["pot"],
        "effective_stack": cfg["stack"],
        "ante_bb": cfg["ante"],
        "rake_percent": cfg["rake"],
        "rake_cap": cfg["cap"],
        "num_folded_players": cfg["folded"],
        "use_bunching": cfg["bunching"],
        "max_bets_per_node": 1,
        "target_dEV": 0.005,
        "max_iterations": 500,
        # Reproducible solve: no wall-clock cut-off, so the recorded values can
        # be re-verified exactly.
        "deterministic": True,
    }
    res = ask_daemon(port, payload)
    if "error" in res:
        raise RuntimeError(f"daemon error on {' '.join(board)}: {res['error']}")
    return res


def metrics_from(res: Dict[str, Any]) -> Dict[str, float]:
    return {
        "oop_ev": float(res.get("oop_ev", 0.0)),
        "ip_ev": float(res.get("ip_ev", 0.0)),
        "cbet_pct": float(res.get("btn_cbet_frequency") or 0.0) * 100.0,
        "oop_check_pct": float(res.get("bb_check_frequency") or 0.0) * 100.0,
        "bet_size_pct": float(res.get("optimal_sizing") or 0.0) * 100.0,
    }


def fmt(x: Optional[float], nd: int = 4) -> str:
    return "" if x is None else f"{x:.{nd}f}"


# --------------------------------------------------------------------------- #
# solve / populate
# --------------------------------------------------------------------------- #
def cmd_solve(args: argparse.Namespace) -> int:
    boards = canonical_boards()[: args.boards]
    config_names = [c.strip() for c in args.configs.split(",") if c.strip()]
    for c in config_names:
        if c not in CONFIGS:
            raise SystemExit(f"Unknown config {c!r}; choices: {', '.join(CONFIGS)}")

    # Preserve any reference values that were already captured by hand.
    existing_refs: Dict[Tuple[str, str], Dict[str, str]] = {}
    csv_path = Path(args.csv)
    if csv_path.exists():
        with csv_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (row.get("board", "").strip(), config_key(row))
                if any((row.get(f"ref_{m}") or "").strip() for m in METRICS):
                    existing_refs[key] = row

    rows: List[Dict[str, Any]] = []
    total = len(boards) * len(config_names)
    done = 0
    for cfg_name in config_names:
        cfg = CONFIGS[cfg_name]
        ranges = get_ranges(cfg["rake"], cfg["cap"])
        for board in boards:
            board_s = " ".join(board)
            ours = solve_spot(args.port, board, cfg, ranges)
            om = metrics_from(ours)
            oracle: Dict[str, float] = {}
            if args.oracle_port:
                ores = solve_spot(args.oracle_port, board, cfg, ranges)
                oracle = metrics_from(ores)

            prev = existing_refs.get((board_s, config_key_from_cfg(cfg_name, cfg)), {})
            row: Dict[str, Any] = {
                "label": prev.get("label") or f"{cfg_name} {board_s}",
                "board": board_s,
                "pot": cfg["pot"],
                "effective_stack": cfg["stack"],
                "rake_percent": cfg["rake"],
                "rake_cap": cfg["cap"],
                "ante_bb": cfg["ante"],
                "num_folded_players": cfg["folded"],
                "use_bunching": "true" if cfg["bunching"] else "false",
                "source": prev.get("source") or "zeno-manual-pending",
            }
            for m in METRICS:
                row[f"ref_{m}"] = prev.get(f"ref_{m}", "")
                row[f"oracle_{m}"] = fmt(oracle.get(m))
                row[f"our_{m}"] = fmt(om[m])
            row["our_exploitability_pct"] = fmt(ours.get("exploitability_pct_pot"))
            row["our_solve_ms"] = str(int(ours.get("solve_time_ms", 0)))
            row["our_leaf_mode"] = str(ours.get("leaf_mode") or ours.get("engine", "?"))
            rows.append(row)

            done += 1
            if done % args.progress_every == 0 or done == total:
                print(f"  solved {done}/{total} spots", flush=True)

    out = csv_path
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print(f"Wrote {len(rows)} spots to {out}", flush=True)

    write_capture_sheet(rows, args.sheet_csv, args.sheet_md)
    print(f"Wrote capture sheet to {args.sheet_csv} and {args.sheet_md}", flush=True)
    return 0


def config_key(row: Dict[str, str]) -> str:
    return (
        f"{row.get('pot', '')}|{row.get('effective_stack', '')}|{row.get('rake_percent', '')}|"
        f"{row.get('rake_cap', '')}|{row.get('ante_bb', '')}|{row.get('num_folded_players', '')}|"
        f"{row.get('use_bunching', '')}"
    )


def config_key_from_cfg(name: str, cfg: Dict[str, Any]) -> str:
    return (
        f"{cfg['pot']}|{cfg['stack']}|{cfg['rake']}|{cfg['cap']}|{cfg['ante']}|"
        f"{cfg['folded']}|{'true' if cfg['bunching'] else 'false'}"
    )


def write_capture_sheet(rows: List[Dict[str, Any]], csv_path: Path, md_path: Path) -> None:
    """Generates the human capture sheet (blank Zeno cells, our values shown)."""
    sheet_fields = ["spot_id", "label", "board", "pot", "effective_stack", "rake_percent",
                    "rake_cap", "ante_bb", "num_folded_players", "use_bunching",
                    "zeno_oop_ev", "zeno_ip_ev", "zeno_cbet_pct", "zeno_oop_check_pct",
                    "zeno_bet_size_pct", "notes"]
    with Path(csv_path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sheet_fields)
        writer.writeheader()
        for i, r in enumerate(rows, 1):
            writer.writerow({
                "spot_id": f"S{i:03d}",
                "label": r["label"],
                "board": r["board"],
                "pot": r["pot"],
                "effective_stack": r["effective_stack"],
                "rake_percent": r["rake_percent"],
                "rake_cap": r["rake_cap"],
                "ante_bb": r["ante_bb"],
                "num_folded_players": r["num_folded_players"],
                "use_bunching": r["use_bunching"],
                "zeno_oop_ev": r.get("ref_oop_ev", ""),
                "zeno_ip_ev": r.get("ref_ip_ev", ""),
                "zeno_cbet_pct": r.get("ref_cbet_pct", ""),
                "zeno_oop_check_pct": r.get("ref_oop_check_pct", ""),
                "zeno_bet_size_pct": r.get("ref_bet_size_pct", ""),
                "notes": "",
            })

    lines = [
        "# ZenoSolver capture sheet",
        "",
        "Fill the `zeno_*` columns with values read from the ZenoSolver UI during",
        "normal use (no automation, no scraping), then run:",
        "",
        "```bash",
        "python scripts/zeno_parity_harness.py import --capture docs/zeno_capture_sheet.csv",
        "python scripts/zeno_parity_harness.py compare --source auto",
        "```",
        "",
        "What to read per spot:",
        "",
        "| Column | Where it comes from in Zeno |",
        "|---|---|",
        "| `zeno_oop_ev` / `zeno_ip_ev` | OOP / IP expected value in bb at the root |",
        "| `zeno_cbet_pct` | BTN c-bet frequency (% of the IP range that bets) |",
        "| `zeno_oop_check_pct` | BB check frequency (% of the OOP range that checks) |",
        "| `zeno_bet_size_pct` | chosen bet size as % of pot (33 / 50 / 75 / 125) |",
        "",
        "Use the same configuration as the spot row (pot, stack, rake, cap, ante,",
        "bunching) in Zeno's settings, otherwise the comparison is meaningless.",
        "",
    ]
    header = ("| ID | Config | Board | Our OOP EV | Our IP EV | Our cbet% | Our check% | "
              "Our size% | Zeno OOP EV | Zeno IP EV | Zeno cbet% | Zeno check% | Zeno size% |")
    lines += [header, "|" + "---|" * 13]
    for i, r in enumerate(rows, 1):
        cfg_label = (f"{r['rake_percent']}%/{r['rake_cap']} {r['effective_stack']}bb "
                     f"ante {r['ante_bb']} bunch {r['use_bunching']}")
        lines.append(
            f"| S{i:03d} | {cfg_label} | {r['board']} | {r['our_oop_ev']} | {r['our_ip_ev']} | "
            f"{r['our_cbet_pct']} | {r['our_oop_check_pct']} | {r['our_bet_size_pct']} | "
            f"{r.get('ref_oop_ev', '') or ''} | {r.get('ref_ip_ev', '') or ''} | "
            f"{r.get('ref_cbet_pct', '') or ''} | {r.get('ref_oop_check_pct', '') or ''} | "
            f"{r.get('ref_bet_size_pct', '') or ''} |"
        )
    Path(md_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# import
# --------------------------------------------------------------------------- #
def cmd_import(args: argparse.Namespace) -> int:
    with Path(args.capture).open(newline="", encoding="utf-8") as f:
        captured = list(csv.DictReader(f))
    with Path(args.csv).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys()) if rows else FIELDNAMES

    index: Dict[Tuple[str, str], Dict[str, str]] = {}
    for row in rows:
        index[(row["board"].strip(), config_key(row))] = row

    merged = 0
    skipped = 0
    for cap in captured:
        board = (cap.get("board") or "").strip()
        if not board:
            continue
        key = (board, (
            f"{(cap.get('pot') or '').strip()}|{(cap.get('effective_stack') or '').strip()}|"
            f"{(cap.get('rake_percent') or '').strip()}|{(cap.get('rake_cap') or '').strip()}|"
            f"{(cap.get('ante_bb') or '').strip()}|{(cap.get('num_folded_players') or '').strip()}|"
            f"{(cap.get('use_bunching') or '').strip()}"
        ))
        row = index.get(key)
        if row is None:
            skipped += 1
            continue
        for m in METRICS:
            val = (cap.get(f"zeno_{m}") or "").strip()
            if val:
                row[f"ref_{m}"] = val
        if (row.get("source") or "").startswith("zeno-manual-pending"):
            row["source"] = "zeno-manual"
        merged += 1

    with Path(args.csv).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"Merged {merged} captured spots into {args.csv} ({skipped} had no matching row)")
    return 0


# --------------------------------------------------------------------------- #
# compare
# --------------------------------------------------------------------------- #
def cmd_compare(args: argparse.Namespace) -> int:
    with Path(args.csv).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    source = args.source
    if source == "auto":
        has_zeno = any((r.get("ref_oop_ev") or "").strip() for r in rows)
        source = "zeno" if has_zeno else "oracle"
    prefix = "ref" if source == "zeno" else "oracle"
    label = ("ZenoSolver (human capture)" if source == "zeno"
             else "exact-CFR oracle (GTO_LEAF_NET=off, not Zeno)")

    pairs: Dict[str, List[Tuple[float, float]]] = {m: [] for m in METRICS}
    used_rows = 0
    for r in rows:
        ours_ok = False
        for m in METRICS:
            ref = (r.get(f"{prefix}_{m}") or "").strip()
            ours = (r.get(f"our_{m}") or "").strip()
            if not ref or not ours:
                continue
            try:
                pairs[m].append((float(ours), float(ref)))
            except ValueError:
                continue
            ours_ok = True
        used_rows += 1 if ours_ok else 0

    print("=" * 100)
    print(f" PARITY REPORT vs {label}")
    print(f" source CSV: {args.csv}")
    print(f" spots with compared values: {used_rows}/{len(rows)}")
    print("=" * 100)
    print(f"{'Metric':<14} {'n':>4} {'MAE':>9} {'medAE':>9} {'p90AE':>9} {'maxAE':>9} "
          f"{'bias':>9} {'r':>7}")
    print("-" * 100)

    summary_lines = []
    worst_ev = 0.0
    for m in METRICS:
        vals = pairs[m]
        if not vals:
            print(f"{m:<14} {0:>4} {'-':>9} {'-':>9} {'-':>9} {'-':>9} {'-':>9} {'-':>7}")
            summary_lines.append((m, 0, None, None, None, None, None, None))
            continue
        ours = [a for a, _ in vals]
        refs = [b for _, b in vals]
        ae = [abs(a - b) for a, b in vals]
        bias = statistics.fmean(a - b for a, b in vals)
        mae = statistics.fmean(ae)
        med = statistics.median(ae)
        p90 = sorted(ae)[max(0, int(math.ceil(0.9 * len(ae))) - 1)]
        mx = max(ae)
        r = pearson(ours, refs)
        if m.endswith("_ev"):
            worst_ev = max(worst_ev, mae)
        print(f"{m:<14} {len(vals):>4} {mae:>9.4f} {med:>9.4f} {p90:>9.4f} {mx:>9.4f} "
              f"{bias:>+9.4f} {('-' if r is None else f'{r:>7.3f}')}")
        summary_lines.append((m, len(vals), mae, med, p90, mx, bias, r))

    print("-" * 100)
    if source == "zeno":
        print("Zeno values were captured manually from the Zeno UI (ToS-compliant).")
    else:
        print("No Zeno values captured yet: the comparison above is against our own")
        print("exact-CFR oracle (learned path vs exact equity), NOT against ZenoSolver.")
        print("Fill docs/zeno_capture_sheet.csv from the Zeno UI and re-run --import/--compare.")
    print(f"Worst per-metric EV MAE: {worst_ev:.4f} bb")

    report = [
        "# ZenoSolver parity report",
        "",
        f"Generated by `scripts/zeno_parity_harness.py compare`.",
        "",
        f"- Reference source: **{label}**",
        f"- Spots compared: **{used_rows} / {len(rows)}**",
        f"- Worst per-metric EV MAE: **{worst_ev:.4f} bb**",
        "",
        "| Metric | n | MAE | median AE | p90 AE | max AE | bias | corr r |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m, n, mae, med, p90, mx, bias, r in summary_lines:
        if n == 0:
            report.append(f"| {m} | 0 | - | - | - | - | - | - |")
        else:
            report.append(
                f"| {m} | {n} | {mae:.4f} | {med:.4f} | {p90:.4f} | {mx:.4f} | "
                f"{bias:+.4f} | {'-' if r is None else f'{r:.3f}'} |"
            )
    report += [
        "",
        "## Method",
        "",
        "1. `solve` solves every spot in the matrix on the running daemon and records",
        "   the engine's own values (`our_*`).",
        "2. The same spot is re-solved with `GTO_LEAF_NET=off` (exact showdown equity,",
        "   no learned model) to provide an independent oracle (`oracle_*`).",
        "3. Zeno values (`ref_*`) can only be added by a human reading the Zeno UI",
        "   (their Terms prohibit bots/benchmarking); `docs/zeno_capture_sheet.md` is",
        "   generated to make that capture a single pass.",
        "4. `compare` reports per-metric error statistics against the selected source.",
    ]
    Path(args.report).write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Wrote {args.report}")

    if args.max_ev_mae is not None and worst_ev > args.max_ev_mae:
        print(f"FAIL: EV MAE {worst_ev:.4f} bb > tolerance {args.max_ev_mae:.4f} bb")
        return 1
    return 0


def pearson(a: List[float], b: List[float]) -> Optional[float]:
    if len(a) < 3:
        return None
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da == 0 or db == 0:
        return None
    return num / (da * db)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("solve", help="solve the spot matrix and write our side + oracle")
    s.add_argument("--port", type=int, default=9998, help="daemon with the learned leaf model")
    s.add_argument("--oracle-port", type=int, default=0,
                   help="daemon started with GTO_LEAF_NET=off (exact oracle); 0 disables")
    s.add_argument("--boards", type=int, default=50)
    s.add_argument("--configs", default=",".join(CONFIGS))
    s.add_argument("--csv", default=str(DEFAULT_CSV))
    s.add_argument("--sheet-csv", default=str(DEFAULT_SHEET_CSV))
    s.add_argument("--sheet-md", default=str(DEFAULT_SHEET_MD))
    s.add_argument("--progress-every", type=int, default=25)
    s.set_defaults(func=cmd_solve)

    i = sub.add_parser("import", help="merge a human-filled capture sheet")
    i.add_argument("--capture", default=str(DEFAULT_SHEET_CSV))
    i.add_argument("--csv", default=str(DEFAULT_CSV))
    i.set_defaults(func=cmd_import)

    c = sub.add_parser("compare", help="report parity against the captured/oracle values")
    c.add_argument("--csv", default=str(DEFAULT_CSV))
    c.add_argument("--source", choices=("auto", "zeno", "oracle"), default="auto")
    c.add_argument("--report", default=str(DEFAULT_REPORT))
    c.add_argument("--max-ev-mae", type=float, default=None,
                   help="fail if the worst per-metric EV MAE exceeds this (bb)")
    c.set_defaults(func=cmd_compare)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
