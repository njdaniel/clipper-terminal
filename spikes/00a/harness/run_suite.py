"""Proof 0A orchestrator. Runs checks 1-4 against a runtime environment and writes evidence.

  python3 run_suite.py --python <runtime>/bin/python --work <dir> --evidence <dir> [--stock-python <py>]

Every case runs in its own process inside `systemd-run --user --scope` so that the per-worker
cgroup memory.peak is attributable (D26). Verdicts are computed here from the independent
expectations in cases.py; nothing is relaxed on failure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cases import LEDGER_CASES, TIMING_CASES  # noqa: E402

BACKTEST_MECHS = ["baseline", "native", "native_bounded", "gate"]
SANDBOX_MECHS = ["baseline", "native", "gate"]


def run_py(py: str, args: list[str], timeout: int = 180) -> dict:
    cmd = ["systemd-run", "--user", "--scope", "--quiet", "-p", "MemoryAccounting=yes", py, *args]
    t = time.time()
    p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, timeout=timeout)
    for line in p.stdout.splitlines():
        if line.startswith("CLIPPER-0A-RESULT "):
            r = json.loads(line[len("CLIPPER-0A-RESULT "):])
            r.setdefault("wall_s", round(time.time() - t, 3))
            return r
    return {"error": f"no result (exit {p.returncode})", "stderr_tail": p.stderr[-3000:]}


def money(s: str) -> Decimal:
    return Decimal(str(s).split()[0])


def timing_verdict(res: dict, case: dict) -> tuple[str, str]:
    if res.get("error"):
        return "ERROR", res["error"]
    if res.get("context") == "sandbox" and (res.get("replay_errors") or not res.get("replay_completed")):
        return "ERROR", f"replay incomplete: {res.get('replay_errors')}"
    act = [{"idx": f["attribution"]["idx"], "px": f["px"], "qty": f["qty"]} for f in res["fills"]]
    bad_origin = [f["attribution"] for f in res["fills"] if f["attribution"]["origin"] != "feed_event"]
    if act == case["expected"] and not bad_origin:
        return "PASS", ""
    return "FAIL", f"expected {case['expected']} got {act}" + (f"; non-feed fills {bad_origin}" if bad_origin else "")


def ledger_verdict(name: str, res: dict, case: dict) -> tuple[str, str, dict]:
    import clipper0a as c
    if res.get("error"):
        return "ERROR", res["error"], {}
    exp = case["expected"]
    fills = res["fills"]
    act = [{"idx": f["attribution"]["idx"], "px": f["px"], "qty": f["qty"]} for f in fills]
    led = c.fifo_ledger(fills, Decimal("100000"))
    detail = {"ledger": led, "engine_cash": res.get("cash"), "engine_positions": res.get("positions")}
    problems = []
    if act != exp["fills"]:
        problems.append(f"fills expected {exp['fills']} got {act}")
    if [f["attribution"]["origin"] for f in fills if f["attribution"]["origin"] != "feed_event"]:
        problems.append("non-feed fill origin")
    if res.get("cash") is not None and money(res["cash"]) != Decimal(led["cash"]):
        problems.append(f"cash: engine {res['cash']} vs ledger {led['cash']}")
    eng_qty = {p["sym"]: Decimal(p["qty"]) for p in res.get("positions", [])}
    for sym, q in led["position_qty"].items():
        if eng_qty.get(sym, Decimal(0)) != Decimal(q):
            problems.append(f"qty {sym}: engine {eng_qty.get(sym)} vs ledger {q}")
    if name == "fifo":
        if led["fifo_realized_gross"] != exp["fifo_realized_gross"]:
            problems.append(f"FIFO realized {led['fifo_realized_gross']} != {exp['fifo_realized_gross']}")
        eng_real = [money(p["realized_pnl"]) for p in res.get("positions", [])]
        detail["engine_realized"] = [str(x) for x in eng_real]
        if eng_real != [Decimal(exp["engine_realized"])]:
            problems.append(f"engine realized {eng_real} != {exp['engine_realized']}")
    if "commissions" in exp:
        got = [str(money(f["commission"])) for f in fills]
        spec = c.FeeSpec()
        indep = [str(x) for x in c.expected_commissions(spec, [(Decimal(f["qty"]), Decimal(f["px"])) for f in fills], "BUY")]
        detail.update({"commissions": got, "independent_recomputation": indep})
        if got != exp["commissions"]:
            problems.append(f"commissions {got} != {exp['commissions']}")
        if indep != exp["commissions"]:
            problems.append(f"independent fee recomputation {indep} != {exp['commissions']}")
    if "refused" in exp:
        reasons = [r.get("reason", "") for r in res.get("refusals", [])]
        detail["refusals"] = reasons
        if len([r for r in reasons if r.startswith(("lot", "tick"))]) != exp["refused"]:
            problems.append(f"refusals {reasons}")
    return ("PASS" if not problems else "FAIL"), "; ".join(problems), detail


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--stock-python")
    a = ap.parse_args()
    ev = Path(a.evidence)
    ev.mkdir(parents=True, exist_ok=True)
    results: dict = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "runtime_python": a.python}

    # Check 1 (artifact): environment introspection; build evidence is produced by build_engine.sh
    art = subprocess.run([a.python, str(HERE / "artifact_check.py")], capture_output=True, text=True, cwd=HERE)
    results["artifact"] = json.loads(art.stdout)
    if a.stock_python:
        st = subprocess.run([a.stock_python, str(HERE / "artifact_check.py")], capture_output=True, text=True, cwd=HERE)
        results["artifact_stock_baseline"] = json.loads(st.stdout)

    # Check 2: BacktestNode from catalog
    results["backtestnode"] = run_py(a.python, ["backtestnode_check.py", str(Path(a.work) / "catalog-fifo")])

    # Check 3: timing suite + Codex baselines
    timing = []
    for name, case in TIMING_CASES.items():
        for ctx, mechs in (("backtest", BACKTEST_MECHS), ("sandbox", SANDBOX_MECHS)):
            for m in mechs:
                r = run_py(a.python, ["run_case.py", "--suite", "timing", "--case", name, "--context", ctx, "--mechanism", m])
                v, why = timing_verdict(r, case)
                timing.append({"case": name, "context": ctx, "mechanism": m, "verdict": v, "why": why, "result": r})
                print(f"timing {name:22s} {ctx:8s} {m:15s} {v} {why[:120]}", flush=True)
    # Diagnostic: upstream-default liquidity (consumption off) for the partial-fill case
    for ctx, mechs in (("backtest", BACKTEST_MECHS), ("sandbox", SANDBOX_MECHS)):
        for m in mechs:
            r = run_py(a.python, ["run_case.py", "--suite", "timing", "--case", "partial_fills", "--context", ctx,
                                  "--mechanism", m, "--liquidity", "upstream-default"])
            v, why = timing_verdict(r, TIMING_CASES["partial_fills"])
            timing.append({"case": "partial_fills[upstream-default-liquidity]", "context": ctx, "mechanism": m,
                           "verdict": v, "why": why, "result": r, "diagnostic": True})
            print(f"timing partial_fills[default-liq] {ctx:8s} {m:15s} {v} {why[:120]}", flush=True)
    results["timing"] = timing
    codex = []
    for var in (1, 2, 3, 4):
        for m in ("baseline", "gate"):
            r = run_py(a.python, ["codex_baselines.py", str(var), m])
            codex.append(r)
            print(f"codex v{var} {m:8s} first_buy={r.get('first_buy')} reported={r.get('codex_reported')}", flush=True)
    results["codex_baselines"] = codex

    # Check 4: attribution / FIFO / fees / lot-tick (gate mechanism) in both contexts
    ledger = []
    for name, case in LEDGER_CASES.items():
        for ctx in ("backtest", "sandbox"):
            r = run_py(a.python, ["run_case.py", "--suite", "ledger", "--case", name, "--context", ctx, "--mechanism", "gate"])
            v, why, detail = ledger_verdict(name, r, case)
            ledger.append({"case": name, "context": ctx, "verdict": v, "why": why, "detail": detail, "result": r})
            print(f"ledger {name:24s} {ctx:8s} {v} {why[:160]}", flush=True)
    results["ledger"] = ledger
    results["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (ev / "results.json").write_text(json.dumps(results, indent=1, default=str))
    print("wrote", ev / "results.json")


if __name__ == "__main__":
    main()
