"""F4 stage B step 2 (local only; runs in the separate databento-dbn venv, NOT the engine venv).
Decodes the allowed MBO file with Databento's own decoder (independent of Nautilus) and writes the
front contract's records as a compact local binary for the truth model and for trade ticks.
Usage: python f4_real_extract.py <local_out_dir> <raw_symbol e.g. MESU6|MESU26>"""

from __future__ import annotations

import json
import struct
import sys

import zstandard

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import f4_real_guard as g  # noqa: E402
import databento_dbn as dbn  # noqa: E402

REC = struct.Struct("<qqQ cc q I Q B")  # ts_recv, ts_event, sequence, action, side, price(1e-9), size, order_id, flags

out = g.local_out(sys.argv[1])
src = g.input_path()
want = sys.argv[2]
dec = dbn.DBNDecoder()
meta, iid, n, counts = None, None, 0, {}
with open(src, "rb") as fh, open(out / "front_mbo.bin", "wb") as fo:
    reader = zstandard.ZstdDecompressor().stream_reader(fh)
    while True:
        chunk = reader.read(1 << 22)
        if not chunk:
            break
        dec.write(chunk)
        for rec in dec.decode():
            if isinstance(rec, dbn.Metadata):
                meta = rec
                for m in rec.mappings.get(want, []) if isinstance(rec.mappings, dict) else []:
                    iid = int(m["symbol"]) if isinstance(m, dict) else int(m.symbol)
                continue
            if not isinstance(rec, dbn.MBOMsg):
                continue
            if iid is None:
                raise RuntimeError(f"no instrument mapping for {want}; mappings keys: {list(meta.mappings)[:10]}")
            if rec.instrument_id != iid:
                continue
            a, s = str(rec.action), str(rec.side)
            a = a[-1] if len(a) > 1 else a  # enum repr -> single char
            fo.write(REC.pack(rec.ts_recv, rec.ts_event, rec.sequence, a[:1].encode(), s[:1].encode(), rec.price,
                              rec.size, rec.order_id, rec.flags))
            counts[a] = counts.get(a, 0) + 1
            n += 1
(out / "extract.json").write_text(json.dumps({"instrument_id_numeric": iid, "records": n, "actions": counts}))
print(json.dumps({"records": n, "actions": counts}))
