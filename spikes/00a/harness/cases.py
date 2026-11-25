"""Proof 0A case catalogue. Each case lists synthetic fixture events (D25), the strategy script,
and the expected outcome under the after_watermark policy (D14): an order may match only against
a book update derived from a NEW feed event for its own instrument with ts_init strictly after
the decision's data watermark. Expected fills are written by hand from that rule and the fixture,
independently of the engine (they are the independent expected ledger for timing)."""

from __future__ import annotations

from clipper0a import bar, q

BUY1 = {"sym": "CLPR", "side": "BUY", "qty": 1}


def std_quotes(n: int, sym: str = "CLPR", t0: float = 0.0, step: float = 1.0) -> list[dict]:
    return [q(sym, t0 + i * step, f"{10 + i}.00", f"{10 + i}.02") for i in range(n)]


TIMING_CASES: dict[str, dict] = {
    "timer": {
        "doc": "Codex counterexample form: order decided on quote#1; an UNRELATED strategy timer fires "
               "0.5 s later (after any small latency has elapsed) with no new CLPR data until quote#2.",
        "events": std_quotes(5),
        "subs": {"quotes": ["CLPR"]},
        "script": [{"on": "event", "idx": 1, "action": BUY1},
                   {"on": "timer", "after_idx": 1, "delay_s": 0.5, "action": None}],
        "expected": [{"idx": 2, "px": "12.02", "qty": "1"}],
    },
    "timer_decision": {
        "doc": "Order submitted FROM a strategy timer 0.5 s after quote#1; no new CLPR data until quote#2.",
        "events": std_quotes(5),
        "subs": {"quotes": ["CLPR"]},
        "script": [{"on": "timer", "after_idx": 1, "delay_s": 0.5, "action": BUY1}],
        "expected": [{"idx": 2, "px": "12.02", "qty": "1"}],
    },
    "end_of_feed": {
        "doc": "Order submitted on the last quote of the feed; no later CLPR event exists.",
        "events": std_quotes(3),
        "subs": {"quotes": ["CLPR"]},
        "script": [{"on": "event", "idx": 2, "action": BUY1}],
        "expected": [],
    },
    "equal_timestamps": {
        "doc": "Decision on quote#1a; quote#1b has the SAME ts_init (not after the watermark).",
        "events": [q("CLPR", 0, "10.00", "10.02"), q("CLPR", 1, "11.00", "11.02"),
                   q("CLPR", 1, "11.50", "11.52"), q("CLPR", 2, "12.00", "12.02")],
        "subs": {"quotes": ["CLPR"]},
        "script": [{"on": "event", "idx": 1, "action": BUY1}],
        "expected": [{"idx": 3, "px": "12.02", "qty": "1"}],
    },
    "other_instrument": {
        "doc": "Decision on CLPR quote#1; an OTHR quote arrives at t=1.5 before the next CLPR quote.",
        "events": [q("CLPR", 0, "10.00", "10.02"), q("CLPR", 1, "11.00", "11.02"),
                   q("OTHR", 1.5, "50.00", "50.02"), q("CLPR", 2, "12.00", "12.02")],
        "subs": {"quotes": ["CLPR", "OTHR"]},
        "script": [{"on": "event", "idx": 1, "action": BUY1}],
        "expected": [{"idx": 3, "px": "12.02", "qty": "1"}],
    },
    "first_update_ordering": {
        "doc": "Decision on quote#1 (ask 11.02); the fill must use quote#2's book (ask 12.02), "
               "i.e. the update must be applied before matching.",
        "events": std_quotes(4),
        "subs": {"quotes": ["CLPR"]},
        "script": [{"on": "event", "idx": 1, "action": BUY1}],
        "expected": [{"idx": 2, "px": "12.02", "qty": "1"}],
    },
    "stale_feed": {
        "doc": "Decision on quote#1; the next CLPR quote arrives only after a 5 s gap.",
        "events": [q("CLPR", 0, "10.00", "10.02"), q("CLPR", 1, "11.00", "11.02"),
                   q("CLPR", 6, "12.00", "12.02"), q("CLPR", 7, "13.00", "13.02")],
        "subs": {"quotes": ["CLPR"]},
        "script": [{"on": "event", "idx": 1, "action": BUY1}],
        "expected": [{"idx": 2, "px": "12.02", "qty": "1"}],
    },
    "resting_orders": {
        "doc": "Limit BUY @11.02 decided on quote#1 (ask 11.02, marketable on the decision book). "
               "quote#2 ask 12.02 (not marketable) -> rests; quote#3 ask 11.02 -> fills.",
        "events": [q("CLPR", 0, "10.00", "10.02"), q("CLPR", 1, "11.00", "11.02"),
                   q("CLPR", 2, "12.00", "12.02"), q("CLPR", 3, "11.00", "11.02"),
                   q("CLPR", 4, "12.00", "12.02")],
        "subs": {"quotes": ["CLPR"]},
        "script": [{"on": "event", "idx": 1, "action": {"sym": "CLPR", "side": "BUY", "qty": 1, "price": "11.02"}}],
        "expected": [{"idx": 3, "px": "11.02", "qty": "1"}],
    },
    "partial_fills": {
        "doc": "Limit BUY 300 @11.02 decided on quote#1; each later quote displays 100 at 11.02. Expected per "
               "upstream's documented liquidity-consumption rule ('a fresh book update at that level resets the "
               "record to the new displayed size'): 100 fills at each of quotes #2, #3, #4.",
        "events": [q("CLPR", 0, "10.00", "10.02"), q("CLPR", 1, "11.00", "11.02"),
                   q("CLPR", 2, "11.00", "11.02"), q("CLPR", 3, "11.00", "11.02"),
                   q("CLPR", 4, "11.00", "11.02"), q("CLPR", 5, "11.00", "11.02")],
        "subs": {"quotes": ["CLPR"]},
        "script": [{"on": "event", "idx": 1, "action": {"sym": "CLPR", "side": "BUY", "qty": 300, "price": "11.02"}}],
        "expected": [{"idx": 2, "px": "11.02", "qty": "100"}, {"idx": 3, "px": "11.02", "qty": "100"},
                     {"idx": 4, "px": "11.02", "qty": "100"}],
    },
    "quotes_between_bars": {
        "doc": "Strategy decides on the 1-minute bar closing at t=60; bid/ask quotes exist at t=70 and t=80. "
               "First eligible execution event is the t=70 quote (finest data available).",
        "events": [bar("CLPR", 60, "10.00", "10.50", "9.90", "10.20"), q("CLPR", 70, "12.50", "12.52"),
                   q("CLPR", 80, "12.60", "12.62"), bar("CLPR", 120, "12.50", "12.70", "12.40", "12.60")],
        "subs": {"bars": [("CLPR", "1-MINUTE")]},
        "script": [{"on": "event", "idx": 0, "action": BUY1}],
        "expected": [{"idx": 1, "px": "12.52", "qty": "1"}],
    },
}

