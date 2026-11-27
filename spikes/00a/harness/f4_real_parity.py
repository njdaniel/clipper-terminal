"""F4 stage B parity (D29; LOCAL ONLY): backtest vs replay sandbox on one 120 s real-tape slice.

  python f4_real_parity.py <backtest|sandbox> <local_dir> <L1|L2|L3> <consumption|default> <queue|noqueue> <publishers.json>

Slice: the first 120 s of window 2 (6 probes). The stream is an L3 snapshot of the book at slice start
(CLEAR + ADD per resting order, F_SNAPSHOT) followed by the slice's batches and trades; L2/L1 are derived
from that same stream exactly as in f4_real_experiment. The sandbox replays the stream at 1x wall-clock
speed (offsets preserved, timestamps restamped); replay lag is measured and reported.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from decimal import Decimal

import f4_real_experiment as X
import f4_real_guard as g

SLICE_START = X.DAY0 + (16 * 3600) * X.SEC
SLICE_LEN = 120 * X.SEC


def slice_stream(local, level, publishers):
    """Return (stream_items, schedule) with stream items as (offset_ns, nautilus_obj_factory(ts)) pairs."""
    from nautilus_trader.adapters.databento import DatabentoDataLoader
    from nautilus_trader.model import BookAction, BookOrder, OrderBookDelta, OrderSide, Price, Quantity

    deltas = [d for d in DatabentoDataLoader(publishers).load_order_book_deltas(g.input_path(), price_precision=2)
              if str(d.instrument_id) == X.FRONT and d.ts_init <= SLICE_START + SLICE_LEN]
    iid = deltas[0].instrument_id
    book = {}
    k = 0
    while k < len(deltas) and deltas[k].ts_init < SLICE_START:
        d = deltas[k]
        if d.action == BookAction.CLEAR:
            book.clear()
        elif d.action == BookAction.DELETE:
            book.pop(d.order.order_id, None)
        else:
            book[d.order.order_id] = (d.order.side, d.order.price, d.order.size)
        k += 1
    while k < len(deltas) and not (deltas[k - 1].flags & X.F_LAST):  # start on a batch boundary
        k += 1
    snap_ts = SLICE_START
    snap = [OrderBookDelta.clear(iid, 0, snap_ts, snap_ts)]
    items = list(book.items())
    for n, (oid, (sd, px, sz)) in enumerate(items):
        flags = 32 | (X.F_LAST if n == len(items) - 1 else 0)  # F_SNAPSHOT (+F_LAST)
        snap.append(OrderBookDelta(iid, BookAction.ADD, BookOrder(sd, px, sz, oid), flags, 0, snap_ts, snap_ts))
    sl = snap + deltas[k:]
    return iid, sl


def build(local, level, publishers):
    """Stream for the slice through the SAME derivation code as the full-day experiment."""
    iid, sl = slice_stream(local, level, publishers)
    out = X.derive_stream(sl, level, local, ts_min=SLICE_START, ts_max=SLICE_START + SLICE_LEN)
    sched = [p for p in X.probe_schedule() if SLICE_START <= p["t"] < SLICE_START + SLICE_LEN - 25 * X.SEC]
    return out, sched


def run(mode, local, level, liq, queue, publishers):
    data, sched = build(local, level, publishers)
    if mode == "backtest":
        res = X.engine_on(data, sched, level, liq, queue, offset=0)
        return {"probes": res["probes"], "events": len(data)}
    return sandbox(data, sched, level, liq, queue)


def sandbox(data, sched, level, liq, queue):
    from nautilus_trader.adapters.sandbox import SandboxExecutionClientConfig, SandboxExecutionClientFactory
    from nautilus_trader.common import Environment, LoggerConfig, LogLevel
    from nautilus_trader.config import DataClientConfig, LiveRiskEngineConfig
    from nautilus_trader.execution import FillModel, MakerTakerFeeModel, StaticLatencyModel
    from nautilus_trader.live import LiveNode
    from nautilus_trader.live.clients import DataClientFactory, MarketDataClient
    from nautilus_trader.model import AccountId, AccountType, BookType, Currency, Money, OmsType, TraderId, Venue

    t0 = data[0].ts_init
    st = {"handle": None, "lag_ns": [], "base": None}
    # The sandbox runs on the wall clock; the replayed contract would otherwise be "expired" (Sep 2026).
    # Constructed metadata only (no definition records in the D29 input): expiry = now + 365 days.
    inst = X.instrument(expiration_ns=time.time_ns() + 365 * 86400 * X.SEC)

    class Replay(MarketDataClient):
        async def _connect(self):
            self._handle_instrument(inst)
            self.create_task(self._go(), "replay")

        async def _go(self):
            await asyncio.sleep(2.0)
            base = self.clock.timestamp_ns()
            st["base"] = base
            for d in data:
                due = base + (d.ts_init - t0)
                now = self.clock.timestamp_ns()
                if due > now + 500_000:
                    await asyncio.sleep((due - now) / X.SEC)
                    now = self.clock.timestamp_ns()
                st["lag_ns"].append(max(0, now - due))
                self._handle_data(X.restamp(d, due))
            await asyncio.sleep(27.0)  # let the last horizons pass
            st["handle"].stop()

        async def _disconnect(self):
            pass

        for _n in ("quotes", "trades", "book_deltas"):
            exec(f"async def _subscribe_{_n}(self, command): pass\nasync def _unsubscribe_{_n}(self, command): pass")

    class Factory(DataClientFactory):
        @staticmethod
        def create(*, name, config, cache, clock):
            return Replay(name=name, config=config, cache=cache, clock=clock, venue=Venue("GLBX"))

    usd = Currency.from_str("USD")
    sb = SandboxExecutionClientConfig(
        venue=Venue("GLBX"), starting_balances=[Money(1e9, usd)], account_id=AccountId.from_str("GLBX-001"),
        base_currency=usd, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, default_leverage=Decimal(1),
        book_type={"L1": BookType.L1_MBP, "L2": BookType.L2_MBP, "L3": BookType.L3_MBO}[level],
        fill_model=FillModel(), fee_model=MakerTakerFeeModel(maker_rate=Decimal(0), taker_rate=Decimal(0)),
        latency_model=StaticLatencyModel(base_latency_nanos=0), liquidity_consumption=liq, queue_position=queue,
        trade_execution=True, bar_execution=False)
    lvl = LogLevel.WARNING if __import__("os").environ.get("F4_DEBUG") else LogLevel.ERROR
    node = (LiveNode.builder("CLIPPER-F4P", TraderId.from_str("CLIPPER-F4P"), Environment.SANDBOX)
            .with_reconciliation(reconciliation=False).with_risk_engine_config(LiveRiskEngineConfig(bypass=False))
            .with_logging(LoggerConfig(stdout_level=lvl))
            .add_data_client("REPLAY", Factory(), DataClientConfig())
            .add_simulated_exec_client("GLBX", SandboxExecutionClientFactory(), sb).build())
    gate = X.make_gate(sched, level, inst, offset_fn=lambda: (st["base"] - t0) if st["base"] is not None else None)
    node.add_strategy(gate)
    st["handle"] = node.handle()
    node.run()
    probes = X.collect_probes(gate, node.cache)
    lag = sorted(st["lag_ns"])
    return {"probes": probes, "events": len(data),
            "replay_lag_ms": {"p50": lag[len(lag) // 2] / 1e6, "p99": lag[int(len(lag) * 0.99)] / 1e6, "max": lag[-1] / 1e6}}


if __name__ == "__main__":
    mode, local = sys.argv[1], g.local_out(sys.argv[2])
    level, liq, queue, pubs = sys.argv[3], sys.argv[4] == "consumption", sys.argv[5] == "queue", sys.argv[6]
    t = time.time()
    res = run(mode, local, level, liq, queue, pubs)
    name = f"parity_{mode}_{level}_{'liq' if liq else 'noliq'}_{'q' if queue else 'noq'}.json"
    (local / name).write_text(json.dumps(res))
    print(json.dumps({"file": name, "probes": len(res["probes"]), "events": res["events"],
                      "replay_lag_ms": res.get("replay_lag_ms"), "seconds": round(time.time() - t, 1)}))
