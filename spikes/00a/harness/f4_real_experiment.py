"""F4 stage B (D29; LOCAL ONLY): stock nautilus_trader 2.0.0rc9 on the July-15 MES MBO fixture.

  python f4_real_experiment.py truth  <local_dir>
  python f4_real_experiment.py engine <local_dir> <L1|L2|L3> <consumption|default> <queue|noqueue> <publishers.json>
  python f4_real_experiment.py score  <local_dir>          # writes local scores + a publishable aggregate

Probes (identical for every config; scheduled on exchange receive time, ts_recv):
  three 10-minute RTH windows; each minute one AGGRESSIVE probe at :00 (limit at the opposite best, qty =
  3x that level's displayed size, 5 s horizon) and one PASSIVE probe at :30 (1 lot at the near best,
  25 s horizon). Sides alternate. Every order is released by the Clipper gate on the first complete
  event batch after the decision batch (ts strictly later), and cancelled at its horizon.
TRUTH is computed from the raw Databento records (independent decoder output front_mbo.bin), by order
identity: an aggressive probe takes resting liquidity at or better than its limit, minus what it already
took from the SAME order ids, plus opposite-side aggressor trades it would have met first; a passive probe
fills when an opposite-side aggressor trade at its price exceeds the size still ahead of it in its queue.
Only aggregates leave the machine (f4_real_guard.publishable).
"""

from __future__ import annotations

import json
import pickle
import struct
import sys
import time
from collections import OrderedDict
from decimal import Decimal
from pathlib import Path

import f4_real_guard as g

REC = struct.Struct("<qqQ cc q I Q B")
PX = 1_000_000_000  # dbn fixed-point price scale
SEC = 1_000_000_000
F_LAST = 128
WINDOWS_UTC = [(13, 35), (16, 0), (19, 45)]  # 2026-07-15, EDT RTH; 10 minutes each
DAY0 = 1_784_073_600 * SEC  # 2026-07-15T00:00:00Z
AGG_H, PAS_H, BIG_H = 5 * SEC, 25 * SEC, 2 * SEC
MULT = {"aggr": 3, "big": 20}


def horizon(kind: str) -> int:
    return {"aggr": AGG_H, "big": BIG_H, "pass": PAS_H}[kind]
FRONT = "MESU26.GLBX"


def probe_schedule() -> list[dict]:
    out = []
    for w, (h, m) in enumerate(WINDOWS_UTC):
        start = DAY0 + (h * 3600 + m * 60) * SEC
        for k in range(10):
            out.append({"id": f"w{w}a{k}", "kind": "aggr", "t": start + k * 60 * SEC, "side": "BUY" if k % 2 == 0 else "SELL"})
            out.append({"id": f"w{w}b{k}", "kind": "big", "t": start + (k * 60 + 15) * SEC, "side": "SELL" if k % 2 == 0 else "BUY"})
            out.append({"id": f"w{w}p{k}", "kind": "pass", "t": start + (k * 60 + 30) * SEC, "side": "BUY" if k % 2 == 0 else "SELL"})
    return out


END_TS = DAY0 + (19 * 3600 + 56 * 60) * SEC  # stop replay after the last horizon


# ======================================================================= raw records
def raw_batches(local: Path):
    """Yield (ts_recv, [records], [trades]) per F_LAST batch from the independent decode."""
    recs, trades = [], []
    with open(local / "front_mbo.bin", "rb") as f:
        while True:
            b = f.read(REC.size)
            if not b:
                break
            r = REC.unpack(b)
            if r[0] > END_TS:
                break
            act = r[3]
            if act == b"T":
                trades.append(r)
            elif act in (b"A", b"C", b"M", b"R"):
                recs.append(r)
            if r[8] & F_LAST:
                yield r[0], recs, trades
                recs, trades = [], []


