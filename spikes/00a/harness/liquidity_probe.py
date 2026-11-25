"""Diagnostic for finding F4 (L1 liquidity semantics). Gate mechanism; one limit BUY 300 @11.02
decided on quote#1. Usage: python liquidity_probe.py <variant> <backtest|sandbox> <consumption|upstream-default>

Variants:
  identical     later quotes identical: 11.02 x 100, four times
  sizes_change  later quotes at 11.02 with displayed size 100, 150, 200, 200
  price_moves   11.02 x100, then 11.03 (level gone), then 11.02 x100 again, repeated
Documented upstream rule (fill-prices-and-matching.md): with consumption enabled, "a fresh book
update at that level resets the record to the new displayed size".
"""

from __future__ import annotations

import json
import sys

import run_case
from cases import TIMING_CASES
from clipper0a import q

VARIANTS = {
    "identical": [q("CLPR", 0, "10.00", "10.02"), q("CLPR", 1, "11.00", "11.02"), q("CLPR", 2, "11.00", "11.02"),
                  q("CLPR", 3, "11.00", "11.02"), q("CLPR", 4, "11.00", "11.02"), q("CLPR", 5, "11.00", "11.02")],
    "sizes_change": [q("CLPR", 0, "10.00", "10.02"), q("CLPR", 1, "11.00", "11.02"), q("CLPR", 2, "11.00", "11.02", 100, 100),
                     q("CLPR", 3, "11.00", "11.02", 150, 150), q("CLPR", 4, "11.00", "11.02", 200, 200),
                     q("CLPR", 5, "11.00", "11.02", 200, 200)],
    "price_moves": [q("CLPR", 0, "10.00", "10.02"), q("CLPR", 1, "11.00", "11.02"), q("CLPR", 2, "11.00", "11.02"),
                    q("CLPR", 3, "11.01", "11.03"), q("CLPR", 4, "11.00", "11.02"), q("CLPR", 5, "11.01", "11.03"),
                    q("CLPR", 6, "11.00", "11.02")],
}
# Documented-rule expectation (each fresh update at the level offers its displayed size again)
DOCUMENTED = {"identical": [(2, "100"), (3, "100"), (4, "100")],
              "sizes_change": [(2, "100"), (3, "150"), (4, "50")],
              "price_moves": [(2, "100"), (4, "100"), (6, "100")]}

variant, ctx, liq = sys.argv[1], sys.argv[2], sys.argv[3]
run_case.LIQUIDITY_CONSUMPTION = liq == "consumption"
case = dict(TIMING_CASES["partial_fills"], events=VARIANTS[variant])
r = (run_case.run_backtest if ctx == "backtest" else run_case.run_sandbox)(case, "gate")
got = [(f["attribution"]["idx"], f["qty"]) for f in r["fills"]]
print("CLIPPER-0A-RESULT " + json.dumps({"variant": variant, "context": ctx, "liquidity": liq, "fills": got,
                                         "documented_rule_expectation": DOCUMENTED[variant],
                                         "matches_documented_rule": got == [list(x) for x in DOCUMENTED[variant]]
                                         or got == DOCUMENTED[variant]}))
