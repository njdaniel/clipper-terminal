# Clipper Terminal: second architecture review (desktop-first amendment)

**Reviewer:** Claude (Opus 5.5), via Claude Code. Issue #1, PR #2.
**Date:** 2026-11-25

**Reviewed:** the maintainer's desktop-first amendment, `ac228bc` through
`e2b61d4`. That covers `overview.md`, the ADR file, `implementation-plan.md`,
and the new `desktop-validation.md`, together with the maintainer direction
comments on PR #2.

**Also in this commit:** at the maintainer's request, Claude **revised** the
architecture documents to reconcile the amendment with the
[first review](claude-review.md) and the
[maintainer decisions](maintainer-decisions.md). Each finding below states
where the revision addresses it.

**Independence caveat:** this review is independent of the amendment. It is
**not** independent of the reconciliation, because Claude wrote both. Have a
reviewer other than Claude check the reconciled text before sign-off.

## Verdict

**The desktop-first direction is sound.** A Tauri 2 shell that only presents
the UI and attaches to the service, over an independent Python/Nautilus
service, is the right split. It keeps Rust out of financial logic, and the
service and MCP stay usable with no window open.

The amendment as committed had two problems:
- It **did not reconcile** the first review or decisions D1–D6. Those
  contradictions are P0, because approving the docs would approve a
  self-contradicting design.
- It left several desktop choices open that upstream evidence already
  settles: sidecars, Wayland window placement, packaging and E2E tooling.

The biggest remaining risks are **empirical**: WebKitGTK rendering on the
reference NVIDIA GPU, and packaging Python and Nautilus inside a `.deb`. Only
the Phase 0 spike can settle them, so the spike, not more document review,
is the real approval gate.

## How the claims were checked

Facts marked **[verified]** were checked on 2026-11-25 against crates.io, npm,
upstream source or docs, or the reference machine itself. Nothing was
installed or run beyond read-only system queries.

```bash
# Tauri versions
curl -s https://crates.io/api/v1/crates/tauri | jq .crate.max_stable_version
curl -s https://registry.npmjs.org/@tauri-apps/cli | jq '."dist-tags"'
curl -s https://crates.io/api/v1/crates/tauri-runtime-cef | jq .crate.max_version
# Shell plugin kills children on exit
gh api 'repos/tauri-apps/plugins-workspace/contents/plugins/shell/src/lib.rs?ref=v2' --jq .content | base64 -d | grep -n -A10 'RunEvent::Exit'
# Wayland position support in tao
gh api 'repos/tauri-apps/tao/contents/src/window.rs?ref=dev' --jq .content | base64 -d | grep -n -B1 'Linux(Wayland)'
# Debian bundling, WebDriver and PATH notes
gh api repos/tauri-apps/tauri-docs/contents/src/content/docs/distribute/debian.mdx --jq .content | base64 -d
gh api 'repos/tauri-apps/tauri-docs/contents/src/content/docs/develop/Tests/WebDriver/index.mdx' --jq .content | base64 -d
# Reference machine
echo "$XDG_SESSION_TYPE $DISPLAY $WAYLAND_DISPLAY $XDG_CURRENT_DESKTOP"; nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
dpkg -l 'libwebkit2gtk-4.1*'; loginctl show-user "$USER" -p Linger; cat /proc/sys/kernel/yama/ptrace_scope
```

