# Alpha architecture decision records

Status for all records: **proposed**, 2026-11-25, tracking #1. Each decision can be split into its own immutable ADR when accepted. Revisions after approval should supersede rather than silently rewrite decisions.

| ID | Decision | Alternatives and consequences | Acceptance evidence |
|---|---|---|---|
| ADR-001 | Local-first Python modular monolith, React/TS browser, uv and npm lockfiles, FastAPI REST/WS, CLI and MCP sharing application services. | Desktop-native/Rust-only or microservices cost more initial integration; browser UI still needs secure local auth. | Fresh Linux install and E2E vertical slice from CLI and UI. |
| ADR-002 | Adopt upstream NautilusTrader behind version-specific adapter; stable 1.x preferred pending comparison with 2.x RC for simulated usage only. | Custom engine or fork duplicates financial risk and maintenance; RC may improve longevity but API may break. | Exact pin, supported Python wheel, adapter matrix, deterministic backtest and sandbox smoke; source references match pin. |
| ADR-003 | Native catalog/Parquet as canonical historical storage, immutable dataset manifests; SQLite metadata/audit and DuckDB/Polars analytics. | All data in relational DB or unversioned CSV simpler initially but weaker scale/reproducibility. | Round-trip fixture with checksums, coverage and isolated concurrent reads; backup restore and schema migration. |
| ADR-004 | One engine node per worker process; bounded supervisor and job queue, separate long-running paper workers. | In-process concurrent nodes unsupported upstream; distributed queue premature. | Parallel jobs, cancellation, timeout, resource cap and crash isolation tests. |
| ADR-005 | Python strategies shared across modes through engine lifecycle; no custom Pine interpreter. | Pine compatibility or vectorized-only strategies attractive but expand scope and semantics mismatch. | Versioned sample EMA strategy used in both backtest and sandbox with explicit environment differences. |
| ADR-006 | MCP first-class via official SDK over stdio, scoped client to same local API; no raw shell/SQL/credential tools. | Direct engine access bypasses policy and durability; remote MCP requires stronger auth. | Claude Code and Codex configuration examples plus actual interoperability test, scoped-token negative tests. |
| ADR-007 | Paper-only alpha with trusted human approval for AI orders and bounded deployments; real execution unavailable. | UI-only toggle or unrestricted agent orders too fragile. | Negative tests across all transports and strategy runtime, simulated order/cancel/stop tests and policy audit. |
| ADR-008 | Durable paper journal and explicit recovery-required mode when engine state cannot be restored safely. | Blind replay/reset risks duplicate fills or lost positions; custom matching engine rejected. | Kill/restart at order lifecycle boundaries; verify recovery or safe halt, no balance reset or duplicate accepted command. |
| ADR-009 | Lightweight Charts and Monaco, React state derived from typed API read models; independent drawing/indicator plugins. | Full proprietary TradingView charting library has different licensing; building rendering from scratch is unnecessary. | Chart perf fixture, resize and accessibility tests; attribution retained. |
| ADR-010 | Restricted strategy execution and local-only default network exposure; only trusted built-ins until isolation passes. | Python process alone cannot isolate malicious code. | Negative tests for secret access, filesystem escape, network, resource exhaustion and invalid outputs; document residual risk. |
| ADR-011 | AGPL-3.0-or-later per existing repo; third-party notices and data entitlements; future Clipper Cloud separate control plane. | GPL network-use gap; permissive license permits closed derivatives. Do not presume network boundary alone resolves AGPL. | Dependency/license inventory, attribution visible, legal/market-data review before commercialization. |
| ADR-012 | US equities/ETFs, daily/minute bars first, synthetic fixture offline; single live data provider chosen through spike. | Multi-asset and tick-level execution broaden data licensing and model complexity. | Provider capability/cost/terms matrix, correct timestamps and sessions, validated symbol mapping and data entitlement. |
| ADR-013 | Financial correctness is a release gate; source/run manifests, independent expected results, conservative ambiguous fill policy. | Treating attractive backtest metrics as evidence of correctness invites leakage and false confidence. | Hand-calculated fixtures with fee, price, partial fill where supported, P&L, look-ahead and split handling checks; reproducibility across runs. |

## Maintainer and Claude review questions

1. Confirm local Linux-first and US equity/ETF cash-long scope, or name a better initial asset class/provider. Is a paid market feed acceptable, and at what budget?
2. Stable 1.x preference vs early 2.x adoption: what exact tested feature/maintenance tradeoff justifies a pin? Which Python version works with all dependencies?
3. Can selected sandbox persist/recover open orders and balances faithfully? If not, approve fail-closed recovery-required mode and explicit account archival for alpha; is resumable paper trading a hard release requirement?
4. Is approval once per bounded deployment sufficient for paper orders from strategy code, with per-manual-order approval? How should default notional and expiry limits be set by user?
5. Which OS sandbox/container approach can safely isolate untrusted code without excessive local setup? Is trusted-code-only alpha acceptable until isolation tests pass?
6. Review shared API/worker event journal transaction boundaries, stale feed behavior, duplicate command delivery, price/quantity precision and chart/session timestamp mapping.
7. Is there any reason to split repositories beyond eventual Clipper Cloud? Confirm AGPL-or-later choice, source-offer process and IP/contributor governance with legal counsel before commercialization.
8. Confirm performance targets after measuring hardware and sample data; adjust estimates and scope before generating backlog.

## Independent critique protocol

Claude should read the exact proposed docs on the PR branch, inspect existing repository, check upstream APIs for the selected release line, identify counterexamples and alternatives, rank findings P0/P1/P2, and write a separate `docs/architecture/claude-review.md` with sources, reproduction steps for claims where possible, recommended changes, unresolved questions and a verdict. Do not label this proposal as independently reviewed yet. No code implementation in #1. Maintainer approves reconciled design and only then creates full implementation backlog.
