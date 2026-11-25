# Maintainer decisions on the alpha architecture review

**Date:** 2026-11-25
**Tracking:** issue #1, PR #2
**Decided by:** the maintainer for Whalesback Systems LLC

These answer the six open questions in
[`claude-review.md`](claude-review.md#unresolved-questions-for-the-maintainer).
They were inputs to reconciliation, which has since been applied to the
proposal documents (revisions 2 and 3). The decisions themselves are unchanged.
Where a consequence was worded too strongly, it is corrected inline and marked
*Corrected after the Codex review*.

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
- Each approval is bound to a hash of the exact intent.
  *Corrected after the Codex review:* the approval envelope is versioned now,
  with an explicit evidence type, so a future WebAuthn evidence type can be
  added without changing the intent binding. The exact future API is left
  open, and a protected verifier and confirmation display are still required
  (ADR-007).
- The docs publish the local threat model. Same-user agents can read Clipper's
  files, its API token and the data-provider keys.
- The audit journal is hash-chained.
  *Corrected after the Codex review:* this is a local integrity check. It
  detects corruption, edits to individual rows and truncation relative to the
  recorded head. It does **not** detect a consistent rewrite by a process that
  can write both stores (ADR-015).

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

## Reconciliation list (historical; applied in revisions 2 and 3)

These were the tasks for the draft author, and they have been carried out. The
current state is in the ADR file. P1–P8 were decided in D13–D21. Anything still
open is listed in the ADR file under "Open items".

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
ADR-015. Future approvals must rely on proof of human presence.
*Corrected after the Codex review:* whether that holds under either display
mode is unverified, and depends on a protected verifier and confirmation
display (ADR-007).

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

## Decisions on the Codex review questions (2026-11-25)

These answer pending items P1–P8 in the ADR file, and settle the open
reference to an external orchestration product.

### D13 (P1). D1 stands: the paper-only artifact gate is not relaxed

**Decision:** D1 is not amended. Paper trading comes first, so alpha ships a
**simulation-only NautilusTrader build**: built from the exact upstream tag,
with only the sandbox and Databento adapters, and with no execution factory
that can reach a real account. If Phase 0 shows the restricted build is not
feasible, the evidence comes back to the maintainer. Relaxing D1 is not a
fallback.

### D14 (P2). Execution timing and fixtures

**Decision:**
- `after_watermark` is the default: an order fills on the first eligible
  matching event after the decision's data watermark.
- `signal_close` is available only as an explicitly named, labelled option.
- The fee schedule is a configurable, versioned broker specification. Fixture
  values come from a published broker schedule.
- Cost basis is FIFO.
- Splits fail closed.

### D15 (P3). MCP can halt, not cancel

**Decision:** the MCP `paper:halt` grant only latches off new exposure and
stops the strategy. Cancel, flatten and re-enable are human-only. The human
grants and revokes `paper:halt` through the CLI.

### D16 (P4). Logout ends local paper sessions; upgrades wait

**Decision (alpha):**
- Logging out of the desktop session **ends the local paper session**.
- The end procedure **cancels open orders** and **preserves the history**: the
  journal is sealed with reason `logout`, stays readable, and can be exported.
- Package upgrades wait until all sessions have stopped. The service does not
  switch versions while a session is active.

**Later:** Clipper Cloud may run sessions independently of a desktop login.
That is out of scope for local alpha.

### D17 (P5). XWayland first; escalate on failure

**Decision:** XWayland is the priority display mode. If it fails the Phase 0
targets, **escalate to the maintainer** before trying alternatives.

**Consequence:** this narrows D10. Evaluating Tauri 3 with CEF, or relying on
native Wayland, happens only at the maintainer's direction after escalation,
not automatically.

### D18 (P6). Durability states and terminal records

**Decision:** approved as proposed.
- The UI shows three states, *received*, *venue response* and *filled*, and
  publishes each one only after its commit.
- On a clean end, the worker writes the terminal record. On interruption, the
  service writes it through fenced takeover.
- Either way there is one sealed ledger.

### D19 (P7). Market-data retention

**Decision:** approved as proposed.
- The journal always records feed identity, sequence and timestamps.
- It stores the driving market data only where the provider licence allows,
  and flags it (`driving_data_retained=false`) otherwise.
- Exports follow the same rule.

### D20 (P8). Licensing workflow: approved with conditions

**Decision:**
- NautilusTrader stays **replaceable** by the recipient, through the tested
  engine-override path.
- Source is published **only as required by the applicable licences**. Legal
  review determines what each release must provide. Expected candidates are
  the source of the modified LGPL engine build and Clipper's AGPL corresponding
  source for conveyed builds.
- **Every release requires maintainer and legal review** before it ships.

### D21. No named orchestration product in alpha

**Decision:** the orchestration product that earlier drafts named is out of
alpha scope, and alpha documents do not name it. They use the generic term
**"external AI orchestration tools"**: Clipper works with such tools only
through its public APIs and MCP, and never depends on one.

## Decisions on the Codex follow-up questions (2026-11-25)

These answer questions 1–3 of [`codex-review-2.md`](codex-review-2.md#6-remaining-open-questions-for-the-maintainer).
Questions 4 and 5 are still open. Revision 4 carries proposed defaults for
them, P9 and P10 in the ADR file.

### D22. Execution-timing enforcement: test both, prefer native support

**Decision:** Phase 0 tests two ways of enforcing `after_watermark` (D14):

- **(a) Native.** An upstream-supported rc9 configuration, constrained so that
  timers and end-of-feed drains cannot release orders against stale book
  state. If an upstream next-event settlement mode or hook can be added, that
  counts as native too.
- **(b) Clipper gate.** A narrow eligibility gate on the matching path: an
  order may match only against a book update derived from a new feed event for
  its own instrument.

**Native support is preferred.** Clipper adopts (b) only if (a) cannot pass
the counterexample suite. Proposing a native mode upstream is part of either
outcome.

### D23. Runtime versions install side by side

**Decision:** each release's runtime (CPython, engine, service code) installs
**side by side** with earlier ones, as a separately versioned package. A newer
runtime activates only once no paper session or job is using the old one. Old
runtimes are removed only by an explicit cleanup that checks they are unused.
This replaces "one package with versioned directories": Codex showed dpkg
deletes the old version's files from that layout during upgrade.

### D24. Logout timeout, supervised shutdown, and one controller per session

**Logout:**
- When a session's controlling login ends, the worker gets a **30-second
  graceful end**: halt the strategy, cancel open orders, record the outcomes,
  write the terminal record (`logout`) and seal the journal.
- If that runs past 30 s, a **supervised shutdown** stops the worker. It
  **preserves the history** and marks the session `interrupted` (reason
  `logout_timeout`), with whatever was committed.

**Multiple logins:**
- Multiple windows, including windows in different logins of the same user,
  may view a paper session.
- Each local paper session has **exactly one active controller**. Only the
  controller can issue human order-changing actions: approve, cancel, flatten,
  re-enable and stop.
- Control moves only by an **explicit control transfer**, which is recorded in
  the journal.
- The session's lifetime follows its **controller's** login. Logging out of a
  non-controlling login does not end the session.

### D25. Phase 0 fixture data, retention and export

**Decision:**
- Phase 0 uses **synthetic data**: OHLCV bars **plus bid/ask quotes**, with
  full **provenance** (generator, seed, version, declared corporate-action
  coverage).
- For all data, Clipper stores or exports market data **only when the licence
  allows**. Otherwise it records that the data was withheld and flags it
  (`driving_data_retained=false`, export field withheld).

### D26. Initial performance and memory targets

**Decision (initial targets, to be revisited after measurement):**
- **Chart interaction:** at least **30 FPS sustained**, with a **target of
  60 FPS**.
- ~~**Desktop memory:** under **1 GB**.~~ *Superseded by D27: no fixed
  memory cap.*
- **NautilusTrader memory** is measured **separately**, and its **peak usage
  is reported**. No limit is set yet.

*The earlier interpretation question about what "desktop" includes is moot
under D27.*

### D27. No fixed memory cap; require smooth operation and no leaks

**Decision (supersedes D26's 1 GB desktop limit):**
- There is **no fixed memory cap** for the desktop or the service.
- Clipper must **run smoothly**. D26's interaction target is unchanged: at
  least 30 FPS sustained, target 60.
- Clipper must **not leak memory**.
- NautilusTrader memory is still measured separately, and its peak is
  reported.

**How "no leaks" is tested.** These are initial criteria, adjustable after
Phase 0. Claude proposed the thresholds; the maintainer may change them.

- **Soak run.** A 2-hour scripted workload with two windows open. It pans and
  zooms, switches symbols and timeframes, opens and closes detached windows
  every 10 minutes, reconnects streams, and repeats fixture backtests.
  Memory (PSS) is sampled every 60 s for each process group: the shell, the
  webview processes, the service, and the NautilusTrader workers.
- **Steady state.** After a 15-minute warm-up, each group's memory must
  plateau. Growth over the rest of the run must stay under 5% of its
  post-warm-up level, and must not keep rising across repeated cycles.
- **Release.** Closing the detached windows and finishing the jobs must
  bring the shell, webview and service memory back to within 10% of the
  baseline taken before the cycle. No webview processes may be left
  orphaned.
- **Engine.** Twenty sequential fixture backtests in fresh workers must show
  no rise in per-run peak. A 2-hour replay-fed paper session must reach a
  plateau.
- **Reporting.** Peak and steady-state memory are reported for every group.

### D28. Architectural direction approved

**Decision (2026-11-25):** the maintainer approves the architectural direction
of revision 4, as amended by D27.

**What this approves:** the direction set out in the overview and ADR-001 to
ADR-020.

**What stays gated on Phase 0 evidence** (implementation plan, Epic 00E):
- accepting each ADR, or amending it;
- merging PR #2 and closing issue #1;
- creating the implementation backlog.

The numbered epics in the implementation plan (`fbcaf6a`) are the provisional
roadmap.
