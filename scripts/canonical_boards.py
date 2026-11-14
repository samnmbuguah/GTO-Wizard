"""Shared canonical flop board set for the solver/model verification scripts.

50 suit-diverse, texture-balanced boards: dry Ace-high, wet connected, paired,
trips and monotone flops. Both ``scripts/audit_solver_claims.py`` and
``scripts/verify_model_accuracy.py`` use this list so the two audits cover the
same boards.
"""

CANONICAL_50_BOARDS = [
    # Dry Ace-High & Broadways (12)
    ["Ah", "Kd", "2c"], ["As", "Qh", "5d"], ["Ad", "Jc", "4h"], ["Ah", "Th", "3c"],
    ["As", "8c", "2d"], ["Kh", "Qd", "4c"], ["Ks", "Jc", "3d"], ["Kd", "Tc", "2h"],
    ["Qh", "Jd", "3c"], ["Qs", "Tc", "2d"], ["Jh", "Tc", "4d"], ["Ah", "7c", "2s"],
    # Wet Connected & Dynamic (13)
    ["9s", "8h", "7s"], ["9d", "8c", "7h"], ["8s", "7c", "6d"], ["7s", "6h", "5d"],
    ["Ts", "9d", "8h"], ["Jh", "Ts", "9c"], ["Qs", "Jh", "Td"], ["6s", "5h", "4d"],
    ["5s", "4h", "3d"], ["9s", "7c", "6d"], ["8s", "6h", "5c"], ["Ts", "8h", "7d"],
    ["Js", "9c", "8d"],
    # Paired & Trips (15)
    ["8s", "8h", "2c"], ["Ks", "Kh", "3d"], ["As", "Ah", "5c"], ["Qs", "Qc", "7d"],
    ["Js", "Jd", "4c"], ["Ts", "Tc", "8d"], ["7s", "7h", "2d"], ["6s", "6c", "3h"],
    ["5s", "5d", "2c"], ["4s", "4h", "9c"], ["3s", "3c", "Kd"], ["2s", "2h", "Ac"],
    ["8s", "8h", "8d"], ["Kh", "Kd", "Ks"], ["2s", "2c", "2d"],
    # Monotone Flush Boards (10)
    ["Kh", "Th", "4h"], ["As", "8s", "2s"], ["Qd", "Jd", "5d"], ["Jh", "9h", "4h"],
    ["Ts", "7s", "2s"], ["8c", "6c", "3c"], ["Kd", "9d", "3d"], ["Ac", "Tc", "7c"],
    ["Qh", "8h", "3h"], ["9s", "5s", "2s"],
]
