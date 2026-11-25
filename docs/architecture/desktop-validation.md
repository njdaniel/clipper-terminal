# Phase 0 validation spike (before architecture approval)

**Status:** not executed.
**Reference:** issue #1, PR #2; ADR-001, ADR-002, ADR-013, ADR-016,
ADR-017; Codex review P0 findings.
**Timebox:** 4–8 working days for all four proofs.

Run on the reference machine (`overview.md` §13). GPU and multi-monitor work
needs that real hardware. Production features, credentials and real execution
are all out of scope; use synthetic data only. Work on a disposable spike
branch and link the evidence from PR #2.

The spike is **four proofs, reported independently and run in order**. They
sit on the critical path to approval, so do not polish styling or UI before
0A–0C have reported.

## Fixed starting point

- Tauri 2.12.x with only `single-instance` and `window-state`. **No
  `tauri-plugin-shell`.**
- CPython 3.13 from python-build-standalone, installed at
  `/opt/clipper/<version>/`. The environment is built **at that path** from
  locked, non-editable wheels.
- NautilusTrader `2.0.0rc9`: the ordinary wheel, for comparison only, and the
  restricted build (proof 0A).
- `mcp>=2.3,<3`; FastAPI; a systemd user unit; Lightweight Charts 5.3.

Record each result as PASS, FAIL or NOT RUN, with expected and actual
outcomes.

## 0A: Engine artifact and financial timing

1. **Artifact gate (D1, ADR-002).**
   - List the execution factories in the ordinary rc9 wheel, for comparison.
   - Build the restricted wheel from tag `v2.0.0rc9`, enabling only the
     `nautilus-sandbox` and `nautilus-databento` features and removing the
     Python modules of the excluded adapters.
   - Inspect the wheel and `_libnautilus`, and list the importable execution
     factories: only the sandbox may appear.
   - Record the tag, the patch diff, the toolchain, checksums and build time.
2. **Packaged engine.** From the installed prefix:
   - run a deterministic synthetic `BacktestNode` run;
   - construct a sandbox `LiveNode` with explicit fee, fill and latency
     specifications, fed by replayed data;
   - confirm results come from the typed event projection, with no pandas
     needed.
   Record import time and peak memory.
3. **Execution timing (ADR-013).** Run one fixture three ways:
   - zero latency, to show the same-close settlement;
   - the `after_watermark` policy on bars only, expecting the next bar's close;
   - `after_watermark` with finer execution bars, expecting the first
     subsequent update.
   Compare each against an independently calculated ledger. Include a bar
   where a stop and a target compete.

## 0B: Package, identity and lifecycle

4. **`.deb`.**
   - Build in an Ubuntu 22.04 container at the final prefix.
   - Verify that no build paths remain (grep the prefix and `pyvenv.cfg`),
     that `ldd` finds every ELF dependency, and that native imports work.
   - Install on the reference machine without developer toolchains, then
     launch offline.
   - Run the service, CLI and MCP with no development environment present.
   - Record the floor of the assembled package and its size.
5. **Identity and authentication on the installed package.**
   - The HMAC identity challenge succeeds, and the client sends no bearer
     before a valid proof.
   - Rejection cases: a spoofed listener on the recorded port, a stale
     `service.json`, a wrong version.
   - Authenticated REST reads and writes work.
   - Stream ticket issuance works, and the WebSocket connects using
     `Sec-WebSocket-Protocol`.
   - Record the actual `Origin` and `Host` values on HTTP and WebSocket from
     the WebKitGTK webview. If the origin is opaque, record FAIL and propose a
     transport.
   - Token rotation on reattach; concurrent shell, CLI and MCP clients.
   - Refusals: a CLI grant with a browser `Origin`, and an MCP grant on the
     approval and acknowledgement routes.
6. **Lifecycle.**
   - Second launch; closing the last window with a synthetic job active (the
     tray stays visible); `kill -9` on the shell, then reopen.
   - Service restart while a transient worker lives: the worker is adopted
     through its launch intent and generation.
   - Kill the worker, then check the service's **terminal takeover**: exactly
     one record, and the journal sealed.
   - "Stop service" with an active job: native confirmation, drain, and the
     outcome reported.
   - Upgrade to a second version with an active worker: side-by-side
     prefixes, and the old worker untouched.
   - Logout, with `PartOf=graphical-session.target`: drained, and the reason
     recorded.
   - Reboot: the next start performs takeover.
   - Uninstall: user data is kept.
