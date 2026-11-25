"""Check 2: synthetic BacktestNode run from a Parquet catalog, from the installed runtime prefix.
Writes the FIFO fixture (instrument + quotes, with provenance) to a fresh catalog, runs a
BacktestNode with explicit fee/fill/latency specs and the Clipper gate strategy, and returns
typed results (cache OrderFilled events; no pandas). Usage: python backtestnode_check.py <catalog_dir>"""

from __future__ import annotations

import json
import shutil
import sys
from decimal import Decimal

from nautilus_trader.backtest import BacktestDataConfig, BacktestEngineConfig, BacktestNode, BacktestRunConfig, BacktestVenueConfig
from nautilus_trader.common import LoggerConfig, LogLevel
from nautilus_trader.config import StrategyConfig
from nautilus_trader.execution import FillModel, MakerTakerFeeModel, StaticLatencyModel
from nautilus_trader.model import NautilusDataType, TraderId
from nautilus_trader.persistence import DataCatalogConfig, ParquetDataCatalog

import clipper0a as c
from cases import LEDGER_CASES

T0 = 1_767_225_600 * c.SEC


def main(path: str) -> dict:
    case = LEDGER_CASES["fifo"]
    shutil.rmtree(path, ignore_errors=True)
    __import__("os").makedirs(path)
    cat = ParquetDataCatalog(path)
    cat.write_instruments([c.make_instrument("CLPR")])
    quotes, keymap, emitted = [], {}, []
    for i, ev in enumerate(case["events"]):
        ts = T0 + int(ev["t"] * c.SEC)
        quotes.append(c.to_nautilus(ev, ts))
        keymap[("CLPR", "quote", ts, ev["bid"], ev["ask"])] = i
        emitted.append({**ev, "idx": i, "ts": ts})
    cat.write_quote_ticks(quotes)
    run_id = "clipper-0a-node"
    venue = BacktestVenueConfig(
        name="SIM", oms_type="NETTING", account_type="CASH", starting_balances=["100000 USD"],
        base_currency=c.USD, default_leverage=Decimal(1), support_gtd_orders=False,
        fee_model=MakerTakerFeeModel(maker_rate=Decimal(0), taker_rate=Decimal(0)),
        fill_model=FillModel(), latency_model=StaticLatencyModel(base_latency_nanos=0),
    )
    data = BacktestDataConfig(data_type=NautilusDataType.QuoteTick, catalog=DataCatalogConfig(path),
                              instrument_id=c.iid("CLPR"))
    cfg = BacktestRunConfig(venues=[venue], data=[data], id=run_id, raise_exception=True,
                            dispose_on_completion=False,
                            engine=BacktestEngineConfig(trader_id=TraderId.from_str("CLIPPER-0A"),
                                                        logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    node = BacktestNode(configs=[cfg])
    node.build()
    s = c.GatedStrategy(StrategyConfig()).configure(
        case["script"], case["subs"],
        lambda d: keymap.get((str(d.instrument_id.symbol), "quote", d.ts_init, str(d.bid_price), str(d.ask_price))))
    node.add_strategy(run_id, s)
    node.run()
    cache = node.get_engine_cache(run_id)
    fills = c.cache_fills(cache)
    for f in fills:
        f["attribution"] = c.attribute(f, emitted, 0)
    acct = cache.account_for_venue(c.VENUE)
    positions = [{"qty": str(p.quantity), "realized_pnl": str(p.realized_pnl)} for p in cache.positions()]
    ledger = c.fifo_ledger(fills, Decimal("100000"))
    out = {"fills": fills, "cash": str(acct.balance_total(c.USD)), "positions": positions, "ledger": ledger,
           "catalog_files": sorted(str(p) for p in __import__("pathlib").Path(path).rglob("*.parquet")),
           "fixture_provenance": c.fixture_provenance("fifo", case["events"]), "memory": c.cgroup_memory_peak()}
    node.dispose()
    return out


if __name__ == "__main__":
    print("CLIPPER-0A-RESULT " + json.dumps(main(sys.argv[1]), default=str))