class RawBook:
    """Order-level book from raw records (Databento MBO semantics: A add, C cancel size, M modify, R clear)."""

    def __init__(self):
        self.orders: dict[int, list] = {}  # oid -> [side, price, size, seq]

    def apply(self, r):
        _, _, seq, act, side, price, size, oid, _ = r
        if act == b"R":
            self.orders.clear()
        elif act == b"A":
            self.orders[oid] = [side, price, size, seq]
        elif act == b"C":
            o = self.orders.get(oid)
            if o is not None:
                o[2] -= size
                if o[2] <= 0:
                    del self.orders[oid]
        elif act == b"M":
            o = self.orders.get(oid)
            if o is None:
                self.orders[oid] = [side, price, size, seq]
            else:
                lose_priority = price != o[1] or size > o[2]
                o[1], o[2] = price, size
                if lose_priority:
                    o[3] = seq

    def best(self, side: bytes):
        px = [o[1] for o in self.orders.values() if o[0] == side]
        if not px:
            return None
        return max(px) if side == b"B" else min(px)

    def level_size(self, side: bytes, price: int) -> int:
        return sum(o[2] for o in self.orders.values() if o[0] == side and o[1] == price)


def truth(local: Path) -> dict:
    probes = probe_schedule()
    pending = list(probes)
    active, results = [], {}
    book = RawBook()
    for ts, recs, trades in raw_batches(local):
        # 1) trades precede the book updates they cause (tape order)
        for a in active:
            if a["state"] != "live":
                continue
            for tr in trades:
                _, _, _, _, tside, tpx, tsz, _, _ = tr
                rem = a["qty"] - a["filled"]
                if rem <= 0:
                    break
                if a["kind"] in ("aggr", "big"):
                    # an opposite aggressor at or through our limit meets our resting order first
                    if (a["side"] == "BUY" and tside == b"A" and tpx <= a["limit"]) or \
                       (a["side"] == "SELL" and tside == b"B" and tpx >= a["limit"]):
                        q = min(rem, tsz)
                        a["filled"] += q
                        a["by_trade"] += q
                else:
                    opp = b"A" if a["side"] == "BUY" else b"B"
                    if tside != opp:
                        continue
                    through = tpx < a["limit"] if a["side"] == "BUY" else tpx > a["limit"]
                    at = tpx == a["limit"]
                    if through:
                        a["filled"] = a["qty"]
                    elif at:
                        ahead = sum(book.orders[o][2] for o in a["ahead"] if o in book.orders)
                        if tsz > ahead:
                            a["filled"] += min(rem, tsz - ahead)
        # 2) book updates
        for r in recs:
            book.apply(r)
        # 3) aggressive probes take newly available liquidity at/through limit (by order identity)
        for a in active:
            if a["state"] != "live" or a["kind"] not in ("aggr", "big"):
                continue
            opp = b"A" if a["side"] == "BUY" else b"B"
            ok = (lambda p: p <= a["limit"]) if a["side"] == "BUY" else (lambda p: p >= a["limit"])
            elig = sorted(((o[1], o[3], oid, o[2]) for oid, o in book.orders.items() if o[0] == opp and ok(o[1])),
                          key=lambda x: (x[0] if a["side"] == "BUY" else -x[0], x[1]))
            for _, _, oid, size in elig:
                rem = a["qty"] - a["filled"]
                if rem <= 0:
                    break
                avail = size - a["taken"].get(oid, 0)
                if avail > 0:
                    take = min(rem, avail)
                    a["filled"] += take
                    a["by_book"] += take
                    a["taken"][oid] = a["taken"].get(oid, 0) + take
            # (an id whose tape size later shrinks keeps its 'taken' count: conservative)
        # passive: book moving through our price fills the rest
        for a in active:
            if a["state"] == "live" and a["kind"] == "pass":
                oppb = book.best(b"A" if a["side"] == "BUY" else b"B")
                if oppb is not None and ((a["side"] == "BUY" and oppb <= a["limit"]) or (a["side"] == "SELL" and oppb >= a["limit"])):
                    a["filled"] = a["qty"]
        # 4) horizons
        for a in active:
            if a["state"] == "live" and ts > a["release_ts"] + horizon(a["kind"]):
                a["state"] = "done"
        # 5) releases: decided earlier, released on this (strictly later) batch, after it is applied
        for a in active:
            if a["state"] == "decided" and ts > a["decision_ts"]:
                a["state"], a["release_ts"] = "live", ts
                if a["kind"] == "pass":
                    near = b"B" if a["side"] == "BUY" else b"A"
                    a["ahead"] = [oid for oid, o in book.orders.items() if o[0] == near and o[1] == a["limit"]]
                else:
                    pass  # initial take happens at step 3 of the NEXT batch? no: take now, below
        for a in active:
            if a["state"] == "live" and a["kind"] in ("aggr", "big") and a.get("initial") is None:
                a["initial"] = True
                opp = b"A" if a["side"] == "BUY" else b"B"
                ok = (lambda p: p <= a["limit"]) if a["side"] == "BUY" else (lambda p: p >= a["limit"])
                elig = sorted(((o[1], o[3], oid, o[2]) for oid, o in book.orders.items() if o[0] == opp and ok(o[1])),
                              key=lambda x: (x[0] if a["side"] == "BUY" else -x[0], x[1]))
                for _, _, oid, size in elig:
                    rem = a["qty"] - a["filled"]
                    if rem <= 0:
                        break
                    take = min(rem, size - a["taken"].get(oid, 0))
                    if take > 0:
                        a["filled"] += take
                        a["by_book"] += take
                        a["taken"][oid] = a["taken"].get(oid, 0) + take
        # 6) decisions at the first batch at/after the probe time (book state after this batch)
        while pending and ts >= pending[0]["t"]:
            p = dict(pending.pop(0))
            bb, ba = book.best(b"B"), book.best(b"A")
            if bb is None or ba is None:
                p["state"] = "skipped"
                results[p["id"]] = p
                continue
            if p["kind"] in ("aggr", "big"):
                p["limit"] = ba if p["side"] == "BUY" else bb
                p["qty"] = MULT[p["kind"]] * book.level_size(b"A" if p["side"] == "BUY" else b"B", p["limit"])
            else:
                p["limit"] = bb if p["side"] == "BUY" else ba
                p["qty"] = 1
            p.update(state="decided", decision_ts=ts, filled=0, taken={}, by_trade=0, by_book=0)
            active.append(p)
            results[p["id"]] = p
    return {pid: {"kind": p["kind"], "qty": p.get("qty"), "filled": p.get("filled", 0), "state": p["state"],
                  "limit": p.get("limit"), "decision_ts": p.get("decision_ts"),
                  "by_trade": p.get("by_trade", 0), "by_book": p.get("by_book", 0)} for pid, p in results.items()}