7. **Durability.**
   - Run the outbox, receipt and outcome chain with a synthetic sandbox
     session.
   - Kill at each boundary: after approval and before delivery; after receipt
     and before the act; after the fill and before the commit.
   - Lost and duplicated retries; the same command ID with a changed digest
     returns `conflict`.
   - Disk full while writing the journal: the session freezes.
   - Abrupt power loss, in a VM with `FULL`, to check committed events survive.

## 0C: Display and GPU (D7 default first)

8. **XWayland (`GDK_BACKEND=x11`) must pass.** Run with
   `WEBKIT_DISABLE_DMABUF_RENDERER` unset and set to `1`:
   - Check for a blank or flickering window at startup.
   - Run the chart performance protocol (overview §10).
   - Two windows on two monitors: detach and **restore after relaunch**, plus
     fallback when a monitor is unplugged.
   - Resize and DPI changes.
   - Tray visibility on COSMIC.
   - Process count and PSS per window.
9. **Native Wayland, secondary.** Repeat 8 with best-effort bounds and record
   the limits.
10. **CEF evaluation (D10)**, only if XWayland fails: Tauri 3 with
    `tauri-runtime-cef`, repeating proof 8.
11. **Webview least privilege.**
    - Commands are declared through `AppManifest::commands`, and each
      window's capabilities grant only its own commands.
    - `on_navigation` and the new-window handler deny everything except
      bundled content.
    - CSP blocks remote scripts.
    - No token in arguments, logs, URLs or the bundle.
    - Record whether `xdotool` can drive the UI under XWayland versus Wayland.
      This is threat-model evidence for ADR-015.

## 0D: Workspace contract proxy

This proof is deliberately smaller than Phase 3.

12. With a **synthetic workspace service stub**:
    - MCP reads a chart's state and changes its symbol, timeframe and one
      indicator. Two windows update through the stream contract (snapshot
      cursor, then subscribe).
    - A stale revision returns `conflict`.
    - Changing the epoch forces a resnapshot.
    - With every window closed, a mutation reports `presentation: "pending"`.
    - The indicator values MCP returns match what the chart renders.
13. Run one desktop E2E smoke test through `tauri-driver` in **external mode**
    (no plugin in the product build), on the reference machine and under Xvfb.

## Evidence format

For each step, record:
- the procedure;
- the version matrix (moving candidates to tested selections, overview §14);
- expected versus actual result;
- redacted logs and screenshots;
- measurements, with warm and cold samples;
- the verdict (PASS / FAIL / NOT RUN).

Never claim support or performance without evidence.

## Go / no-go

**Go** only if all of the following hold:
- **0A:** the artifact gate passes, or P1 is decided otherwise, and the
  timing fixture matches the independent ledger;
- **0B:** the installed package passes authenticated reads, writes and
  subscriptions, spoof rejection, adoption, takeover and the durability kill
  tests;
- **0C:** **XWayland** meets the targets, including detached-window restore;
- **0D:** the contract proxy converges.

**If only native Wayland passes,** or only CEF does, record the failure and
bring the evidence to the maintainer (D7, D10, P5). Do not silently fall back
to a browser product.

**References:**
- [Tauri sidecars](https://tauri.app/develop/sidecar/) (not used)
- [Debian packaging](https://tauri.app/distribute/debian/)
- [Capabilities](https://v2.tauri.app/security/capabilities/)
- [WebDriver testing](https://v2.tauri.app/develop/tests/webdriver/)
- tao `Window` docs on Wayland
- [SQLite `synchronous`](https://www.sqlite.org/pragma.html#pragma_synchronous)
- [SQLite online backup](https://www.sqlite.org/backup.html)
- Nautilus rc9 `crates/pyo3/Cargo.toml` and `bar-execution.md`
  ("Order submission timing")
