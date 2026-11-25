"""API probe for NautilusTrader 2.0.0rc9 (Phase 0 / 0A). Not a test; prints facts the harness relies on."""

from __future__ import annotations

from decimal import Decimal

from nautilus_trader.backtest import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, StrategyConfig
from nautilus_trader.execution import FeeModel
from nautilus_trader.model import (
    AccountType, Currency, Equity, InstrumentId, Money, OmsType, OrderSide, Price,
    Quantity, QuoteTick, Symbol, TimeInForce, TraderId, Venue,
)
from nautilus_trader.trading import Strategy

USD = Currency.from_str("USD")
VENUE = Venue("SIM")
IID = InstrumentId(Symbol("CLPR"), VENUE)
T0 = 1_700_000_000_000_000_000
SEC = 1_000_000_000


class CountingFee(FeeModel):
    calls = 0

    def get_commission(self, order, fill_quantity, fill_px, instrument):  # noqa: D401
        CountingFee.calls += 1
        return Money.from_str("1.00 USD")


class ProbeStrategy(Strategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self.seen = []
        self.fills = []
        self.wrapped_calls = 0
        self.override_calls = 0

    def on_start(self) -> None:
        self.subscribe_quotes(IID)

    def on_quote(self, quote) -> None:
        self.seen.append((quote.ts_init, str(quote.bid_price), str(quote.ask_price)))
        if len(self.seen) == 2:
            o = self.order_factory.market(instrument_id=IID, order_side=OrderSide.BUY,
                                          quantity=Quantity.from_int(1), time_in_force=TimeInForce.GTC)
            self.submit_order(o)

    def on_order_filled(self, event) -> None:
        self.fills.append((event.ts_event, str(event.last_px), str(event.last_qty), str(event.commission),
                           str(event.trade_id)))


class OverridingStrategy(ProbeStrategy):
    def submit_order(self, order, *args, **kwargs):  # MRO override test
        self.override_calls += 1
        return super().submit_order(order, *args, **kwargs)


def wrap(cls):
    orig = cls.on_quote

    def on_quote(self, quote):
        self.wrapped_calls += 1
        return orig(self, quote)

    cls.on_quote = on_quote
    return cls


def run(strategy_cls, latency=None):
    engine = BacktestEngine(config=BacktestEngineConfig(trader_id=TraderId.from_str("PROBE-001")))
    kw = {}
    if latency is not None:
        from nautilus_trader.execution import StaticLatencyModel
        kw["latency_model"] = StaticLatencyModel(base_latency_nanos=latency)
    engine.add_venue(venue=VENUE, oms_type=OmsType.NETTING, account_type=AccountType.CASH,
                     starting_balances=[Money.from_str("100000 USD")], base_currency=USD,
                     default_leverage=Decimal(1), fee_model=CountingFee(), **kw)
    inst = Equity(instrument_id=IID, raw_symbol=Symbol("CLPR"), currency=USD, price_precision=2,
                  price_increment=Price.from_str("0.01"), ts_event=0, ts_init=0,
                  lot_size=Quantity.from_int(1))
    engine.add_instrument(inst)
    quotes = [QuoteTick(IID, Price.from_str(f"{10 + i}.00"), Price.from_str(f"{10 + i}.02"),
                        Quantity.from_int(100), Quantity.from_int(100), T0 + i * SEC, T0 + i * SEC)
              for i in range(5)]
    engine.add_data(quotes)
    s = strategy_cls(StrategyConfig())
    engine.add_strategy(s)
    engine.run()
    out = dict(seen=s.seen, fills=s.fills, wrapped=s.wrapped_calls, overrides=s.override_calls)
    engine.dispose()
    return out


if __name__ == "__main__":
    import nautilus_trader
    print("version", nautilus_trader.__version__)
    print("zero-latency market on quote#2:", run(ProbeStrategy))
    print("latency 0.5s:", run(ProbeStrategy, latency=SEC // 2))
    print("override submit_order:", run(OverridingStrategy))
    print("wrapped on_quote:", run(wrap(type("W", (ProbeStrategy,), {}))))
    print("fee model calls:", CountingFee.calls)
