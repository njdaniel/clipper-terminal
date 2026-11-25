# Proof 0A — generated results summary

Run: 2026-11-25T22:27:41Z → 2026-11-25T22:38:13Z · runtime `$WORK/runtime/bin/python`

## Check 1 — artifact inspection (installed restricted wheel)

- nautilus_trader 2.0.0rc9, CPython 3.13.14
- native submodules (20): `analysis, backtest, common, core, cryptography, data, databento, execution, indicators, infrastructure, live, model, network, persistence, portfolio, risk, sandbox, serialization, testkit, trading`
- must import: `nautilus_trader.adapters.sandbox`=OK, `nautilus_trader.adapters.databento`=OK
- must fail: `nautilus_trader.adapters.binance`=absent, `nautilus_trader.adapters.interactive_brokers`=absent, `nautilus_trader.adapters.blockchain`=absent, `nautilus_trader._libnautilus.binance`=absent, `nautilus_trader._libnautilus.interactive_brokers`=absent, `nautilus_trader._libnautilus.blockchain`=absent
- native execution factories: `['SandboxExecutionClientFactory']`
- Python execution factory/base names: `['ExecutionClient', 'ExecutionClientFactory', 'SandboxExecutionClientFactory']`
- pandas present: False
- *stock rc9 wheel for comparison*: 39 native submodules; native execution factories `['AxExecutionClientFactory', 'BetfairExecutionClientFactory', 'BinanceExecutionClientFactory', 'BybitExecutionClientFactory', 'CoinbaseExecutionClientFactory', 'DeribitExecutionClientFactory', 'DeriveExecutionClientFactory', 'DydxExecutionClientFactory', 'HyperliquidExecutionClientFactory', 'InteractiveBrokersExecutionClientFactory', 'KalshiExecutionClientFactory', 'KrakenExecutionClientFactory', 'LighterExecutionClientFactory', 'OKXExecutionClientFactory', 'PolymarketExecutionClientFactory', 'SandboxExecutionClientFactory']`

## Check 2 — BacktestNode from Parquet catalog (FIFO fixture, gate)

- fills: [('BUY', '10.00', '1', 1), ('BUY', '20.00', '1', 2), ('SELL', '30.00', '1', 3)]
- engine cash 100000.00 USD; positions [{'qty': '1', 'realized_pnl': '15.00 USD'}]; FIFO ledger 20.00 gross, cash 100000.00
- worker memory.peak 51.6 MiB; catalog files 2

## Check 3 — execution timing (after_watermark), counterexample suite

| case | context | baseline | native | native_bounded | gate |
|---|---|---|---|---|---|
| timer | backtest | FAIL | FAIL | FAIL | PASS |
| timer | sandbox | FAIL | FAIL | — | PASS |
| timer_decision | backtest | FAIL | PASS | PASS | PASS |
| timer_decision | sandbox | FAIL | FAIL | — | PASS |
| end_of_feed | backtest | FAIL | FAIL | FAIL | PASS |
| end_of_feed | sandbox | FAIL | FAIL | — | PASS |
| equal_timestamps | backtest | FAIL | PASS | PASS | PASS |
| equal_timestamps | sandbox | FAIL | FAIL | — | PASS |
| other_instrument | backtest | FAIL | PASS | PASS | PASS |
| other_instrument | sandbox | FAIL | FAIL | — | PASS |
| first_update_ordering | backtest | FAIL | PASS | PASS | PASS |
| first_update_ordering | sandbox | FAIL | FAIL | — | PASS |
| stale_feed | backtest | FAIL | PASS | PASS | PASS |
| stale_feed | sandbox | FAIL | FAIL | — | PASS |
| resting_orders | backtest | FAIL | PASS | PASS | PASS |
| resting_orders | sandbox | FAIL | FAIL | — | PASS |
| partial_fills | backtest | FAIL | FAIL | FAIL | FAIL |
| partial_fills | sandbox | FAIL | FAIL | — | FAIL |
| quotes_between_bars | backtest | FAIL | PASS | PASS | PASS |
| quotes_between_bars | sandbox | FAIL | FAIL | — | PASS |
| partial_fills[upstream-default-liquidity] | backtest | FAIL | FAIL | FAIL | FAIL |
| partial_fills[upstream-default-liquidity] | sandbox | FAIL | FAIL | — | PASS |

