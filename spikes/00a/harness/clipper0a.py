"""Clipper Phase 0 / proof 0A harness library (disposable spike code, not production).

Contents:
  * synthetic fixture model with provenance (D25)
  * Clipper timing gate (D22 mechanism b) as a Strategy base class
  * scripted test strategy driven by fixture-event triggers
  * Clipper per-share fee specification with order-level min/cap and
    effective-dated Section 31 fixture rates (ADR-013)
  * Clipper pre-trade lot/tick validation
  * independent ledger: FIFO lots, cash, fees; fill attribution
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from nautilus_trader.execution import FeeModel
from nautilus_trader.model import (
    Bar, BarType, Currency, Equity, InstrumentId, Money, OrderSide, Price, Quantity, QuoteTick,
    Symbol, TimeInForce, Venue,
)
from nautilus_trader.trading import Strategy

USD = Currency.from_str("USD")
VENUE = Venue("SIM")
SEC = 1_000_000_000
GENERATOR = {"name": "clipper-spike-00a-fixtures", "version": "1"}

# --------------------------------------------------------------------------------------
# Instruments
# --------------------------------------------------------------------------------------

INSTRUMENTS = {
    # symbol: (price_precision, increment, lot_size)
    "CLPR": (2, "0.01", 1),
    "OTHR": (2, "0.01", 1),
    "PNNY": (2, "0.01", 1),
    "LOTS": (2, "0.01", 100),
}


def iid(sym: str) -> InstrumentId:
    return InstrumentId(Symbol(sym), VENUE)


def make_instrument(sym: str) -> Equity:
    prec, inc, lot = INSTRUMENTS[sym]
    return Equity(
        instrument_id=iid(sym), raw_symbol=Symbol(sym), currency=USD, price_precision=prec,
        price_increment=Price.from_str(inc), ts_event=0, ts_init=0, lot_size=Quantity.from_int(lot),
    )


# --------------------------------------------------------------------------------------
# Fixtures (D25): synthetic quotes and bars with provenance
# --------------------------------------------------------------------------------------

def q(sym: str, t: float, bid: str, ask: str, bsz: int = 100, asz: int = 100) -> dict:
    return {"kind": "quote", "sym": sym, "t": t, "bid": bid, "ask": ask, "bsz": bsz, "asz": asz}


def bar(sym: str, t_close: float, o: str, h: str, l: str, c: str, v: int = 1000, step: str = "1-MINUTE") -> dict:
    return {"kind": "bar", "sym": sym, "t": t_close, "o": o, "h": h, "l": l, "c": c, "v": v, "step": step}


def fixture_provenance(name: str, events: list[dict], seed: int = 0) -> dict:
    canon = json.dumps(events, sort_keys=True, separators=(",", ":")).encode()
    return {
        "generator": GENERATOR, "fixture": name, "seed": seed,
        "corporate_actions": "declared none (synthetic instruments)",
        "rows": len(events), "sha256": hashlib.sha256(canon).hexdigest(),
    }


def bar_type(sym: str, step: str = "1-MINUTE") -> BarType:
    return BarType.from_str(f"{sym}.SIM-{step}-LAST-EXTERNAL")


def to_nautilus(ev: dict, ts: int):
    if ev["kind"] == "quote":
        return QuoteTick(iid(ev["sym"]), Price.from_str(ev["bid"]), Price.from_str(ev["ask"]),
                         Quantity.from_int(ev["bsz"]), Quantity.from_int(ev["asz"]), ts, ts)
    bt = bar_type(ev["sym"], ev["step"])
    return Bar(bar_type=bt, open=Price.from_str(ev["o"]), high=Price.from_str(ev["h"]),
               low=Price.from_str(ev["l"]), close=Price.from_str(ev["c"]),
               volume=Quantity.from_int(ev["v"]), ts_event=ts, ts_init=ts)


# --------------------------------------------------------------------------------------
# Fee specification (ADR-013): per-share commission, order-level min and cap across fills
# --------------------------------------------------------------------------------------

CENT = Decimal("0.01")


@dataclass(frozen=True)
class FeeSpec:
    """Versioned broker fee specification. Commission values follow a published
    fixed per-share schedule shape (USD 0.005/share, min USD 1.00/order, max 1% of
    trade value). SECTION_31 rates below are FIXTURE values for testing effective
    dating, not current SEC rates."""
    spec_id: str = "clipper-fee-spec-fixture"
    version: int = 1
    per_share: Decimal = Decimal("0.005")
    min_per_order: Decimal = Decimal("1.00")
    max_pct_of_value: Decimal = Decimal("0.01")
    section31: tuple = ((0, Decimal("0.0000278")), (1_780_272_000 * SEC, Decimal("0.0000206")))  # 2026-06-01


def _r(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


class ClipperFeeModel(FeeModel):
    """Instantiated per process from a FeeSpec (one instance per engine)."""

    def __new__(cls, spec: FeeSpec | None = None, *a, **k):
        return super().__new__(cls)

    def __init__(self, spec: FeeSpec | None = None) -> None:
        self.spec = spec or FeeSpec()
        self._cum: dict[str, tuple[Decimal, Decimal, Decimal]] = {}  # coid -> (qty, value, charged)
        self.evlog: list[dict] = []

    def _sec31_rate(self, ts: int) -> Decimal:
        rate = Decimal(0)
        for start, r in self.spec.section31:
            if ts >= start:
                rate = r
        return rate

    def get_commission(self, order, fill_quantity, fill_px, instrument):
        s = self.spec
        coid = str(order.client_order_id)
        qty, val, charged = self._cum.get(coid, (Decimal(0), Decimal(0), Decimal(0)))
        fq, fp = Decimal(str(fill_quantity)), Decimal(str(fill_px))
        qty, val = qty + fq, val + fq * fp
        target = min(max(s.per_share * qty, s.min_per_order), s.max_pct_of_value * val)
        target = max(_r(target), Decimal(0))
        commission = max(target - charged, Decimal(0))
        sec31 = Decimal(0)
        if order.side == OrderSide.SELL:
            sec31 = _r(fq * fp * self._sec31_rate(order.ts_last if hasattr(order, "ts_last") else 0))
        self._cum[coid] = (qty, val, charged + commission)
        total = commission + sec31
        self.evlog.append({"coid": coid, "fill_qty": str(fq), "fill_px": str(fp), "commission": str(commission),
                         "sec31": str(sec31), "total": str(total)})
        return Money(float(total), USD)


def expected_commissions(spec: FeeSpec, fills: list[tuple[Decimal, Decimal]], side: str, ts: int = 0) -> list[Decimal]:
    """Independent re-statement of the fee rule for the ledger (does not call ClipperFeeModel)."""
    out, qty, val, charged = [], Decimal(0), Decimal(0), Decimal(0)
    rate = Decimal(0)
    for start, r in spec.section31:
        if ts >= start:
            rate = r
    for fq, fp in fills:
        qty += fq
        val += fq * fp
        tgt = _r(min(max(spec.per_share * qty, spec.min_per_order), spec.max_pct_of_value * val))
        c = max(tgt - charged, Decimal(0))
        charged += c
        sec = _r(fq * fp * rate) if side == "SELL" else Decimal(0)
        out.append(c + sec)
    return out


# --------------------------------------------------------------------------------------
# Clipper pre-trade lot/tick validation (part of the Clipper gate, ADR-008/013)
# --------------------------------------------------------------------------------------

def pretrade_refusal(instrument_sym: str, qty: Decimal, price: Decimal | None) -> str | None:
    prec, inc, lot = INSTRUMENTS[instrument_sym]
    if qty <= 0 or qty % Decimal(lot) != 0:
        return f"lot: quantity {qty} not a positive multiple of lot size {lot}"
    if price is not None and price % Decimal(inc) != 0:
        return f"tick: price {price} not a multiple of increment {inc}"
    return None


# --------------------------------------------------------------------------------------
# Scripted strategy + Clipper timing gate
# --------------------------------------------------------------------------------------

class ScriptedStrategy(Strategy):
    """Submits orders when given fixture events arrive (or from timers). `index_of` maps a
    received data object to its fixture index (set by the runner)."""

    def __init__(self, config) -> None:
        super().__init__(config)
        self.script: list[dict] = []
        self.subs: dict = {}
        self.index_of = lambda _d: None
        self.evlog: list[dict] = []
        self.fills: list[dict] = []
        self.refusals: list[dict] = []

    def configure(self, script: list[dict], subs: dict, index_of) -> "ScriptedStrategy":
        self.script, self.subs, self.index_of = script, subs, index_of
        return self

    # -- lifecycle -------------------------------------------------------------------
    def on_start(self) -> None:
        for sym in self.subs.get("quotes", []):
            self.subscribe_quotes(iid(sym))
        for sym, step in self.subs.get("bars", []):
            self.subscribe_bars(bar_type(sym, step))

    # -- data ------------------------------------------------------------------------
    def _on_any(self, data, kind: str) -> None:
        idx = self.index_of(data)
        self.evlog.append({"seq": len(self.evlog), "kind": kind, "idx": idx, "ts": data.ts_init,
                         "clock": self.clock.timestamp_ns()})
        for act in self.script:
            if act.get("on") == "event" and act["idx"] == idx:
                self._do(act["action"])
            elif act.get("on") == "timer" and act["after_idx"] == idx:
                at = data.ts_init + int(act["delay_s"] * act.get("scale", 1.0) * SEC)
                name = f"t{idx}"
                a = act["action"]
                self.clock.set_time_alert_ns(name, at, lambda _e, a=a: self._timer(a))

    def _timer(self, action: dict) -> None:
        self.evlog.append({"seq": len(self.evlog), "kind": "timer", "idx": None, "ts": None,
                         "clock": self.clock.timestamp_ns()})
        self._do(action)

    def on_quote(self, quote) -> None:
        self._on_any(quote, "quote")

    def on_bar(self, b) -> None:
        self._on_any(b, "bar")

    # -- orders ----------------------------------------------------------------------
    def _do(self, a: dict | None) -> None:
        if a is None:
            return
        side = OrderSide.BUY if a["side"] == "BUY" else OrderSide.SELL
        qty = Decimal(str(a["qty"]))
        price = Decimal(a["price"]) if a.get("price") else None
        reason = pretrade_refusal(a["sym"], qty, price) if a.get("pretrade", True) else None
        if reason:
            self.refusals.append({"action": a, "reason": reason, "clock": self.clock.timestamp_ns()})
            return
        if price is None:
            order = self.order_factory.market(instrument_id=iid(a["sym"]), order_side=side,
                                              quantity=Quantity.from_str(str(qty)), time_in_force=TimeInForce.GTC)
        else:
            order = self.order_factory.limit(instrument_id=iid(a["sym"]), order_side=side,
                                             quantity=Quantity.from_str(str(qty)), price=Price.from_str(a["price"]),
                                             time_in_force=TimeInForce.GTC)
        self.evlog.append({"seq": len(self.evlog), "kind": "submit", "coid": str(order.client_order_id),
                         "clock": self.clock.timestamp_ns()})
        self.submit_order(order)

    def on_order_filled(self, e) -> None:
        self.fills.append({"seq": len(self.evlog), "coid": str(e.client_order_id), "sym": str(e.instrument_id.symbol),
                           "side": "BUY" if e.order_side == OrderSide.BUY else "SELL",
                           "ts": e.ts_event, "px": str(e.last_px), "qty": str(e.last_qty),
                           "commission": str(e.commission), "trade_id": str(e.trade_id)})
        self.evlog.append({"seq": len(self.evlog), "kind": "fill", "coid": str(e.client_order_id),
                         "clock": self.clock.timestamp_ns()})

    def on_order_denied(self, e) -> None:
        self.refusals.append({"engine_denied": str(e.client_order_id), "reason": str(e.reason)})

    def on_order_rejected(self, e) -> None:
        self.refusals.append({"engine_rejected": str(e.client_order_id), "reason": str(e.reason)})


class GatedStrategy(ScriptedStrategy):
    """Clipper timing gate (D22 mechanism b). Orders submitted by strategy code are held and
    released only when a new feed event for the order's instrument arrives with
    ts_init > the decision's data watermark. Data callbacks are wrapped at class creation so
    the gate runs before user handlers; the gate subscribes to quotes for traded instruments
    (finest execution data available)."""

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        _wrap_data_callbacks(cls)

    def __init__(self, config) -> None:
        super().__init__(config)
        self._held: list[tuple[Any, int, str]] = []  # (order, watermark, sym)
        self._last_seen: dict[str, int] = {}
        self.gate_log: list[dict] = []
        self._gate_subscribed: set[str] = set()

    def _gate_on_data(self, data) -> None:
        inst = data.bar_type.instrument_id if isinstance(data, Bar) else data.instrument_id
        sym, ts = str(inst.symbol), data.ts_init
        if self._last_seen.get(sym, -1) > ts:
            return
        keep = []
        for order, wm, osym in self._held:
            if osym == sym and ts > wm:
                self.gate_log.append({"release": str(order.client_order_id), "on_idx": self.index_of(data),
                                      "on_ts": ts, "watermark": wm})
                Strategy.submit_order(self, order)
            else:
                keep.append((order, wm, osym))
        self._held = keep
        self._last_seen[sym] = max(self._last_seen.get(sym, -1), ts)

    def submit_order(self, order, *args, **kwargs):
        sym = str(order.instrument_id.symbol)
        wm = self._last_seen.get(sym, self.clock.timestamp_ns())
        self._held.append((order, wm, sym))
        self.gate_log.append({"hold": str(order.client_order_id), "watermark": wm})
        if sym not in self._gate_subscribed and sym not in self.subs.get("quotes", []):
            self.subscribe_quotes(iid(sym))
            self._gate_subscribed.add(sym)

    def held_at_end(self) -> list[str]:
        return [str(o.client_order_id) for o, _, _ in self._held]


def _wrap_data_callbacks(cls) -> None:
    for name in ("on_quote", "on_bar", "on_trade"):
        orig = getattr(cls, name, None)
        if orig is None or getattr(orig, "_clipper_gate", False):
            continue

        def make(orig):
            def wrapper(self, data):
                self._gate_on_data(data)
                if self._data_is_subscribed(data):
                    return orig(self, data)
                return None
            wrapper._clipper_gate = True
            return wrapper
        setattr(cls, name, make(orig))


def _data_is_subscribed(self, data) -> bool:
    if isinstance(data, Bar):
        return True
    return str(data.instrument_id.symbol) in self.subs.get("quotes", [])


GatedStrategy._data_is_subscribed = _data_is_subscribed
_wrap_data_callbacks(GatedStrategy)


# --------------------------------------------------------------------------------------
# Independent ledger: FIFO, cash; attribution
# --------------------------------------------------------------------------------------

def cache_fills(cache) -> list[dict]:
    """Authoritative fills: OrderFilled events from the engine cache. (Strategy callbacks miss
    fills produced by the end-of-run drain after strategies have stopped.)"""
    out = []
    for o in cache.orders():
        for e in (o.events() if callable(o.events) else o.events):
            if type(e).__name__ != "OrderFilled":
                continue
            out.append({"coid": str(e.client_order_id), "sym": str(e.instrument_id.symbol),
                        "side": "BUY" if e.order_side == OrderSide.BUY else "SELL", "ts": e.ts_event,
                        "px": str(e.last_px), "qty": str(e.last_qty), "commission": str(e.commission),
                        "trade_id": str(e.trade_id)})
    return sorted(out, key=lambda f: (f["ts"], f["trade_id"]))


def fifo_ledger(fills: list[dict], start_cash: Decimal) -> dict:
    lots: dict[str, list[list[Decimal]]] = {}
    realized = Decimal(0)
    cash = start_cash
    fees = Decimal(0)
    for f in fills:
        qty, px = Decimal(f["qty"]), Decimal(f["px"])
        fee = Decimal(f["commission"].split()[0])
        fees += fee
        book = lots.setdefault(f["sym"], [])
        if f["side"] == "BUY":
            book.append([qty, px])
            cash -= qty * px + fee
        else:
            cash += qty * px - fee
            rem = qty
            while rem > 0:
                lot = book[0]
                take = min(rem, lot[0])
                realized += take * (px - lot[1])
                lot[0] -= take
                rem -= take
                if lot[0] == 0:
                    book.pop(0)
    return {"fifo_realized_gross": str(realized), "fees": str(fees), "cash": str(cash),
            "open_lots": {k: [[str(a), str(b)] for a, b in v] for k, v in lots.items()},
            "position_qty": {k: str(sum(a for a, _ in v)) for k, v in lots.items()}}


def attribute(fill: dict, emitted: list[dict], tolerance_ns: int) -> dict:
    """Attribute a fill to the feed event that produced it: latest emitted event for the same
    instrument at or before the fill time whose relevant price equals the fill price."""
    px = Decimal(fill["px"])
    best = None
    for e in emitted:
        if e["sym"] != fill["sym"] or e["ts"] > fill["ts"]:
            continue
        if e["kind"] == "quote":
            leg = "ask" if fill["side"] == "BUY" else "bid"
            if Decimal(e[leg]) == px:
                best = (e, leg)
        else:
            for leg in ("o", "h", "l", "c"):
                if Decimal(e[leg]) == px:
                    best = (e, {"o": "open", "h": "high", "l": "low", "c": "close"}[leg])
    if best is None:
        return {"idx": None, "leg": None, "origin": "unattributed"}
    e, leg = best
    lag = fill["ts"] - e["ts"]
    origin = "feed_event" if lag <= tolerance_ns else "non_feed_release"
    return {"idx": e["idx"], "leg": leg, "lag_ns": lag, "origin": origin}


def cgroup_memory_peak() -> dict:
    try:
        rel = open("/proc/self/cgroup").read().strip().split("::")[-1]
        base = f"/sys/fs/cgroup{rel}"
        out = {"cgroup": rel}
        for k in ("memory.peak", "memory.current"):
            try:
                out[k] = int(open(f"{base}/{k}").read().strip())
            except OSError as exc:
                out[k] = f"unavailable: {exc.__class__.__name__}"
        return out
    except OSError as exc:
        return {"error": str(exc)}


@dataclass
class CaseResult:
    case: str
    context: str
    mechanism: str
    expected: Any
    actual: Any
    verdict: str
    notes: list = field(default_factory=list)