# ======================================================================= engine
def load_deltas(publishers: str, ts_max: int):
    from nautilus_trader.adapters.databento import DatabentoDataLoader
    return [d for d in DatabentoDataLoader(publishers).load_order_book_deltas(g.input_path(), price_precision=2)
            if str(d.instrument_id) == FRONT and d.ts_init <= ts_max]


def load_engine_data(local: Path, level: str, publishers: str):
    return derive_stream(load_deltas(publishers, END_TS), level, local, None, END_TS)


def derive_stream(deltas, level: str, local: Path, ts_min, ts_max):
    """L3: Nautilus-decoded deltas batched by F_LAST; L2/L1 derived from the same deltas; plus trades
    from the independent decode at ts_recv-1 ns so they precede the updates they cause. Trades are taken
    from [ts_min, ts_max] (ts_min None = from the start)."""
    from nautilus_trader.model import (AggressorSide, BookAction, BookOrder, OrderBookDelta, OrderBookDeltas, OrderSide,
                                       Price, Quantity, QuoteTick, TradeId, TradeTick)
    iid = deltas[0].instrument_id
    out = []
    # trades
    with open(local / "front_mbo.bin", "rb") as f:
        n = 0
        while True:
            b = f.read(REC.size)
            if not b:
                break
            r = REC.unpack(b)
            if r[0] > ts_max:
                break
            if ts_min is not None and r[0] < ts_min:
                continue
            if r[3] == b"T" and r[6] > 0:
                n += 1
                agg = AggressorSide.BUY if r[4] == b"B" else (AggressorSide.SELL if r[4] == b"A" else AggressorSide.NO_AGGRESSOR)
                px = Price(r[5] / PX, 2)
                out.append(TradeTick(iid, px, Quantity.from_int(r[6]), agg, TradeId(f"{r[2]}-{n}"), r[1], r[0] - 1))
    # book data (integer price keys in cents; incremental best tracking)
    batch = []
    book = {}  # oid -> (side, price_int, size)
    levels = {"B": {}, "A": {}}
    best = {"B": None, "A": None}
    seq = 0

    def lvl_add(sd, px, q):
        nv = levels[sd].get(px, 0) + q
        if nv <= 0:
            levels[sd].pop(px, None)
            if best[sd] == px:
                best[sd] = (max(levels[sd]) if sd == "B" else min(levels[sd])) if levels[sd] else None
        else:
            levels[sd][px] = nv
            if best[sd] is None or (sd == "B" and px > best[sd]) or (sd == "A" and px < best[sd]):
                best[sd] = px

    def pstr(px):
        return f"{px / 100:.2f}"

    for d in deltas:
        batch.append(d)
        if not (d.flags & F_LAST):
            continue
        ts = d.ts_init
        if level == "L3":
            out.append(OrderBookDeltas(iid, batch))
            batch = []
            continue
        touched, cleared = set(), False
        before = (best["B"], best["A"])
        for x in batch:
            a = x.action
            if a == BookAction.CLEAR:
                book.clear()
                levels["B"].clear(); levels["A"].clear()
                best["B"] = best["A"] = None
                cleared = True
                continue
            oid = x.order.order_id
            prev = book.get(oid)
            if prev:
                lvl_add(prev[0], prev[1], -prev[2])
                touched.add((prev[0], prev[1]))
            if a == BookAction.DELETE:
                book.pop(oid, None)
            else:
                sd = "B" if x.order.side == OrderSide.BUY else "A"
                px = int(round(x.order.price.as_double() * 100))
                sz = int(x.order.size)
                book[oid] = (sd, px, sz)
                lvl_add(sd, px, sz)
                touched.add((sd, px))
        if level == "L2":
            ds = []
            if cleared:
                ds.append(OrderBookDelta.clear(iid, seq, ts, ts))
                touched |= {(sd, px) for sd in ("B", "A") for px in levels[sd]}
            items = sorted(touched)
            for k, (sd, px) in enumerate(items):
                seq += 1
                q = levels[sd].get(px, 0)
                act = BookAction.UPDATE if q > 0 else BookAction.DELETE
                ds.append(OrderBookDelta(iid, act, BookOrder(OrderSide.BUY if sd == "B" else OrderSide.SELL,
                                                             Price.from_str(pstr(px)), Quantity.from_int(max(q, 0)), 0),
                                         F_LAST if k == len(items) - 1 else 0, seq, ts, ts))
            if ds:
                out.append(OrderBookDeltas(iid, ds))
        else:  # L1: quote when a top level is touched (mbp-1 semantics), both sides present
            bb, ba = best["B"], best["A"]
            if bb is not None and ba is not None:
                top = cleared or any((sd == "B" and px in (bb, before[0])) or (sd == "A" and px in (ba, before[1]))
                                     for sd, px in touched)
                if top:
                    out.append(QuoteTick(iid, Price.from_str(pstr(bb)), Price.from_str(pstr(ba)),
                                         Quantity.from_int(levels["B"][bb]), Quantity.from_int(levels["A"][ba]), ts, ts))
        batch = []
    out.sort(key=lambda x: x.ts_init)  # stable: trades (ts_recv-1) precede same-receive book updates
    return out


