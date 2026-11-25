# Alpha architecture decision records

Every record below is **proposed**, as of 2026-11-25, tracking issue #1. This
revision reconciles the draft with [`claude-review.md`](../architecture/claude-review.md),
[`maintainer-decisions.md`](../architecture/maintainer-decisions.md) (D1–D6) and
the maintainer's desktop-first direction. When a record is accepted, split it
into its own immutable ADR. Revise accepted records by superseding them, never
by rewriting.

| ID | Decision | Alternatives and consequences | Acceptance evidence |
|---|---|---|---|
| ADR-001 | **Runtime ownership:** a desktop-first Tauri 2 (2.12.x) Rust shell, a shared React/TS UI, and a Python 3.13 / FastAPI local service. CLI, MCP and desktop share one set of application services. Rust is limited to the shell plus Nautilus's own core; no Nautilus crates are linked into the shell. | A browser-only product conflicts with product direction. A Rust trading service would duplicate the engine and turn LGPL into a static-linking case. Tauri 3 is in alpha, so keep the shell thin and plugin-light. | The desktop spike passes (see `desktop-validation.md`); clean `.deb` install; one shared OpenAPI client; desktop E2E through WebdriverIO or `tauri-driver`. |
| ADR-002 | **NautilusTrader v2**, exact RC pin (`2.0.0rc9` today), moving to `2.0.0` final through one PR that runs the full fixture suite. CPython 3.13. Adapter layer in `trading/`; no v1/v2 compatibility layer. | v1 is legacy upstream (security backports only, for about three months), its catalog schema is incompatible, and its sandbox hard-codes fill and fee models. RC churn stays contained in the adapter. No RC for any future real-money release. | Engine smoke inside the packaged environment; capability matrix; deterministic backtest fixture; sandbox smoke with an explicit fee model. |
| ADR-003 | The Nautilus v2 Parquet catalog is canonical, with immutable dataset manifests. `app.db` (SQLite WAL, single writer) holds metadata, workspace and audit. Session journals are separate files. No DuckDB or Polars in alpha. | All data in one relational database, or unversioned CSV: simpler, but weaker on scale and reproducibility. A fourth query engine adds nothing for one user. | Round-trip fixture with checksums; coverage; concurrent reads from pinned snapshots; backup and restore; schema migration. |
| ADR-004 | One engine node per worker process. On Linux, workers run as transient systemd user units with cgroup limits, behind a `WorkerLauncher` interface. | Running several nodes in one process is unsupported upstream. A distributed queue is premature. Tying workers to the service or shell process would stop them on restart. | Parallel jobs; cancellation; timeout and memory caps enforced; a worker survives a service restart; crash isolation. |
| ADR-005 | Python strategies, shared between backtest and paper through the engine lifecycle. No Pine interpreter. Strategies are workspace files identified by content hash; no in-app editor in alpha. | Pine compatibility or vectorized-only strategies widen scope and differ in semantics. Monaco is deferred because agents and users already edit files with their own tools. | A versioned sample EMA strategy runs in both modes with identical fee and fill configuration, and the differences are documented. |
| ADR-006 | MCP is the **primary AI control interface** (D8): first-class, and it **comes first** (D4). UI automation is not a supported agent path. Official Python SDK v2 (`mcp>=2.3,<3`) over stdio. Scopes: `research:read`, `workspace:read`, `workspace:write`, `paper:prepare`. Approval and policy routes are refused to MCP tokens. | Direct engine or database access bypasses policy. Remote MCP is deferred to Cloud. Elicitation or host dialogs are not approval. | Claude Code and Codex at their negotiated protocol versions; the research slice works with no window; workspace changes converge across windows; scope-denial tests. |
| ADR-007 | **Phased authorization (D2).** Alpha: human approval in desktop or CLI, bound to an intent hash, single-use and expiring; MCP can only prepare intents; the threat model is documented. Future (before real money, Cloud or untrusted strategies): proof of human presence, such as WebAuthn, and credentials isolated from agents. | A UI toggle or unrestricted agent orders are too fragile. Strong authorization now would delay alpha. | Negative tests for expiry, replay, tampering, cross-session use and scope; a red-team test in which an agent tries to approve its own intent through MCP is refused. The test also records which paths outside MCP still work in alpha (REST with the desktop session token, X11 input injection into the UI, direct database edits) and which are detected (edits to past audit entries, through the hash chain). |
| ADR-008 | **Session-scoped paper trading (D1).** The journal is the ledger of record: one SQLite file per session, a single writer, a `flock` lease, idempotent commands, and event plus projection in one transaction. A restart ends the session as *interrupted*. Nautilus cache database backing is forbidden for sandbox sessions. Resume is deferred. | Upstream cannot restore sandbox state: balances are the only seed, and fill and position reports are empty. Persisting the cache would bring back "working" orders that never fill. Replay-based resume (review option B) is the future path. | Kill tests at submit, ack, fill and persist; no duplicate order from a retried command; the interrupted session's journal is intact; no silent reset. |
| ADR-009 | Lightweight Charts 5.3 and its official plugins; one shared React UI. Docked panels first, then detachable native windows. Workspace state lives in the service. Indicators are computed in the service. | A custom renderer is unnecessary. Indicators computed in JS would diverge from what the agent sees. | Chart performance inside the Tauri webview; detach and reattach; multi-monitor restore under XWayland; accessibility; attribution. |
| ADR-010 | **Strategy trust:** a strategy is trusted when it is a workspace file at a hash the user acknowledged. No OS sandbox in alpha. The worker launcher is the seam for adding bubblewrap or a container later. | Local sandboxing gives no protection against a same-user agent with a shell. Paper workers with a live feed need network access and credentials, so isolation needs the feed split out first. | A strategy is refused without acknowledgement of its hash; residual risk documented; prerequisites for untrusted code recorded. |
| ADR-011 | AGPL-3.0-or-later core (confirmed, D3). Third-party notices, and data entitlements tracked. Clipper Cloud is a separate product that may be proprietary. | A permissive licence would allow closed derivatives. A network boundary alone does not settle AGPL questions. | Licence inventory (Python, Rust crates, npm) in CI; attribution visible; legal and market-data review before commercial use. |
| ADR-012 | US equities and ETFs, daily and minute bars. **Free data first** (D5): fixtures and user CSV/Parquet. One paid provider, with Databento leading, chosen through a spike for Alpha-P stage 2. Budget set after the spike. | Multiple asset classes or tick data widen licensing and modelling. A paid feed on the critical path would block development. | Provider cost, terms and coverage matrix; correct timestamps and sessions; validated symbol mapping; terms-of-service check for every source. |
| ADR-013 | Financial correctness is a release gate: run manifests, independently computed expected results, an ambiguity detector, explicit cash-account configuration, one shared fee model, and price-return labelling. | Treating attractive backtest metrics as evidence of correctness invites leakage and false confidence. | Hand-calculated fixtures covering fees, precision, partial fills, P&L, look-ahead, split refusal and bar-timestamp mapping; reproducible across runs. |
| ADR-014 | **Contributor licensing:** a CLA is required before the first external contribution, to keep dual licensing possible. The agreement goes through legal review before adoption, and nothing external is merged until then. DCO sign-off stays. | Inbound=outbound alone would make every outside contribution AGPL-only and block proprietary Cloud use of it. | Counsel-approved CLA text; signing tooling chosen; `CONTRIBUTING.md` links the agreement. |
| ADR-015 | **Local threat model:** same-user agents, including those with Docker group access, are inside the OS trust boundary. Alpha controls guard against mistakes and detect tampering. | Separating Clipper into its own OS user would not help while the user's group membership makes agents root-equivalent. | Threat model published; red-team results recorded. |
| ADR-016 | The **shell owns presentation and the service launch or attach; the OS service manager owns lifetime.** On Linux that is a systemd user unit, plus a `service.json` discovery file and an authenticated handshake. No Tauri sidecars and no `tauri-plugin-shell`. | Sidecars are killed on normal exit and orphaned on a crash. A detached process with no supervisor does not restart cleanly. | No duplicate service; close, reopen and shell-crash continuity; explicit safe shutdown; spoofed or stale endpoints rejected. |
| ADR-017 | **Linux packaging and display:** one `.deb` containing the shell, a standalone CPython 3.13, a relocatable uv virtual environment and the user units, built on an Ubuntu 22.04 base. XWayland by default (`GDK_BACKEND=x11`, approved in D7), with Wayland as a tested secondary mode. Validate WebKitGTK on NVIDIA. `.deb` only for Alpha-R (D11). | A frozen PyInstaller binary weakens LGPL replaceability. AppImage and Flatpak are deferred. Wayland cannot position windows. If WebKitGTK fails, Phase 0 may evaluate Tauri 3's CEF runtime (D10); adopting it requires amending this ADR. | Clean install on the reference machine; offline launch; upgrade and uninstall keep data; display and GPU matrix recorded. |
| ADR-018 | **Windows later:** platform-specific code sits behind interfaces (service manager, worker launcher, command transport, locks, paths, webview origin). No Linux-only dependencies in the service. | Building Windows now would double the test matrix. Ignoring it now would bake systemd and Unix sockets into the core. | Portability rules in `overview.md` §11 pass review. A Windows build spike happens before Windows work is scheduled. |

