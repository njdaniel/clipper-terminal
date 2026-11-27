"""Build the publishable F4 real-data evidence (D29: aggregates only) from local results.
Usage: python f4_real_publish.py <local_dir> <out_json>
Everything written passes f4_real_guard.publishable(): counts, unitless ratios, verdicts, config,
input SHA-256, contract and date. No prices, sizes, timestamps or order ids."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import f4_real_experiment as X
import f4_real_guard as g

local = g.local_out(sys.argv[1])
inv = json.loads((local / "inventory.json").read_text())
grid = json.loads((local / "PUBLISHABLE_aggregate.json").read_text())["counts_by_config"]
truth = json.loads((local / "truth.json").read_text())

# decomposition (L3, consumption, queue): engine vs truth fill source, as ratios
trade_ts = set()
with open(local / "front_mbo.bin", "rb") as f:
    while True:
        b = f.read(X.REC.size)
        if not b:
            break
        r = X.REC.unpack(b)
        if r[0] > X.END_TS:
            break
        if r[3] == b"T":
            trade_ts.add(r[0] - 1)
eng = json.loads((local / "engine_L3_liq_q.json").read_text())["probes"]
decomp = {}
for kind in ("aggr", "big"):
    et = eb = tt = tb = ob = otr = 0
    for pid, t in truth.items():
        if t["kind"] != kind:
            continue
        e = eng[pid]
        etr = sum(q for ts, q in e["fill_detail_LOCAL"] if ts in trade_ts)
        et, eb, tt, tb = et + etr, eb + e["filled"] - etr, tt + t["by_trade"], tb + t["by_book"]
        if e["filled"] > t["filled"]:
            ob += (e["filled"] - etr) > t["by_book"]
            otr += etr > t["by_trade"]
    decomp[kind] = {"engine_book_over_truth_book": round(eb / tb, 3) if tb else None,
                    "engine_trade_over_truth_trade": round(et / tt, 3) if tt else None,
                    "overfilled_with_book_excess": ob, "overfilled_with_trade_excess": otr}

# parity: sandbox vs backtest on the same 120 s slice, per config
parity = {}
for bt in sorted(local.glob("parity_backtest_*.json")):
    cfg = bt.stem.replace("parity_backtest_", "")
    sb = local / f"parity_sandbox_{cfg}.json"
    if not sb.exists():
        continue
    b, s = json.loads(bt.read_text()), json.loads(sb.read_text())
    bp, sp = b["probes"], s["probes"]
    same = sum(1 for k in bp if k in sp and sp[k]["filled"] == bp[k]["filled"] and sp[k]["qty"] == bp[k]["qty"])
    bt_truth = sum(1 for k in bp if bp[k]["filled"] == truth[k]["filled"])
    sb_truth = sum(1 for k in sp if sp[k]["filled"] == truth[k]["filled"])
    lag = s.get("replay_lag_ms") or {}
    parity[cfg] = {"probe_count": len(bp), "sandbox_equals_backtest": same, "backtest_equals_truth": bt_truth,
                   "sandbox_equals_truth": sb_truth, "replay_lag_ms_p99": lag.get("p99"), "replay_lag_ms_max": lag.get("max")}

out = g.publishable({
    "input_sha256": inv["input_sha256"], "contract": "MESU6 (Nautilus id MESU26.GLBX), GLBX.MDP3 mbo, MES.FUT parent",
    "date": "2026-07-15",
    "config": {"engine": "stock PyPI nautilus_trader 2.0.0rc9", "windows_utc": ["13:35-13:45", "16:00-16:10", "19:45-19:55"],
               "probes_per_window": {"aggr_3x_5s": 10, "big_20x_2s": 10, "passive_1lot_25s": 10},
               "gate": "release on first strictly later event batch; cancel at horizon",
               "venue": "MARGIN/NETTING, zero fees, FillModel(), latency 0, trade_execution on",
               "trades": "from databento-dbn decode at ts_recv-1ns (Nautilus MBO decode drops T/F records)",
               "instrument": "constructed from public CME spec (tick 0.25, multiplier 5); sandbox expiry set relative to wall clock",
               "parity_slice": "16:00:00-16:02:00 UTC, L3 snapshot + slice, sandbox replay at 1x"},
    "counts_by_config": grid,
    "ratios": {"fill_source_decomposition_L3_liq_q": decomp},
    "parity": parity,
    "notes": "Truth = order-identity model from raw records (independent decoder). Aggregates only per D29.",
})
Path(sys.argv[2]).write_text(json.dumps(out, indent=1))
print(json.dumps(out["parity"]))
