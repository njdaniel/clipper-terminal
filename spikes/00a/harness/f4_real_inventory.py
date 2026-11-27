"""F4 stage B step 1 (local only): decode the allowed MBO file with stock rc9 and summarise it.
Usage: python f4_real_inventory.py <local_out_dir> <publishers.json>
Writes <local_out_dir>/inventory.json (LOCAL; contains tape statistics) and prints only the
input SHA-256 and per-instrument record counts to stdout for the operator."""

from __future__ import annotations

import json
import sys
import time
from collections import Counter

import f4_real_guard as g

out = g.local_out(sys.argv[1])
src = g.input_path()
from nautilus_trader.adapters.databento import DatabentoDataLoader  # noqa: E402

t = time.time()
loader = DatabentoDataLoader(sys.argv[2])
schema = loader.schema_for_file(src)
deltas = loader.load_order_book_deltas(src, price_precision=2)
t_deltas = time.time() - t
by_inst = Counter(str(d.instrument_id) for d in deltas)
try:
    t2 = time.time()
    trades = loader.load_trades(src, price_precision=2)
    trades_info = {"count": len(trades), "seconds": round(time.time() - t2, 1),
                   "by_instrument": dict(Counter(str(x.instrument_id) for x in trades).most_common(5))}
except Exception as exc:  # noqa: BLE001 - record whether trades can be decoded from MBO
    trades_info = {"error": f"{type(exc).__name__}: {exc}"}
front = by_inst.most_common(1)[0][0]
fd = [d for d in deltas if str(d.instrument_id) == front]
inv = {"input_sha256": g.sha256(src), "schema": schema, "decode_seconds": round(t_deltas, 1),
       "deltas_total": len(deltas), "instruments": dict(by_inst.most_common(10)), "front": front,
       "front_first_ts": fd[0].ts_event, "front_last_ts": fd[-1].ts_event,
       "front_snapshot_flagged": sum(1 for d in fd[:5000] if d.flags & 32), "trades": trades_info}
(out / "inventory.json").write_text(json.dumps(inv, indent=1))
print(json.dumps({"input_sha256": inv["input_sha256"], "schema": schema, "front": front,
                  "instruments": inv["instruments"], "deltas_total": len(deltas),
                  "trades_decoded": trades_info.get("count", trades_info.get("error"))}))
