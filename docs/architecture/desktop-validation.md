# Desktop packaging and lifecycle validation (pre-approval spike)

Status: **not executed**. Reference: maintainer direction in PR #2, issue #1. Timebox proposal: 2–5 working days. Run on actual Pop!_OS 24.04 x86-64 or representative VM; multi-monitor behavior needs real hardware. No production feature work, no credentials or real execution. Use a disposable spike branch and synthetic data; commit evidence here or link it from PR #2.

## Experiment

1. Record distro, kernel, session type (Wayland/X11), systemd user session, WebKitGTK runtime/devel packages, glibc, Rust/Tauri/Node, Python and Nautilus versions. Pin Python 3.13 if compatible with actual engine wheels; record alternatives. Confirm Rust shell can render the shared React workspace and a chart fixture without external browser or remote assets.
2. Package a tiny Python FastAPI health/version endpoint with a Nautilus import and deterministic synthetic smoke run. Compare a pinned installed venv/service launcher against a Tauri external binary or frozen bundle. Prefer a Linux .deb candidate; verify package dependencies and LGPL replacement rights; do not assume a frozen binary meets licensing. Record artifact size, install steps, startup timing and failure logs. Test clean install without developer toolchains, offline after install; upgrade/uninstall behavior must preserve data unless explicitly removed.
3. Compare systemd user unit with independent detached supervisor. Tauri launches/attaches through fixed typed commands, restricted runtime directory, single-instance lock and authenticated health/version handshake. Reject stale sockets, wrong-version endpoints and spoof listeners. Do not expose generic command execution, arbitrary paths or arbitrary HTTP proxy to the webview.
4. Test lifecycle with a long-running synthetic job/heartbeat: open first window; second launch; close one and last window; kill shell; reopen; attach headless CLI/MCP; explicit stop when idle and with active job. Ensure UI disconnect is not a worker stop; explicit shutdown must report actual outcome; no orphan uncontrolled or duplicate workers. Record what happens on logout/reboot (no continuity promise). Verify health/error visibility and bounded startup/reconnect.
5. On Wayland and X11 where available, exercise dock/undock, two native windows, resize/DPI, monitor disconnect, close/reopen, saved layout and safe fallback to visible display. Separate native bounds from shared semantic chart state. Record compositor limitations rather than assuming exact native placement.
6. Verify least privilege: local bundled content, CSP, scoped Tauri capabilities, no broad shell or filesystem commands, loopback API Host/Origin allowlist, no wildcard CORS, distinct MCP research/workspace scopes, no credentials in process args, logs or front-end bundle. Exercise unauthorized requests and arbitrary external navigation. Same-user shell threat and human approval mechanism remain separate review gates.
7. Prove shared API/typed client contract with a synthetic workspace snapshot: desktop chart state read by MCP, scoped mutation of symbol/timeframe/indicator, desktop reflects event; stale revision conflict; close all windows and mutate workspace; next attach restores. Browser is only a development/test harness.

## Evidence format

Record command or test procedure, expected vs actual outcome, version matrix, screenshots or logs (redacted), package and startup measurements, open blockers, workarounds, and recommendation. Mark each test PASS / FAIL / NOT RUN. No claim of supported Wayland/X11 or standalone packaging without evidence.

## Go/no-go

Pass only if standalone desktop install and independent lifecycle are credible on the reference OS and the secure shared workspace contract has a workable path. If package format, WebKitGTK or compositor limitations block delivery, propose a different native packaging/supervision approach and bring it to maintainer; do not silently revert to a browser product. Do not merge PR #2 or commit to the implementation schedule before evidence review and reconciliation of independent Claude critique.

Upstream references: [Tauri sidecars](https://tauri.app/develop/sidecar/), [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/), [Tauri capabilities](https://v2.tauri.app/security/capabilities/). These establish available mechanisms, not successful tests on Pop!_OS.
