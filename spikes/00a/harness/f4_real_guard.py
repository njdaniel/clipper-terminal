"""D29 guard for the F4 real-data investigation. Every real-data script imports this module first.

* exactly one input is allowed (the Leviathan July-15 MES MBO development fixture);
* the STRAT-004 May lockbox is never opened;
* outputs go to a local directory that must lie outside every git repository;
* nothing here prints market data; publishable artefacts are written by `publishable()` only.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

# Leviathan checkout location (override with LEVIATHAN_DIR); the allowed file inside it is fixed.
ALLOWED_INPUT = Path(os.path.expanduser(os.environ.get("LEVIATHAN_DIR", "~/code/github.com/njdaniel/leviathan"))) \
    / "engine/data/databento/glbx-mes-mbo-jul15/mbo.2026-07-15.dbn.zst"
FORBIDDEN_FRAGMENTS = ("glbx-mes-mbo-may2026",)
PUBLISH_KEYS = {"probe_count", "match_count", "ratios", "verdicts", "config", "input_sha256", "contract", "date",
                "notes", "counts_by_config", "parity"}


def input_path(p: str | os.PathLike = ALLOWED_INPUT) -> Path:
    real = Path(os.path.realpath(p))
    if any(f in str(real) for f in FORBIDDEN_FRAGMENTS):
        raise PermissionError(f"D29: refusing lockbox path {real}")
    if real != Path(os.path.realpath(ALLOWED_INPUT)):
        raise PermissionError(f"D29: only {ALLOWED_INPUT} is allowed, got {real}")
    return real


def local_out(path: str | os.PathLike) -> Path:
    out = Path(os.path.realpath(path))
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["git", "-C", str(out), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if r.returncode == 0:
        raise PermissionError(f"D29: local output dir {out} is inside git repo {r.stdout.strip()}")
    return out


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def publishable(obj: dict) -> dict:
    """Allow-list filter for anything leaving the machine (D29: aggregates only)."""
    bad = set(obj) - PUBLISH_KEYS
    if bad:
        raise ValueError(f"D29: non-publishable keys {sorted(bad)}")
    text = json.dumps(obj)
    for forbidden in ("ts_event", "ts_init", '"px"', "order_id", "price"):
        if forbidden in text:
            raise ValueError(f"D29: publishable payload contains '{forbidden}'")
    return obj
