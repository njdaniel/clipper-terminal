"""Informational (check 4): what does the engine itself do with lot/tick violations when the
Clipper pre-trade gate is bypassed? Not a pass/fail input; documents why the Clipper check exists."""

from __future__ import annotations

import json
from decimal import Decimal

import clipper0a as c
import run_case
from cases import LEDGER_CASES

case = dict(LEDGER_CASES["lot_tick_refusal"])
case["script"] = [
    {"on": "event", "idx": 0, "action": {"sym": "LOTS", "side": "BUY", "qty": 150, "pretrade": False}},
    {"on": "event", "idx": 0, "action": {"sym": "LOTS", "side": "BUY", "qty": 100, "price": "11.025", "pretrade": False}},
]
out = {}
try:
    r = run_case.run_backtest(case, "baseline")
    out = {"fills": [(f["qty"], f["px"]) for f in r["fills"]], "refusals": r["refusals"], "cash": r.get("cash"),
           "positions": r.get("positions")}
except Exception as exc:  # noqa: BLE001 - recorded
    out = {"exception": f"{type(exc).__name__}: {exc}"}
print("CLIPPER-0A-RESULT " + json.dumps(out, default=str))
