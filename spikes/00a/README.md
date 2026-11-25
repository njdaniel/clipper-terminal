# Phase 0 · proof 0A — engine artifact, execution timing, attribution and FIFO

**Issue:** #4 (parent #3; architecture #1 / PR #2).
**Specification:** the [pinned revision-4 validation spec](https://github.com/njdaniel/clipper-terminal/blob/899859b8465be65121a6887d217ef20a68cf3d5f/docs/architecture/desktop-validation.md#0a-engine-artifact-and-financial-timing),
checks 1–4.
**Branch:** `spike/00a-engine-validation`. This branch is disposable spike code, not production. Do not merge it.
**Executed:** 2026-11-25 on the reference machine (Pop!_OS 24.04, Ryzen 7 7700X, 61 GiB RAM,
glibc 2.39), by Claude.

**Rules followed:**
- synthetic data only (D25);
- no credentials and no real execution;
- no requirement relaxed: failures are reported as failures.

> **Verdict and findings:** see [Results](#results). The generated per-case tables are in
> [`evidence/summary.md`](evidence/summary.md).

## Contents

| Path | What it is |
|---|---|
| `build/clipper-sim-only.patch` | Parts 1–3 of the four-part patch, plus the stub index change from part 4 |
| `build/prune.sh` | Part 4: removes the Python packages of every adapter that isn't compiled in |
| `build/build_engine.sh` | Reproducible build from tag `v2.0.0rc9`: verifies the commit, applies the patch and prune, records the toolchain and `cargo tree`, runs maturin, hashes the wheel |
| `harness/clipper0a.py` | Fixtures with provenance, the Clipper timing gate, the fee specification, the pre-trade lot/tick check, the FIFO ledger and fill attribution |
| `harness/cases.py` | Timing counterexample suite and ledger cases, each with **hand-written expected outcomes** (the independent expected ledger) |
| `harness/run_case.py` | Runs one case in one process: backtest (`BacktestEngine`) or replay sandbox (`LiveNode` with the sandbox execution client) |
| `harness/run_suite.py` | Runs checks 1–4. Each case runs in its own `systemd-run --user --scope`, so its cgroup `memory.peak` belongs to that worker |
| `harness/artifact_check.py` | Inspects the installed environment: imports, native submodules, execution factories, pandas |
| `harness/backtestnode_check.py` | `BacktestNode` run from a Parquet catalog |
| `harness/codex_baselines.py` | Re-implementation of the upstream scenario behind Codex's four baseline variations |
| `harness/liquidity_probe.py` | Diagnostic for finding F4: L1 partial-fill liquidity in both contexts and both settings |
| `harness/engine_lot_tick_probe.py` | Informational: what the engine does with lot and tick violations without the Clipper check |
| `harness/probe_api.py` | API facts the harness relies on |
| `reproduce.sh` | End-to-end reproduction |
| `evidence/` | Build evidence, artifact scans, `results.json` (trimmed) and `summary.md` |

## Reproduce

```bash
cd spikes/00a && ./reproduce.sh /path/to/scratch   # ~13 min build + ~12 min suite on the reference machine
```

**Requirements:**
- Linux x86-64;
- rustup (the upstream `rust-toolchain.toml` pins 1.99.1, which installs automatically);
- uv (CPython 3.13.14 from python-build-standalone);
- a systemd user session (for per-case `memory.peak`);
- network access to GitHub, crates.io and PyPI for the build.

## Method

**Mechanisms under test (D22):**
- `baseline`: stock behaviour with zero latency. Included to show the failure being guarded against.
- `native`, D22(a): upstream `StaticLatencyModel(1 ms)`, with no Clipper code in the matching path.
- `native_bounded`: the native mechanism plus `support_gtd_orders=False` and `engine.run(end=<last data
  ts>)`. Backtest only. It tests whether bounding the run suppresses the end-of-run drain.
- `gate`, D22(b): the Clipper timing gate. `GatedStrategy` wraps data callbacks at class creation and
  overrides `submit_order`:
  - it holds every strategy order;
  - it releases an order only when a new feed event for that order's instrument arrives with
    `ts_init` strictly after the decision's data watermark;
  - it subscribes to quotes for any traded instrument, so it sees the finest execution data.
  Orders still held when the data ends are reported as unfilled, never filled.

**Contexts:**
- **Backtest:** `BacktestEngine`, with fixture timestamps from 2026-01-01T00:00Z.
- **Replay sandbox:** `LiveNode` with `SandboxExecutionClientFactory`, fed by a custom Python
  `MarketDataClient`. It replays the fixture in real time, with 1 fixture second = 0.25 s, and stamps
  `ts_init` from the node clock.

One engine node runs per process, as upstream requires.

**Fill truth:** fills are read from the engine cache (`OrderFilled` events), **not** from strategy
callbacks. The end-of-run drain fills orders after strategies have stopped, so those fills never reach
`on_order_filled` (see finding F2).

**Attribution:** each fill is matched to the latest emitted feed event for the same instrument at or
before the fill time whose relevant price equals the fill price (ask or bid for quotes; OHLC leg for
bars).
- The **origin** is `feed_event` only when the fill time equals the event time in backtest, or is
  within 50 ms of it in sandbox.
- Otherwise the origin is `non_feed_release`, meaning a timer, drain or latency alert fired against an
  older book.

**Verdicts** are exact comparisons with the expectations in `cases.py`, which were written from the D14
rule and the fixture. They were not taken from engine output.

**Venue specification pinned for every case:**
- `account_type=CASH`, `oms_type=NETTING`, `default_leverage=1`, base currency USD;
- an explicit fee model: zero maker/taker, or the Clipper fee specification;
- `liquidity_consumption=True` (see finding F4).

## Deviations from the specification

1. **Runtime prefix.** The "installed runtime prefix" is a fixed-path environment built by uv on
   CPython 3.13.14 from python-build-standalone, containing only the restricted wheel. It is not the
   `/opt/clipper/<version>` `.deb` layout, which belongs to proof 0B (#5).
2. **Build base.** The wheel was built on the reference host (glibc 2.39), so it is tagged
   `manylinux_2_39`. ADR-017's Ubuntu 22.04 build base, which gives a lower glibc floor, also belongs to
   0B.
3. **Tag signature.** `v2.0.0rc9` is an **unsigned** annotated tag: object `280573e`, created by
   `github-actions`. The build therefore pins and verifies the commit (`da6b57a`) rather than a signature.
4. **Section 31 rates.** The rates in the fee specification are **fixture values** for testing effective
   dating, not current SEC rates. The commission shape (USD 0.005 per share, minimum USD 1.00 per order,
   maximum 1% of trade value) follows a published fixed per-share broker schedule.

## Results

### Verdict: **0A is NO-GO as specified. Escalated for a maintainer ruling.**

| Check | Verdict | One line |
|---|---|---|
| 1. Simulation-only build (D13) | **PASS**, with one caveat | Built from the exact tag. Only the sandbox and Databento remain. No real-venue execution factory exists in Python, in the native library or in the binary's symbols. The native build is bit-for-bit reproducible. |
| 2. Packaged engine | **PASS** | A synthetic `BacktestNode` run from a Parquet catalog, and a replay-fed sandbox `LiveNode`, both work with explicit specifications. Typed results come without pandas. Worker `memory.peak` is recorded. |
| 3. Timing enforcement (D14, D22) | **FAIL** | **Native fails** (3 of 10 cases in backtest, all 10 in sandbox). **The Clipper gate passes 9 of 10 in both contexts.** Its one failure, `partial_fills`, is a fill-*quantity* failure caused by engine liquidity semantics, not a timing failure. |
| 4. Attribution, FIFO, fees, lot/tick | **PASS** | FIFO 20.00 against the engine's 15.00, with cash and quantity reconciling exactly. The order-level fee minimum and cap hold across partial fills. Lot and tick violations are refused. All of this holds in both contexts. |

The issue's acceptance criteria require checks 1–4 to PASS, and one timing mechanism to pass **every** case
in both contexts. That is not met because of `partial_fills`. Per D13 and issue #4, this is reported and
escalated. Nothing was relaxed, and no downstream phase may treat 0A as a go.

### Check 1: simulation-only build

**Source and patch:**
- **Source:** tag `v2.0.0rc9` → commit `da6b57aefdd62b44f675e434ffcfefca7f4025dd`. The tag is unsigned (deviation 3).
- **The four-part patch:**
  - [`build/clipper-sim-only.patch`](build/clipper-sim-only.patch) defines 20 per-adapter features, keeping
    `adapters` as an upstream-compatible umbrella. It changes all 20 native registration guards to
    `#[cfg(feature = "adapter-<name>")]`. It changes maturin's features to `extension-module, arrow,
    high-precision, mimalloc, tracing-bridge, adapter-sandbox, adapter-databento`, sets
    `no-default-features = true` and drops `defi`, `hypersync`, `redis` and `postgres`. It also prunes
    the adapter `.pyi` index.
  - [`build/prune.sh`](build/prune.sh) removes 19 excluded Python adapter packages, `blockchain` included.

**Toolchain:**
- rustc and cargo 1.99.1, maturin 1.15.0, CPython 3.13.14 (SQLite 3.53.1), gcc 13.3, glibc 2.39.
- Build time 736 s from scratch (636 s on rebuild); peak RSS about 10 GB.

**Feature graph** ([`evidence/build/cargo-tree-enabled-features.txt`](evidence/build/cargo-tree-enabled-features.txt), using the wheel's exact flags):
- `nautilus-pyo3` has `[adapter-databento, adapter-sandbox, arrow, extension-module, high-precision,
  mimalloc, tracing-bridge]`.
- `nautilus-infrastructure` has `[extension-module, pyo3, pyo3-stub-gen, python]`, so no Redis or Postgres.
- No excluded adapter crate appears anywhere in the resolved graph.

**Wheel:** `nautilus_trader-2.0.0rc9-cp313-cp313-manylinux_2_39_x86_64.whl`, 43.7 MB (the stock wheel is 74 MB).
- Its manifest has only `adapters/{databento,sandbox}`.
- The native library has 20 submodules, against 39 in stock.

**Imports** (from the installed runtime):
- `sandbox` and `databento` import.
- `binance`, `interactive_brokers` and `blockchain` are absent, as both Python packages and native modules.
- The **only** native execution factory is `SandboxExecutionClientFactory`. The stock wheel has 16 venue
  factories ([`evidence/artifact/`](evidence/artifact/)).

**Binary scan:** symbol strings for Binance, IB, OKX, Bybit, blockchain, Kraken, Polymarket and
Hyperliquid occur 0 times (3–15 each in stock). The sandbox and Databento symbols are retained
([`native-symbol-scan.txt`](evidence/artifact/native-symbol-scan.txt)).

**Wheel tested:** the runtime used build 1's wheel (`0d6edf14…`). Files under `evidence/build/` were
rewritten by build 2 (`7f13884b…`); its feature graph and manifest are identical.

**Reproducibility:** two builds produced an identical native library (`ef4a81d0…`) and identical
manifests. The wheels differ only in the CycloneDX SBOM's `serialNumber` and `timestamp`, and in the
`RECORD` hash of that SBOM ([`reproducibility.txt`](evidence/build/reproducibility.txt)).

**Caveat (C1).** The generic SDK base classes `nautilus_trader.live.clients.ExecutionClient` and
`ExecutionClientFactory` remain. They are not venue adapters, and they cannot reach an account by
themselves. But trusted user code could build a broker client on them, or on any network library. The
artifact gate holds; this is the residual-risk note that ADR-010 already anticipates.

### Check 2: packaged engine

- **`BacktestNode`** from a Parquet catalog (instrument plus quotes) with the gate strategy: fills
  10.00, 20.00 and 30.00, exactly as expected. Cash and position reconcile with the independent ledger.
  `memory.peak` about 54 MiB.
- **Replay sandbox.** The custom `MarketDataClient` feeds `LiveNode(Environment.SANDBOX)` with
  `SandboxExecutionClientFactory`. The specifications are explicit: fee, `FillModel()`,
  `StaticLatencyModel`, `CASH`, `NETTING`, leverage 1, `liquidity_consumption=True`.
- **pandas** is not installed, and none of these paths needs it. Results come from cache `OrderFilled`
  events.
- **NautilusTrader worker memory (D26),** measured separately as cgroup `memory.peak` per worker:
  backtest median about 43 MiB (max about 45); sandbox median about 46 MiB (max about 48). See
  `evidence/summary.md`.

### Check 3: execution timing

**Repeatability:** the suite ran twice: run 1, then run 2 with every fill and latency specification
explicit. **Every verdict was identical** across the two runs, including the real-time sandbox
([`suite-run1.log`](evidence/suite-run1.log), [`suite-run2.log`](evidence/suite-run2.log)).
`results.json` and `summary.md` come from run 2.

These are the counterexample-suite results: 10 cases, counting both timer forms. Full grid and failure
details are in [`evidence/summary.md`](evidence/summary.md).

| Mechanism | Backtest | Replay sandbox |
|---|---|---|
| baseline (zero latency) | 0/10 | 0/10 |
| **native**, D22(a): latency 1 ms | 7/10. Fails `timer` (the Codex form), `end_of_feed`, `partial_fills` | **0/10** |
| native_bounded (+ no GTD, `run(end=…)`) | 7/10. Bounding the run does **not** suppress the end-of-run drain | n/a |
| **Clipper gate**, D22(b) | **9/10**. Fails `partial_fills` only | **9/10**. Fails `partial_fills` only |

- **All four of Codex's baseline variations reproduce exactly** on the restricted wheel:
  - 00:01:00 @ 1.10010;
  - 00:02:00 @ 1.10020;
  - 00:01:02 @ 1.10010 (timer);
  - 00:01:01 @ 1.10010 (end-of-run drain).

  The gate moves the first three to the next eligible bar and leaves variation 4 unfilled.
- **D22 outcome:** native support cannot pass the suite. In the sandbox, the latency alert drains orders
  against the stale book with no new data, and `quotes_between_bars` fills at the signal bar's close.
  The rule "prefer native only if every case passes" therefore selects **the Clipper gate**. The gate's
  remaining failure is not a timing defect: every gate fill occurs on an eligible feed event after the
  watermark.

### Check 4: attribution, FIFO, fees, lot/tick (gate; backtest and sandbox)

- **Attribution:** every fill in every PASS case is attributed to its expected feed event and leg, with
  origin `feed_event`. rc9 `OrderFilled` events carry only a simulator `trade_id` and no feed reference
  (F7). Clipper's attribution comes from price/time matching plus the gate's own release log.
- **FIFO:** buy 1 @ 10, buy 1 @ 20, sell 1 @ 30. FIFO realized P&L is **20.00**; the engine reports
  **15.00** (proportional, average-cost allocation). Cash 100,000.00 and position quantity 1 reconcile
  exactly.
- **Fee minimum across partial fills:** 150 shares in fills of 50, 60 and 40. Commissions are
  1.00 / 0.00 / 0.00, and the independent recomputation agrees.
- **Fee cap across partial fills:** 10,000 shares @ 0.40 in fills of 2,500, 2,600, 2,700 and 2,200.
  Commissions are 10.00 / 10.40 / 10.80 / 8.80, a total of 40.00 against 50.00 uncapped.
- **Lot and tick:** Clipper's pre-trade check refuses 150 shares on a 100-share lot, and refuses a price
  of 11.025 on a 0.01 increment. The valid order fills.
- **Fixture change:** the fee fixtures use changing displayed sizes, so they test fee arithmetic and not
  the liquidity defect (F4).

### Findings

| ID | Finding | Evidence | Consequence |
|---|---|---|---|
| F1 | The simulation-only build is feasible with a small, auditable patch. Upstream's single `adapters` feature and guard are the obstacle. | Check 1 | D13 is satisfiable. Propose per-adapter features upstream. |
| F2 | **End-of-run drain fills are invisible to strategies.** The engine fills a pending order after strategies stop, so `on_order_filled` never runs. Variation 4's fill shows `seen_by_strategy=false`. | `codex_baselines` v4; `timing/end_of_feed` | Clipper must read fills from engine events and the cache, never from strategy callbacks. The gate prevents these fills. |
| F3 | **Native latency cannot enforce `after_watermark`.** In backtest, unrelated timers and the end-of-run drain release orders against stale books. In the sandbox, the latency alert drains without data, and orders submitted on a bar match at that bar's close even when quotes follow. | Check 3 grid | D22(a) rejected on evidence. Use the Clipper gate. |
| F4 | **L1 partial-fill liquidity: backtest and sandbox disagree, and neither engine setting matches upstream's documented rule in both contexts.** The documented rule is that a fresh book update at a level resets consumption to the new displayed size. See [`evidence/liquidity-probe.jsonl`](evidence/liquidity-probe.jsonl) and the table below. **Sandbox with the upstream default** matches the documented rule in all three variants. **Backtest with the upstream default** fills one order **twice** at a single 100-share quote (200 shares), in every variant. That goes beyond the documented "same displayed size can support more than one simulated order". **`liquidity_consumption=True`** resets only when displayed size changes, so in both contexts it under-fills on identical re-quotes and when a level returns after a price move. | `partial_fills` rows; `liquidity_probe.py` (12 runs) | Backtest-to-paper parity (ADR-005, ADR-013) does not hold for partial fills under any single setting. This is the **blocking** item. |
| F5 | An L1 market order larger than displayed size fills the residual **one tick worse**, which is unlimited liquidity one tick away. This is documented upstream. | `engine-lot-tick-probe.json` (50 @ 10.03) | Keep orders as limits with price collars (ADR-008). Flag market orders larger than displayed size. |
| F6 | The engine does **not** enforce lot size, and enforces tick size only through price precision. | `engine-lot-tick-probe.json` | Clipper's pre-trade lot/tick check is required (it passes). |
| F7 | rc9 fills carry no reference to the input feed record. | `OrderFilled` fields | Attribution is Clipper's inference, as ADR-013 anticipates. Make it a reviewed component. |
| F8 | The engine's realized P&L includes commissions and uses average cost. | FIFO and fee cases | The FIFO projection stays the record (D14). Report the difference in method, as specified. |
| F9 | The gate holds orders inside the strategy's `submit_order`. Code that calls `Strategy.submit_order` directly would bypass it. | design | The structural validation in ADR-005 must forbid direct base-class calls. The production gate should sit in the worker's order path, not only in a base class. |

Liquidity probe: a limit BUY of 300 decided on quote 1, run with the gate. ✓ means the fills match the
documented rule.

| Variant | Backtest, default | Backtest, consumption | Sandbox, default | Sandbox, consumption |
|---|---|---|---|---|
| identical re-quotes (100 each) | ✗ 200 at one quote, then 100 | ✗ 100 total | **✓** 100/100/100 | ✗ 100 total |
| displayed size changes 100→150→200 | ✗ 200 at one quote, then 100 | ✓ 100/150/50 | ✓ 100/150/50 | ✓ 100/150/50 |
| price moves away and back | ✗ 200 at one quote, then 100 | ✗ 100 total | **✓** 100/100/100 | ✗ 100 total |

### Escalation: maintainer ruling needed (D13, D22; issue #4)

The blocking case is `partial_fills` (F4). The options, with my recommendation first:

1. **Keep the documented expectation and fix the engine behaviour upstream.** Report two defects with
   these fixtures:
   - the backtest L1 quote path fills one order twice at a single displayed size;
   - consumption doesn't reset on fresh updates at the same size.

   Until they're fixed, Clipper pins `liquidity_consumption=True`, which never overfills in either
   context, and **labels** partial fills as conservative under-fills. Partial-fill parity stays an open
   Alpha-R release gate. Note that the sandbox's default behaviour already matches the documented rule,
   so the defects are on the backtest side and in the consumption mode.
2. **Clipper-owned liquidity accounting in the gate.** The gate would cap each release by the displayed
   size not yet consumed at that event, so backtest and sandbox follow one Clipper rule. That puts more
   Clipper code in the matching path; it needs its own fixtures and an ADR-013 amendment.
3. **Change the requirement.** Accept upstream's actual semantics (replenish only when displayed size
   changes) as Clipper's model. That relaxes the documented expectation, so it is your decision, not
   mine.

Other inputs for the ruling: caveat C1; F2 and F9, which bind on the implementation, not the
architecture; and deviations 1–2, which proof 0B (#5) covers.
