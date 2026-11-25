"""Run ONE proof-0A case in this process (one engine node per process, per upstream guidance) and
print a JSON result. Usage:

  python run_case.py --suite timing|ledger --case NAME --context backtest|sandbox \
                     --mechanism baseline|native|native_bounded|gate

Mechanisms:
  baseline        zero latency, stock behaviour (expected to violate after_watermark)
  native          D22(a): upstream StaticLatencyModel(1 ms), no Clipper code in the matching path
  native_bounded  D22(a) constrained: native + support_gtd_orders=False + engine.run(end=<last data ts>)
                  (backtest only; probes whether bounding the run suppresses the end-of-run drain)
  gate            D22(b): Clipper timing gate (GatedStrategy), zero latency
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from decimal import Decimal

import nautilus_trader
from nautilus_trader.common import LoggerConfig, LogLevel
from nautilus_trader.config import BacktestEngineConfig, StrategyConfig
from nautilus_trader.execution import FillModel, MakerTakerFeeModel, StaticLatencyModel
from nautilus_trader.model import AccountType, Money, OmsType, TraderId

import clipper0a as c
from cases import LEDGER_CASES, TIMING_CASES

START_CASH = Decimal("100000")
# Clipper pinned venue fill spec (conservative): never let one displayed size support more than
# one fill. Upstream default (False) reuses displayed size within an iteration (overfill).
LIQUIDITY_CONSUMPTION = True
NATIVE_LATENCY_NS = 1_000_000  # 1 ms


def fee_model(kind: str):
    if kind == "clipper":
        return c.ClipperFeeModel(c.FeeSpec())
    return MakerTakerFeeModel(maker_rate=Decimal(0), taker_rate=Decimal(0))


def index_key(data) -> tuple:
    if isinstance(data, c.Bar):
        return (str(data.bar_type.instrument_id.symbol), "bar", data.ts_init, str(data.close))
    return (str(data.instrument_id.symbol), "quote", data.ts_init, str(data.bid_price), str(data.ask_price))


def ev_key(ev: dict, ts: int) -> tuple:
    if ev["kind"] == "bar":
        return (ev["sym"], "bar", ts, ev["c"])
    return (ev["sym"], "quote", ts, ev["bid"], ev["ask"])


def strategy_for(mech: str, case: dict, index_of):
    cls = c.GatedStrategy if mech == "gate" else c.ScriptedStrategy
    return cls(StrategyConfig()).configure(case["script"], case["subs"], index_of)


def collect(strategy, emitted: list[dict], tolerance_ns: int, cache) -> dict:
    fills = []
    seen = {f["trade_id"] for f in strategy.fills}
    for f in c.cache_fills(cache):
        f["attribution"] = c.attribute(f, emitted, tolerance_ns)
        f["seen_by_strategy"] = f["trade_id"] in seen
        fills.append(f)
    out = {"fills": fills, "refusals": strategy.refusals, "log": strategy.evlog}
    if isinstance(strategy, c.GatedStrategy):
        out["gate_log"] = strategy.gate_log
        out["held_at_end"] = strategy.held_at_end()
    return out


# ------------------------------------------------------------------------------ backtest
def run_backtest(case: dict, mech: str) -> dict:
    from nautilus_trader.backtest import BacktestEngine

    T0 = 1_767_225_600 * c.SEC  # 2026-01-01T00:00:00Z (fixed, reproducible)
    engine = BacktestEngine(config=BacktestEngineConfig(
        trader_id=TraderId.from_str("CLIPPER-0A"), logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    # Explicit fill / latency specifications on every run (ADR-013)
    kw = {"fill_model": FillModel(), "latency_model": StaticLatencyModel(base_latency_nanos=0)}
    if mech in ("native", "native_bounded"):
        kw["latency_model"] = StaticLatencyModel(base_latency_nanos=NATIVE_LATENCY_NS)
    if mech == "native_bounded":
        kw["support_gtd_orders"] = False
    fm = fee_model(case.get("fees", "zero"))
    engine.add_venue(venue=c.VENUE, oms_type=OmsType.NETTING, account_type=AccountType.CASH,
                     starting_balances=[Money(float(START_CASH), c.USD)], base_currency=c.USD,
                     default_leverage=Decimal(1), fee_model=fm, liquidity_consumption=LIQUIDITY_CONSUMPTION, **kw)
    for sym in sorted({e["sym"] for e in case["events"]}):
        engine.add_instrument(c.make_instrument(sym))
    emitted, data, keymap = [], [], {}
    for i, ev in enumerate(case["events"]):
        ts = T0 + int(round(ev["t"] * c.SEC))
        data.append(c.to_nautilus(ev, ts))
        keymap[ev_key(ev, ts)] = i
        emitted.append({**ev, "idx": i, "ts": ts})
    engine.add_data(data)
    s = strategy_for(mech, case, lambda d: keymap.get(index_key(d)))
    engine.add_strategy(s)
    if mech == "native_bounded":
        engine.run(end=max(e["ts"] for e in emitted))
    else:
        engine.run()
    out = collect(s, emitted, tolerance_ns=0, cache=engine.cache)
    out.update(engine_state(engine))
    out["t0_ns"] = T0
    engine.dispose()
    return out


def engine_state(engine_or_node) -> dict:
    st = {}
    try:
        cache = engine_or_node.cache
        cache = cache() if callable(cache) else cache
        acct = cache.account_for_venue(c.VENUE)
        st["cash"] = str(acct.balance_total(c.USD))
        pos = []
        for p in cache.positions():
            pos.append({"sym": str(p.instrument_id.symbol), "qty": str(p.quantity),
                        "realized_pnl": str(p.realized_pnl), "side": str(p.side)})
        st["positions"] = pos
    except Exception as exc:  # recorded, not hidden
        st["engine_state_error"] = f"{type(exc).__name__}: {exc}"
    return st


# ------------------------------------------------------------------------------ sandbox (replay)
SCALE = 0.25  # 1 fixture second = 0.25 s wall clock


def run_sandbox(case: dict, mech: str) -> dict:
    from nautilus_trader.adapters.sandbox import SandboxExecutionClientConfig, SandboxExecutionClientFactory
    from nautilus_trader.common import Environment
    from nautilus_trader.config import DataClientConfig, LiveRiskEngineConfig
    from nautilus_trader.live import LiveNode
    from nautilus_trader.live.clients import DataClientFactory, MarketDataClient
    from nautilus_trader.model import AccountId

    state = {"emitted": [], "keymap": {}, "handle": None, "done": False, "errors": []}
    events = case["events"]

    class ReplayClient(MarketDataClient):
        """Replays the synthetic fixture in (scaled) real time; stamps ts with the node clock."""

        async def _connect(self) -> None:
            for sym in sorted({e["sym"] for e in events}):
                self._handle_instrument(c.make_instrument(sym))
            self.create_task(self._replay(), "clipper-replay")

        async def _replay(self) -> None:
            try:
                await asyncio.sleep(1.5)  # let strategy subscriptions settle
                base = self.clock.timestamp_ns()
                last_t, last_ts = None, None
                for i, ev in enumerate(events):
                    target = base + int(ev["t"] * SCALE * c.SEC)
                    now = self.clock.timestamp_ns()
                    if target > now:
                        await asyncio.sleep((target - now) / c.SEC)
                    ts = last_ts if (last_t is not None and ev["t"] == last_t) else self.clock.timestamp_ns()
                    last_t, last_ts = ev["t"], ts
                    state["keymap"][ev_key(ev, ts)] = i
                    state["emitted"].append({**ev, "idx": i, "ts": ts})
                    self._handle_data(c.to_nautilus(ev, ts))
                await asyncio.sleep(2.0)  # grace for any late releases / drains
            except Exception as exc:
                state["errors"].append(repr(exc))
            finally:
                state["done"] = True
                if state["handle"] is not None:
                    state["handle"].stop()

        async def _disconnect(self) -> None:
            pass

        async def _subscribe_quotes(self, command) -> None:
            pass

        async def _unsubscribe_quotes(self, command) -> None:
            pass

        async def _subscribe_bars(self, command) -> None:
            pass

        async def _unsubscribe_bars(self, command) -> None:
            pass

    class ReplayFactory(DataClientFactory):
        @staticmethod
        def create(*, name, config, cache, clock):
            return ReplayClient(name=name, config=config, cache=cache, clock=clock, venue=c.VENUE)

    fm = fee_model(case.get("fees", "zero"))
    sb_kwargs = dict(venue=c.VENUE, starting_balances=[Money(float(START_CASH), c.USD)],
                     account_id=AccountId.from_str("SIM-001"), base_currency=c.USD,
                     oms_type=OmsType.NETTING, account_type=AccountType.CASH,
                     default_leverage=Decimal(1), fee_model=fm, liquidity_consumption=LIQUIDITY_CONSUMPTION,
                     fill_model=FillModel(), latency_model=StaticLatencyModel(base_latency_nanos=0))
    if mech == "native":
        sb_kwargs["latency_model"] = StaticLatencyModel(base_latency_nanos=NATIVE_LATENCY_NS)
    node = (LiveNode.builder("CLIPPER-0A-SANDBOX", TraderId.from_str("CLIPPER-0A"), Environment.SANDBOX)
            .with_reconciliation(reconciliation=False)
            .with_risk_engine_config(LiveRiskEngineConfig(bypass=False))
            .with_logging(LoggerConfig(stdout_level=LogLevel.ERROR))
            .add_data_client("REPLAY", ReplayFactory(), DataClientConfig())
            .add_simulated_exec_client("SIM", SandboxExecutionClientFactory(),
                                       SandboxExecutionClientConfig(**sb_kwargs))
            .build())
    script = [dict(a, scale=SCALE) if a.get("on") == "timer" else a for a in case["script"]]
    s = strategy_for(mech, dict(case, script=script), lambda d: state["keymap"].get(index_key(d)))
    node.add_strategy(s)
    state["handle"] = node.handle()
    node.run()
    out = collect(s, state["emitted"], tolerance_ns=int(0.05 * c.SEC), cache=node.cache)
    out.update(engine_state(node))
    out["replay_errors"] = state["errors"]
    out["replay_completed"] = state["done"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=["timing", "ledger"], required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--context", choices=["backtest", "sandbox"], required=True)
    ap.add_argument("--mechanism", choices=["baseline", "native", "native_bounded", "gate"], required=True)
    ap.add_argument("--liquidity", choices=["consumption", "upstream-default"], default="consumption")
    a = ap.parse_args()
    global LIQUIDITY_CONSUMPTION
    LIQUIDITY_CONSUMPTION = a.liquidity == "consumption"
    case = (TIMING_CASES if a.suite == "timing" else LEDGER_CASES)[a.case]
    t = time.time()
    try:
        res = run_backtest(case, a.mechanism) if a.context == "backtest" else run_sandbox(case, a.mechanism)
        res["error"] = None
    except Exception as exc:
        import traceback
        res = {"error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    res.update({"suite": a.suite, "case": a.case, "context": a.context, "mechanism": a.mechanism,
                "liquidity_consumption": LIQUIDITY_CONSUMPTION,
                "wall_s": round(time.time() - t, 3), "nautilus_version": nautilus_trader.__version__,
                "python": sys.version.split()[0], "memory": c.cgroup_memory_peak(),
                "fixture_provenance": c.fixture_provenance(a.case, case["events"])})
    print("CLIPPER-0A-RESULT " + json.dumps(res, default=str))


if __name__ == "__main__":
    main()
