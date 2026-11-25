# Clipper Alpha 0.1 — phased delivery and release gates

Status: proposed for review in #1. This is a planning document, not a backlog or implementation commitment. Scope and estimates assume one maintained local Linux deployment, two coding agents plus independent review, readily available synthetic data, and a supported live data feed. Parallelize only once contracts are agreed; do not interpret agent hours as verified engineering throughput.

## Critical path

```mermaid
flowchart LR
  A[Architecture approval] --> F[Foundation and contracts]
  F --> S[Engine version and provider spikes]
  F --> U[UI shell and API client]
  S --> D[Data catalog and fixtures]
  D --> B[Backtest worker and evidence]
  B --> M[MCP vertical slice]
  U --> V[Visual backtest results]
  B --> V
  S --> P[Paper worker and safe order path]
  F --> P
  P --> R[Recovery and fault tests]
  M --> G[Alpha acceptance]
  V --> G
  R --> G
```

| Phase | Scope and dependencies | Rough elapsed effort | Exit gate |
|---|---|---|---|
| 0 | Independent Claude critique, revise, maintainer approve; no features yet | 1–2 days | Review recorded, decisions accepted, open blockers resolved or assigned to spikes |
| 1 | Monorepo, locked deps, CI, domain DTOs, API and event schemas, auth, supervisor skeleton; evaluate exact Nautilus/CPython/MCP pins and data provider | 2–4 days | Fresh Linux setup, engine smoke with synthetic dataset, capability report, verified SDK connectivity, no real-money adapter |
| 2 | Import/catalog validation, instrument registry, versioned strategy and run manifests; deterministic backtest worker; REST/CLI/MCP job interface. UI shell in parallel | 4–7 days | Known expected ledger fixture passes; two isolated jobs, cancellation and results from MCP; chart renders fixture |
| 3 | Chart trade markers, metrics and strategy editor; paper account, live read-only feed, sandbox engine, approved manual order and bounded strategy deployment | 5–10 days | Same strategy source used in both modes, real feed labeled correctly, audited paper lifecycle, no route to brokerage |
| 4 | Recovery/fault tests, strategy isolation, permissions, performance, install docs, end-to-end acceptance | 5–10 days | All alpha gates below, unresolved failures surfaced; maintainer release decision |
| Later | Advanced indicators/drawings, screening, replay, optimization, broader instruments, Cloud, broker paper, live brokerage | separate estimate | Separate acceptance and risk reviews |

Rough target: 3–5 calendar weeks for alpha with dedicated capacity and some overlapping work; 1–2 weeks for offline research vertical slice. Provider licensing, version compatibility, restart semantics and security may materially extend schedule, especially while agents work on other projects. No public beta or real-money date is promised.

## Workstream handoffs

- Foundation owner defines Pydantic DTOs, OpenAPI generation and test contracts before other agents implement.
- Trading/data agent owns instrument mapping, catalog, fixtures, engine adapter and worker; UI never invents financial results.
- UI agent owns workspace, chart rendering, watchlist, results and approval panel against contract fixtures and then real service.
- MCP/CLI agent owns host setup, scoped API access, job control and typed tools; cannot bypass policy.
- Independent reviewer owns adverse test cases, not implementation approvals of its own code. Keep changes small, use CI and record evidence; do not let agents repeatedly change shared contracts without review.

## Alpha release checklist

- [ ] Clean checkout on Linux, documented install with pinned dependencies; offline synthetic fixture works without credentials.
- [ ] Version-specific evidence for backtest and sandbox Python adapters, provider coverage and supported order types. Unsupported features explicitly rejected.
- [ ] Import and validate minute/daily fixtures; symbol, time zone, calendar, sessions and immutable snapshot hashes correct.
- [ ] Register example Python strategy with source hash; run backtest via CLI, MCP and web; inspect same results by ID, with fee and fill-model assumptions.
- [ ] Independently expected order/fill/accounting fixtures pass; test future data mutation does not alter prior decisions, timestamp availability, duplicate/missing data, commissions, quantity/price precision, insufficient cash, no fabricated intrabar ordering. Two repeat runs produce equivalent normalized artifacts.
- [ ] UI shows candles, volume, trade markers, equity curve, net and gross returns, drawdown, trades and warnings; results link to manifest. No mock financial numbers shown as live.
- [ ] MCP handshake and smoke from both Claude Code and Codex; tools list, job submit/status/results, cancellation, chart selection, paper account view. Pagination, redaction and permission denial verified.
- [ ] Real-time read-only provider feed drives sandbox fills; no outbound real-order adapter or route exists. Live data gap/staleness blocks new paper orders.
- [ ] Paper order approval bound to exact intent; expiry, replay, tampering, cross-account and scope tests. Standing strategy grant bounded; loss, notional, order rate and duration enforced outside strategy code.
- [ ] Paper worker continues when UI/MCP disconnects. Crash at submit/ack/fill/persist boundaries either restores correctly with evidence or halts recovery-required. No double fill, unreported reset, false success or unsafe automatic retry.
- [ ] Emergency stop, cancel working orders and separate flatten authorization tested; actual results reported rather than guaranteed.
- [ ] Trusted strategy-only fallback until isolated execution passes tests for secret/file/network access, process escape, CPU/memory and malicious output; no untrusted strategy uploads by default.
- [ ] UI performance measured on declared hardware against targets; local API tokens, origin restrictions, log redaction, backups and restore verified.
- [ ] License inventory, TradingView attribution, dataset entitlement documented; no unauthorized dataset in repository/release.
- [ ] Explicit exclusions and known limitations published, maintainer approves release.

## Risk register

| Risk | Severity | Mitigation / decision gate |
|---|---|---|
| 1.x / 2.x API incompatibility | High | Timebox spike, exact pin and matching docs, adapter tests; don't write cross-version abstraction prematurely |
| Inadequate equity feed or licensing | High | Compare candidates early; synthetic research slice independent; no provider claim before test/terms review |
| Sandbox restart cannot restore matching state | High | Durable journal plus safe halt; prove recovery before auto-resume; maintainer decide if limitation acceptable |
| Look-ahead/survivorship/intrabar assumptions | High | Independent fixtures, dataset provenance, explicit availability/calendar and conservative fill policy |
| AI generated code or prompt injection bypass | High | No arbitrary execution or direct DB access, restrict worker identity and network, explicit approvals and trusted sources |
| Duplicate commands or stale feed | High | Idempotency, leases, sequenced events, fail closed on ambiguity, fault injection |
| Public repository secrets or licensed data | High | Ignore rules, secret scan, synthetic CI data, review history before release |
| Overbuilding frontend or cloud | Medium | One workspace and vertical slice first; cloud auth, billing and scale later |
| Agent coordination and resource contention | Medium | Small workstreams, shared contracts, max two coding agents initially, review gates |

## Suggested backlog after design approval (not created yet)

Foundation and CI; NautilusTrader adapter; market data and quality; MCP/CLI; backtesting and financial verification; paper trading and recovery; charting/UI; strategy development; indicators/drawings; research/optimization; watchlists/screener; cloud readiness/security; future live brokerage. Each issue needs a testable acceptance gate, dependencies, ownership, explicit non-goals and evidence. Create epics after maintainer sign-off, not from this draft alone.