Mechanism totals (non-diagnostic cases):

- backtest / baseline: FAIL 10
- backtest / gate: FAIL 1, PASS 9
- backtest / native: FAIL 3, PASS 7
- backtest / native_bounded: FAIL 3, PASS 7
- sandbox / baseline: FAIL 10
- sandbox / gate: FAIL 1, PASS 9
- sandbox / native: FAIL 10

Failure details:

- `timer` backtest/baseline: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `timer` backtest/native: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]; non-feed fills [{'idx': 1, 'leg': 'ask', 'lag_ns': 500000000, 'origin': 'non_feed_release'}]
- `timer` backtest/native_bounded: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]; non-feed fills [{'idx': 1, 'leg': 'ask', 'lag_ns': 500000000, 'origin': 'non_feed_release'}]
- `timer` sandbox/baseline: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `timer` sandbox/native: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `timer_decision` backtest/baseline: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]; non-feed fills [{'idx': 1, 'leg': 'ask', 'lag_ns': 500000000, 'origin': 'non_feed_release'}]
- `timer_decision` sandbox/baseline: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]; non-feed fills [{'idx': 1, 'leg': 'ask', 'lag_ns': 126502271, 'origin': 'non_feed_release'}]
- `timer_decision` sandbox/native: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]; non-feed fills [{'idx': 1, 'leg': 'ask', 'lag_ns': 127629526, 'origin': 'non_feed_release'}]
- `end_of_feed` backtest/baseline: FAIL — expected [] got [{'idx': 2, 'px': '12.02', 'qty': '1'}]
- `end_of_feed` backtest/native: FAIL — expected [] got [{'idx': 2, 'px': '12.02', 'qty': '1'}]; non-feed fills [{'idx': 2, 'leg': 'ask', 'lag_ns': 1000000, 'origin': 'non_feed_release'}]
- `end_of_feed` backtest/native_bounded: FAIL — expected [] got [{'idx': 2, 'px': '12.02', 'qty': '1'}]; non-feed fills [{'idx': 2, 'leg': 'ask', 'lag_ns': 1000000, 'origin': 'non_feed_release'}]
- `end_of_feed` sandbox/baseline: FAIL — expected [] got [{'idx': 2, 'px': '12.02', 'qty': '1'}]
- `end_of_feed` sandbox/native: FAIL — expected [] got [{'idx': 2, 'px': '12.02', 'qty': '1'}]
- `equal_timestamps` backtest/baseline: FAIL — expected [{'idx': 3, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `equal_timestamps` sandbox/baseline: FAIL — expected [{'idx': 3, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `equal_timestamps` sandbox/native: FAIL — expected [{'idx': 3, 'px': '12.02', 'qty': '1'}] got [{'idx': 2, 'px': '11.52', 'qty': '1'}]
- `other_instrument` backtest/baseline: FAIL — expected [{'idx': 3, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `other_instrument` sandbox/baseline: FAIL — expected [{'idx': 3, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `other_instrument` sandbox/native: FAIL — expected [{'idx': 3, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `first_update_ordering` backtest/baseline: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `first_update_ordering` sandbox/baseline: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `first_update_ordering` sandbox/native: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `stale_feed` backtest/baseline: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `stale_feed` sandbox/baseline: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `stale_feed` sandbox/native: FAIL — expected [{'idx': 2, 'px': '12.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `resting_orders` backtest/baseline: FAIL — expected [{'idx': 3, 'px': '11.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `resting_orders` sandbox/baseline: FAIL — expected [{'idx': 3, 'px': '11.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `resting_orders` sandbox/native: FAIL — expected [{'idx': 3, 'px': '11.02', 'qty': '1'}] got [{'idx': 1, 'px': '11.02', 'qty': '1'}]
- `partial_fills` backtest/baseline: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 1, 'px': '11.02', 'qty': '100'}]
- `partial_fills` backtest/native: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 2, 'px': '11.02', 'qty': '100'}]
- `partial_fills` backtest/native_bounded: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 2, 'px': '11.02', 'qty': '100'}]
- `partial_fills` backtest/gate: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 2, 'px': '11.02', 'qty': '100'}]
- `partial_fills` sandbox/baseline: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 1, 'px': '11.02', 'qty': '100'}]
- `partial_fills` sandbox/native: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 1, 'px': '11.02', 'qty': '100'}]
- `partial_fills` sandbox/gate: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 2, 'px': '11.02', 'qty': '100'}]
- `quotes_between_bars` backtest/baseline: FAIL — expected [{'idx': 1, 'px': '12.52', 'qty': '1'}] got [{'idx': 0, 'px': '10.20', 'qty': '1'}]
- `quotes_between_bars` sandbox/baseline: FAIL — expected [{'idx': 1, 'px': '12.52', 'qty': '1'}] got [{'idx': 0, 'px': '10.20', 'qty': '1'}]
- `quotes_between_bars` sandbox/native: FAIL — expected [{'idx': 1, 'px': '12.52', 'qty': '1'}] got [{'idx': 0, 'px': '10.20', 'qty': '1'}]
- `partial_fills[upstream-default-liquidity]` backtest/baseline: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 1, 'px': '11.02', 'qty': '100'}, {'idx': 1, 'px': '11.02', 'qty': '100'}, {'idx': 2, 'px': '11.02', 'qty': '100'}]
- `partial_fills[upstream-default-liquidity]` backtest/native: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}]
- `partial_fills[upstream-default-liquidity]` backtest/native_bounded: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}]
- `partial_fills[upstream-default-liquidity]` backtest/gate: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}]
- `partial_fills[upstream-default-liquidity]` sandbox/baseline: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 1, 'px': '11.02', 'qty': '100'}, {'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}]
- `partial_fills[upstream-default-liquidity]` sandbox/native: FAIL — expected [{'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}, {'idx': 4, 'px': '11.02', 'qty': '100'}] got [{'idx': 1, 'px': '11.02', 'qty': '100'}, {'idx': 2, 'px': '11.02', 'qty': '100'}, {'idx': 3, 'px': '11.02', 'qty': '100'}]

### Codex baseline variations (stock behaviour reproduced on the restricted wheel)

| variation | mechanism | first buy (ours) | Codex reported | seen by strategy |
|---|---|---|---|---|
| 1 | baseline | 00:01:00 1.10010 | 00:01:00 1.10010 | True |
| 1 | gate | 00:02:00 1.10020 | 00:01:00 1.10010 | True |
| 2 | baseline | 00:02:00 1.10020 | 00:02:00 1.10020 | True |
| 2 | gate | 00:03:00 1.10030 | 00:02:00 1.10020 | True |
| 3 | baseline | 00:01:02 1.10010 | 00:01:02 1.10010 | True |
| 3 | gate | 00:03:00 1.10030 | 00:01:02 1.10010 | True |
| 4 | baseline | 00:01:01 1.10010 | 00:01:01 1.10010 | False |
| 4 | gate | no fill  | 00:01:01 1.10010 | — |

## Check 4 — attribution, FIFO, fees, lot/tick (gate)

| case | context | verdict | details |
|---|---|---|---|
| fifo | backtest | PASS | FIFO 20.00 vs engine ['15.00']; cash engine 100000.00 USD / ledger 100000.00  |
| fifo | sandbox | PASS | FIFO 20.00 vs engine ['15.00']; cash engine 100000.00 USD / ledger 100000.00  |
| fee_min_across_partials | backtest | PASS | commissions ['1.00', '0.00', '0.00']; cash engine 98346.00 USD / ledger 98346.00  |
| fee_min_across_partials | sandbox | PASS | commissions ['1.00', '0.00', '0.00']; cash engine 98346.00 USD / ledger 98346.00  |
| fee_cap_across_partials | backtest | PASS | commissions ['10.00', '10.40', '10.80', '8.80']; cash engine 95960.00 USD / ledger 95960.00  |
| fee_cap_across_partials | sandbox | PASS | commissions ['10.00', '10.40', '10.80', '8.80']; cash engine 95960.00 USD / ledger 95960.00  |
| lot_tick_refusal | backtest | PASS | refusals 2; cash engine 98998.00 USD / ledger 98998.00  |
| lot_tick_refusal | sandbox | PASS | refusals 2; cash engine 98998.00 USD / ledger 98998.00  |

## Worker memory (cgroup memory.peak, MiB)

- backtest: n=48, min 42.1, median 42.8, max 46.8
- sandbox: n=37, min 45.7, median 45.9, max 48.2

