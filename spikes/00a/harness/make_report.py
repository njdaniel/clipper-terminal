"""Render proof-0A results.json into evidence/summary.md and a trimmed results file.
Usage: python3 make_report.py <results.json> <evidence_dir>"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

res = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
L = []
A = L.append


def mib(r):
    m = (r or {}).get("memory", {})
    p = m.get("memory.peak")
    return f"{p / 2**20:.1f}" if isinstance(p, int) else "n/a"


A("# Proof 0A — generated results summary\n")
A(f"Run: {res['started']} → {res['finished']} · runtime `{res['runtime_python']}`\n")

# ---- check 1
art = res["artifact"]
A("## Check 1 — artifact inspection (installed restricted wheel)\n")
A(f"- nautilus_trader {art['nautilus_version']}, CPython {art['python']}")
A(f"- native submodules ({len(art['native_submodules'])}): `{', '.join(art['native_submodules'])}`")
A(f"- must import: " + ", ".join(f"`{m['module']}`={'OK' if m['imported'] else 'FAIL'}" for m in art["must_import"]))
A(f"- must fail: " + ", ".join(f"`{m['module']}`={'absent' if not m['imported'] else 'PRESENT'}" for m in art["must_fail"]))
A(f"- native execution factories: `{sorted(art['native_execution_factories'])}`")
A(f"- Python execution factory/base names: `{sorted(art['execution_factories'])}`")
A(f"- pandas present: {art['pandas_present']}")
if "artifact_stock_baseline" in res:
    st = res["artifact_stock_baseline"]
    A(f"- *stock rc9 wheel for comparison*: {len(st['native_submodules'])} native submodules; native execution "
      f"factories `{sorted(st['native_execution_factories'])}`")
A("")

# ---- check 2
bn = res["backtestnode"]
A("## Check 2 — BacktestNode from Parquet catalog (FIFO fixture, gate)\n")
if bn.get("error"):
    A(f"ERROR: {bn['error']}")
else:
    A(f"- fills: {[(f['side'], f['px'], f['qty'], f['attribution']['idx']) for f in bn['fills']]}")
    A(f"- engine cash {bn['cash']}; positions {bn['positions']}; FIFO ledger {bn['ledger']['fifo_realized_gross']} gross, "
      f"cash {bn['ledger']['cash']}")
    A(f"- worker memory.peak {mib(bn)} MiB; catalog files {len(bn['catalog_files'])}")
A("")

# ---- check 3
A("## Check 3 — execution timing (after_watermark), counterexample suite\n")
grid = defaultdict(dict)
for t in res["timing"]:
    grid[(t["case"], t["context"])][t["mechanism"]] = t
mechs = ["baseline", "native", "native_bounded", "gate"]
A("| case | context | " + " | ".join(mechs) + " |")
A("|---|---|" + "---|" * len(mechs))
for (case, ctx), row in grid.items():
    cells = [row[m]["verdict"] if m in row else "—" for m in mechs]
    A(f"| {case} | {ctx} | " + " | ".join(cells) + " |")
A("")
A("Mechanism totals (non-diagnostic cases):\n")
tot = defaultdict(lambda: defaultdict(int))
for t in res["timing"]:
    if t.get("diagnostic"):
        continue
    tot[(t["context"], t["mechanism"])][t["verdict"]] += 1
for (ctx, m), v in sorted(tot.items()):
    A(f"- {ctx} / {m}: " + ", ".join(f"{k} {n}" for k, n in sorted(v.items())))
A("")
A("Failure details:\n")
for t in res["timing"]:
    if t["verdict"] != "PASS":
        A(f"- `{t['case']}` {t['context']}/{t['mechanism']}: {t['verdict']} — {t['why']}")
A("")
A("### Codex baseline variations (stock behaviour reproduced on the restricted wheel)\n")
A("| variation | mechanism | first buy (ours) | Codex reported | seen by strategy |")
A("|---|---|---|---|---|")
for r in res["codex_baselines"]:
    fb = r.get("first_buy") or {}
    A(f"| {r.get('variation')} | {r.get('mechanism')} | {fb.get('time', 'no fill')} {fb.get('px', '')} | "
      f"{r['codex_reported']['time']} {r['codex_reported']['px']} | {fb.get('seen_by_strategy', '—')} |")
A("")

# ---- check 4
A("## Check 4 — attribution, FIFO, fees, lot/tick (gate)\n")
A("| case | context | verdict | details |")
A("|---|---|---|---|")
for l in res["ledger"]:
    d = l["detail"]
    extra = []
    if "commissions" in d:
        extra.append(f"commissions {d['commissions']}")
    if "engine_realized" in d:
        extra.append(f"FIFO {d['ledger']['fifo_realized_gross']} vs engine {d['engine_realized']}")
    if "refusals" in d:
        extra.append(f"refusals {len(d['refusals'])}")
    if d.get("ledger"):
        extra.append(f"cash engine {d.get('engine_cash')} / ledger {d['ledger']['cash']}")
    A(f"| {l['case']} | {l['context']} | {l['verdict']} | {'; '.join(extra)} {l['why']} |")
A("")

# ---- memory
A("## Worker memory (cgroup memory.peak, MiB)\n")
peaks = defaultdict(list)
for t in res["timing"] + res["ledger"]:
    r = t["result"]
    m = (r.get("memory") or {}).get("memory.peak")
    if isinstance(m, int):
        peaks[t["context"]].append(m / 2**20)
for ctx, v in peaks.items():
    A(f"- {ctx}: n={len(v)}, min {min(v):.1f}, median {sorted(v)[len(v)//2]:.1f}, max {max(v):.1f}")
A("")
(out / "summary.md").write_text("\n".join(L) + "\n")

# trimmed results (drop per-event strategy logs to keep the committed file reviewable)
for t in res["timing"] + res["ledger"]:
    t["result"].pop("log", None)
(out / "results.json").write_text(json.dumps(res, indent=1, default=str))
print("wrote", out / "summary.md")