# Check 4: attribution / FIFO / fee / lot-tick (run with the gate, the mechanism under test for D14).
LEDGER_CASES: dict[str, dict] = {
    "fifo": {
        "doc": "BUY 1 -> fills @10.00, BUY 1 -> @20.00, SELL 1 -> @30.00 (zero fees). FIFO realized 20; "
               "engine average-cost realized expected 15.",
        "events": [q("CLPR", 0, "4.98", "5.00"), q("CLPR", 1, "9.98", "10.00"), q("CLPR", 2, "19.98", "20.00"),
                   q("CLPR", 3, "30.00", "30.02"), q("CLPR", 4, "30.00", "30.02")],
        "subs": {"quotes": ["CLPR"]},
        "script": [{"on": "event", "idx": 0, "action": BUY1}, {"on": "event", "idx": 1, "action": BUY1},
                   {"on": "event", "idx": 2, "action": {"sym": "CLPR", "side": "SELL", "qty": 1}}],
        "fees": "zero",
        "expected": {"fills": [{"idx": 1, "px": "10.00", "qty": "1"}, {"idx": 2, "px": "20.00", "qty": "1"},
                               {"idx": 3, "px": "30.00", "qty": "1"}],
                     "fifo_realized_gross": "20.00", "engine_realized": "15.00",
                     "cash": "100000.00", "position_qty": "1"},
    },
    "fee_min_across_partials": {
        "doc": "BUY 150 @11.02 limit; later quotes display 50, 60, 70 (sizes change so consumed liquidity "
               "resets) -> fills 50/60/40. Per-share 0.75 total < min 1.00 -> 1.00 total, charged once: "
               "1.00, 0.00, 0.00.",
        "events": [q("CLPR", 0, "10.00", "10.02"), q("CLPR", 1, "11.00", "11.02", 40, 40),
                   q("CLPR", 2, "11.00", "11.02", 50, 50), q("CLPR", 3, "11.00", "11.02", 60, 60),
                   q("CLPR", 4, "11.00", "11.02", 70, 70), q("CLPR", 5, "11.00", "11.02", 80, 80)],
        "subs": {"quotes": ["CLPR"]},
        "script": [{"on": "event", "idx": 1, "action": {"sym": "CLPR", "side": "BUY", "qty": 150, "price": "11.02"}}],
        "fees": "clipper",
        "expected": {"fills": [{"idx": 2, "px": "11.02", "qty": "50"}, {"idx": 3, "px": "11.02", "qty": "60"},
                               {"idx": 4, "px": "11.02", "qty": "40"}],
                     "commissions": ["1.00", "0.00", "0.00"]},
    },
    "fee_cap_across_partials": {
        "doc": "BUY 10000 PNNY @0.40; quotes display 2500, 2600, 2700, 2800 -> fills 2500/2600/2700/2200. "
               "Per-share 50.00 total > cap 1% of 4000 = 40.00. Cumulative cap per fill: 10.00, 10.40, 10.80, 8.80.",
        "events": [q("PNNY", 0, "0.39", "0.40", 2400, 2400), q("PNNY", 1, "0.39", "0.40", 2500, 2500),
                   q("PNNY", 2, "0.39", "0.40", 2600, 2600), q("PNNY", 3, "0.39", "0.40", 2700, 2700),
                   q("PNNY", 4, "0.39", "0.40", 2800, 2800), q("PNNY", 5, "0.39", "0.40", 2900, 2900)],
        "subs": {"quotes": ["PNNY"]},
        "script": [{"on": "event", "idx": 0, "action": {"sym": "PNNY", "side": "BUY", "qty": 10000, "price": "0.40"}}],
        "fees": "clipper",
        "expected": {"fills": [{"idx": 1, "px": "0.40", "qty": "2500"}, {"idx": 2, "px": "0.40", "qty": "2600"},
                               {"idx": 3, "px": "0.40", "qty": "2700"}, {"idx": 4, "px": "0.40", "qty": "2200"}],
                     "commissions": ["10.00", "10.40", "10.80", "8.80"]},
    },
    "lot_tick_refusal": {
        "doc": "Clipper pre-trade gate refuses a 150-share order on a 100-lot instrument and an 11.025 "
               "price on a 0.01-increment instrument; a valid 100-lot order passes.",
        "events": [q("LOTS", 0, "10.00", "10.02"), q("LOTS", 1, "10.00", "10.02"), q("LOTS", 2, "10.00", "10.02")],
        "subs": {"quotes": ["LOTS"]},
        "script": [{"on": "event", "idx": 0, "action": {"sym": "LOTS", "side": "BUY", "qty": 150}},
                   {"on": "event", "idx": 0, "action": {"sym": "LOTS", "side": "BUY", "qty": 100, "price": "11.025"}},
                   {"on": "event", "idx": 0, "action": {"sym": "LOTS", "side": "BUY", "qty": 100}}],
        "fees": "zero",
        "expected": {"refused": 2, "fills": [{"idx": 1, "px": "10.02", "qty": "100"}]},
    },
}
