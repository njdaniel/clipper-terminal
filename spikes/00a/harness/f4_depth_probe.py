"""F4 extension (synthetic, stage A): L1 vs L2 vs L3 execution from EQUIVALENT events derived from one
synthetic MBO tape per scenario, under explicit configuration, in backtest and replay sandbox.

  python f4_depth_probe.py <scenario> <L1|L2|L3> <backtest|sandbox> <consumption|default> <queue|noqueue>

Each scenario is an MBO tape (order-level adds/updates/deletes + trades). Derived views:
  L3  OrderBookDeltas with the tape's order ids (book_type L3_MBO)
  L2  per-event price-level deltas of the aggregated book (book_type L2_MBP, order_id = 0)
  L1  QuoteTick of top of book after every event that touches a top level, as mbp-1/tbbo do,
      even when the resulting values are unchanged (book_type L1_MBP)
  all trades -> TradeTick
TRUTH is defined from order identity on the tape: liquidity at a level is the size of tape orders
there, minus what the simulated order has already taken from those SAME orders.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict
from decimal import Decimal

from nautilus_trader.common import LoggerConfig, LogLevel
from nautilus_trader.config import BacktestEngineConfig, StrategyConfig
from nautilus_trader.execution import FillModel, MakerTakerFeeModel, StaticLatencyModel
from nautilus_trader.model import (
    AccountType, AggressorSide, BookAction, BookOrder, BookType, Money, OmsType, OrderBookDelta, OrderBookDeltas,
    OrderSide, Price, Quantity, QuoteTick, RecordFlag, TimeInForce, TradeId, TradeTick, TraderId,
)
from nautilus_trader.trading import Strategy

import clipper0a as c

B, S = OrderSide.BUY, OrderSide.SELL
F_LAST = int(RecordFlag.F_LAST.value)
F_SNAP = int(RecordFlag.F_SNAPSHOT.value)

# ------------------------------------------------------------------ scenarios (MBO tapes)
# event: {"t": seconds, "ops": [(action, side, price, size, order_id)], "trade": (price, size, aggressor) | None}
SNAP = [("ADD", "B", "11.00", 100, 1), ("ADD", "A", "11.02", 100, 2)]

SCENARIOS = {
    "S1_same_order_persists": {
        "doc": "Ask order #2 (11.02 x100) never leaves the tape; only bid #1 churns. After the simulated order "
               "takes #2's 100, no further liquidity exists at 11.02.",
        "tape": [{"t": 0, "ops": SNAP}, {"t": 1, "ops": [("UPDATE", "B", "11.00", 110, 1)]},
                 {"t": 2, "ops": [("UPDATE", "B", "11.00", 120, 1)]}, {"t": 3, "ops": [("UPDATE", "B", "11.00", 130, 1)]},
                 {"t": 4, "ops": [("UPDATE", "B", "11.00", 140, 1)]}],
        "order": {"side": "BUY", "qty": 300, "price": "11.02", "decide_at": 1},
        "truth": [(2, "100")],
    },
    "S2_new_orders_arrive": {
        "doc": "Ask #2 is deleted at t=3 and NEW ask #3 (11.02 x100) added in the same event; #3 deleted and "
               "#4 added at t=4. Each new order is fresh liquidity.",
        "tape": [{"t": 0, "ops": SNAP}, {"t": 1, "ops": [("UPDATE", "B", "11.00", 110, 1)]},
                 {"t": 2, "ops": [("UPDATE", "B", "11.00", 120, 1)]},
                 {"t": 3, "ops": [("DELETE", "A", "11.02", 100, 2), ("ADD", "A", "11.02", 100, 3)]},
                 {"t": 4, "ops": [("DELETE", "A", "11.02", 100, 3), ("ADD", "A", "11.02", 100, 4)]},
                 {"t": 5, "ops": [("UPDATE", "B", "11.00", 150, 1)]}],
        "order": {"side": "BUY", "qty": 300, "price": "11.02", "decide_at": 1},
        "truth": [(2, "100"), (3, "100"), (4, "100")],
    },
    "S3_level_moves_and_returns": {
        "doc": "Ask #2 deleted at t=3 (best ask becomes #5 at 11.03); NEW ask #6 at 11.02 x100 added at t=4.",
        "tape": [{"t": 0, "ops": SNAP + [("ADD", "A", "11.03", 100, 5)]}, {"t": 1, "ops": [("UPDATE", "B", "11.00", 110, 1)]},
                 {"t": 2, "ops": [("UPDATE", "B", "11.00", 120, 1)]}, {"t": 3, "ops": [("DELETE", "A", "11.02", 100, 2)]},
                 {"t": 4, "ops": [("ADD", "A", "11.02", 100, 6)]}, {"t": 5, "ops": [("UPDATE", "B", "11.00", 150, 1)]}],
        "order": {"side": "BUY", "qty": 300, "price": "11.02", "decide_at": 1},
        "truth": [(2, "100"), (4, "100")],
    },
    "S4_queue_position": {
        "doc": "Passive BUY 50 @11.00 joins behind bid #1 (100). Sell trades at 11.00: 60 at t=3 (#1 -> 40), "
               "60 at t=4 (#1 gone, 20 reach us), 100 at t=5 (our remaining 30).",
        "tape": [{"t": 0, "ops": SNAP}, {"t": 1, "ops": [("UPDATE", "A", "11.02", 110, 2)]},
                 {"t": 2, "ops": [("UPDATE", "A", "11.02", 120, 2)]},
                 {"t": 3, "ops": [("UPDATE", "B", "11.00", 40, 1)], "trade": ("11.00", 60, "SELL")},
                 {"t": 4, "ops": [("DELETE", "B", "11.00", 40, 1)], "trade": ("11.00", 60, "SELL")},
                 {"t": 5, "ops": [], "trade": ("11.00", 100, "SELL")},
                 {"t": 6, "ops": [("UPDATE", "A", "11.02", 130, 2)]}],
        "order": {"side": "BUY", "qty": 50, "price": "11.00", "decide_at": 1},
        "truth": [(4, "20"), (5, "30")],
    },
}


# ------------------------------------------------------------------ derivations
def side(s: str):
    return B if s == "B" else S


def derive(tape: list[dict], level: str, iid, t0: int, scale: float = 1.0) -> list[tuple[int, int, object]]:
    """Return [(event_idx, ts, nautilus_data), ...] for the requested view."""
    out = []
    book = {"B": {}, "A": {}}  # order_id -> (price, size)
    seq = 0
    for idx, ev in enumerate(tape):
        ts = t0 + int(ev["t"] * scale * c.SEC)
        if ev.get("trade"):  # trade record precedes the resting-order reduction, as on the real MBO tape
            px, sz, agg = ev["trade"]
            out.append((idx, ts, TradeTick(iid, Price.from_str(px), Quantity.from_int(sz),
                                           AggressorSide.SELL if agg == "SELL" else AggressorSide.BUY,
                                           TradeId(f"T{idx}"), ts, ts)))
        before = {s: _levels(book[s]) for s in book}
        for act, sd, px, sz, oid in ev["ops"]:
            if act == "DELETE":
                book[sd].pop(oid, None)
            else:
                book[sd][oid] = (px, sz)
        after = {s: _levels(book[s]) for s in book}
        if level == "L3" and ev["ops"]:
            deltas = []
            if idx == 0:
                deltas.append(OrderBookDelta.clear(iid, seq, ts, ts))
            for k, (act, sd, px, sz, oid) in enumerate(ev["ops"]):
                seq += 1
                flags = (F_LAST if k == len(ev["ops"]) - 1 else 0) | (F_SNAP if idx == 0 else 0)
                deltas.append(OrderBookDelta(iid, getattr(BookAction, act),
                                             BookOrder(side(sd), Price.from_str(px), Quantity.from_int(sz), oid),
                                             flags, seq, ts, ts))
            out.append((idx, ts, OrderBookDeltas(iid, deltas)))
        elif level == "L2" and ev["ops"]:
            touched = {(sd, px) for _, sd, px, _, _ in ev["ops"]}
            deltas = [OrderBookDelta.clear(iid, seq, ts, ts)] if idx == 0 else []
            items = sorted(touched)
            for k, (sd, px) in enumerate(items):
                seq += 1
                new = after[sd].get(px, 0)
                act = BookAction.DELETE if new == 0 else (BookAction.ADD if px not in before[sd] else BookAction.UPDATE)
                flags = (F_LAST if k == len(items) - 1 else 0) | (F_SNAP if idx == 0 else 0)
                deltas.append(OrderBookDelta(iid, act, BookOrder(side(sd), Price.from_str(px), Quantity.from_int(max(new, 0)), 0),
                                             flags, seq, ts, ts))
            out.append((idx, ts, OrderBookDeltas(iid, deltas)))
        elif level == "L1" and ev["ops"]:
            touches_top = any(px == _best(before[sd], sd) or px == _best(after[sd], sd) for _, sd, px, _, _ in ev["ops"])
            bb, ba = _best(after["B"], "B"), _best(after["A"], "A")
            if (touches_top or idx == 0) and bb is not None and ba is not None:  # L1 cannot represent an empty side
                out.append((idx, ts, QuoteTick(iid, Price.from_str(bb), Price.from_str(ba),
                                               Quantity.from_int(after["B"][bb]), Quantity.from_int(after["A"][ba]), ts, ts)))
    return out


def _levels(orders: dict) -> dict:
    agg = defaultdict(int)
    for px, sz in orders.values():
        agg[px] += sz
    return dict(agg)


def _best(levels: dict, sd: str):
    if not levels:
        return None
    return max(levels, key=Decimal) if sd == "B" else min(levels, key=Decimal)


# ------------------------------------------------------------------ gated strategy for depth data
class DepthGate(Strategy):
    """Clipper timing gate over any feed event type (quotes, deltas, trades)."""

    def __init__(self, config) -> None:
        super().__init__(config)
        self.level, self.order_spec, self.idx_of = None, None, None
        self.held, self.last_ts, self.decided = [], -1, False

    def on_start(self) -> None:
        iid = c.iid("CLPR")
        if self.level == "L1":
            self.subscribe_quotes(iid)
        else:
            self.subscribe_book_deltas(iid, BookType.L3_MBO if self.level == "L3" else BookType.L2_MBP)
        self.subscribe_trades(iid)

    def _event(self, data) -> None:
        ts = data.ts_init
        if ts > self.last_ts:
            for o in self.held:
                Strategy.submit_order(self, o)
            self.held = []
            self.last_ts = ts
        idx = self.idx_of(ts)
        if idx == self.order_spec["decide_at"] and not self.decided:
            self.decided = True
            sp = self.order_spec
            o = self.order_factory.limit(instrument_id=c.iid("CLPR"), order_side=B if sp["side"] == "BUY" else S,
                                         quantity=Quantity.from_int(sp["qty"]), price=Price.from_str(sp["price"]),
                                         time_in_force=TimeInForce.GTC)
            self.held.append(o)

    def on_quote(self, d) -> None:
        self._event(d)

    def on_book_deltas(self, d) -> None:
        self._event(d)

    def on_trade(self, d) -> None:
        self._event(d)


# ------------------------------------------------------------------ runners
def venue_kwargs(level: str, liq: bool, queue: bool) -> dict:
    return dict(oms_type=OmsType.NETTING, account_type=AccountType.CASH, base_currency=c.USD,
                default_leverage=Decimal(1), fee_model=MakerTakerFeeModel(maker_rate=Decimal(0), taker_rate=Decimal(0)),
                fill_model=FillModel(), latency_model=StaticLatencyModel(base_latency_nanos=0),
                book_type={"L1": BookType.L1_MBP, "L2": BookType.L2_MBP, "L3": BookType.L3_MBO}[level],
                liquidity_consumption=liq, queue_position=queue)


def result(cache, ev_ts: list[int]) -> list:
    fills = []
    for f in c.cache_fills(cache):
        idx = max((i for i, t in enumerate(ev_ts) if t <= f["ts"]), default=None)
        fills.append([idx, f["qty"]])
    return fills


def run_backtest(sc: dict, level: str, liq: bool, queue: bool) -> list:
    from nautilus_trader.backtest import BacktestEngine
    t0 = 1_767_225_600 * c.SEC
    eng = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId.from_str("CLIPPER-F4"),
                                                     logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    eng.add_venue(venue=c.VENUE, starting_balances=[Money(100000, c.USD)], **venue_kwargs(level, liq, queue))
    eng.add_instrument(c.make_instrument("CLPR"))
    data = derive(sc["tape"], level, c.iid("CLPR"), t0)
    eng.add_data([d for _, _, d in data])
    ev_ts = [t0 + int(e["t"] * c.SEC) for e in sc["tape"]]
    s = DepthGate(StrategyConfig())
    s.level, s.order_spec = level, sc["order"]
    s.idx_of = lambda ts: ev_ts.index(ts) if ts in ev_ts else None
    eng.add_strategy(s)
    eng.run()
    out = result(eng.cache, ev_ts)
    eng.dispose()
    return out


def run_sandbox(sc: dict, level: str, liq: bool, queue: bool) -> list:
    from nautilus_trader.adapters.sandbox import SandboxExecutionClientConfig, SandboxExecutionClientFactory
    from nautilus_trader.common import Environment
    from nautilus_trader.config import DataClientConfig, LiveRiskEngineConfig
    from nautilus_trader.live import LiveNode
    from nautilus_trader.live.clients import DataClientFactory, MarketDataClient
    from nautilus_trader.model import AccountId
    SCALE = 0.25
    st = {"handle": None, "ev_ts": []}

    class Replay(MarketDataClient):
        async def _connect(self):
            self._handle_instrument(c.make_instrument("CLPR"))
            self.create_task(self._go(), "replay")

        async def _go(self):
            await asyncio.sleep(1.5)
            base = self.clock.timestamp_ns()
            st["ev_ts"] = [base + int(e["t"] * SCALE * c.SEC) for e in sc["tape"]]
            for idx, ts, d in derive(sc["tape"], level, c.iid("CLPR"), base, SCALE):
                now = self.clock.timestamp_ns()
                if ts > now:
                    await asyncio.sleep((ts - now) / c.SEC)
                self._handle_data(d)
            await asyncio.sleep(1.5)
            st["handle"].stop()

        async def _disconnect(self):
            pass

        for _n in ("quotes", "trades", "book_deltas"):
            exec(f"async def _subscribe_{_n}(self, command): pass\nasync def _unsubscribe_{_n}(self, command): pass")

    class Factory(DataClientFactory):
        @staticmethod
        def create(*, name, config, cache, clock):
            return Replay(name=name, config=config, cache=cache, clock=clock, venue=c.VENUE)

    vk = venue_kwargs(level, liq, queue)
    sb = SandboxExecutionClientConfig(venue=c.VENUE, starting_balances=[Money(100000, c.USD)],
                                      account_id=AccountId.from_str("SIM-001"), base_currency=vk["base_currency"],
                                      oms_type=vk["oms_type"], account_type=vk["account_type"],
                                      default_leverage=vk["default_leverage"], book_type=vk["book_type"],
                                      fill_model=vk["fill_model"], fee_model=vk["fee_model"],
                                      latency_model=vk["latency_model"], liquidity_consumption=liq, queue_position=queue)
    node = (LiveNode.builder("CLIPPER-F4", TraderId.from_str("CLIPPER-F4"), Environment.SANDBOX)
            .with_reconciliation(reconciliation=False).with_risk_engine_config(LiveRiskEngineConfig(bypass=False))
            .with_logging(LoggerConfig(stdout_level=LogLevel.ERROR))
            .add_data_client("REPLAY", Factory(), DataClientConfig())
            .add_simulated_exec_client("SIM", SandboxExecutionClientFactory(), sb).build())
    s = DepthGate(StrategyConfig())
    s.level, s.order_spec = level, sc["order"]
    s.idx_of = lambda ts: st["ev_ts"].index(ts) if ts in st["ev_ts"] else None
    node.add_strategy(s)
    st["handle"] = node.handle()
    node.run()
    return result(node.cache, st["ev_ts"])


if __name__ == "__main__":
    scen, level, ctx, liq, queue = sys.argv[1:6]
    sc = SCENARIOS[scen]
    liq_b, queue_b = liq == "consumption", queue == "queue"
    try:
        fills = (run_backtest if ctx == "backtest" else run_sandbox)(sc, level, liq_b, queue_b)
        err = None
    except Exception as exc:  # noqa: BLE001 - recorded
        fills, err = None, f"{type(exc).__name__}: {exc}"
    truth = [list(x) for x in sc["truth"]]
    print("CLIPPER-0A-RESULT " + json.dumps({"scenario": scen, "level": level, "context": ctx, "liquidity_consumption": liq_b,
                                             "queue_position": queue_b, "fills": fills, "truth": truth,
                                             "matches_truth": fills == truth, "error": err}))