def _best(levels: dict, sd: str):
    if not levels:
        return None
    return max(levels, key=Decimal) if sd == "B" else min(levels, key=Decimal)


def instrument(expiration_ns: int = 1_789_747_200 * SEC):
    from nautilus_trader.model import AssetClass, Currency, FuturesContract, InstrumentId, Price, Quantity, Symbol
    # Public CME contract specification for MES (Micro E-mini S&P 500): tick 0.25 index points, multiplier 5.
    # No definition records are in the approved input (D29), so these are constructed, not decoded.
    iid = InstrumentId.from_str(FRONT)
    return FuturesContract(instrument_id=iid, raw_symbol=Symbol("MESU6"), asset_class=AssetClass.INDEX,
                           currency=Currency.from_str("USD"), price_precision=2, price_increment=Price.from_str("0.25"),
                           multiplier=Quantity.from_int(5), lot_size=Quantity.from_int(1), underlying="ES",
                           activation_ns=0, expiration_ns=expiration_ns, ts_event=0, ts_init=0,
                           margin_init=Decimal("0.01"), margin_maint=Decimal("0.01"), exchange="XCME")


def make_gate(schedule, level, inst, offset_fn=None):
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.model import BookType, OrderSide, Quantity, TimeInForce
    from nautilus_trader.trading import Strategy

    class Gate(Strategy):
        def __init__(self, config):
            super().__init__(config)
            self.pending = list(schedule)
            self.decided, self.live, self.orders = [], [], {}
            self.last_ts = -1

        def on_start(self):
            if level == "L1":
                self.subscribe_quotes(inst.id)
            else:
                self.subscribe_book_deltas(inst.id, BookType.L3_MBO if level == "L3" else BookType.L2_MBP, managed=True)
            self.subscribe_trades(inst.id)

        def _top(self):
            if level == "L1":
                qt = self.cache.quote(inst.id)
                if qt is None:
                    return None
                return qt.bid_price, qt.ask_price, int(qt.bid_size), int(qt.ask_size)
            b = self.cache.order_book(inst.id)
            if b is None or b.best_bid_price() is None or b.best_ask_price() is None:
                return None
            # F10: on an L3 book best_*_size() returns the FIRST order's size, not the level total;
            # size from the aggregated best level instead.
            bl, al = b.bids()[0], b.asks()[0]
            return b.best_bid_price(), b.best_ask_price(), int(bl.size()), int(al.size())

        def _event(self, ts, is_book):
            off = (offset_fn() if offset_fn else 0) or 0
            if ts > self.last_ts:
                for p in self.live:
                    if p["state"] == "live" and ts > p["release_ts"] + horizon(p["kind"]):
                        o = self.cache.order(p["coid"])
                        is_open = (o.is_open() if callable(o.is_open) else o.is_open) if o is not None else False
                        if is_open:
                            try:
                                self.cancel_order(p["coid"])
                            except TypeError:
                                self.cancel_order(o)
                        p["state"] = "done"
                for p in self.decided:
                    if ts > p["decision_ts"]:
                        o = p.pop("order")
                        Strategy.submit_order(self, o)
                        p.update(state="live", release_ts=ts, coid=o.client_order_id)
                        self.live.append(p)
                self.decided = [p for p in self.decided if p["state"] == "decided"]
                self.last_ts = ts
            if not is_book:
                return
            while self.pending and ts >= self.pending[0]["t"] + off:
                p = dict(self.pending.pop(0))
                top = self._top()
                if top is None:
                    continue
                bb, ba, bsz, asz = top
                side = OrderSide.BUY if p["side"] == "BUY" else OrderSide.SELL
                if p["kind"] in ("aggr", "big"):
                    m = MULT[p["kind"]]
                    limit, qty = (ba, m * asz) if p["side"] == "BUY" else (bb, m * bsz)
                else:
                    limit, qty = (bb if p["side"] == "BUY" else ba), 1
                p["order"] = self.order_factory.limit(instrument_id=inst.id, order_side=side, quantity=Quantity.from_int(qty),
                                                      price=limit, time_in_force=TimeInForce.GTC)
                p.update(state="decided", decision_ts=ts - off, qty=qty, limit=str(limit))
                self.decided.append(p)
                self.orders[p["id"]] = p

        def on_quote(self, q):
            self._event(q.ts_init, True)

        def on_book_deltas(self, d):
            self._event(d.ts_init, True)

        def on_trade(self, tr):
            self._event(tr.ts_init, False)

    return Gate(StrategyConfig())


