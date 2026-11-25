# Phase 0 validation spike (the acceptance evidence)

**Status:** not executed.
**Revision:** 4 (2026-11-25).
**Feeds into:** ADR-001/002/004/005/008/013/016/017/019/020, and the Codex
follow-up P0s.
**Timebox:** 6–10 working days.

**Rules:**
- Run on the reference machine (`overview.md` §13).
- No production features, credentials or real execution.
- Use only **synthetic OHLCV bars plus bid/ask quotes, with provenance**
  (D25).
- Work on a disposable spike branch, and link the evidence from PR #2.
- The ADRs are accepted on this evidence.

The four proofs run in order and are reported independently. Polishing styling
or UI waits until 0A and 0B have reported.

Record every check as **PASS**, **FAIL** or **NOT RUN**, with the expected and
actual result. Phase 0 can only fail closed: an unrun check never counts as a
pass.

## 0A: Engine artifact and financial timing

1. **Simulation-only build (D13, ADR-002).**
   - Start from tag `v2.0.0rc9` and apply the four-part patch: per-adapter
     features in place of the `adapters` umbrella; per-adapter native
     registration guards in `crates/pyo3/src/lib.rs`; maturin features
     without `defi`, `hypersync`, `redis` or `postgres`; the excluded Python
     packages and `.pyi` stubs pruned.
   - Record `cargo tree -p nautilus-pyo3 -e features` run with the wheel's
     own flags.
   - Inspect the wheel manifest and native modules. Import factories: the
     sandbox and Databento must import; Binance, Interactive Brokers and
     blockchain must fail.
   - Record the tag, the patch diff, the toolchain, checksums and build time.
   - **If the build is infeasible, escalate. Do not relax D1.**
2. **Packaged engine.** From the installed runtime prefix:
   - a synthetic `BacktestNode` run;
   - a sandbox `LiveNode` fed by the replay feed, with explicit
     specifications;
   - results from the typed projection, with no pandas installed.
   - Measure NautilusTrader worker memory separately: report peak
     `memory.peak` (D26).
3. **Timing enforcement (D14, D22).** Run the **counterexample suite** under
   both mechanisms:
   - **(a) native:** a constrained upstream configuration;
   - **(b) Clipper gate.**

   The suite covers:
   - a strategy timer;
   - the end of the feed;
   - equal timestamps;
   - another instrument's data;
   - first-update ordering;
   - a stale feed;
   - resting orders;
   - partial fills;
   - bid/ask quotes arriving between bars.

   Reproduce Codex's four variations of the upstream example as baselines.
   Run the suite for the backtest and for the replay sandbox. **Prefer (a) if
   it passes everything.** Record which mechanism passes, and what upstream
   change (a) would need.
4. **Attribution and FIFO.**
   - Every fill carries an attribution record: the feed event ID or OHLC leg,
     or an explicit origin.
   - FIFO fixture: buy 1 @ 10 and 1 @ 20, then sell 1 @ 30. FIFO gives 20 and
     the engine gives 15. Quantities and cash must reconcile exactly.
   - Add fixtures for lot and tick refusal, and for an order-level fee
     minimum and cap across partial fills.
   - Check each against an independent ledger.

## 0B: Package, channels, lifecycle and durability

5. **Side-by-side packages (D23).**
   - Build `clipper-runtime-<v1>`, `clipper-runtime-<v2>` and `clipper` in an
     Ubuntu 22.04 container, each runtime at its final path.
   - Verify for every launcher and worker:
     - the interpreter symlink, `pyvenv.cfg`, `sys.executable` and
       `sys.base_prefix`;
     - `ldd`;
     - no leftover build paths.
   - Install offline with no developer toolchain.
   - Upgrade to v2 **while a v1 worker is active**:
     - v1's files must remain and the worker must keep running;
     - activation must wait behind the admission fence;
     - the user `daemon-reload` must run.
   - `prerm` must refuse removal while v1 is in use; `clipper runtime prune`
     removes it afterwards.
   - Uninstall must keep user data.
6. **Channels and authentication.**
   - **Unix socket:** a wrong-UID peer is refused, and so is a stale socket.
   - **Relay attempt:** a listener that relays to the real service must not
     obtain any credential, because native clients never use TCP and the
     webview gets its port over the socket.
   - **Port binding:** the service holds the port without `SO_REUSEPORT`.
   - **Installed webview:** authenticated REST reads and writes; stream
     ticket issue, consumption before the upgrade, a simultaneous double
     redemption, expiry, and wrong-origin or wrong-scope denial.
   - **Recorded values:** the actual HTTP and WebSocket `Origin` and `Host`.
     If the origin is opaque, record **FAIL** and test the Rust bridge.
   - **CSP:** a shell-served CSP header naming the current port, delivered
     before content loads. If that fails, fall back to a fixed per-user port.
   - **Grants:** bearer rotation on reattach; MCP grant rotation and revocation
     while connected (streams close; the principal is kept).
7. **Lifecycle.**
   - Second launch.
   - Closing the last window while a job runs leaves the tray visible.
   - `kill -9` the shell, then reopen.
   - Restart the service with a live worker: it is adopted, with
     `InvocationID`, lease and generation checked.
   - Takeover of an intent stuck in `starting`.
   - The lease file is opened `O_CLOEXEC`. A child that inherits a descriptor,
     and a replaced lock path, must both be refused.
   - "Stop service" drains, then reports.
   - Reboot, followed by takeover on the next start.
