"""Reproduce the four baseline variations reported in codex-review-2.md §4 (first buy of the
upstream rc9 `examples/backtest/synthetic_data_pnl_test.py` scenario). The scenario is
re-implemented here (same instrument parameters, bars and trade rule), not copied.

  1. no latency                          -> Codex: 00:01:00 @ 1.10010
  2. StaticLatencyModel(1 s)             -> Codex: 00:02:00 @ 1.10020
  3. 1 s latency + unrelated timer +2 s  -> Codex: 00:01:02 @ 1.10010
  4. 1 s latency, only 2 bars            -> Codex: 00:01:01 @ 1.10010
Each variation is also run through the Clipper timing gate for comparison. Usage:
  python codex_baselines.py <variation 1-4> <baseline|gate>
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from decimal import Decimal

from nautilus_trader.backtest import BacktestEngine
from nautilus_trader.common import LoggerConfig, LogLevel
from nautilus_trader.config import BacktestEngineConfig, StrategyConfig
from nautilus_trader.core.datetime import dt_to_unix_nanos
from nautilus_trader.execution import PerContractFeeModel, StaticLatencyModel
from nautilus_trader.model import (
    AccountType, AssetClass, Bar, BarType, Currency, FuturesContract, InstrumentId, Money, OmsType,
    OrderSide, Price, Quantity, Symbol, TimeInForce, TraderId, Venue,
)
from nautilus_trader.trading import Strategy

import clipper0a as c

USD = Currency.from_str("USD")
VENUE = Venue("SIM")
EXPECTED_CODEX = {1: ("00:01:00", "1.10010"), 2: ("00:02:00", "1.10020"),
                  3: ("00:01:02", "1.10010"), 4: ("00:01:01", "1.10010")}


def instrument() -> FuturesContract:
    sym = Symbol("6E")
    return FuturesContract(
        instrument_id=InstrumentId(sym, VENUE), raw_symbol=sym, asset_class=AssetClass.FX, currency=USD,
        price_precision=5, price_increment=Price.from_str("0.00005"), multiplier=Quantity.from_int(125_000),
        lot_size=Quantity.from_int(1), underlying="EUR/USD", activation_ns=0,
        expiration_ns=int(datetime(2024, 12, 17, 14, 16, tzinfo=UTC).timestamp() * 1e9),
        ts_event=0, ts_init=0, margin_init=Decimal("0.21818181812"), margin_maint=Decimal("0.18181818182"),
        exchange="SIM",
    )


class Scenario(Strategy):
    def __init__(self, config) -> None:
        super().__init__(config)
        self.n = -1
        self.timer = False
        self.fills = []
        self.bt = None
        self.inst_id = None

    def on_start(self) -> None:
        self.subscribe_bars(self.bt)

    def on_bar(self, b) -> None:
        self.n += 1
        flat = self.portfolio.is_completely_net_flat()
        if flat and self.n == 1:
            self.submit_order(self.order_factory.market(instrument_id=self.inst_id, order_side=OrderSide.BUY,
                                                        quantity=Quantity.from_str("1"), time_in_force=TimeInForce.GTC))
            if self.timer:
                self.clock.set_time_alert_ns("fixture_timer", b.ts_init + 2_000_000_000, lambda _e: None)
        if (not flat) and self.n == 7:
            self.submit_order(self.order_factory.market(instrument_id=self.inst_id, order_side=OrderSide.SELL,
                                                        quantity=Quantity.from_str("1"), time_in_force=TimeInForce.GTC))

    def on_order_filled(self, e) -> None:
        self.fills.append({"side": str(e.order_side), "ts": e.ts_event, "px": str(e.last_px)})


class GatedScenario(c.GatedStrategy):
    """Same trade rule, routed through the Clipper gate."""

    def __init__(self, config) -> None:
        super().__init__(config)
        self.n = -1
        self.timer = False
        self.bt = None
        self.inst_id = None
        self.subs = {"quotes": []}

    def on_start(self) -> None:
        self.subscribe_bars(self.bt)

    def on_bar(self, b) -> None:
        Scenario.on_bar(self, b)


def run(variation: int, mech: str) -> dict:
    engine = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId.from_str("TESTER-001"),
                                                        logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    kw = {}
    if variation >= 2:
        kw["latency_model"] = StaticLatencyModel(base_latency_nanos=1_000_000_000)
    engine.add_venue(venue=VENUE, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, base_currency=USD,
                     fee_model=PerContractFeeModel(Money.from_str("2.50 USD")),
                     starting_balances=[Money.from_str("1000000 USD")], **kw)
    inst = instrument()
    engine.add_instrument(inst)
    bt = BarType.from_str(f"{inst.id}-1-MINUTE-LAST-EXTERNAL")
    base = dt_to_unix_nanos(datetime(2024, 1, 1, tzinfo=UTC))
    nbars = 2 if variation == 4 else 12
    bars = [Bar(bar_type=bt, open=inst.make_price(1.10000 + i * 0.0001), high=inst.make_price(1.20000 + i * 0.0001),
                low=inst.make_price(1.10000 + i * 0.0001), close=inst.make_price(1.10000 + i * 0.0001),
                volume=Quantity.from_str("100"), ts_event=base + i * 60_000_000_000, ts_init=base + i * 60_000_000_000)
            for i in range(nbars)]
    engine.add_data(bars)
    s = (GatedScenario if mech == "gate" else Scenario)(StrategyConfig())
    s.bt, s.inst_id, s.timer = bt, inst.id, (variation == 3)
    if mech == "gate":
        s.index_of = lambda _d: None
    engine.add_strategy(s)
    engine.run()
    fills = c.cache_fills(engine.cache)  # authoritative (includes end-of-run drain fills)
    strategy_seen = {f["px"] + "@" + str(f["ts"]) for f in s.fills}
    for f in fills:
        f["seen_by_strategy"] = (f["px"] + "@" + str(f["ts"])) in strategy_seen
    first_buy = next((f for f in fills if f["side"] == "BUY"), None)
    res = {"variation": variation, "mechanism": mech, "fills": fills}
    if first_buy:
        t = datetime.fromtimestamp(first_buy["ts"] / 1e9, tz=UTC).strftime("%H:%M:%S")
        res["first_buy"] = {"time": t, "px": first_buy["px"], "seen_by_strategy": first_buy["seen_by_strategy"]}
    else:
        res["first_buy"] = None
    if mech == "gate":
        res["held_at_end"] = s.held_at_end()
    res["codex_reported"] = dict(zip(("time", "px"), EXPECTED_CODEX[variation]))
    engine.dispose()
    return res


if __name__ == "__main__":
    print("CLIPPER-0A-RESULT " + json.dumps(run(int(sys.argv[1]), sys.argv[2])))