| Topic | Fact |
|---|---|
| Tauri | `tauri` 2.12.7 (2026-11-18). CLI `latest` is 2.12.6, and `next` is **3.0.0-alpha.6** (2026-11-06). The v3 alpha's breaking changes so far fall mostly on plugin and hook APIs. [verified] |
| CEF runtime | `tauri-runtime-cef` exists **only as a 3.0.0 alpha** (alpha.7). It is a Chromium alternative to WebKitGTK, with no stable release. [verified] |
| Sidecars | `externalBin` sidecars run through `tauri-plugin-shell`. On `RunEvent::Exit` the plugin takes every tracked child and calls `kill()` on it. A crash skips that, so the children are orphaned. [verified, `plugins/shell/src/lib.rs` v2] |
| Wayland | Tao `outer_position` "has no effect" and `set_outer_position` is "unsupported" on Linux (Wayland). So are `cursor_position` and others. [verified] |
| Debian bundle | It declares `libwebkit2gtk-4.1-0` and `libgtk-3-0`, plus appindicator for tray apps. `bundle > linux > deb > files` adds arbitrary files. Build on the oldest base you support (Ubuntu 22.04 is suggested) to keep the glibc floor low. GUI apps **do not inherit the shell's `PATH`**. [verified] |
| Desktop E2E | WebdriverIO with `@wdio/tauri-service` on Linux, Windows and macOS, or `tauri-driver` directly on Linux and Windows. Playwright cannot drive the Tauri webview. [verified] |
| Reference machine | COSMIC, Wayland session, XWayland `DISPLAY=:1`. **NVIDIA RTX 4090, driver 580.159.03.** `libwebkit2gtk-4.1-0` 2.52.3. `libayatana-appindicator3-1` present. `Linger=yes`. Yama `ptrace_scope=1`. User in the `sudo` and `docker` groups. [verified] |
| Engine on Windows | Nautilus `2.0.0rc9` publishes `win_amd64` wheels for CPython 3.13–3.15. [verified, first review] |

## Findings on the desktop amendment

Severity scale: **P0** blocks approval. **P1** must be decided before the
affected phase. **P2** should be fixed but does not block.

### P0-D1: The amendment contradicts the first review and decisions D1–D6

