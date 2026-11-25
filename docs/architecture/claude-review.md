# Clipper Terminal Alpha 0.1: independent architecture review

**Reviewer:** Claude (Opus 5.5), via Claude Code, for issue #1 / PR #2
**Date:** 2026-11-25
**Reviewed:** `docs/architecture/overview.md`, `docs/adr/0001-alpha-architecture-decisions.md` and `docs/architecture/implementation-plan.md` on `docs/architecture-alpha` at `37ae864`
**Status:** Review only. This document does not approve the design, and it does not change the proposal documents. Reconciliation and sign-off belong to the maintainer.

> **Errata (2026-11-25):** the independent [Codex review](codex-review.md) contradicted several claims in this review. The corrections are listed in [`claude-review-2.md` § Errata](claude-review-2.md#errata-after-the-codex-review). This review is otherwise left as written.

## Verdict

**The direction is right, but three decisions must change before the backlog is created.**

The draft is careful in many places. It refuses to fork the engine, keeps real-money routing out of the build, gives web, CLI and MCP one shared command path, and calls out intrabar ambiguity and survivorship bias. Most of its component boundaries are sound.

It also defers three questions to "spikes" that this review was able to answer from upstream source and release metadata. All three answers go against the draft:

1. **ADR-002 picks the wrong engine line.** NautilusTrader v1 is now legacy. Its sandbox cannot match the backtest's fill and fee models, and its catalog format is incompatible with v2.
2. **ADR-008's recovery problem is settled, not open.** In both release lines the sandbox keeps all matching and account state in memory. It can be seeded with cash balances only, and it reports no fills or positions to reconciliation. Restarting a paper account is not possible upstream. The draft treats paper recovery like recovery against a real venue. That makes the design more complex than it needs to be, and it still leaves the product promise unmet.
3. **ADR-007's "AI cannot self-approve" has no enforcement mechanism.** Claude Code and Codex run as the same OS user, with a shell. Anything the human's UI or CLI can do with the per-install token, the agent can do too.

Separately, the scope and the 3–5 week estimate are not credible together (P1-6).

Recommendation: accept ADR-001, 003 (amended), 004, 005, 006 (amended), 009, 012 and 013 in principle. Rewrite ADR-002, 007, 008 and 010, and add a contributor-licensing decision (P1-7) before backlog creation.

## How the claims were checked

Everything below marked **[verified]** was checked against primary sources on 2026-11-25. Commands are included so the maintainer can repeat each check. No software was installed and no engine code was run. Claims that need runtime confirmation are marked **[inference]** and come with a test to run.

```bash
# Release lines, Python support and wheels
curl -s https://pypi.org/pypi/nautilus_trader/json | jq '.info.version, .info.requires_python'
curl -s https://pypi.org/pypi/nautilus_trader/2.0.0rc9/json | jq '.info.requires_python, .info.requires_dist'
# v1 support policy
gh api 'repos/nautechsystems/nautilus_trader/contents/MIGRATION_V2.md?ref=develop' --jq .content | base64 -d | sed -n '1,10p'
# Sandbox internals, v1 and v2
gh api 'repos/nautechsystems/nautilus_trader/contents/nautilus_trader/adapters/sandbox/execution.py?ref=v1.231.0' --jq .content | base64 -d | sed -n '100,195p'
gh api 'repos/nautechsystems/nautilus_trader/contents/crates/adapters/sandbox/src/config.rs?ref=v2.0.0rc9' --jq .content | base64 -d
gh api 'repos/nautechsystems/nautilus_trader/contents/crates/adapters/sandbox/src/execution.rs?ref=v2.0.0rc9' --jq .content | base64 -d | sed -n '880,962p'
# Risk engine limits (v2)
gh api 'repos/nautechsystems/nautilus_trader/contents/crates/risk/src/engine/config.rs?ref=v2.0.0rc9' --jq .content | base64 -d | grep 'pub '
# MCP SDK
gh api repos/modelcontextprotocol/python-sdk/releases --jq '.[] | select(.tag_name=="v2.0.0") | .body'
# Lightweight Charts
curl -s https://registry.npmjs.org/lightweight-charts | jq '."dist-tags"'
gh api repos/tradingview/lightweight-charts/contents/NOTICE --jq .content | base64 -d
```

### Upstream facts this review relies on

| Topic | Fact | Source |
|---|---|---|
| Nautilus stable | `1.231.0`, released 2026-08-02. No 1.x release since. Requires Python `>=3.12,<3.15`; wheels are `manylinux_2_35`. | PyPI JSON [verified] |
| Nautilus next | `2.0.0rc9`, released 2026-11-10, after RC3–RC9 roughly every two weeks since August. Requires Python `>=3.13,<3.16`; wheels are `manylinux_2_34`. **No required runtime dependencies** (v1 pins pandas, pyarrow, fsspec, msgspec and others). | PyPI JSON [verified] |
| v1 support | "Legacy v1 lives on `develop_v1` and receives only critical security backports for approximately three months after the v2 cutover. It receives no feature or parity work." `develop` is already v2. | `MIGRATION_V2.md` on `develop` [verified] |
| Docs versus PyPI | The `docs/latest` site describes 2.x. A plain `pip install nautilus_trader` still installs 1.x, and v2 examples fail against it. | `docs/getting_started/installation.md` [verified] |
| Catalog | v2 Arrow schemas and catalog API differ from v1. v1 catalogs need migration, and migration fails on rows with excess precision. | `MIGRATION_V2.md` "Migrate catalogs" [verified] |
| Sandbox in v1 | A Python module exists. It **hard-codes** `FillModel()`, `MakerTakerFeeModel()` and `LatencyModel(0)`. Defaults are `account_type="MARGIN"` and `oms_type="NETTING"`. Initial state is `starting_balances` only. All four reconciliation report methods return `None` or `[]`. | `adapters/sandbox/execution.py` lines 109–193 at `v1.231.0` [verified] |
| Sandbox in v2 | A Python module exists, backed by a Rust crate. Fill, fee, margin and latency models are **configurable**, and a fee model is **required** (an explicit zero-fee model is allowed). Also supports `bar_adaptive_high_low_ordering` and `queue_position`. Initial state is still `starting_balances` only. Order status reports are **built from the node cache**. Fill and position reports return empty lists. | `crates/adapters/sandbox/src/{config,execution}.rs` at `v2.0.0rc9` [verified] |
| Process model | "Run one concurrent `LiveNode` per process"; the same applies to `BacktestNode`, because of global singleton state. | `docs/concepts/live.md`, `architecture.md` [verified] |
| Cache persistence (v2) | Redis or Postgres only, configured through `LiveNodeBuilder`. Custom Python clients do not support database cache backing, and neither does `run_async()`. | `MIGRATION_V2.md` "Known limitations" [verified] |
| Risk engine (v2) | Config holds `bypass`, `max_order_submit`, `max_order_modify`, `max_notional_per_order` and `full_position_exit_venues`. No position, loss, duration or instrument-allowlist limits. | `crates/risk/src/engine/config.rs` [verified] |
| Bar execution | Bars become four synthetic L1 updates (O, then H/L in configured or adaptive order, then C). `ts_init` must be the bar **close**. Orders submitted from `on_bar` are processed after that bar. Upstream offers no "reject ambiguous bar" mode. | `docs/concepts/backtesting/bar-execution.md` at `v2.0.0rc9` [verified] |
| Fee models (v2) | `MakerTakerFeeModel`, `FixedFeeModel` and `PerContractFeeModel`, plus custom Python `FeeModel` subclasses through `get_commission(...)`. | `docs/concepts/behavioral_models.md` [verified] |
| Equity data adapters | Both lines ship `databento` and `interactive_brokers`. There are no Alpaca or Polygon adapters. | Wheel file listings [verified] |
| Licence | NautilusTrader is **LGPL-3.0**. | GitHub repository metadata [verified] |
| MCP Python SDK | `2.3.0` is current, and `2.0.0` was released 2026-07-28. **v1.x is in maintenance mode, security fixes only.** v2 speaks protocol revision 2026-07-28 (stateless; the server cannot call the client) and still serves older clients. `FastMCP` is renamed `MCPServer`. The tasks extension (SEP-2663) is **not** included. | GitHub release notes [verified] |
| MCP spec | Revisions: 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25 and 2026-07-28. | `modelcontextprotocol` repo [verified] |
| Lightweight Charts | `5.3.0` (2026-11-10), Apache-2.0. The NOTICE file reads "TradingView Lightweight Charts™ Copyright (c) 2025 TradingView, Inc." Official plugin packages now include `session-highlighting`, `user-price-lines`, `vertical-line` and `accessibility`. There are still **no official trend-line or shape drawing tools**. | npm and GitHub [verified] |

## Findings

Severity scale: **P0** must change before the backlog is created. **P1** must be decided before the affected epic starts. **P2** should be fixed but does not block.

### P0-1: ADR-002 prefers stable 1.x, but 1.x is the legacy line

**Claim challenged:** "Prefer an exact stable 1.x pin if required adapters and fixtures pass; run a timeboxed comparison with a pinned 2.x RC only for simulation."

**Evidence:**
- Upstream has declared v1 legacy: security backports only, for about three months after cutover, and no feature or parity work. A greenfield project starting on 1.x would begin its life on an end-of-life line and owe a full port almost at once.
- The port is not cosmetic. Import paths change (`TradingNode` becomes `LiveNode`). Config classes move from msgspec to PyO3. Custom `StrategyConfig` fields do not carry over. Catalog schemas change and need migration. Everything ADR-003 stores in a v1 catalog would have to be migrated.
- The v1 sandbox hard-codes its fill, fee and latency models. Backtest-to-paper parity (ADR-005's "same strategy in both modes") therefore cannot be configured. Equity per-share commissions are impossible without subclassing internals. The v2 sandbox exposes these models as config and *requires* an explicit fee model. That is exactly the parity property ADR-013 wants.
- v2 has no required runtime dependencies, so it cannot conflict with FastAPI, Pydantic or the MCP SDK. v1 pins pandas, pyarrow, fsspec and msgspec.
- The upstream docs the draft cites (`docs/latest`) describe v2. Building on 1.x means coding against docs for another API, which is the failure the draft itself warns about.

**Risk of switching to v2:** it is still a release candidate, and RCs keep breaking APIs (RC3–RC9 in three months). The draft's own rule, "no RC for future real-money production", is right, and it does not apply here: alpha has no real money.

**Recommendation:** Rewrite ADR-002 as follows.
- Target the v2 line. Pin an exact RC (`nautilus_trader==2.0.0rc9` today) in its own virtual environment.
- Move to `2.0.0` final when it ships, through one PR that runs the full financial fixture suite.
- Put every engine call behind the adapter layer the draft already proposes, so RC churn stays in one package.
- Do not build a v1/v2 compatibility abstraction. The draft is right to rule one out.
- Use **CPython 3.13** as the primary interpreter, with 3.14 in CI. 3.13 is the oldest version both release lines support, which keeps a fallback to 1.x possible during the spike without changing interpreters.
- State the glibc floor: `manylinux_2_34`, that is Ubuntu 22.04+, Debian 12+ or RHEL 9+.
- Keep a short 1.231 smoke test in the Phase 1 spike only as a fallback.

### P0-2: Paper recovery cannot work upstream, so decide the product semantics now

**Claim challenged:** ADR-008 and the overview's paper section treat recovery as an open spike ("Can selected sandbox persist/recover open orders and balances faithfully?"). They model failures on a real venue: UNKNOWN dispatch outcome, reconcile by client order ID before retry, and an eight-state account machine.

**Evidence:**
- **[verified]** In both 1.231 and 2.0rc9 the sandbox builds a fresh in-memory `SimulatedExchange` from `starting_balances`. There is no setting to seed positions or working orders. It returns no fill or position reports, so upstream reconciliation has nothing to reconcile against. Restarting a sandbox account gives you a new account with new cash.
- **[inference, needs a kill test]** The v2 sandbox answers order status queries from the node *cache*. If someone enables Redis or Postgres cache backing to "get persistence", a restarted node would reload open orders from the cache. The sandbox would then report those orders back as working, so reconciliation agrees with itself. But the fresh matching engine does not hold them, so they never fill, and the balance resets to starting cash. That is a silent, plausible-looking corruption. **The design must forbid Nautilus cache database backing for sandbox accounts** until a kill/restart test proves otherwise.
- With an in-process simulated venue, the failure model is **simpler** than the draft assumes. There is no external counterparty, so a fill that never reached the journal never happened anywhere. "UNKNOWN at the venue" cannot occur. The only real ambiguities are (a) app-to-worker command delivery and (b) whether the worker process died.

**Consequence for the product:** journey 4 promises a "bounded continuous strategy deployment" that survives AI disconnection. Journey 5 says any worker interruption leads to recovery_required, with no reconstruction. Taken together, every reboot, laptop suspend, OOM kill or Clipper upgrade permanently ends a paper account. For a local-first desktop tool that is routine, not an edge case. Users will see paper trading that cannot last a weekend.

**Alternatives:**

| Option | Description | Cost | Verdict |
|---|---|---|---|
| A. Fail closed (current draft) | Any restart sets recovery_required, then archive and start a new account. | Low | Honest, but should be presented as **session-scoped paper deployments**, not "continuous". |
| B. Journal-authoritative replay | Record the market data each deployment consumed, plus all commands. On restart, replay them through a fresh engine on a test clock to rebuild state, then switch to live data. | High: data recording licence, determinism, replay time | The right long-term design; it also gives "paper session replay" as a feature. |
| C. Upstream contribution | Add starting positions and orders (a state snapshot) to `SandboxExecutionClientConfig`. | Medium, and depends on upstream | Worth opening an upstream issue now. Do not depend on it. |
| D. Broker paper account (e.g. IBKR paper through the IB adapter) | The venue holds state, and upstream live reconciliation works. | Medium. Needs a broker account, a Gateway process and paid data. **Puts a real-execution-capable adapter in the build.** | Contradicts the "no real execution in alpha builds" invariant; defer. |
| E. Clipper-owned paper matcher | Clipper runs its own fills and ledger. | High; duplicates financial logic | Rejected, as the draft rightly says. |

**Recommendation:**
- Adopt **A for alpha, designed so B can follow**. Make the journal the account's ledger of record from day one.
- Label deployments "session-scoped" in UI and docs, and make resumable paper trading an **explicit alpha non-goal**.
- Collapse the recovery state machine to the failure points that actually exist (see P1-3).
- If the data licence allows, record consumed market data per deployment.
- File the upstream issue for C.

### P0-3: Human approval cannot be enforced against a same-user AI agent with a shell

**Claim challenged:** "AI cannot self-approve or change limits. Server-side enforcement independent of MCP host UI." "Credentials… isolated from agents… wherever feasible." Issue #1's acceptance criteria also require that "AI-driven order-changing actions require explicit authorization; credentials are not exposed to agents."

**Evidence (threat model):** Claude Code and Codex, the target hosts, execute shell commands as the user. The proposed design puts the per-install API token in a user-readable file, approves through `POST /v1/approvals/{id}/approve`, keeps SQLite and policy files in the user's home directory, and runs a browser UI on loopback. An agent can therefore:
- read the token and `curl` the approve endpoint;
- edit the SQLite approval or policy rows directly, or edit the "trusted" strategy source;
- kill and restart workers;
- drive the browser (Playwright, CDP or a browser extension) and click **Approve** in the "trusted UI";
- read data-provider keys from any user-readable store, including `secret-tool` / the keyring.

Splitting MCP tools into read-only and mutating sets limits only the *MCP channel*. It does not limit the agent.

**Alternatives:**
1. **Human-presence proof (recommended).** Approval requires a WebAuthn assertion with user verification (passkey, security key or platform biometrics). The challenge is the hash of the canonical intent (account, instrument, side, quantity, price collar, expiry and policy revision). Registering a new authenticator itself requires an existing credential, or a one-time physical step at install. An agent cannot produce a touch or biometric. The approval is bound to the exact intent, so tampering after approval breaks it. Python libraries for this are mature. Cost: about 2–4 days, plus a localhost-origin spike, because WebAuthn needs a secure context and `localhost` qualifies.
2. **OS user separation.** Run `clipperd` as a dedicated system user that owns its data, tokens and provider keys. Approvals happen through a separate channel the agent cannot reach. This is strong but makes local setup much heavier.
3. **Explicit acceptance.** Declare same-user agents inside the trust boundary for paper alpha. Approvals then guard against agent *mistakes*, not a malicious agent. This is cheap and honest, but it **fails issue #1's acceptance criterion as written**. The maintainer would have to amend that criterion.

**Recommendation:**
- Choose (1) for order and deployment approvals, together with (3)'s honest documentation for everything else: data credentials, workspace files and audit tampering.
- Make the audit journal hash-chained, so edits outside Clipper are detectable after the fact, even if not preventable.
- Bootstrap browser auth the way Jupyter does: the CLI opens the browser with a one-time code in the URL fragment, exchanged for an `HttpOnly`, `SameSite=Strict` session cookie, so the token never sits where web content can read it.
- Validate the `Host` header against an allowlist to block DNS rebinding.
- Give the MCP token a scope that the **server** refuses on all approval and policy routes.
- Revise ADR-007's acceptance evidence to include a red-team test: an agent with shell access tries to approve its own order, and the attempt must fail or be detected.

### P1-1: The live data provider sits on the paper-trading critical path

The draft requires "one validated live data provider" for alpha but selects none. The only US-equity data adapters upstream are Databento (paid, especially for live data) and Interactive Brokers (needs an account, a Gateway or TWS process, and market-data subscriptions). Approvals, the journal, the worker lifecycle, the UI and MCP paper flows should not wait on a commercial and legal decision.

**Recommendation:** split Phase 3.
- **Paper (replay):** drive the sandbox, or a `BacktestEngine` paced in real time, from catalog data at 1×–N× speed. This tests every approval, journal, stop and UI path with no credentials, and it is deterministic in CI.
- **Paper (live feed):** add one provider later, behind the same feed boundary.

Use quotes or trades for live paper where licensing allows. A minute-bar-driven sandbox inherits the same intrabar ambiguity as backtests, and live bars only arrive at the bar's close.

### P1-2: The strategy isolation model contradicts itself and protects the wrong boundary

- The sandbox paper worker *must* have network access and the provider credentials, because Nautilus data clients run inside the node, in the same process as strategy code. "No network or host secrets" for strategy execution (ADR-010) is incompatible with ADR-004/007's in-process sandbox, unless the feed is split out. Options: a Clipper feed process that owns credentials and serves normalized data to a custom Python data client over a Unix socket, or upstream's Redis-backed external message bus, which adds Redis.
- "Only trusted built-in strategies run until isolation passes" breaks journeys 2 and 3. Their whole point is running *user- or AI-authored* strategies.
- Locally, an agent with a shell can already run arbitrary Python as the user. Sandboxing the strategy adds **no** protection against that agent. Isolation matters for (a) third-party strategy files of unknown origin, (b) shell-less MCP hosts and (c) Cloud.
- Risk limits "enforced outside strategy code" are still enforced *inside the same Python process*. Non-adversarial code respects them; malicious code can monkeypatch them.

**Recommendation:**
- Redefine "trusted" as **a workspace file at a recorded content hash that the human acknowledged running**. A WebAuthn approval of a strategy hash fits naturally with P0-3.
- Defer OS-level sandboxing for local alpha, and record it as a Cloud and untrusted-code prerequisite.
- Keep the seam: workers start through one launcher that can later add bubblewrap, nsjail or rootless Podman.
- Document that in-process limits are guardrails, not a security boundary.

### P1-3: Persistence and transaction boundaries are vague and partly contradictory

- "Single application writer for metadata" conflicts with the sequence diagram, where the worker persists sequenced events. "Commit event plus projection atomically **when feasible**" is not a decision.
- With an in-process simulated venue, the journal is the only truth (P0-2), so its consistency rules must be exact.

**Recommended concrete design:**
1. `app.db`: app metadata, approvals, run manifests. The gateway is the only writer.
2. `accounts/<id>.db`: one SQLite WAL file per paper account. The account's worker is the only writer; the gateway and UI only read it. An exclusive `flock` on the file is the **ownership lease**. The kernel releases it when the process dies, which replaces the custom lease and heartbeat logic for ownership. Keep heartbeats for feed health only.
3. Commands go from app to worker over a Unix socket. Each carries a `command_id`. The worker inserts it into a `commands` table with a `UNIQUE(command_id)` constraint *before* acting, and acknowledges only after commit. The app retries with the same ID until it gets an ack or the lock shows the worker dead. Delivery is then idempotent, and the draft's "UNKNOWN, freeze, reconcile" path is no longer needed for paper.
4. Derive `ClientOrderId` deterministically from the approval or command ID. Check upstream's length and character limits on the pinned version. A replayed command then cannot create a second order.
5. An actor subscribed to all order and position events writes each event **and** its projection in a single transaction. That is a hard rule, not "when feasible". Use `synchronous=NORMAL` in WAL mode: a power loss can drop the last transaction but not break consistency. Because the simulated venue's state dies with the process, consistency is what matters.
6. Workers run independently of the gateway, as `systemd-run --user` transient units on Linux. A gateway crash or upgrade then does not kill paper workers, and the restarted gateway re-attaches through the lock and socket. As a bonus, cgroup `MemoryMax`, `CPUQuota` and `RuntimeMaxSec` cover ADR-004's resource caps without custom code.
7. Reduce account states to `ready`, `running`, `stopped`, `recovery_required` and `archived`, with *degraded/stale feed* as a flag rather than a state. Reduce job states similarly, dropping `cancel_requested` unless the UI really needs it.

### P1-4: Financial correctness claims go beyond what upstream provides

- **"Default reject ambiguous same-bar execution":** upstream has no rejection mode. Bar execution always simulates an O→H/L→C path, and `bar_adaptive_high_low_ordering` is the only adjustment. Options are a Clipper post-run detector, which flags any bar where a stop and a target both fall inside one bar's range, or using finer data. Recommend the detector, plus the documented adaptive ordering, plus a warning in the results.
- **Bar timestamps:** the catalog must store `ts_init` at bar **close**. Charts conventionally plot bars at **open**. Specify both, and specify the mapping for trade markers: a fill at time *t* belongs to the bar whose interval (open, close] contains *t*. Otherwise markers will be off by one bar. Lightweight Charts has no time-zone support; display in exchange time requires shifting timestamps, which the chart docs describe.
- **Account semantics:** the sandbox defaults to `MARGIN`/`NETTING` [verified, v1], and v2 changed default leverage to 10× for margin accounts. Pin `account_type=CASH`, `default_leverage=1` and `oms_type` explicitly in every config, with a fixture test. The cash model does not model T+1 settlement, good-faith violations, pattern-day-trader rules or borrow. Document this, and reject or flag strategies that would rely on it.
- **Fees:** US equities usually need a per-share commission with min/max, plus SEC and FINRA TAF fees on sells. Implement one custom `FeeModel` and pass the **same configured instance** to backtest and sandbox (v2 only, see P0-1). Record it in the run manifest.
- **Corporate actions:** the engine does not apply splits or dividends. With unadjusted prices, strategies see false gaps at splits. With adjusted prices, fills are wrong. Alpha rule: unadjusted prices only, refuse datasets that cross a known split or reverse split for the traded instrument, and label returns "price return, excludes dividends". Do not show benchmark comparisons against total-return indices.
- **Precision:** US equities trade in $0.0001 increments below $1.00 (Reg NMS Rule 612). Either use price precision 4 for all equity instruments or exclude sub-dollar names in alpha. Never let the JS client aggregate money: all P&L comes from the server as decimal strings, as the draft says, and the UI must never `parseFloat` and sum.
- **Metrics:** define Sharpe and Sortino annualization, the risk-free rate and return frequency in the results schema. Minute-bar Sharpe ratios that are silently annualized wrongly are a classic credibility failure.

### P1-5: Bounded authorization limits are mostly Clipper's job

Upstream `RiskEngineConfig` provides order submit/modify rate limits and per-order notional limits [verified]. Max position, max loss, deployment duration, instrument allowlists and allowed order types are **not** upstream. They need a Clipper pre-trade gate: a small risk actor or execution hook, tested independently.

Two further requirements:
- Define the loss limit's mark price, for example the last trade or mid. When the feed is stale, the gate must block new orders rather than evaluate a stale mark.
- Approvals for market orders need a **price collar**. The preview price and the fill price can be far apart after the human's delay.

Build emergency stop on upstream's trading-state control (HALTED / REDUCING; confirm the API in the pinned v2) plus cancel-all, rather than a parallel mechanism.

### P1-6: Scope versus estimate, and complexity that can be cut

Phases 1–4 sum to 16–31 working days for: a React terminal UI with Monaco, the FastAPI gateway, an OpenAPI client, WebSocket sequencing, CLI, MCP, a supervisor, a validated data catalog, deterministic backtests, live and paper workers, an approval system, recovery fault-injection, strategy sandboxing and a financial fixture suite. That estimate is not credible, and the doc itself warns not to treat agent hours as throughput.

**Cut or defer for alpha:**
- **Monaco.** Strategies are files in a workspace that users and agents edit with their own tools. Show read-only source with its hash in the UI, and drop the in-browser editor.
- **DuckDB/Polars.** The v2 catalog already provides `query(...)` and `query_data_arrow_stream(...)`. A fourth storage and query technology adds nothing for one user.
- **Live provider and standing deployments**, until replay paper works (P1-1).
- **Strategy OS sandboxing** (P1-2).

**Re-phase:**
- **Alpha-R (research):** import and validate data, run backtests, run them through MCP, show charts and results.
- **Alpha-P (paper):** replay feed, approvals, journal and stop/cancel, then a live feed.

Estimate each phase after the Phase 1 spike, not before.

### P1-7: The contributor licence model decides whether Clipper Cloud can be proprietary

ADR-011 proposes a "separate control plane" for a future Cloud, and the overview notes that the copyright notice does not establish IP assignment. The current `CONTRIBUTING.md` uses inbound=outbound plus DCO. Under that model, every external contribution is AGPL-only and Whalesback Systems is a licensee of it like anyone else. Any hosted offering that modifies or links Clipper must then comply with AGPL §13 for those parts, permanently. If a proprietary or dual-licensed Cloud is a goal, a CLA or copyright assignment must be in place **before the first external contribution**, because it cannot be applied retroactively without every contributor's consent. If an open-core Cloud with full §13 compliance is acceptable, inbound=outbound is fine.

**Recommendation:** add ADR-014 recording this choice, and get legal review before accepting any outside PR.

### P1-8: The local web surface needs explicit browser-attack defences

Beyond P0-3:
- Validate the `Host` header (DNS rebinding).
- Allow only an exact `Origin`, with no CORS wildcard.
- Make state-changing routes reject requests without a custom header or token, which blocks form-based CSRF from any website.
- Rate-limit approval attempts.
- Return no stack traces, as the draft already says.

Add negative tests for each. These are cheap now and painful to retrofit.

### P2 findings

1. **MCP SDK pin.** Specify `mcp>=2.3,<3` and write against `MCPServer`, not v1 `FastMCP` examples, which are in maintenance only. Test against each host's *negotiated* protocol version, since Claude Code and Codex may differ between 2025-11-25 and 2026-07-28. Under 2026-07-28 the server cannot call the client and the SDK lacks the tasks extension, so the draft's job-ID polling design is correct; keep it. Do **not** use MCP elicitation or host confirmation dialogs as approval, because the agent side mediates them (consistent with P0-3). The SDK's built-in MCP Apps extension could later render a backtest chart inside the host; note it as an option, not alpha scope.
2. **Dependency pin table.** Add one to the plan: `nautilus_trader==2.0.0rc9` (exact), `mcp~=2.3`, `fastapi==0.165.*` (0.x minors break; pin and upgrade deliberately), `pydantic~=2.14`, `lightweight-charts@5.3.0`, CPython 3.13. Lock with `uv.lock` / `package-lock.json`. Add a scheduled job that checks for Nautilus RC and final releases.
3. **Third-party notices.** The draft mentions only TradingView attribution. When dependencies land, add rows to `THIRD_PARTY_NOTICES.md` for:
   - NautilusTrader: LGPL-3.0. It is compatible with AGPL. If Clipper is ever shipped as a frozen bundle (PyInstaller, AppImage), users must be able to replace the library.
   - Lightweight Charts: Apache-2.0. Reproduce its NOTICE text in the root `NOTICE`, as Apache §4(d) requires, and keep the attribution link or logo.
   - The Rust crates bundled inside the Nautilus wheel, taken from its metadata.
   - MCP SDK, FastAPI, Pydantic and React (MIT), and Monaco (MIT) if kept.

   This is what the existing `CONTRIBUTING.md` checklist already requires.
4. **Wrong sandbox citation.** The overview cites the Rust `nautilus_sandbox` crate and says "Python integration requires pin-specific test". A Python `nautilus_trader.adapters.sandbox` module exists in both lines; cite it, and the v2 config fields above.
5. **WebSocket sequencing.** Define the `seq` scope (per stream per entity, not per connection), the snapshot-plus-resume protocol and the buffer limits. Server-sent events would be simpler for server-to-UI streams, because commands already travel over REST.
6. **Wording and brand.** "TradingView-style charting" in product copy invites trademark trouble; say "professional charting" instead. "Leviathan" appears without definition; define it or remove it.
7. **Performance targets.** Add a peak RSS budget per backtest worker, catalog size assumptions (500 symbols × 10 years of minute bars is roughly 500 million rows), and a cold-start target for loading the Nautilus wheel (about 180 MB in v1, 74 MB in v2).
8. **Chart plugins.** Use the official `session-highlighting` plugin for RTH/ETH shading, plus `user-price-lines` and `accessibility`. Drawing tools remain custom, so keep them out of alpha as the draft proposes.

## Decisions endorsed after challenge

- No custom matching engine, no fork (ADR-002 rationale). The P0-2 analysis strengthens this.
- One node per process (ADR-004), confirmed upstream.
- One command path for web, CLI and MCP, with no MCP shell, SQL or file tools (ADR-006).
- No real-execution adapter in alpha builds. The draft's build-level separation beats a toggle, and it is the reason to reject option D in P0-2.
- Decimal strings at API boundaries, provenance-rich immutable datasets, and independent hand-calculated fixtures (ADR-013).
- Separate stop, cancel and flatten actions, where flatten is a new authorized order and a fill is never promised.
- Deferring remote MCP, Cloud auth and multi-tenancy.

## Unresolved questions for the maintainer

1. Is session-scoped paper trading (P0-2 option A) acceptable for alpha, with replay-based resume (option B) as a later epic?
2. WebAuthn approval (P0-3 option 1) or amending issue #1's acceptance criterion (option 3)?
3. Will Clipper Cloud ever be proprietary or dual-licensed? If so, adopt a CLA now (P1-7).
4. Is the split into Alpha-R and Alpha-P acceptable, with live provider selection deferred until replay paper works?
5. Data budget: is Databento live or IBKR market data acceptable for Alpha-P, and does its licence allow recording the consumed stream (needed for option B)?
6. Which Linux distribution is the documented reference machine (glibc ≥ 2.34; systemd user session available)?

## Recommended changes to the proposal documents

Owner: the draft author, during reconciliation.

- `adr/0001`: rewrite ADR-002 (P0-1), ADR-007 (P0-3), ADR-008 (P0-2, P1-3) and ADR-010 (P1-2). Amend ADR-003 to drop DuckDB/Polars and ADR-009 to drop Monaco. Add ADR-014 (contributor licensing) and ADR-015 (local threat model: same-user agents).
- `overview.md` §4–5: replace the UNKNOWN-reconcile flow with the idempotent command and flock design. State that Nautilus cache database backing is forbidden for sandbox accounts. Add the price collar and the timestamp and marker mapping.
- `implementation-plan.md`: re-phase into Alpha-R and Alpha-P, add the dependency pin table, and add red-team and kill-test gates. Remove the 3–5 week figure until the Phase 1 spike reports.
