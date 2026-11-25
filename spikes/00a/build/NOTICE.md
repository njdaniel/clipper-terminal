# Notice — NautilusTrader modifications

`clipper-sim-only.patch` and `prune.sh` modify NautilusTrader `v2.0.0rc9`
(<https://github.com/nautechsystems/nautilus_trader>), Copyright (C) 2015-2026 Nautech Systems Pty Ltd,
licensed under the GNU Lesser General Public License v3.0 (LGPL-3.0-only). The patch hunks reproduce
fragments of that source; the patch is a modification of LGPL-3.0 files and is provided under
LGPL-3.0-only. Changes: per-adapter Cargo features, per-adapter native registration guards, restricted
maturin features, and removal of excluded adapter Python packages (Clipper Phase 0 / proof 0A,
2026-11-25). Built wheels are not committed. This spike is evidence only and is not a release
(release licensing evidence and legal review: D20).
