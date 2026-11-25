"""Check 1 (artifact gate, D1/D13): run with the interpreter of the environment under test.
Prints JSON describing which adapter modules import and which execution-client factories exist."""

from __future__ import annotations

import importlib
import json
import pkgutil
import sys

import nautilus_trader
import nautilus_trader._libnautilus as native

MUST_IMPORT = ["nautilus_trader.adapters.sandbox", "nautilus_trader.adapters.databento"]
MUST_FAIL = ["nautilus_trader.adapters.binance", "nautilus_trader.adapters.interactive_brokers",
             "nautilus_trader.adapters.blockchain", "nautilus_trader._libnautilus.binance",
             "nautilus_trader._libnautilus.interactive_brokers", "nautilus_trader._libnautilus.blockchain"]


def try_import(name: str) -> dict:
    try:
        importlib.import_module(name)
        return {"module": name, "imported": True}
    except Exception as exc:  # noqa: BLE001 - we record the failure type
        return {"module": name, "imported": False, "error": f"{type(exc).__name__}: {exc}"}


def all_modules() -> list[str]:
    names = []
    for info in pkgutil.walk_packages(nautilus_trader.__path__, "nautilus_trader.", onerror=lambda _n: None):
        names.append(info.name)
    return sorted(set(names))


def factories() -> dict:
    found, import_errors = {}, {}
    for name in all_modules():
        try:
            mod = importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001
            import_errors[name] = f"{type(exc).__name__}: {exc}"
            continue
        for attr in dir(mod):
            if ("Exec" in attr and "ClientFactory" in attr) or attr.endswith("ExecutionClient"):
                found.setdefault(attr, []).append(name)
    return {"execution_factories": found, "module_import_errors": import_errors}


def native_factories() -> dict:
    found = {}
    for sub in native_submodules():
        mod = getattr(native, sub)
        for attr in dir(mod):
            if "Exec" in attr and "Factory" in attr:
                found.setdefault(attr, []).append(f"_libnautilus.{sub}")
    return found


def native_submodules() -> list[str]:
    return sorted(a for a in dir(native) if not a.startswith("_") and type(getattr(native, a)).__name__ == "module")


def main() -> None:
    try:
        import pandas  # noqa: F401
        pandas_present = True
    except ImportError:
        pandas_present = False
    out = {
        "nautilus_version": nautilus_trader.__version__, "python": sys.version.split()[0],
        "native_library": native.__file__, "native_submodules": native_submodules(),
        "must_import": [try_import(m) for m in MUST_IMPORT],
        "must_fail": [try_import(m) for m in MUST_FAIL],
        "pandas_present": pandas_present,
        "native_execution_factories": native_factories(),
        **factories(),
    }
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