As committed, the amendment:
- still prefers Nautilus 1.x (ADR-002 and overview §4);
- keeps journey 4 ("bounded continuous deployment") and journey 5 ("block new
  orders until reconciliation"), which contradict D1's session-scoped paper
  trading;
- calls AGPL and the CLA "pending explicit maintainer confirmation", though D3
  already confirmed them;
- keeps a live provider on the paper critical path, against D5's free-data-first
  decision;
- orders the critical path with MCP *after* the backtest worker and the UI shell
  in parallel, against D4's MCP-first decision;
- keeps the UNKNOWN/reconcile flow, DuckDB and Polars, and an eight-state
  account machine.

**Disposition:** reconciled in this revision. See the status table below.

### P1-D1: Sidecars cannot provide the independent lifecycle the amendment requires

The amendment proposes to "compare … Tauri external binary bundling" for the
service. A sidecar is killed when the app exits normally and orphaned when it
crashes. That is the worst combination for a paper session: it stops on an
ordinary quit and runs unsupervised after a crash.

**Disposition:** ADR-016 now says no sidecars and no `tauri-plugin-shell`. The
service is a systemd user unit, started through the service manager, with a
discovery file and an authenticated handshake. Dropping the shell plugin also
removes a broad capability.

### P1-D2: Window placement under Wayland, and the security cost of XWayland

The amendment promises "restore after relaunch and fallback to a visible
monitor", and also says the compositor controls positioning. Under native
Wayland the position APIs are unsupported, so restoring a detached window to a
given monitor **cannot work** there.

**Disposition:** XWayland (`GDK_BACKEND=x11`) becomes the default (ADR-017),
matching how the maintainer already runs apps. Native Wayland is a secondary
mode with best-effort bounds.

**Trade-off the maintainer should weigh:** X11 has no isolation between
clients. Any X client can read the screen and inject input, so under XWayland
an agent can click **Approve** with `xdotool`. Native Wayland blocks that. For
alpha this is consistent with D2, where approval guards only against mistakes.
It does mean the display-mode default and the future approval design interact.
The future WebAuthn approach holds under both. Spike experiment 6 records the
difference.

### P1-D3: Performance targets ignore the webview and the GPU

The targets are written for a "documented Linux dev machine". The UI renders in
**WebKitGTK**, not Chromium, and the reference GPU is an RTX 4090 on the
proprietary driver. Blank or flickering windows from WebKitGTK on NVIDIA, with
workarounds such as `WEBKIT_DISABLE_DMABUF_RENDERER=1`, are a known problem
area. A chart that runs at 60 FPS in Chrome tells you nothing about Clipper.

**Disposition:**
- Targets are now measured inside the Tauri webview, with the display mode
  and driver recorded (overview §10).
- The spike runs a four-cell matrix: XWayland or Wayland, each with the DMABUF
  renderer on or off.
- The fallback, Tauri 3 with CEF, is named but **gated on maintainer
  approval**, because it means adopting an alpha.

### P1-D4: The packaging options in the amendment conflict with licensing and the lifecycle

"A frozen bundle" (PyInstaller or similar) as an `externalBin` combines the
sidecar lifecycle problem with weakened LGPL replaceability for Nautilus. Also,
GUI apps do not inherit `PATH`, so "use the user's Python or uv" fails when the
app starts from a desktop launcher.

**Disposition (ADR-017):** one `.deb` containing a standalone CPython 3.13, a
relocatable uv virtual environment built from `uv.lock` (Nautilus stays a
replaceable wheel), absolute paths throughout, and a build on an Ubuntu 22.04
base. Nautilus v2's `manylinux_2_34` floor is satisfied there.

### P1-D5: Indicators are not assigned an owner, so the agent and the chart can diverge

AI desktop control includes `set_chart_indicators`, and the agent will reason
about indicator values. Lightweight Charts has no indicators. If the UI
computed them in JS, the agent (which reads them from the service) and the
chart could disagree.

**Disposition:** indicators are computed in the service (overview §3 and §5,
ADR-009). Spike experiment 7 checks that the values match.

### P1-D6: "Windows later" is not designed for

The amendment defers "other desktop platforms" without stating what must stay
portable. At the same time it proposes systemd units, Unix sockets and `flock`,
all of which would leak into the core if nobody constrains them.

**Disposition:** ADR-018 and overview §11 put the platform-specific pieces
(service manager, worker launcher, command transport, locks, paths, webview
origin, packaging, stop signals) behind interfaces. Nautilus v2 already ships
Windows wheels. Run a Windows build spike before scheduling Windows work.

### P1-D7: The E2E tooling cannot test the desktop app

The plan lists "Playwright UI/MCP E2E". Playwright cannot drive the Tauri
webview, so it would test only the browser harness, which is not the product.

**Disposition:** desktop E2E now uses WebdriverIO with `@wdio/tauri-service`,
or `tauri-driver`, which cover Linux and later Windows. Playwright stays for the
harness and API tests.

### P2 findings

1. **Tauri version:** the amendment didn't pin one, and Tauri 3 is in alpha.
   Now pinned to 2.12.x, with the shell kept thin and plugin-light so a later
   migration is cheap.
2. **"Typed proxy" through Rust:** routing API calls through Tauri commands
   would break the WebSocket stream and the generated OpenAPI client, and it
   adds an IPC surface. Chosen instead: the webview calls loopback directly,
   with a token handed over by one bootstrap command, plus Host and Origin
   checks, CSP and enumerated capabilities.
3. **An invisible background service.** Once the last window closes, a paper
   session keeps running with nothing on screen. That is a safety and UX
   problem. A tray or status indicator is now required; confirm it shows on
   COSMIC.
4. **Scope.** Alpha 1 had become desktop shell, packaging, multi-window,
   multi-monitor, MCP workspace control, research and paper all at once. Now
   split into Alpha-R and Alpha-P, with detachable windows at the end of
   Alpha-R.
5. **Memory per window.** Each WebKitGTK window adds a web process. The spike
   records memory per window.
6. **Webview origin** differs by platform (`tauri://localhost` on Linux, and
   the WebView2 origin on Windows). The allowlist is now configured per
   platform; confirm the values in the spike.
7. **"Leviathan"** is still referenced without definition. Define it or remove
   it. The revision keeps the maintainer's sentence and flags it.
8. **A shell-only approval token was considered and rejected.** One idea was
   approvals accepted only with a token held in shell memory, which Yama
   `ptrace_scope=1` protects from non-descendant processes. It doesn't work: an
   agent can launch the shell binary itself and drive it through X11, so no
   same-user secret is unforgeable. That supports D2's split between alpha and
   future.

## Status of first-review findings after the revision

"Addressed" means the reconciled text now says what the first review
recommended, or what the maintainer decided. It does not mean the claim has
been verified at runtime.

| Finding | Status | Where |
|---|---|---|
| P0-1 engine line | Addressed: v2 exact RC pin, CPython 3.13 | ADR-002, overview §7 |
| P0-2 paper recovery | Addressed per D1: session-scoped, journal of record, cache backing forbidden, resume deferred | ADR-008, overview §7 |
| P0-3 same-user approval bypass | Accepted for alpha per D2; future path recorded | ADR-007, ADR-015, overview §9 |
| P1-1 provider on critical path | Addressed: replay-fed paper first | Plan phases 5–6, ADR-012 |
| P1-2 strategy isolation | Addressed: trust is a hash the user acknowledged; launcher seam; feed split recorded as a prerequisite | ADR-010, overview §9 |
| P1-3 persistence | Addressed: `flock` lease, idempotent commands, one transaction per event | overview §7 |
| P1-4 financial correctness | Addressed in the rules; needs fixtures | overview §6–7, ADR-013 |
| P1-5 limits | Addressed: Clipper's pre-trade gate, price collar | overview §7 |
| P1-6 scope and complexity | Addressed: Alpha-R and Alpha-P, no DuckDB or Polars; Monaco removal **needs maintainer confirmation** | Plan, ADR-003/005/009 |
| P1-7 contributor licensing | Addressed per D3: CLA pending legal review | ADR-014, `CONTRIBUTING.md` |
| P1-8 local web defences | Addressed | overview §4 |
| P2-1 MCP SDK v2 | Addressed | ADR-006, overview §8 |
| P2-2 dependency pins | Addressed in text; lockfiles come in Phase 1 | overview, spike |
| P2-3 third-party notices | **Open** until dependencies land in Phase 1 | `THIRD_PARTY_NOTICES.md` |
| P2-4 sandbox citation | Addressed: Python v2 sandbox cited | overview §7 |
| P2-5 WebSocket `seq` scope | Addressed: per stream | overview §8 |
| P2-6 wording | "TradingView-style" removed; "Leviathan" still open (P2-7 above) | overview §1 |
| P2-7 performance budgets | Partly: memory targets to be set by profiling | overview §10 |
| P2-8 chart plugins | Addressed | overview §10 |

## Questions for the maintainer

1. Keep XWayland as the default display mode? It gives window placement, at
   the cost of X11's lack of input isolation (P1-D2).
2. Remove Monaco from alpha?
3. If WebKitGTK fails on the RTX 4090, may Phase 0 evaluate Tauri 3 with CEF
   (an alpha), or should that need a separate ADR first?
4. Is a `.deb` only acceptable for Alpha-R packaging, with AppImage and Flatpak
   deferred?
5. Who reviews this reconciliation independently? It shouldn't be Claude.

**Answered 2026-11-25** in [`maintainer-decisions.md`](maintainer-decisions.md), D7–D12.

## What should happen next

1. The maintainer answers the questions above.
2. Someone other than Claude reviews the reconciled documents.
3. Run Phase 0: the desktop and packaging spike plus the engine pin spike on
   the reference machine. Record the evidence in `desktop-validation.md` or
   link it from PR #2.
4. Accept, or amend, the ADRs based on that evidence. Only then create the
   backlog.