## Changes from the previous draft

- ADR-002 changed from preferring 1.x to v2.
- ADR-007 and ADR-008 rewritten for D1 and D2.
- ADR-003 drops DuckDB and Polars; ADR-005 and ADR-009 drop Monaco from alpha.
- ADR-010 redefines what "trusted" means.
- ADR-014, ADR-015 and ADR-018 are new.
- ADR-016 replaces "compare sidecar packaging" with "no sidecars", based on
  the shell plugin's exit behaviour.
- ADR-017 sets XWayland as the default and adds the NVIDIA and WebKitGTK
  checks.

## Maintainer answers

The questions raised in the second review are answered in
[`maintainer-decisions.md`](../architecture/maintainer-decisions.md), D7–D12:

- XWayland default: approved (D7).
- MCP is the primary AI control interface (D8).
- Monaco is out of alpha (D9).
- Phase 0 may evaluate Tauri 3 with CEF (D10).
- Alpha-R ships as a `.deb` only (D11).
- Codex reviews the reconciliation (D12).

## Review protocol

The [second review](../architecture/claude-review-2.md) covers the desktop
amendment and this reconciliation. Claude wrote this reconciliation, so Codex
reviews it independently (D12) before sign-off. The
maintainer approves the reconciled design. Only then is the backlog created.
No implementation happens under issue #1.