def collect_probes(gate, cache, offset=0) -> dict:
    fills = {}
    for o in cache.orders():
        evs = [e for e in o.events() if type(e).__name__ == "OrderFilled"]
        fills[str(o.client_order_id)] = (sum(int(e.last_qty) for e in evs), [(e.ts_event - offset, int(e.last_qty)) for e in evs])
    out = {}
    for pid, p in gate.orders.items():
        q, detail = fills.get(str(p.get("coid")), (0, []))
        out[pid] = {"kind": p["kind"], "qty": p["qty"], "filled": q, "fill_detail_LOCAL": detail, "limit": p["limit"],
                    "decision_ts": p["decision_ts"], "released": "coid" in p}
    return out


def venue_kwargs(level, liq, queue):
    from nautilus_trader.execution import FillModel, MakerTakerFeeModel, StaticLatencyModel
    from nautilus_trader.model import BookType
    return dict(fill_model=FillModel(), fee_model=MakerTakerFeeModel(maker_rate=Decimal(0), taker_rate=Decimal(0)),
                latency_model=StaticLatencyModel(base_latency_nanos=0),
                book_type={"L1": BookType.L1_MBP, "L2": BookType.L2_MBP, "L3": BookType.L3_MBO}[level],
                liquidity_consumption=liq, queue_position=queue, trade_execution=True, bar_execution=False)