8. **Logout and the controller (D24, synthetic session).**
   - Two logins of the same user (or two sessions on a test seat).
   - A non-controller's actions are refused.
   - Transfer control while an approval is pending: the approval is
     invalidated and the transfer journalled.
   - Logout by the non-controller leaves the session running.
   - Logout by the controller, with working orders and queued submit and
     cancel commands: the session ends within 30 s as `logout`, cancellations
     resolve, and the journal is sealed.
   - Force the drain past 30 s: a supervised stop, then takeover marks the
     session `interrupted` with reason `logout_timeout`, and the history is
     preserved.
   - The gateway is unavailable during logout.
   - Lingering both on and off.
9. **Durability.**
   - The outbox, receipt and outcome chain.
   - Kills at each boundary.
   - Expiry after a lost receipt: the existing receipt is looked up, never
     marked undelivered.
   - The same ID with a changed digest returns `conflict`.
   - A gateway outage while the worker commits, then replay.
   - A crash between the journal's terminal commit and the `app.db` repair.
   - Sealed-journal triggers refuse INSERT, UPDATE and DELETE.
   - Disk full: the reserved block is used, or the session goes to
     `finalization_pending`.
   - Abrupt power loss (in a VM) with `FULL`.
   - **MCP halt:** an `on_stop` that cancels is not invoked; a delayed submit
     in the latency queue is withdrawn; a halt racing a dispatch; working
     orders stay live.

## 0C: Display, GPU and memory (D7, D17, D26)

10. **XWayland first** (`GDK_BACKEND=x11`), with `WEBKIT_DISABLE_DMABUF_RENDERER`
    unset and set to `1`:
    - no blank window at startup;
    - the pan/zoom protocol: **≥ 30 FPS sustained, target 60**;
    - two windows on two monitors: detach, **restore after relaunch**, and
      fall back when a monitor is unplugged;
    - resize and DPI changes;
    - tray on COSMIC;
    - **desktop memory < 1 GB** total PSS (shell, all webview processes and
      the service) with two windows open;
    - NautilusTrader peak memory reported separately.
11. **Native Wayland: diagnostic only.** Run the same matrix and record the
    results. They inform an escalation but are not a fallback.
12. **If XWayland fails:** stop and escalate to the maintainer (D17). CEF is
    evaluated only at the maintainer's direction.
13. **Webview least privilege:**
    - commands declared through `AppManifest::commands`;
    - a detached window is denied the main window's commands;
    - `on_navigation` and `on_new_window` deny navigation;
    - no token in arguments, logs, URLs or the bundle;
    - whether `xdotool` can drive the UI under XWayland versus Wayland, as
      threat-model evidence.

## 0D: Workspace contract proxy

14. With a synthetic workspace stub:
    - MCP reads a chart's state and changes its symbol, timeframe and one
      indicator.
    - Two windows update through **durable cursors**. Changes committed
      between the snapshot and the subscription are not lost.
    - A stale revision returns `conflict`.
    - A service restart keeps the cursors valid and resets presentation
      hints.
    - With every window closed, the result is `presentation: "pending"`.
    - The indicator values MCP returns match what the chart renders.
15. One desktop E2E smoke test through `tauri-driver` in external mode, on
    the reference machine and under Xvfb.

## Evidence format

For each check, record:
- the procedure;
- the version matrix (moving entries from candidate to tested, overview §14);
- the fixture provenance;
- expected versus actual;
- redacted logs and screenshots;
- measurements (warm and cold, with the GPU driver, display mode and
  WebKitGTK version);
- the verdict.

## Go / no-go

**Go only if every listed check passes:**
- **0A:** checks 1–4. The artifact must be a **conforming simulation-only
  build under D13**: no exception. Timing passes the full counterexample suite
  under one mechanism, and FIFO and attribution reconcile.
- **0B:** checks 5–9, including the relay, side-by-side upgrade, controller
  logout and timeout, seal, lease and halt tests.
- **0C:** check 10, **under XWayland**: 30 FPS sustained, detached-window
  restore, desktop under 1 GB, and NautilusTrader peak reported.
- **0D:** check 14.

**Any FAIL, or any infeasible artifact,** is escalated to the maintainer with
its evidence (D13, D17). There is no silent fallback to a browser product, a
relaxed D1, or another display stack.

**References:**
- [Tauri capabilities](https://v2.tauri.app/security/capabilities/)
- [Tauri CSP](https://v2.tauri.app/security/csp/)
- [WebDriver testing](https://v2.tauri.app/develop/tests/webdriver/)
- [Debian maintainer scripts](https://www.debian.org/doc/debian-policy/ch-maintainerscripts.html)
- [systemd.service `ExecStop` / `TimeoutStopSec`](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)
- [logind D-Bus API](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html)
- [SQLite `synchronous`](https://www.sqlite.org/pragma.html#pragma_synchronous)
- [SQLite triggers](https://www.sqlite.org/lang_createtrigger.html)
- [`flock(2)`](https://man7.org/linux/man-pages/man2/flock.2.html)
- [`openat2(2)`](https://man7.org/linux/man-pages/man2/openat2.2.html)
- Nautilus rc9: `crates/pyo3/Cargo.toml`, `crates/pyo3/src/lib.rs`,
  `python/pyproject.toml`, and `bar-execution.md`
