# Maintainer decisions on the alpha architecture review

**Date:** 2026-11-25
**Tracking:** issue #1, PR #2
**Decided by:** the maintainer for Whalesback Systems LLC

These answer the six open questions in
[`claude-review.md`](claude-review.md#unresolved-questions-for-the-maintainer).
They are inputs to reconciliation: the proposal documents (`overview.md`,
`adr/0001-alpha-architecture-decisions.md`, `implementation-plan.md`) still
need revising to match them. The section "Reconciliation still required" below
lists what changes.

## D1. Paper trading in alpha is session-scoped, and there is no live trading

**Decision:** alpha paper trading is session-scoped. A session ends when its
worker stops for any reason, including a crash, reboot or upgrade. Alpha has
no live trading: no real-money order routing, and no execution adapter able to
reach a real account. Persistence that lets a session resume after a restart
is wanted later, not in alpha.

**Required in alpha: trade logging.** Every paper session keeps a durable
journal that survives the worker exiting. The journal records:

- commands and approvals, with actor, reason and policy revision
- order submissions, acceptances, rejections, modifications and cancellations
- fills, with price, quantity, fees and the timestamp of the data that drove them
- account cash and positions after each change
- how the session started and ended (stopped by the user, emergency stop, worker crash, feed failure)

The journal is the session's ledger of record. It can be exported, and it
stays readable after the session ends. A worker that dies mid-session leaves
the session marked *interrupted* with its log intact. A new session starts only
when the user asks for one; Clipper never resets funds silently.

**Deferred:** resuming a session after a restart. The review's option B
(replaying recorded data and commands) and option C (adding a state snapshot to
the Nautilus sandbox upstream) are the candidates. The alpha journal schema
must keep this possible, which means recording a command ID and data timestamp
for every event.

**Interpretation to confirm:** "no live trading" is read here as *no
real-money execution*. Paper sessions driven by a live market-data feed remain
in scope for Alpha-P, after paper sessions driven by replayed data (see D4 and
D5).

## D2. Strong AI authorization is a future requirement, not an alpha one

**Decision:** issue #1's acceptance criterion is reworded. In alpha, approvals
guard against agent *mistakes*. They do not hold against a same-user agent that
has shell access. Future releases must support approvals that such an agent
cannot produce.

**Alpha:**
- Order-changing actions from AI still need explicit human approval in the
  Clipper UI or CLI.
- The server refuses approval and policy routes for the MCP token.
- Each approval is bound to a hash of the exact intent, so adding WebAuthn
  later needs no API change.
- The docs publish the local threat model. Same-user agents can read Clipper's
  files, its API token and the data-provider keys.
- The audit journal is hash-chained, so edits made outside Clipper are
  detectable even though they can't be prevented.

**Future (required before real-money trading, Clipper Cloud, or running
strategies from unknown sources):**
- Approvals require proof of human presence that an agent cannot produce, for
  example WebAuthn with user verification over the intent hash.
- Credentials are isolated from agents.

**Machine note:** the reference user is in the `docker` group (see D6), and
access to the Docker socket is root-equivalent. Running Clipper as a separate
OS user would not keep a same-user agent out on this machine. That is one more
reason to prefer human-presence proof over OS user separation in the future.

## D3. Licensing: AGPL core, dual-licensing rights kept, CLA before the first outside contribution

**Decision:**
- The self-hosted core stays open source under AGPL-3.0-or-later.
- Clipper Cloud may be proprietary.
- Whalesback Systems LLC keeps the ability to dual-license Clipper Terminal.
- A Contributor License Agreement is required before the first external
  contribution is accepted.
- **The CLA text must go through legal review before it is adopted.** Until
  then, no external contribution is merged.

**Consequences:**
- `CONTRIBUTING.md` now states the CLA requirement and the merge hold.
- Counsel should confirm that the CLA grants Whalesback Systems LLC enough
  rights to relicense or sublicense contributions, covers contributions made
  for an employer (a corporate CLA), and is compatible with the existing DCO
  sign-off.
- Possible starting points to hand counsel: Apache-style individual and
  corporate CLAs, and the Harmony agreements. These are suggestions, not
  recommendations.
- Choosing CLA signing tooling, such as a GitHub CLA bot, is part of adoption.
- Third-party code keeps its own licenses (NautilusTrader under LGPL-3.0,
  Lightweight Charts under Apache-2.0, and the rest). Dual-licensing covers
  only code Whalesback Systems LLC owns or has been granted rights to.
  Proprietary distribution still has to comply with every dependency's terms.

## D4. Phasing: research first with MCP established first, then paper

**Decision:** split alpha into **Alpha-R** (research), then **Alpha-P** (paper).
In Alpha-R, the MCP interface comes first.

**Alpha-R order:**
1. Foundation: locked dependencies, CI, domain DTOs, application services and
   the engine spike.
2. **MCP vertical slice:** import a synthetic or user-supplied dataset, check
   its coverage, run a backtest as a job, poll its status, fetch the results
   and the trade log. Everything goes through the application services, from
   Claude Code and Codex, with no web UI required.
3. CLI on the same services.
4. Web UI against the same services: chart, results and trade markers.

**Alpha-P order:**
1. Paper sessions driven by replayed data: approvals, journal, stop, cancel,
   emergency stop, plus MCP tools to prepare orders and view state.
2. A live-feed paper session with one provider (see D5).

The MCP tool contracts are therefore the first public interface to stabilize.
The web UI must not need any application capability that MCP lacks, except
human approval.

## D5. Data: no budget yet; Databento is the leading paid candidate, and free options must work

**Decision:** no data budget is set. Databento is the leading paid candidate.
Its adapter exists in both Nautilus release lines. Free options must be
first-class, so Clipper is usable without paying for data.

**Consequences:**
- Synthetic fixtures and user-supplied CSV or Parquet import are the free path
  and the default for CI. Alpha-R must be fully usable with them.
- Alpha-P's first paper mode uses replayed catalog data, so it needs no paid
  feed either.
- The provider spike compares Databento (historical and live US equities,
  current pricing, any new-account credit, licence terms for local use and for
  *recording* a live stream, which D1's future resume needs) against free or
  low-cost sources.
- Every source is checked against its terms of service before adoption.
  Sources that forbid automated access or redistribution are excluded, and so
  is scraping unofficial endpoints.
- Nothing ships with provider credentials or licensed data, and CI never uses
  paid keys.
- A data budget is set after the spike reports actual costs.

## D6. The reference machine is the maintainer's workstation

Recorded from the machine on 2026-11-25:

| Item | Value |
|---|---|
| OS | Pop!_OS 24.04 LTS, kernel 7.0.11, x86-64 |
| glibc | 2.39 (meets the `manylinux_2_34` floor of the Nautilus v2 wheels) |
| CPU / RAM | AMD Ryzen 7 7700X (8 cores, 16 threads), 61 GiB |
| GPU | NVIDIA RTX 4090, proprietary driver 580.159.03 (added 2026-11-25 for the desktop review) |
| Storage | Local NVMe SSDs |
| Desktop | COSMIC. The session reports Wayland, with XWayland on `DISPLAY=:1`; the maintainer runs applications under X11. |
| Init | systemd user session available, so `systemd-run --user` workers are possible |
| Python | System 3.12.3. The project uses a uv-managed CPython 3.13, which is not installed yet. |
| Node | 24.18.0 through nvm |
| Isolation tools | bubblewrap 0.11.0, Docker 29.6.1 |
| Privileges | User is in `sudo` and `docker` (see D2) |

**Consequences:**
- Performance targets are measured on this machine.
- Headed browser and Playwright tests run against the X11/XWayland display.
  CI runs headless on Ubuntu 24.04.
- The browser UI does not depend on the display server. Nothing in alpha may
  require Wayland-only or X11-only APIs.

## Reconciliation still required

Owner: the draft author, during reconciliation. Maintainer sign-off comes
after.

- **ADR-002:** v2 line, exact RC pin, CPython 3.13 (review P0-1; no
  maintainer objection was raised).
- **ADR-007:** split into an alpha form and a future form, per D2.
- **ADR-008:** session-scoped paper trading, the journal as ledger of record,
  resume deferred, and Nautilus cache database backing forbidden for sandbox
  accounts (D1, review P0-2 and P1-3).
- **ADR-010:** "trusted" means a workspace file at a hash the human
  acknowledged; OS sandboxing is deferred (review P1-2).
- **ADR-011:** add the dual-licensing goal and the CLA gate, and add ADR-014
  for contributor licensing (D3).
- **ADR-012:** free data path first, Databento as candidate, budget after the
  spike (D5).
- **Implementation plan:** Alpha-R (MCP first), then Alpha-P (replay, then
  live feed); the dependency pin table; red-team and kill-test gates. Drop the
  3–5 week figure until the Phase 1 spike reports (D4, review P1-6).
- **Overview:** reference machine (D6), local threat model (D2), and
  trade-log requirements (D1).

## Follow-up decisions from the second review (2026-11-25)

These answer the questions in
[`claude-review-2.md`](claude-review-2.md#questions-for-the-maintainer).

### D7. XWayland is the default display mode on Linux

**Decision:** approved. Clipper runs under XWayland (`GDK_BACKEND=x11`) by
default, so detached windows can be placed and restored. Native Wayland stays
a tested secondary mode.

**Consequence:** under X11, any same-user program can read the screen and
inject input into Clipper's windows. This is accepted for alpha under D2 and
ADR-015. Future approvals must rely on proof of human presence, which holds
under either display mode.

### D8. MCP is the primary AI control interface

**Decision:** AI agents control Clipper through MCP tools. Driving the UI by
input injection, screenshots or computer use is not a supported control path.

**Consequences:**
- Every capability an agent needs is exposed as an MCP tool. The one exception
  is human approval, which stays out of MCP.
- Tool documentation and host setup guides tell agents to use MCP and not to
  automate the UI.
- In alpha this is a policy and design rule, not an enforced boundary: under
  X11 (D7), Clipper cannot technically prevent UI automation.

### D9. No in-app code editor in alpha

**Decision:** Monaco is removed from alpha. Strategies are workspace files
edited with the user's or agent's own tools. The UI shows the source read-only,
with its hash.

### D10. Phase 0 may evaluate Tauri 3 with the CEF runtime

**Decision:** if WebKitGTK fails the chart targets on the reference GPU, Phase 0
may evaluate Tauri 3 with the CEF (Chromium) runtime.

**Consequence:** evaluating it is allowed. Adopting it is not decided: it
would mean taking on an alpha dependency, and it needs an amendment to
ADR-017 after the evidence is reviewed.

### D11. Alpha-R ships as a `.deb` only

**Decision:** Alpha-R packaging is a single `.deb` for the reference platform.
AppImage and Flatpak are deferred.

### D12. Codex reviews the reconciled design

**Decision:** Codex performs the independent review of the reconciled
documents. Claude wrote them, so Claude's reviews are not independent of that
text. The review is written to `docs/architecture/codex-review.md`.