def engine_on(data, schedule, level, liq, queue, offset=0) -> dict:
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LoggerConfig, LogLevel
    from nautilus_trader.config import BacktestEngineConfig
    from nautilus_trader.model import AccountType, Currency, Money, OmsType, TraderId, Venue
    inst = instrument()
    eng = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId.from_str("CLIPPER-F4R"),
                                                     logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    eng.add_venue(venue=Venue("GLBX"), oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
                  starting_balances=[Money(1e9, Currency.from_str("USD"))], base_currency=Currency.from_str("USD"),
                  default_leverage=Decimal(1), **venue_kwargs(level, liq, queue))
    eng.add_instrument(inst)
    eng.add_data(data)
    gate = make_gate(schedule, level, inst)
    eng.add_strategy(gate)
    t = time.time()
    eng.run()
    t_run = time.time() - t
    probes = collect_probes(gate, eng.cache)
    eng.dispose()
    return {"probes": probes, "run_s": round(t_run, 1)}


def engine(local: Path, level: str, liq: bool, queue: bool, publishers: str) -> dict:
    t = time.time()
    data = load_engine_data(local, level, publishers)
    t_load = time.time() - t
    res = engine_on(data, probe_schedule(), level, liq, queue)
    return {"probes": res["probes"], "load_s": round(t_load, 1), "run_s": res["run_s"], "events": len(data),
            "memory": __import__("clipper0a").cgroup_memory_peak()}


