# Desktop packaging and lifecycle validation (pre-approval spike)

**Status:** not executed.
**Reference:** maintainer direction on PR #2; issue #1; ADR-001, ADR-016,
ADR-017.
**Timebox:** 3–6 working days, shared with the engine pin spike.

Run on the reference machine (`overview.md` §13). Multi-monitor and GPU tests
need that real hardware; a VM does not count. Rules for the spike: no
production features, no credentials, no real execution, synthetic data only.
Work on a disposable spike branch and link the evidence from PR #2.

## Fixed starting point

- Tauri 2.12.x, with plugins limited to `single-instance` and `window-state`.
  **No `tauri-plugin-shell`.**
- CPython 3.13 from python-build-standalone, plus a relocatable uv virtual
  environment containing `nautilus_trader==2.0.0rc9`, FastAPI and `mcp>=2.3,<3`.
- A systemd user unit for the service.
- Lightweight Charts 5.3 inside the webview.

## Experiments

Mark each one PASS, FAIL or NOT RUN, and record the actual result alongside the
expected one.

1. **Environment record.** Distro, kernel, COSMIC version, session type,
   `DISPLAY` and `WAYLAND_DISPLAY`, NVIDIA driver, WebKitGTK version, glibc,
   Rust, Tauri, Node, uv, Python, Nautilus, `Linger`, and Yama `ptrace_scope`.
2. **Engine inside the package.** From the relocatable environment, import
   `nautilus_trader`, run a deterministic synthetic `BacktestNode` run, and
   construct a sandbox `LiveNode` with an explicit fee model and replayed data.
   Record wheel size, import time and peak memory.
3. **`.deb` build.** Build in an Ubuntu 22.04 container. Install on the
   reference machine without developer toolchains, then launch offline.
   Upgrade over itself and uninstall; user data in XDG directories must
   survive. Confirm `nautilus_trader` can be replaced inside the environment
   (LGPL). Record package size and install steps.
4. **Service lifecycle.**
   - The shell starts the user unit through the service manager. Discovery
     file and authenticated handshake work.
   - Rejection cases: a stale `service.json`, a wrong-version service, and a
     spoofed listener on the recorded port.
   - Lifecycle sequence: second launch; close one window; close the last
     window with a synthetic job active (the service keeps running, the tray
     stays visible); `kill -9` the shell; reopen and reattach; CLI and MCP
     start the service with no shell; explicit stop while idle and while a job
     is active.
   - A worker launched as a transient unit survives a service restart.
   - Record behaviour across logout and reboot with `Linger=yes`. No
     continuity is promised.
5. **Display and GPU matrix.** Run each cell under XWayland
   (`GDK_BACKEND=x11`) and under native Wayland, each with
   `WEBKIT_DISABLE_DMABUF_RENDERER` unset and set to `1`:
   - Startup: blank or flickering window?
   - The chart performance fixture: 5k-bar first paint, and pan and zoom with
     10k visible bars, measured in the webview.
   - Two windows on two monitors.
   - Resize and DPI changes.
   - Unplugging a monitor.
   - Restoring window positions with `window-state`: expected to work under
     XWayland and not under Wayland.
   - Tray indicator visibility on COSMIC.
   - Memory per webview window.
6. **Least privilege.**
   - Capabilities file lists only enumerated commands.
   - CSP blocks a remote script and remote navigation.
   - The API rejects a wrong Host header, a wrong Origin, a mutation without
     a token, and an MCP token on the approval route.
   - No token in process arguments, logs or the frontend bundle.
   - Record whether X11 input injection (`xdotool`) can drive the UI under
     XWayland versus Wayland. This is threat-model evidence for ADR-015.
7. **Shared workspace contract.**
   - MCP reads a chart's state and changes its symbol, timeframe and
     indicators. Both windows update.
   - A stale revision returns `conflict`.
   - With every window closed, a mutation reports `presentation: "pending"`
     and appears on the next attach.
   - The indicator values MCP returns match what the chart renders.
8. **Desktop E2E harness.** Run one smoke test through WebdriverIO with
   `@wdio/tauri-service`, or through `tauri-driver`, on the reference machine
   and headless under Xvfb.

## Evidence format

For each experiment, record:
- the procedure or command;
- expected versus actual result;
- a version matrix;
- redacted logs and screenshots;
- measurements;
- the verdict (PASS / FAIL / NOT RUN).

Never claim Wayland or X11 support, packaging, or performance without this
evidence.

## Go / no-go

**Go** only if all of these hold:
- the `.deb` installs and launches offline;
- the service lifecycle is independent of the shell;
- the chart meets its targets in at least one display mode on the reference
  GPU;
- the workspace contract works end to end.

**If WebKitGTK fails on every display mode,** bring options to the maintainer:
- Tauri 3 with the CEF runtime (alpha);
- driver or compositor workarounds;
- relaxing the targets.

Do not silently fall back to a browser product.

**References:**
- [Tauri sidecars](https://tauri.app/develop/sidecar/). Not used: the shell
  plugin kills tracked children on `RunEvent::Exit`.
- [Debian packaging](https://tauri.app/distribute/debian/).
- [Prerequisites](https://v2.tauri.app/start/prerequisites/).
- [Capabilities](https://v2.tauri.app/security/capabilities/).
- [WebDriver testing](https://tauri.app/develop/tests/webdriver/).
- Tao `Window` docs: position APIs are unsupported on Wayland.

These establish available mechanisms, not successful tests on Pop!_OS.