def restamp(obj, ts: int):
    from nautilus_trader.model import BookAction, OrderBookDelta, OrderBookDeltas, QuoteTick, TradeTick
    if isinstance(obj, OrderBookDeltas):
        ds = []
        for d in obj.deltas:
            if d.action == BookAction.CLEAR:
                ds.append(OrderBookDelta.clear(d.instrument_id, d.sequence, ts, ts))
            else:
                ds.append(OrderBookDelta(d.instrument_id, d.action, d.order, d.flags, d.sequence, ts, ts))
        return OrderBookDeltas(obj.instrument_id, ds)
    if isinstance(obj, QuoteTick):
        return QuoteTick(obj.instrument_id, obj.bid_price, obj.ask_price, obj.bid_size, obj.ask_size, ts, ts)
    if isinstance(obj, TradeTick):
        return TradeTick(obj.instrument_id, obj.price, obj.size, obj.aggressor_side, obj.trade_id, ts, ts)
    raise TypeError(type(obj).__name__)


# ======================================================================= scoring
def score(local: Path) -> dict:
    tru = json.loads((local / "truth.json").read_text())
    rows, publish = [], {}
    for f in sorted(local.glob("engine_*_*_*.json")):
        cfg = f.stem.replace("engine_", "")
        eng = json.loads(f.read_text())["probes"]
        agg = {k: {"n": 0, "exact": 0, "over": 0, "under": 0, "eng": 0, "tru": 0, "decision_mismatch": 0}
               for k in ("aggr", "big", "pass")}
        for pid, t in tru.items():
            if t["state"] == "skipped" or pid not in eng:
                continue
            e = eng[pid]
            a = agg[t["kind"]]
            a["n"] += 1
            if e["decision_ts"] != t["decision_ts"] or e["qty"] != t["qty"] or Decimal(e["limit"]) != Decimal(t["limit"]) / PX:
                a["decision_mismatch"] += 1
            a["eng"] += e["filled"]
            a["tru"] += t["filled"]
            if e["filled"] == t["filled"]:
                a["exact"] += 1
            elif e["filled"] > t["filled"]:
                a["over"] += 1
            else:
                a["under"] += 1
        for k in agg:
            agg[k]["ratio_engine_over_truth"] = round(agg[k]["eng"] / agg[k]["tru"], 4) if agg[k]["tru"] else None
        rows.append((cfg, agg))
        publish[cfg] = {k: {kk: v[kk] for kk in ("n", "exact", "over", "under", "decision_mismatch", "ratio_engine_over_truth")}
                        for k, v in agg.items()}
    (local / "scores_LOCAL.json").write_text(json.dumps(dict(rows), indent=1))
    return publish


if __name__ == "__main__":
    mode, local = sys.argv[1], g.local_out(sys.argv[2])
    g.input_path()  # guard check on every invocation
    if mode == "truth":
        t = time.time()
        res = truth(local)
        (local / "truth.json").write_text(json.dumps(res))
        print(json.dumps({"truth_probes": len(res), "skipped": sum(1 for r in res.values() if r["state"] == "skipped"),
                          "seconds": round(time.time() - t, 1)}))
    elif mode == "engine":
        level, liq, queue, pubs = sys.argv[3], sys.argv[4] == "consumption", sys.argv[5] == "queue", sys.argv[6]
        res = engine(local, level, liq, queue, pubs)
        name = f"engine_{level}_{'liq' if liq else 'noliq'}_{'q' if queue else 'noq'}.json"
        (local / name).write_text(json.dumps(res))
        print(json.dumps({"config": name, "probes": len(res["probes"]), "load_s": res["load_s"], "run_s": res["run_s"],
                          "events": res["events"], "peak_MiB": round(res["memory"].get("memory.peak", 0) / 2**20, 1)}))
    elif mode == "score":
        pub = g.publishable({"counts_by_config": score(local)})
        (local / "PUBLISHABLE_aggregate.json").write_text(json.dumps(pub, indent=1))
        print(json.dumps(pub))
